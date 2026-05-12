from __future__ import annotations

import logging

from backend.strategy.models import (
    Candle,
    MarketBias,
    PriceActionSignal,
    SupportResistanceLevel,
    Timeframe,
)
from backend.strategy.support_resistance import find_nearest_levels, is_near_level

logger = logging.getLogger(__name__)


def analyze_price_action(
    candles_by_tf: dict[Timeframe, list[Candle]],
    levels: list[SupportResistanceLevel],
    spot_price: float,
) -> PriceActionSignal:
    """
    Analyze price action across timeframes relative to S/R levels.
    Returns a signal indicating trend, position relative to levels, and confidence.
    """
    daily = candles_by_tf.get(Timeframe.DAILY, [])
    tf_15m = candles_by_tf.get(Timeframe.FIFTEEN_MIN, [])
    tf_5m = candles_by_tf.get(Timeframe.FIVE_MIN, [])

    atr = compute_atr(tf_15m if tf_15m else daily, period=14)
    bias = _determine_trend(daily, tf_15m, tf_5m)
    trend_strength = _trend_strength(tf_15m if tf_15m else daily)

    supports, resistances = find_nearest_levels(spot_price, levels)
    at_support = False
    at_resistance = False
    rejection = False
    pattern = ""

    if supports and is_near_level(spot_price, supports[0], atr):
        at_support = True
        if tf_5m:
            rejection = _detect_rejection_at_support(tf_5m[-5:], supports[0].price)
            if rejection:
                pattern = "bullish_rejection_at_support"

    if resistances and is_near_level(spot_price, resistances[0], atr):
        at_resistance = True
        if tf_5m:
            rejection = _detect_rejection_at_resistance(tf_5m[-5:], resistances[0].price)
            if rejection:
                pattern = "bearish_rejection_at_resistance"

    confidence = _compute_confidence(bias, trend_strength, at_support, at_resistance, rejection)

    return PriceActionSignal(
        bias=bias,
        trend_strength=trend_strength,
        at_support=at_support,
        at_resistance=at_resistance,
        rejection_detected=rejection,
        pattern=pattern,
        atr=atr,
        confidence=confidence,
    )


def compute_atr(candles: list[Candle], period: int = 14) -> float:
    """Compute Average True Range over the given period."""
    if len(candles) < 2:
        return 0.0

    true_ranges: list[float] = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    if not true_ranges:
        return 0.0

    use_period = min(period, len(true_ranges))
    return sum(true_ranges[-use_period:]) / use_period


def _determine_trend(
    daily: list[Candle],
    tf_15m: list[Candle],
    tf_5m: list[Candle],
) -> MarketBias:
    """
    Determine overall market bias from multi-timeframe trend analysis.
    Daily trend is dominant; lower timeframes confirm or diverge.
    """
    daily_bias = _single_tf_trend(daily, lookback=10)
    intraday_bias = _single_tf_trend(tf_15m if tf_15m else tf_5m, lookback=20)

    if daily_bias == intraday_bias:
        return daily_bias

    if daily_bias == MarketBias.NEUTRAL:
        return intraday_bias

    if intraday_bias == MarketBias.NEUTRAL:
        return daily_bias

    return MarketBias.NEUTRAL


def _single_tf_trend(candles: list[Candle], lookback: int = 10) -> MarketBias:
    """Simple trend detection: compare recent closes to EMA-like average."""
    if len(candles) < lookback:
        return MarketBias.NEUTRAL

    recent = candles[-lookback:]
    closes = [c.close for c in recent]

    higher_highs = sum(
        1 for i in range(1, len(recent)) if recent[i].high > recent[i - 1].high
    )
    lower_lows = sum(
        1 for i in range(1, len(recent)) if recent[i].low < recent[i - 1].low
    )

    up_ratio = higher_highs / (lookback - 1)
    down_ratio = lower_lows / (lookback - 1)

    first_half_avg = sum(closes[: lookback // 2]) / (lookback // 2)
    second_half_avg = sum(closes[lookback // 2:]) / (lookback - lookback // 2)

    if second_half_avg > first_half_avg * 1.002 and up_ratio > 0.55:
        return MarketBias.BULLISH
    elif second_half_avg < first_half_avg * 0.998 and down_ratio > 0.55:
        return MarketBias.BEARISH
    else:
        return MarketBias.NEUTRAL


def _trend_strength(candles: list[Candle], lookback: int = 20) -> float:
    """Compute trend strength as a 0-100 score based on directional move consistency."""
    if len(candles) < lookback:
        lookback = len(candles)
    if lookback < 3:
        return 0.0

    recent = candles[-lookback:]
    up_moves = sum(1 for i in range(1, len(recent)) if recent[i].close > recent[i - 1].close)
    total_moves = len(recent) - 1

    if total_moves == 0:
        return 0.0

    directional_ratio = max(up_moves, total_moves - up_moves) / total_moves
    return round(directional_ratio * 100, 1)


def _detect_rejection_at_support(candles: list[Candle], support_price: float) -> bool:
    """
    Detect bullish rejection (long lower wick) near support.
    A rejection wick is when the low touches support but close is well above.
    """
    if not candles:
        return False

    for candle in candles[-3:]:
        body_size = abs(candle.close - candle.open)
        lower_wick = min(candle.open, candle.close) - candle.low
        total_range = candle.high - candle.low

        if total_range == 0:
            continue

        wick_ratio = lower_wick / total_range
        touches_support = candle.low <= support_price * 1.001

        if wick_ratio > 0.5 and touches_support and candle.close > candle.open:
            return True

    return False


def _detect_rejection_at_resistance(candles: list[Candle], resistance_price: float) -> bool:
    """
    Detect bearish rejection (long upper wick) near resistance.
    """
    if not candles:
        return False

    for candle in candles[-3:]:
        body_size = abs(candle.close - candle.open)
        upper_wick = candle.high - max(candle.open, candle.close)
        total_range = candle.high - candle.low

        if total_range == 0:
            continue

        wick_ratio = upper_wick / total_range
        touches_resistance = candle.high >= resistance_price * 0.999

        if wick_ratio > 0.5 and touches_resistance and candle.close < candle.open:
            return True

    return False


def _compute_confidence(
    bias: MarketBias,
    trend_strength: float,
    at_support: bool,
    at_resistance: bool,
    rejection: bool,
) -> float:
    """
    Compute price action confidence score (0-100).
    Higher if price is at a level with rejection and clear trend.
    """
    score = 30.0  # base

    if at_support or at_resistance:
        score += 25.0

    if rejection:
        score += 25.0

    if trend_strength > 60:
        score += 10.0
    elif trend_strength > 50:
        score += 5.0

    if bias != MarketBias.NEUTRAL:
        score += 10.0

    return min(score, 100.0)
