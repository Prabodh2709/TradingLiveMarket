from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from backend.config import settings as app_settings
from backend.smartapi_client import session
from backend.strategy.config import strategy_settings
from backend.strategy.historical_data import resolve_ltp
from backend.strategy.models import ActiveTrade, ExitReason, TradePlan
from backend.trading_engine import sell_option, sell_option_open

logger = logging.getLogger(__name__)


async def execute_entry(plan: TradePlan) -> Optional[ActiveTrade]:
    """
    Execute a trade entry using smart order execution.
    Paper mode: uses existing trading engine.
    Live mode: places limit order with market fallback.
    """
    if strategy_settings.execution_mode == "paper":
        return await _paper_entry(plan)
    else:
        return await _live_entry(plan)


async def execute_exit(trade: ActiveTrade, reason: ExitReason) -> Optional[float]:
    """
    Execute a trade exit (square-off).
    Returns realized P&L or None if execution failed.
    """
    exit_price = resolve_ltp(trade.trade_plan.token, "NFO", trade.trade_plan.symbol)
    if not exit_price or exit_price <= 0:
        exit_price = trade.current_price

    if exit_price <= 0:
        logger.error("Cannot exit %s: no valid price", trade.trade_plan.symbol)
        return None

    if strategy_settings.execution_mode == "paper":
        return await _paper_exit(trade, exit_price, reason)
    else:
        return await _live_exit(trade, exit_price, reason)


async def _paper_entry(plan: TradePlan) -> Optional[ActiveTrade]:
    """Execute entry via paper trading engine."""
    try:
        lot_size = (
            app_settings.banknifty_lot_size
            if plan.signal.instrument == "BANKNIFTY"
            else app_settings.nifty_lot_size
        )

        result = sell_option_open(
            symbol=plan.symbol,
            token=plan.token,
            name=plan.signal.instrument,
            strike=plan.strike,
            option_type=plan.option_type,
            expiry=plan.expiry,
            qty=plan.qty,
            price=plan.entry_price,
        )

        active = ActiveTrade(
            trade_plan=plan,
            entry_filled_price=plan.entry_price,
            current_price=plan.entry_price,
        )

        logger.info(
            "PAPER ENTRY: SELL %d lots %s @ %.2f (premium received: ₹%.2f)",
            plan.qty, plan.symbol, plan.entry_price, result.get("premium_received", 0),
        )
        return active

    except Exception as e:
        logger.error("Paper entry failed for %s: %s", plan.symbol, e)
        return None


async def _paper_exit(trade: ActiveTrade, price: float, reason: ExitReason) -> Optional[float]:
    """Execute exit via paper trading engine."""
    try:
        result = sell_option(
            token=trade.trade_plan.token,
            qty=trade.trade_plan.qty,
            price=price,
        )

        pnl = result.get("pnl", 0)
        trade.status = "CLOSED"

        logger.info(
            "PAPER EXIT [%s]: BUY-CLOSE %d lots %s @ %.2f, P&L=₹%.2f",
            reason.value, trade.trade_plan.qty, trade.trade_plan.symbol, price, pnl,
        )
        return pnl

    except Exception as e:
        logger.error("Paper exit failed for %s: %s", trade.trade_plan.symbol, e)
        return None


async def _live_entry(plan: TradePlan) -> Optional[ActiveTrade]:
    """
    Execute entry via Angel One SmartAPI.
    Places limit order, waits for fill, falls back to market.
    """
    if not session.is_logged_in or not session._obj:
        logger.error("Cannot place live order: not logged in")
        return None

    lot_size = (
        app_settings.banknifty_lot_size
        if plan.signal.instrument == "BANKNIFTY"
        else app_settings.nifty_lot_size
    )
    total_qty = plan.qty * lot_size

    order_params = {
        "variety": "NORMAL",
        "tradingsymbol": plan.symbol,
        "symboltoken": plan.token,
        "transactiontype": "SELL",
        "exchange": "NFO",
        "ordertype": "LIMIT",
        "producttype": "CARRYFORWARD",
        "duration": "DAY",
        "price": str(plan.entry_price),
        "quantity": str(total_qty),
    }

    try:
        order_response = session._obj.placeOrder(order_params)
    except Exception as e:
        logger.error("Live order placement failed: %s", e)
        return None

    if not order_response or order_response.get("status") is False:
        msg = order_response.get("message", "Unknown") if order_response else "No response"
        logger.error("Order rejected: %s", msg)
        return None

    order_id = order_response.get("data", {}).get("orderid")
    if not order_id:
        logger.error("No order ID returned from placeOrder")
        return None

    logger.info("Limit order placed: %s for %s @ %.2f", order_id, plan.symbol, plan.entry_price)

    # Wait for fill with timeout
    filled_price = await _wait_for_fill(order_id, plan)

    if filled_price is None:
        # Fallback to market order
        logger.info("Order %s not filled in %ds, modifying to MARKET", order_id, strategy_settings.limit_order_timeout_s)
        filled_price = await _modify_to_market(order_id, plan)

    if filled_price is None:
        logger.error("Failed to execute entry for %s", plan.symbol)
        return None

    active = ActiveTrade(
        trade_plan=plan,
        entry_filled_price=filled_price,
        current_price=filled_price,
    )

    logger.info("LIVE ENTRY FILLED: SELL %d lots %s @ %.2f", plan.qty, plan.symbol, filled_price)
    return active


async def _live_exit(trade: ActiveTrade, price: float, reason: ExitReason) -> Optional[float]:
    """Execute exit via Angel One SmartAPI with market order for certainty."""
    if not session.is_logged_in or not session._obj:
        logger.error("Cannot place live exit: not logged in")
        return None

    lot_size = (
        app_settings.banknifty_lot_size
        if trade.trade_plan.signal.instrument == "BANKNIFTY"
        else app_settings.nifty_lot_size
    )
    total_qty = trade.trade_plan.qty * lot_size

    order_params = {
        "variety": "NORMAL",
        "tradingsymbol": trade.trade_plan.symbol,
        "symboltoken": trade.trade_plan.token,
        "transactiontype": "BUY",
        "exchange": "NFO",
        "ordertype": "MARKET",
        "producttype": "CARRYFORWARD",
        "duration": "DAY",
        "quantity": str(total_qty),
        "price": "0",
    }

    try:
        order_response = session._obj.placeOrder(order_params)
    except Exception as e:
        logger.error("Live exit order failed: %s", e)
        return None

    if not order_response or order_response.get("status") is False:
        msg = order_response.get("message", "Unknown") if order_response else "No response"
        logger.error("Exit order rejected: %s", msg)
        return None

    entry = trade.entry_filled_price or trade.trade_plan.entry_price
    pnl = (entry - price) * trade.trade_plan.qty * lot_size
    trade.status = "CLOSED"

    logger.info(
        "LIVE EXIT [%s]: BUY %d lots %s @ %.2f, P&L=₹%.2f",
        reason.value, trade.trade_plan.qty, trade.trade_plan.symbol, price, pnl,
    )
    return pnl


async def _wait_for_fill(order_id: str, plan: TradePlan) -> Optional[float]:
    """Poll order status until filled or timeout."""
    timeout = strategy_settings.limit_order_timeout_s
    interval = 5
    elapsed = 0

    while elapsed < timeout:
        await asyncio.sleep(interval)
        elapsed += interval

        try:
            order_book = session._obj.orderBook()
            if not order_book or not order_book.get("data"):
                continue

            for order in order_book["data"]:
                if order.get("orderid") == order_id:
                    status = order.get("orderstatus", "")
                    if status == "complete":
                        return float(order.get("averageprice", plan.entry_price))
                    elif status in ("rejected", "cancelled"):
                        logger.warning("Order %s was %s", order_id, status)
                        return None
                    break
        except Exception as e:
            logger.debug("Error checking order status: %s", e)

    return None


async def _modify_to_market(order_id: str, plan: TradePlan) -> Optional[float]:
    """Modify existing limit order to market order."""
    try:
        lot_size = (
            app_settings.banknifty_lot_size
            if plan.signal.instrument == "BANKNIFTY"
            else app_settings.nifty_lot_size
        )

        modify_params = {
            "variety": "NORMAL",
            "orderid": order_id,
            "ordertype": "MARKET",
            "producttype": "CARRYFORWARD",
            "duration": "DAY",
            "price": "0",
            "quantity": str(plan.qty * lot_size),
            "tradingsymbol": plan.symbol,
            "symboltoken": plan.token,
            "exchange": "NFO",
        }

        resp = session._obj.modifyOrder(modify_params)
        if resp and resp.get("status") is not False:
            await asyncio.sleep(3)
            # Check fill
            order_book = session._obj.orderBook()
            if order_book and order_book.get("data"):
                for order in order_book["data"]:
                    if order.get("orderid") == order_id and order.get("orderstatus") == "complete":
                        return float(order.get("averageprice", plan.entry_price))
    except Exception as e:
        logger.error("Failed to modify order to market: %s", e)

    return None
