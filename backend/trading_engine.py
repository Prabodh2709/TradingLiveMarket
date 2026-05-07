from __future__ import annotations

import logging
from typing import Optional

from backend.config import settings
from backend.db.schema import OptionType, Position, Trade, TradeAction
from backend.db import store
from backend.websocket_manager import market_data

logger = logging.getLogger(__name__)


def _lot_size_for(name: str) -> int:
    if name.upper() == "BANKNIFTY":
        return settings.banknifty_lot_size
    return settings.nifty_lot_size


def buy_option(
    symbol: str,
    token: str,
    name: str,
    strike: float,
    option_type: str,
    expiry: str,
    qty: int,
    price: float,
) -> dict:
    """Open a new paper position (buy)."""
    portfolio = store.load_portfolio()
    lot_size = _lot_size_for(name)
    total_cost = qty * lot_size * price

    if total_cost > portfolio.balance:
        raise ValueError(
            f"Insufficient balance. Need ₹{total_cost:,.2f}, "
            f"available ₹{portfolio.balance:,.2f}"
        )

    trade = Trade(
        symbol=symbol,
        token=token,
        name=name.upper(),
        strike=strike,
        option_type=OptionType(option_type),
        expiry=expiry,
        action=TradeAction.BUY,
        qty=qty,
        lot_size=lot_size,
        price=price,
    )

    portfolio.balance -= total_cost
    store.save_portfolio(portfolio)
    store.append_trade(trade)

    existing = store.find_position(token)
    if existing:
        positions = store.load_positions()
        for p in positions:
            if p.token == token:
                total_qty = p.qty + qty
                p.avg_price = (
                    (p.avg_price * p.qty + price * qty) / total_qty
                )
                p.qty = total_qty
                break
        store.save_positions(positions)
    else:
        pos = Position(
            symbol=symbol,
            token=token,
            name=name.upper(),
            strike=strike,
            option_type=OptionType(option_type),
            expiry=expiry,
            qty=qty,
            lot_size=lot_size,
            avg_price=price,
            current_price=price,
        )
        positions = store.load_positions()
        positions.append(pos)
        store.save_positions(positions)

    logger.info("BUY %d lots %s @ %.2f (₹%.2f)", qty, symbol, price, total_cost)
    return {
        "trade_id": trade.id,
        "action": "BUY",
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "total_cost": total_cost,
        "balance": portfolio.balance,
    }


def sell_option(
    token: str,
    qty: int,
    price: float,
) -> dict:
    """Close or reduce a paper position (sell / square-off)."""
    positions = store.load_positions()
    target: Optional[Position] = None
    for p in positions:
        if p.token == token:
            target = p
            break

    if not target:
        raise ValueError(f"No open position for token {token}")

    if qty > target.qty:
        raise ValueError(
            f"Cannot sell {qty} lots, only {target.qty} lots held"
        )

    lot_size = target.lot_size
    total_value = qty * lot_size * price
    cost_basis = qty * lot_size * target.avg_price
    pnl = total_value - cost_basis

    trade = Trade(
        symbol=target.symbol,
        token=token,
        name=target.name,
        strike=target.strike,
        option_type=target.option_type,
        expiry=target.expiry,
        action=TradeAction.SELL,
        qty=qty,
        lot_size=lot_size,
        price=price,
        pnl=pnl,
    )

    portfolio = store.load_portfolio()
    portfolio.balance += total_value
    portfolio.realized_pnl += pnl
    store.save_portfolio(portfolio)
    store.append_trade(trade)

    if qty >= target.qty:
        positions = [p for p in positions if p.token != token]
    else:
        for p in positions:
            if p.token == token:
                p.qty -= qty
                break

    store.save_positions(positions)

    logger.info(
        "SELL %d lots %s @ %.2f  P&L=₹%.2f",
        qty, target.symbol, price, pnl,
    )
    return {
        "trade_id": trade.id,
        "action": "SELL",
        "symbol": target.symbol,
        "qty": qty,
        "price": price,
        "total_value": total_value,
        "pnl": pnl,
        "balance": portfolio.balance,
    }


def get_portfolio_summary() -> dict:
    portfolio = store.load_portfolio()
    positions = store.load_positions()

    unrealized_pnl = 0.0
    enriched_positions = []

    for p in positions:
        ltp = market_data.get_ltp(p.token) or p.current_price
        p.current_price = ltp
        p.unrealized_pnl = (ltp - p.avg_price) * p.qty * p.lot_size
        unrealized_pnl += p.unrealized_pnl
        enriched_positions.append(p.model_dump())

    store.save_positions(positions)

    total_pnl = portfolio.realized_pnl + unrealized_pnl

    return {
        "balance": portfolio.balance,
        "initial_balance": portfolio.initial_balance,
        "realized_pnl": portfolio.realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": total_pnl,
        "total_return_pct": (total_pnl / portfolio.initial_balance) * 100,
        "positions": enriched_positions,
        "position_count": len(positions),
    }
