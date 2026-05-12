from __future__ import annotations

import logging
from datetime import datetime

from backend.strategy.config import strategy_settings
from backend.strategy.models import (
    MarketBias,
    OrderFlowSignal,
    PriceActionSignal,
    SentimentSignal,
    SignalAction,
    SupportResistanceLevel,
    TradeSignal,
)

logger = logging.getLogger(__name__)

WEIGHT_SR = 0.30
WEIGHT_PRICE_ACTION = 0.25
WEIGHT_ORDER_FLOW = 0.25
WEIGHT_SENTIMENT = 0.20


def generate_signal(
    instrument: str,
    spot_price: float,
    expiry: str,
    levels: list[SupportResistanceLevel],
    price_action: PriceActionSignal,
    order_flow: OrderFlowSignal,
    sentiment: SentimentSignal,
) -> TradeSignal:
    """
    Aggregate all analysis signals into a final trade decision.
    Determines whether to sell CE, PE, strangle, or no trade.
    """
    action = _determine_action(spot_price, levels, price_action, order_flow, sentiment)
    confidence = _compute_combined_confidence(price_action, order_flow, sentiment, action, levels, spot_price)
    strike_ce, strike_pe = _select_strikes(instrument, spot_price, levels, order_flow, action)
    rationale = _build_rationale(action, price_action, order_flow, sentiment, spot_price, levels)

    signal = TradeSignal(
        instrument=instrument,
        action=action,
        strike_ce=strike_ce,
        strike_pe=strike_pe,
        expiry=expiry,
        confidence=confidence,
        rationale=rationale,
        price_action=price_action,
        order_flow=order_flow,
        sentiment=sentiment,
    )

    logger.info(
        "Signal for %s: %s confidence=%.1f CE=%.0f PE=%.0f",
        instrument, action.value, confidence,
        strike_ce or 0, strike_pe or 0,
    )
    return signal


def _determine_action(
    spot_price: float,
    levels: list[SupportResistanceLevel],
    pa: PriceActionSignal,
    of: OrderFlowSignal,
    sent: SentimentSignal,
) -> SignalAction:
    """
    Core decision logic for option selling:
    - Near resistance with rejection -> Sell CE
    - Near support with rejection -> Sell PE
    - Range-bound between levels -> Sell Strangle
    - Strong trend / volatile -> No Trade
    """
    if sent.market_bias == MarketBias.VOLATILE:
        return SignalAction.NO_TRADE

    if pa.trend_strength > 75 and pa.bias != MarketBias.NEUTRAL:
        return SignalAction.NO_TRADE

    if pa.at_resistance and pa.rejection_detected:
        if pa.bias != MarketBias.BULLISH or pa.trend_strength < 60:
            return SignalAction.SELL_CE

    if pa.at_support and pa.rejection_detected:
        if pa.bias != MarketBias.BEARISH or pa.trend_strength < 60:
            return SignalAction.SELL_PE

    # Range-bound: no strong directional move, price between S/R
    if not pa.at_support and not pa.at_resistance and pa.bias == MarketBias.NEUTRAL:
        if of.pcr > 0.7 and of.pcr < 1.5:
            return SignalAction.SELL_STRANGLE

    # Directional bias without rejection: sell the side that benefits
    if pa.bias == MarketBias.BULLISH and of.oi_buildup_bias in (MarketBias.BULLISH, MarketBias.NEUTRAL):
        return SignalAction.SELL_PE

    if pa.bias == MarketBias.BEARISH and of.oi_buildup_bias in (MarketBias.BEARISH, MarketBias.NEUTRAL):
        return SignalAction.SELL_CE

    return SignalAction.NO_TRADE


def _compute_combined_confidence(
    pa: PriceActionSignal,
    of: OrderFlowSignal,
    sent: SentimentSignal,
    action: SignalAction,
    levels: list[SupportResistanceLevel],
    spot_price: float,
) -> float:
    """Weighted confidence score from all analyzers."""
    if action == SignalAction.NO_TRADE:
        return 0.0

    sr_confidence = _sr_proximity_score(spot_price, levels, pa.atr)
    weighted = (
        sr_confidence * WEIGHT_SR
        + pa.confidence * WEIGHT_PRICE_ACTION
        + of.confidence * WEIGHT_ORDER_FLOW
        + sent.confidence * WEIGHT_SENTIMENT
    )

    # Penalize conflicting signals
    biases = [pa.bias, of.oi_buildup_bias, sent.market_bias]
    conflict_penalty = _conflict_penalty(biases, action)
    weighted -= conflict_penalty

    return max(0.0, min(round(weighted, 1), 100.0))


def _sr_proximity_score(
    spot: float,
    levels: list[SupportResistanceLevel],
    atr: float,
) -> float:
    """Score based on how close spot is to strong S/R levels."""
    if not levels or atr <= 0:
        return 30.0

    nearest_distance = min(abs(spot - l.price) for l in levels[:5])
    ratio = nearest_distance / atr

    if ratio < 0.3:
        return 90.0  # right at a level
    elif ratio < 0.5:
        return 70.0
    elif ratio < 1.0:
        return 50.0
    else:
        return 30.0  # far from any key level


def _conflict_penalty(biases: list[MarketBias], action: SignalAction) -> float:
    """Reduce confidence if signals disagree with the chosen action."""
    penalty = 0.0

    if action == SignalAction.SELL_CE:
        bullish_count = sum(1 for b in biases if b == MarketBias.BULLISH)
        penalty = bullish_count * 8.0
    elif action == SignalAction.SELL_PE:
        bearish_count = sum(1 for b in biases if b == MarketBias.BEARISH)
        penalty = bearish_count * 8.0
    elif action == SignalAction.SELL_STRANGLE:
        volatile_count = sum(1 for b in biases if b == MarketBias.VOLATILE)
        penalty = volatile_count * 12.0

    return penalty


def _select_strikes(
    instrument: str,
    spot_price: float,
    levels: list[SupportResistanceLevel],
    of: OrderFlowSignal,
    action: SignalAction,
) -> tuple[float | None, float | None]:
    """
    Select optimal strikes for selling based on OI levels and configured OTM offset.
    Prefers strikes near strong OI concentration (natural walls).
    """
    offset = (
        strategy_settings.otm_offset_points_nifty
        if instrument == "NIFTY"
        else strategy_settings.otm_offset_points_banknifty
    )

    ce_strike: float | None = None
    pe_strike: float | None = None

    if action in (SignalAction.SELL_CE, SignalAction.SELL_STRANGLE):
        if of.ce_oi_resistance > spot_price:
            ce_strike = of.ce_oi_resistance
        else:
            ce_strike = _round_strike(spot_price + offset, instrument)

    if action in (SignalAction.SELL_PE, SignalAction.SELL_STRANGLE):
        if of.pe_oi_support > 0 and of.pe_oi_support < spot_price:
            pe_strike = of.pe_oi_support
        else:
            pe_strike = _round_strike(spot_price - offset, instrument)

    return ce_strike, pe_strike


def _round_strike(price: float, instrument: str) -> float:
    """Round to nearest valid strike interval."""
    step = 50.0 if instrument == "NIFTY" else 100.0
    return round(price / step) * step


def _build_rationale(
    action: SignalAction,
    pa: PriceActionSignal,
    of: OrderFlowSignal,
    sent: SentimentSignal,
    spot: float,
    levels: list[SupportResistanceLevel],
) -> str:
    """Build human-readable explanation of the trade decision."""
    parts: list[str] = []

    parts.append(f"Action: {action.value}")
    parts.append(f"Spot: {spot:.0f}")
    parts.append(f"Trend: {pa.bias.value} (strength {pa.trend_strength:.0f}%)")

    if pa.at_resistance:
        parts.append("Price at resistance")
    if pa.at_support:
        parts.append("Price at support")
    if pa.rejection_detected:
        parts.append(f"Rejection pattern: {pa.pattern}")

    parts.append(f"PCR: {of.pcr:.2f}, MaxPain: {of.max_pain_strike:.0f}")
    parts.append(f"VIX: {sent.vix:.1f}, Sentiment: {sent.market_bias.value}")

    return " | ".join(parts)
