from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.strategy.config import strategy_settings
from backend.strategy.greeks import fetch_greeks_for_strike
from backend.strategy.historical_data import resolve_ltp, get_spot_price
from backend.strategy.models import ActiveTrade, ExitReason, GreeksData

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def check_exits(active_trades: list[ActiveTrade]) -> list[tuple[ActiveTrade, ExitReason]]:
    """
    Check all active positions for exit conditions.
    Returns list of (trade, reason) that should be closed.
    """
    exits: list[tuple[ActiveTrade, ExitReason]] = []

    for trade in active_trades:
        if trade.status != "OPEN":
            continue

        reason = _evaluate_exit(trade)
        if reason:
            exits.append((trade, reason))

    return exits


def update_prices(active_trades: list[ActiveTrade]) -> None:
    """Update current prices and P&L for all active trades."""
    for trade in active_trades:
        if trade.status != "OPEN":
            continue

        ltp = resolve_ltp(trade.trade_plan.token, "NFO", trade.trade_plan.symbol)
        if ltp and ltp > 0:
            trade.current_price = ltp
            entry = trade.entry_filled_price or trade.trade_plan.entry_price
            lot_size = trade.trade_plan.signal.price_action.atr if trade.trade_plan.signal.price_action else 1
            qty = trade.trade_plan.qty

            from backend.config import settings
            instrument = trade.trade_plan.signal.instrument
            ls = settings.banknifty_lot_size if instrument == "BANKNIFTY" else settings.nifty_lot_size

            # For short positions: profit when price goes down
            trade.unrealized_pnl = (entry - ltp) * qty * ls

            if trade.unrealized_pnl > trade.highest_profit:
                trade.highest_profit = trade.unrealized_pnl
                _update_trailing_sl(trade)


def _evaluate_exit(trade: ActiveTrade) -> Optional[ExitReason]:
    """Evaluate all exit conditions for a single trade."""
    entry_price = trade.entry_filled_price or trade.trade_plan.entry_price
    current_price = trade.current_price

    if current_price <= 0:
        return None

    # Target hit: premium decayed to target
    target = trade.trade_plan.target_price
    if current_price <= target:
        logger.info(
            "TARGET HIT for %s: entry=%.2f current=%.2f target=%.2f",
            trade.trade_plan.symbol, entry_price, current_price, target,
        )
        return ExitReason.TARGET_HIT

    # Stop-loss hit: premium expanded beyond SL
    sl = trade.trade_plan.stop_loss_price
    if trade.trailing_sl_price:
        sl = trade.trailing_sl_price

    if current_price >= sl:
        if trade.trailing_sl_price:
            logger.info(
                "TRAILING SL HIT for %s: entry=%.2f current=%.2f trailing_sl=%.2f",
                trade.trade_plan.symbol, entry_price, current_price, sl,
            )
            return ExitReason.TRAILING_SL_HIT
        else:
            logger.info(
                "STOP LOSS HIT for %s: entry=%.2f current=%.2f sl=%.2f",
                trade.trade_plan.symbol, entry_price, current_price, sl,
            )
            return ExitReason.STOP_LOSS_HIT

    # Greeks deterioration: delta going too deep ITM or IV spiking
    greeks_exit = _check_greeks_deterioration(trade)
    if greeks_exit:
        return greeks_exit

    # Time-based exit
    if _should_time_exit():
        return ExitReason.TIME_EXIT

    # Expiry protection
    if _near_expiry(trade.trade_plan.expiry):
        return ExitReason.EXPIRY_PROTECTION

    return None


def _check_greeks_deterioration(trade: ActiveTrade) -> Optional[ExitReason]:
    """Exit if current Greeks have deteriorated beyond safety thresholds."""
    plan = trade.trade_plan
    spot = get_spot_price(plan.signal.instrument)
    if not spot or trade.current_price <= 0:
        return None

    try:
        current_greeks = fetch_greeks_for_strike(
            plan.signal.instrument,
            plan.expiry,
            plan.strike,
            plan.option_type,
            spot,
            trade.current_price,
        )
    except Exception as e:
        logger.debug("Greeks fetch failed during position check for %s: %s", plan.symbol, e)
        return None

    # Delta danger: option moving deep ITM
    if abs(current_greeks.delta) > strategy_settings.sl_delta_danger_threshold:
        logger.warning(
            "GREEKS EXIT for %s: delta=%.3f exceeds threshold %.2f",
            plan.symbol, current_greeks.delta,
            strategy_settings.sl_delta_danger_threshold,
        )
        return ExitReason.GREEKS_DETERIORATION

    # IV spike: vega working against us
    if trade.entry_iv > 0:
        current_iv = current_greeks.iv
        iv_change_pct = ((current_iv - trade.entry_iv) / trade.entry_iv) * 100
        if iv_change_pct > strategy_settings.sl_iv_spike_exit_pct:
            logger.warning(
                "GREEKS EXIT for %s: IV spiked %.1f%% (%.1f -> %.1f), "
                "threshold %.1f%%",
                plan.symbol, iv_change_pct, trade.entry_iv, current_iv,
                strategy_settings.sl_iv_spike_exit_pct,
            )
            return ExitReason.GREEKS_DETERIORATION

    return None


def _update_trailing_sl(trade: ActiveTrade) -> None:
    """Update trailing stop-loss with dynamic width based on current theta.

    Higher theta (faster decay) -> tighter trail to lock in profit.
    Lower theta (slower decay)  -> wider trail to give room.
    """
    entry_price = trade.entry_filled_price or trade.trade_plan.entry_price
    trigger_pct = strategy_settings.trailing_sl_trigger_pct

    premium_decay_pct = ((entry_price - trade.current_price) / entry_price) * 100

    if premium_decay_pct >= trigger_pct:
        trail_pct = _dynamic_trail_pct(trade)
        trail_amount = entry_price * (trail_pct / 100)
        new_sl = trade.current_price + trail_amount

        if trade.trailing_sl_price is None or new_sl < trade.trailing_sl_price:
            old_sl = trade.trailing_sl_price or trade.trade_plan.stop_loss_price
            trade.trailing_sl_price = round(new_sl, 2)
            logger.debug(
                "Trailing SL updated for %s: %.2f -> %.2f (current=%.2f, trail_pct=%.1f%%)",
                trade.trade_plan.symbol, old_sl, new_sl,
                trade.current_price, trail_pct,
            )


def _dynamic_trail_pct(trade: ActiveTrade) -> float:
    """Compute trailing SL width % based on current theta.

    Uses the configured trailing_sl_pct as the baseline and adjusts:
    - High theta (|theta| > 2): tighten to 60% of baseline (decay is fast, lock profit)
    - Medium theta (0.5-2):     use baseline as-is
    - Low theta (|theta| < 0.5): widen to 150% of baseline (decay is slow, give room)
    """
    base_pct = strategy_settings.trailing_sl_pct
    plan = trade.trade_plan

    try:
        spot = get_spot_price(plan.signal.instrument)
        if not spot or trade.current_price <= 0:
            return base_pct

        greeks = fetch_greeks_for_strike(
            plan.signal.instrument, plan.expiry, plan.strike,
            plan.option_type, spot, trade.current_price,
        )
        abs_theta = abs(greeks.theta)

        if abs_theta > 2.0:
            return base_pct * 0.6
        elif abs_theta < 0.5:
            return base_pct * 1.5
        return base_pct

    except Exception:
        return base_pct


def _should_time_exit() -> bool:
    """Check if we've reached the auto square-off time."""
    from backend.config import settings

    now_ist = datetime.now(IST).time()
    parts = settings.auto_sqoff_time.split(":")
    sqoff_time = datetime.now(IST).replace(
        hour=int(parts[0]), minute=int(parts[1]), second=0, microsecond=0
    ).time()

    return now_ist >= sqoff_time


def _near_expiry(expiry_str: str) -> bool:
    """Check if position is within min_dte of expiry."""
    now = datetime.now(IST)

    for fmt in ("%d%b%Y", "%d%b%y", "%Y-%m-%d"):
        try:
            expiry_date = datetime.strptime(expiry_str.upper(), fmt)
            expiry_date = expiry_date.replace(tzinfo=IST)
            days_to_expiry = (expiry_date - now).days
            return days_to_expiry < strategy_settings.min_dte
        except ValueError:
            continue

    return False


def calculate_exit_price(trade: ActiveTrade) -> float:
    """Get the best available price for exit."""
    ltp = resolve_ltp(trade.trade_plan.token, "NFO", trade.trade_plan.symbol)
    if ltp and ltp > 0:
        return ltp
    return trade.current_price
