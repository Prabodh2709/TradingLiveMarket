from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from backend.config import settings as app_settings
from backend.db import store
from backend.strategy.config import strategy_settings
from backend.strategy.models import (
    ActiveTrade,
    SignalAction,
    StrategyState,
    TradePlan,
    TradeSignal,
)
from backend.websocket_manager import market_data

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def validate_trade(
    signal: TradeSignal,
    state: StrategyState,
) -> list[str]:
    """
    Run all pre-trade risk checks. Returns a list of rejection reasons.
    Empty list means all checks passed.
    """
    rejections: list[str] = []

    if signal.confidence < strategy_settings.min_confidence_score:
        rejections.append(
            f"Confidence {signal.confidence:.1f} below threshold {strategy_settings.min_confidence_score}"
        )

    if state.circuit_breaker_active:
        rejections.append("Circuit breaker is active (max daily loss exceeded)")

    for check in (
        _check_time_filter,
        lambda: _check_max_positions(state),
        lambda: _check_exposure(state),
        lambda: _check_duplicate_position(signal, state),
        lambda: _check_total_lots(state),
        lambda: _check_trade_cooldown(state),
    ):
        msg = check()
        if msg:
            rejections.append(msg)

    return rejections


def compute_trade_plan(
    signal: TradeSignal,
    token: str,
    symbol: str,
    strike: float,
    option_type: str,
    entry_price: float,
    lot_size: int,
) -> Optional[TradePlan]:
    """
    Build a TradePlan with target, SL, and position sizing.
    Returns None if risk/reward is unacceptable.
    """
    qty = _compute_position_size(entry_price, lot_size, signal.instrument)

    if qty <= 0:
        logger.warning("Position size computed as 0 for %s", symbol)
        return None

    target_price = entry_price * (1 - strategy_settings.target_pct / 100)
    sl_price = entry_price * strategy_settings.stop_loss_multiplier

    potential_profit = (entry_price - target_price) * qty * lot_size
    potential_loss = (sl_price - entry_price) * qty * lot_size

    if potential_loss <= 0:
        return None

    rr_ratio = potential_profit / potential_loss

    if rr_ratio < strategy_settings.min_risk_reward_ratio:
        logger.info(
            "RR ratio %.2f below minimum %.2f for %s",
            rr_ratio, strategy_settings.min_risk_reward_ratio, symbol,
        )
        return None

    return TradePlan(
        signal=signal,
        token=token,
        symbol=symbol,
        strike=strike,
        option_type=option_type,
        expiry=signal.expiry,
        qty=qty,
        entry_price=entry_price,
        target_price=round(target_price, 2),
        stop_loss_price=round(sl_price, 2),
        risk_reward_ratio=round(rr_ratio, 2),
        max_loss=round(potential_loss, 2),
    )


def check_circuit_breaker(state: StrategyState) -> bool:
    """
    Check if daily loss has exceeded the circuit breaker threshold.
    Returns True if the breaker should activate.
    """
    portfolio = store.load_portfolio()
    max_loss_amount = portfolio.initial_balance * (strategy_settings.max_daily_loss_pct / 100)

    if state.realized_pnl_today < -max_loss_amount:
        logger.warning(
            "Circuit breaker triggered: daily loss ₹%.2f exceeds max ₹%.2f",
            abs(state.realized_pnl_today), max_loss_amount,
        )
        return True

    unrealized = sum(t.unrealized_pnl for t in state.active_trades)
    total_pnl = state.realized_pnl_today + unrealized

    if total_pnl < -max_loss_amount:
        logger.warning(
            "Circuit breaker triggered: total P&L ₹%.2f exceeds max loss ₹%.2f",
            total_pnl, max_loss_amount,
        )
        return True

    return False


def _check_time_filter() -> Optional[str]:
    """Check if current time is within allowed trading window."""
    now_ist = datetime.now(IST).time()

    no_before = _parse_time(strategy_settings.no_trade_before)
    no_after = _parse_time(strategy_settings.no_trade_after)

    if now_ist < no_before:
        return f"Too early: current time {now_ist.strftime('%H:%M')} before {strategy_settings.no_trade_before}"

    if now_ist > no_after:
        return f"Too late: current time {now_ist.strftime('%H:%M')} after {strategy_settings.no_trade_after}"

    return None


def _check_max_positions(state: StrategyState) -> Optional[str]:
    """Check if max open positions limit is reached."""
    open_count = len([t for t in state.active_trades if t.status == "OPEN"])
    if open_count >= strategy_settings.max_positions:
        return f"Max positions reached: {open_count}/{strategy_settings.max_positions}"
    return None


def _check_exposure(state: StrategyState) -> Optional[str]:
    """Check if total capital at risk exceeds limit."""
    portfolio = store.load_portfolio()
    max_total_risk = portfolio.initial_balance * (strategy_settings.max_total_risk_pct / 100)

    current_risk = sum(t.trade_plan.max_loss for t in state.active_trades if t.status == "OPEN")

    if current_risk >= max_total_risk:
        return (
            f"Max exposure reached: ₹{current_risk:,.0f} at risk, "
            f"limit ₹{max_total_risk:,.0f}"
        )
    return None


def _check_duplicate_position(signal: TradeSignal, state: StrategyState) -> Optional[str]:
    """Reject if an open position already exists on the same strike + option type."""
    for trade in state.active_trades:
        if trade.status != "OPEN":
            continue
        plan = trade.trade_plan
        if plan.signal.instrument != signal.instrument:
            continue
        if signal.strike_ce and plan.strike == signal.strike_ce and plan.option_type == "CE":
            return f"Duplicate: already have open {plan.symbol}"
        if signal.strike_pe and plan.strike == signal.strike_pe and plan.option_type == "PE":
            return f"Duplicate: already have open {plan.symbol}"
    return None


def _check_total_lots(state: StrategyState) -> Optional[str]:
    """Check if total lots across all open positions exceeds limit."""
    total_lots = sum(t.trade_plan.qty for t in state.active_trades if t.status == "OPEN")
    if total_lots >= strategy_settings.max_total_lots:
        return f"Total lot limit reached: {total_lots}/{strategy_settings.max_total_lots} lots open"
    return None


def _check_trade_cooldown(state: StrategyState) -> Optional[str]:
    """Enforce minimum time between trade entries."""
    if not state.last_trade_time:
        return None
    last = datetime.fromisoformat(state.last_trade_time)
    elapsed = (datetime.now(IST) - last).total_seconds()
    if elapsed < strategy_settings.min_time_between_trades_s:
        remaining = int(strategy_settings.min_time_between_trades_s - elapsed)
        return f"Cooldown active: {remaining}s until next trade allowed"
    return None


def _compute_position_size(entry_price: float, lot_size: int, instrument: str) -> int:
    """
    Determine number of lots based on max risk per trade.
    Uses the configured stop-loss to calculate risk per lot.
    """
    portfolio = store.load_portfolio()
    max_risk = portfolio.initial_balance * (strategy_settings.max_risk_per_trade_pct / 100)

    sl_price = entry_price * strategy_settings.stop_loss_multiplier
    risk_per_lot = (sl_price - entry_price) * lot_size

    if risk_per_lot <= 0:
        return 1

    max_lots = int(max_risk / risk_per_lot)
    return max(1, min(max_lots, strategy_settings.max_lots_per_trade))


def _parse_time(t_str: str) -> time:
    parts = t_str.split(":")
    return time(int(parts[0]), int(parts[1]))
