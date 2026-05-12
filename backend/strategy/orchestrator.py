from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.config import settings as app_settings
from backend.instrument_service import get_option_chain
from backend.strategy.config import strategy_settings
from backend.strategy.executor import execute_entry, execute_exit
from backend.strategy.historical_data import fetch_multi_timeframe, get_spot_price
from backend.strategy.market_sentiment import analyze_sentiment, is_vix_spike
from backend.strategy.models import (
    ActiveTrade,
    AnalysisSnapshot,
    DecisionLogEntry,
    ExitReason,
    SignalAction,
    StrategyState,
    Timeframe,
    TradePlan,
    TradeSignal,
)
from backend.strategy.order_flow import analyze_order_flow
from backend.strategy.position_manager import check_exits, update_prices, calculate_exit_price
from backend.strategy.price_action import analyze_price_action
from backend.strategy.risk_manager import (
    check_circuit_breaker,
    compute_trade_plan,
    validate_trade,
)
from backend.strategy.signal import generate_signal
from backend.strategy.support_resistance import detect_levels, find_nearest_levels
from backend.websocket_manager import market_data

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

MAX_LOG_ENTRIES = 200
MAX_RECENT_SIGNALS = 20

_state = StrategyState()
_orchestrator_task: Optional[asyncio.Task] = None


def get_state() -> StrategyState:
    return _state


def start_strategy() -> dict:
    """Start the autonomous strategy loop."""
    global _orchestrator_task

    if _state.running:
        return {"status": "already_running", "started_at": _state.started_at}

    from backend.smartapi_client import session as api_session
    from backend.instrument_service import get_index_token

    if not api_session.is_logged_in:
        try:
            api_session.login()
            logger.info("Auto-login successful for strategy start")
        except Exception as e:
            logger.error("Auto-login failed on strategy start: %s", e)
            return {"status": "error", "message": f"Login required: {e}"}

    # Auto-subscribe index tokens + VIX to WebSocket for real-time data
    try:
        index_tokens = [get_index_token(i) for i in strategy_settings.instruments]
        vix_token = "26017"
        nse_tokens = index_tokens + [vix_token]
        token_list = [{"exchangeType": 1, "tokens": nse_tokens}]
        if not market_data._running:
            market_data.start(token_list)
        else:
            market_data.update_subscription(token_list)
        logger.info("WebSocket subscribed to %d NSE tokens (indices + VIX)", len(nse_tokens))
    except Exception as e:
        logger.warning("WebSocket subscription failed (will use REST fallback): %s", e)

    _state.running = True
    _state.started_at = datetime.now(IST).isoformat()
    _state.stopped_at = None
    _state.circuit_breaker_active = False

    _orchestrator_task = asyncio.get_event_loop().create_task(_strategy_loop())
    logger.info("Autonomous strategy started at %s", _state.started_at)

    _log_decision("SYSTEM", "STRATEGY_STARTED", "Strategy loop initiated by user")
    return {"status": "started", "started_at": _state.started_at}


def stop_strategy(close_positions: bool = False) -> dict:
    """Stop the strategy loop. Optionally close all open positions."""
    global _orchestrator_task

    if not _state.running:
        return {"status": "not_running"}

    _state.running = False
    _state.stopped_at = datetime.now(IST).isoformat()

    if _orchestrator_task and not _orchestrator_task.done():
        _orchestrator_task.cancel()

    _log_decision("SYSTEM", "STRATEGY_STOPPED", f"close_positions={close_positions}")
    logger.info("Autonomous strategy stopped")

    if close_positions:
        asyncio.get_event_loop().create_task(_kill_switch())

    return {"status": "stopped", "stopped_at": _state.stopped_at}


async def _kill_switch() -> None:
    """Emergency close all autonomous positions."""
    for trade in _state.active_trades:
        if trade.status != "OPEN":
            continue
        try:
            price = calculate_exit_price(trade)
            pnl = await execute_exit(trade, ExitReason.KILL_SWITCH)
            if pnl is not None:
                _state.realized_pnl_today += pnl
                _log_decision(
                    trade.trade_plan.signal.instrument,
                    "POSITION_EXITED",
                    f"Kill switch: {trade.trade_plan.symbol} P&L=₹{pnl:.2f}",
                )
        except Exception as e:
            logger.error("Kill switch exit failed for %s: %s", trade.trade_plan.symbol, e)


async def _strategy_loop() -> None:
    """Main orchestrator loop: scan -> analyze -> decide -> execute -> manage."""
    logger.info("Strategy loop running, scan interval: %ds", strategy_settings.scan_interval_seconds)

    # One-time: ensure instrument master / option chain is loaded
    from backend.instrument_service import fetch_instruments
    for inst in strategy_settings.instruments:
        chain = get_option_chain(inst)
        if not chain or not chain.get("strikes"):
            try:
                await fetch_instruments()
                logger.info("Auto-fetched instrument master for option chain data")
            except Exception as e:
                logger.warning("Instrument fetch failed (chain may be unavailable): %s", e)
            break

    while _state.running:
        try:
            # Phase 1: Manage existing positions
            await _manage_positions()

            # Phase 2: Check circuit breakers
            if check_circuit_breaker(_state):
                _state.circuit_breaker_active = True
                _log_decision("SYSTEM", "CIRCUIT_BREAKER", "Daily loss limit exceeded, pausing new trades")
                await asyncio.sleep(strategy_settings.scan_interval_seconds)
                continue

            if is_vix_spike(strategy_settings.vix_spike_pct):
                _log_decision("SYSTEM", "VIX_SPIKE", "VIX spike detected, pausing new entries")
                await asyncio.sleep(strategy_settings.scan_interval_seconds)
                continue

            # Phase 3: Scan for new opportunities
            for instrument in strategy_settings.instruments:
                if not _state.running:
                    break
                await _scan_instrument(instrument)
                await asyncio.sleep(1)

            _state.last_scan_time = datetime.now(IST).isoformat()

        except asyncio.CancelledError:
            logger.info("Strategy loop cancelled")
            break
        except Exception as e:
            logger.exception("Unhandled error in strategy loop: %s", e)
            _log_decision("SYSTEM", "ERROR", str(e))

        await asyncio.sleep(strategy_settings.scan_interval_seconds)

    logger.info("Strategy loop exited")


async def _manage_positions() -> None:
    """Update prices and check for exits on all active positions."""
    open_trades = [t for t in _state.active_trades if t.status == "OPEN"]
    if not open_trades:
        return

    update_prices(open_trades)

    exits = check_exits(open_trades)
    for trade, reason in exits:
        pnl = await execute_exit(trade, reason)
        if pnl is not None:
            _state.realized_pnl_today += pnl
            _state.total_trades_today += 1
            _log_decision(
                trade.trade_plan.signal.instrument,
                "POSITION_EXITED",
                f"{reason.value}: {trade.trade_plan.symbol} P&L=₹{pnl:.2f}",
            )


async def _scan_instrument(instrument: str) -> None:
    """Full analysis pipeline for a single instrument."""
    spot_price = get_spot_price(instrument)
    if not spot_price:
        logger.debug("No spot price for %s, skipping scan", instrument)
        _state.analysis_snapshots[instrument] = AnalysisSnapshot(
            instrument=instrument, spot_price=0.0,
            signal_action="NO_DATA", signal_confidence=0.0,
        )
        return

    # Fetch candle data
    candles_by_tf = fetch_multi_timeframe(instrument)
    if not candles_by_tf.get(Timeframe.DAILY):
        logger.debug("No daily candles for %s, skipping", instrument)
        _state.analysis_snapshots[instrument] = AnalysisSnapshot(
            instrument=instrument, spot_price=spot_price,
            signal_action="NO_DATA", signal_confidence=0.0,
        )
        return

    # Detect S/R levels
    levels = detect_levels(candles_by_tf)

    # Analyze price action
    pa_signal = analyze_price_action(candles_by_tf, levels, spot_price)

    # Get nearest expiry for option chain
    chain = get_option_chain(instrument)
    if not chain or not chain.get("expiry"):
        supports, resistances = find_nearest_levels(spot_price, levels)
        _state.analysis_snapshots[instrument] = AnalysisSnapshot(
            instrument=instrument, spot_price=spot_price,
            levels=sorted(levels[:15], key=lambda l: l.price),
            nearest_support=supports[0].price if supports else None,
            nearest_resistance=resistances[0].price if resistances else None,
            price_action=pa_signal,
            signal_action="NO_CHAIN", signal_confidence=0.0,
        )
        return
    expiry = chain["expiry"]

    # Analyze order flow (reuse chain fetched above)
    of_signal = analyze_order_flow(instrument, expiry, spot_price, chain=chain)

    # Analyze sentiment
    daily_candles = candles_by_tf.get(Timeframe.DAILY, [])
    sent_signal = analyze_sentiment(daily_candles, spot_price)

    # Generate trade signal
    signal = generate_signal(
        instrument, spot_price, expiry, levels, pa_signal, of_signal, sent_signal,
    )

    # Store signal for UI display
    _state.recent_signals = [signal] + _state.recent_signals[:MAX_RECENT_SIGNALS - 1]

    # Store analysis snapshot for transparency UI
    supports, resistances = find_nearest_levels(spot_price, levels)
    _state.analysis_snapshots[instrument] = AnalysisSnapshot(
        instrument=instrument,
        spot_price=spot_price,
        levels=sorted(levels[:15], key=lambda l: l.price),
        nearest_support=supports[0].price if supports else None,
        nearest_resistance=resistances[0].price if resistances else None,
        price_action=pa_signal,
        order_flow=of_signal,
        sentiment=sent_signal,
        signal_action=signal.action.value,
        signal_confidence=signal.confidence,
    )

    if signal.action == SignalAction.NO_TRADE:
        _log_decision(instrument, "SIGNAL_SKIPPED", signal.rationale)
        return

    # Validate against risk rules
    rejections = validate_trade(signal, _state)
    if rejections:
        reason_str = "; ".join(rejections)
        _log_decision(instrument, "TRADE_REJECTED", f"{signal.action.value} rejected: {reason_str}")
        return

    # Execute trade(s)
    await _execute_signal(signal, instrument, chain)


async def _execute_signal(signal: TradeSignal, instrument: str, chain: dict) -> None:
    """Convert signal into trade plan(s) and execute."""
    strikes_data = chain.get("strikes", {})

    if signal.action in (SignalAction.SELL_CE, SignalAction.SELL_STRANGLE):
        if signal.strike_ce:
            await _execute_single_leg(signal, instrument, signal.strike_ce, "CE", strikes_data)

    if signal.action in (SignalAction.SELL_PE, SignalAction.SELL_STRANGLE):
        if signal.strike_pe:
            await _execute_single_leg(signal, instrument, signal.strike_pe, "PE", strikes_data)


async def _execute_single_leg(
    signal: TradeSignal,
    instrument: str,
    strike: float,
    option_type: str,
    strikes_data: dict,
) -> None:
    """Execute a single option leg (CE or PE)."""
    strike_str = str(strike)
    strike_info = strikes_data.get(strike_str, {}).get(option_type, {})

    if not strike_info:
        # Try nearby strikes
        strike_str = str(int(strike))
        strike_info = strikes_data.get(strike_str, {}).get(option_type, {})
        if not strike_info:
            _log_decision(instrument, "EXECUTION_FAILED", f"No data for {strike} {option_type}")
            return

    token = strike_info.get("token", "")
    symbol = strike_info.get("symbol", "")
    lot_size = int(strike_info.get("lotsize", 1))

    if not token or not symbol:
        return

    # Get current premium
    from backend.strategy.historical_data import resolve_ltp
    entry_price = resolve_ltp(token, "NFO", symbol)
    if not entry_price or entry_price <= 0:
        _log_decision(instrument, "EXECUTION_FAILED", f"No LTP for {symbol}")
        return

    # Filter by premium range
    if entry_price < strategy_settings.min_premium:
        _log_decision(instrument, "TRADE_REJECTED", f"Premium ₹{entry_price:.2f} below minimum ₹{strategy_settings.min_premium}")
        return
    if entry_price > strategy_settings.max_premium:
        _log_decision(instrument, "TRADE_REJECTED", f"Premium ₹{entry_price:.2f} above maximum ₹{strategy_settings.max_premium}")
        return

    # Compute trade plan with risk checks
    plan = compute_trade_plan(
        signal=signal,
        token=token,
        symbol=symbol,
        strike=strike,
        option_type=option_type,
        entry_price=entry_price,
        lot_size=lot_size,
    )

    if not plan:
        _log_decision(instrument, "TRADE_REJECTED", f"RR ratio check failed for {symbol}")
        return

    # Execute!
    active_trade = await execute_entry(plan)
    if active_trade:
        _state.active_trades.append(active_trade)
        _state.total_trades_today += 1
        _state.last_trade_time = datetime.now(IST).isoformat()
        _log_decision(
            instrument,
            "TRADE_PLACED",
            f"SELL {plan.qty}x {symbol} @ ₹{entry_price:.2f} | "
            f"Target=₹{plan.target_price:.2f} SL=₹{plan.stop_loss_price:.2f} RR={plan.risk_reward_ratio:.2f}",
            signal=signal,
        )


def _log_decision(
    instrument: str,
    action_taken: str,
    reason: str,
    signal: Optional[TradeSignal] = None,
) -> None:
    """Add entry to the decision log."""
    entry = DecisionLogEntry(
        instrument=instrument,
        action_taken=action_taken,
        reason=reason,
        signal=signal,
    )
    _state.decision_log = [entry] + _state.decision_log[:MAX_LOG_ENTRIES - 1]


def reset_daily_state() -> None:
    """Reset daily counters (called at start of each trading day)."""
    _state.total_trades_today = 0
    _state.realized_pnl_today = 0.0
    _state.circuit_breaker_active = False
    _state.active_trades = [t for t in _state.active_trades if t.status == "OPEN"]
    logger.info("Daily state reset")
