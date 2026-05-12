from __future__ import annotations

import logging
from typing import Optional

from backend.strategy.historical_data import resolve_ltp
from backend.strategy.models import Candle, MarketBias, SentimentSignal, Timeframe
from backend.websocket_manager import market_data

logger = logging.getLogger(__name__)

INDIA_VIX_TOKEN = "26017"
INDIA_VIX_SYMBOL = "India VIX"
NSE_EXCHANGE = "NSE"


def analyze_sentiment(
    daily_candles: list[Candle],
    spot_price: float,
) -> SentimentSignal:
    """
    Analyze overall market sentiment using VIX, broad trend, and gap analysis.
    """
    vix = _get_vix()
    vix_change = _vix_change_pct(vix)
    gap_pct = _compute_gap(daily_candles, spot_price)
    market_bias = _determine_sentiment(daily_candles, vix, gap_pct)
    confidence = _compute_confidence(vix, vix_change, gap_pct, market_bias)

    signal = SentimentSignal(
        vix=vix,
        vix_change_pct=vix_change,
        market_bias=market_bias,
        gap_pct=gap_pct,
        confidence=confidence,
    )

    logger.info(
        "Sentiment: VIX=%.2f (Δ%.1f%%) Gap=%.2f%% Bias=%s Conf=%.0f",
        vix, vix_change, gap_pct, market_bias.value, confidence,
    )
    return signal


def _get_vix() -> float:
    """Get India VIX current value via centralized LTP resolver."""
    ltp = resolve_ltp(INDIA_VIX_TOKEN, NSE_EXCHANGE, INDIA_VIX_SYMBOL)
    return ltp if ltp and ltp > 0 else 0.0


def _vix_change_pct(current_vix: float) -> float:
    """Calculate VIX change from previous close."""
    tick = market_data.latest_prices.get(INDIA_VIX_TOKEN, {})
    prev_close = tick.get("close", 0)
    if prev_close > 0 and current_vix > 0:
        return ((current_vix - prev_close) / prev_close) * 100
    return 0.0


def _compute_gap(daily_candles: list[Candle], spot_price: float) -> float:
    """Compute today's gap percentage from previous day's close."""
    if not daily_candles:
        return 0.0

    prev_close = daily_candles[-1].close
    if prev_close <= 0:
        return 0.0

    today_open = spot_price
    return ((today_open - prev_close) / prev_close) * 100


def _determine_sentiment(
    daily_candles: list[Candle],
    vix: float,
    gap_pct: float,
) -> MarketBias:
    """
    Determine overall market sentiment.
    Volatile if VIX is high; otherwise based on recent price action + gap.
    """
    if vix > 20:
        return MarketBias.VOLATILE

    if not daily_candles or len(daily_candles) < 5:
        return MarketBias.NEUTRAL

    recent_5 = daily_candles[-5:]
    up_days = sum(1 for c in recent_5 if c.close > c.open)

    if gap_pct > 0.5 and up_days >= 3:
        return MarketBias.BULLISH
    elif gap_pct < -0.5 and up_days <= 2:
        return MarketBias.BEARISH
    elif up_days >= 4:
        return MarketBias.BULLISH
    elif up_days <= 1:
        return MarketBias.BEARISH
    else:
        return MarketBias.NEUTRAL


def _compute_confidence(
    vix: float,
    vix_change: float,
    gap_pct: float,
    bias: MarketBias,
) -> float:
    """Compute sentiment confidence (0-100). Higher for stable, clear conditions."""
    score = 40.0

    # Low VIX is good for sellers (stable)
    if 10 <= vix <= 15:
        score += 25.0
    elif 15 < vix <= 18:
        score += 15.0
    elif vix > 20:
        score -= 10.0  # risky for sellers

    # VIX spike is bad
    if abs(vix_change) < 5:
        score += 10.0
    elif abs(vix_change) > 15:
        score -= 15.0

    # Small gap is ideal for range-bound selling
    if abs(gap_pct) < 0.3:
        score += 15.0
    elif abs(gap_pct) > 1.0:
        score -= 10.0

    # Clear bias helps with directional selling
    if bias in (MarketBias.BULLISH, MarketBias.BEARISH):
        score += 10.0
    elif bias == MarketBias.VOLATILE:
        score -= 10.0

    return max(0.0, min(score, 100.0))


def is_vix_spike(threshold_pct: float = 20.0) -> bool:
    """Check if VIX has spiked beyond threshold (circuit breaker check)."""
    vix = _get_vix()
    change = _vix_change_pct(vix)
    return change > threshold_pct
