from __future__ import annotations

import logging
from collections import defaultdict

from backend.strategy.models import Candle, SupportResistanceLevel, Timeframe

logger = logging.getLogger(__name__)

CLUSTER_BAND_PCT = 0.002  # 0.2% band for grouping nearby levels


def detect_levels(
    candles_by_tf: dict[Timeframe, list[Candle]],
) -> list[SupportResistanceLevel]:
    """
    Detect support and resistance levels from multi-timeframe candle data.
    Combines pivot points, swing highs/lows, and PDH/PDL/PDC.
    Returns levels sorted by strength (strongest first).
    """
    all_levels: list[SupportResistanceLevel] = []

    for tf, candles in candles_by_tf.items():
        if not candles:
            continue
        all_levels.extend(_swing_levels(candles, tf))
        all_levels.extend(_pivot_levels(candles, tf))

    daily_candles = candles_by_tf.get(Timeframe.DAILY, [])
    if daily_candles:
        all_levels.extend(_previous_day_levels(daily_candles))

    clustered = _cluster_levels(all_levels)
    clustered.sort(key=lambda l: l.strength, reverse=True)

    logger.info("Detected %d S/R levels (clustered from %d raw)", len(clustered), len(all_levels))
    return clustered


def _swing_levels(candles: list[Candle], timeframe: Timeframe) -> list[SupportResistanceLevel]:
    """Identify swing highs and lows using a 5-bar lookback/lookahead."""
    levels: list[SupportResistanceLevel] = []
    if len(candles) < 5:
        return levels

    lookback = 2

    for i in range(lookback, len(candles) - lookback):
        window_highs = [c.high for c in candles[i - lookback: i + lookback + 1]]
        window_lows = [c.low for c in candles[i - lookback: i + lookback + 1]]

        if candles[i].high == max(window_highs):
            levels.append(SupportResistanceLevel(
                price=candles[i].high,
                strength=1,
                timeframe=timeframe,
                level_type="swing_high",
            ))

        if candles[i].low == min(window_lows):
            levels.append(SupportResistanceLevel(
                price=candles[i].low,
                strength=1,
                timeframe=timeframe,
                level_type="swing_low",
            ))

    return levels


def _pivot_levels(candles: list[Candle], timeframe: Timeframe) -> list[SupportResistanceLevel]:
    """Calculate classic pivot points from the most recent completed candle."""
    if not candles:
        return []

    last = candles[-1]
    pivot = (last.high + last.low + last.close) / 3
    r1 = 2 * pivot - last.low
    s1 = 2 * pivot - last.high
    r2 = pivot + (last.high - last.low)
    s2 = pivot - (last.high - last.low)
    r3 = last.high + 2 * (pivot - last.low)
    s3 = last.low - 2 * (last.high - pivot)

    levels = []
    for price, label in [
        (pivot, "pivot"),
        (r1, "pivot_r1"),
        (r2, "pivot_r2"),
        (r3, "pivot_r3"),
        (s1, "pivot_s1"),
        (s2, "pivot_s2"),
        (s3, "pivot_s3"),
    ]:
        levels.append(SupportResistanceLevel(
            price=round(price, 2),
            strength=2 if label == "pivot" else 1,
            timeframe=timeframe,
            level_type=label,
        ))

    return levels


def _previous_day_levels(daily_candles: list[Candle]) -> list[SupportResistanceLevel]:
    """Extract previous day high, low, close as key levels."""
    if len(daily_candles) < 2:
        return []

    prev = daily_candles[-2]
    return [
        SupportResistanceLevel(
            price=prev.high, strength=3, timeframe=Timeframe.DAILY, level_type="pdh"
        ),
        SupportResistanceLevel(
            price=prev.low, strength=3, timeframe=Timeframe.DAILY, level_type="pdl"
        ),
        SupportResistanceLevel(
            price=prev.close, strength=2, timeframe=Timeframe.DAILY, level_type="pdc"
        ),
    ]


def _cluster_levels(levels: list[SupportResistanceLevel]) -> list[SupportResistanceLevel]:
    """
    Group nearby levels within CLUSTER_BAND_PCT and merge them.
    A clustered level with multiple confluences gets higher strength.
    """
    if not levels:
        return []

    sorted_levels = sorted(levels, key=lambda l: l.price)
    clusters: list[list[SupportResistanceLevel]] = []
    current_cluster: list[SupportResistanceLevel] = [sorted_levels[0]]

    for level in sorted_levels[1:]:
        cluster_avg = sum(l.price for l in current_cluster) / len(current_cluster)
        if abs(level.price - cluster_avg) / cluster_avg <= CLUSTER_BAND_PCT:
            current_cluster.append(level)
        else:
            clusters.append(current_cluster)
            current_cluster = [level]
    clusters.append(current_cluster)

    merged: list[SupportResistanceLevel] = []
    for cluster in clusters:
        avg_price = sum(l.price for l in cluster) / len(cluster)
        total_strength = sum(l.strength for l in cluster)
        best_tf = min(cluster, key=lambda l: _tf_priority(l.timeframe)).timeframe
        merged.append(SupportResistanceLevel(
            price=round(avg_price, 2),
            strength=total_strength,
            timeframe=best_tf,
            level_type=cluster[0].level_type,
        ))

    return merged


def _tf_priority(tf: Timeframe) -> int:
    """Lower number = higher timeframe = more important."""
    return {Timeframe.DAILY: 0, Timeframe.FIFTEEN_MIN: 1, Timeframe.FIVE_MIN: 2}.get(tf, 3)


def find_nearest_levels(
    price: float,
    levels: list[SupportResistanceLevel],
    count: int = 3,
) -> tuple[list[SupportResistanceLevel], list[SupportResistanceLevel]]:
    """
    Find the nearest support levels (below price) and resistance levels (above price).
    Returns (supports, resistances) each sorted by proximity.
    """
    supports = [l for l in levels if l.price < price]
    resistances = [l for l in levels if l.price > price]

    supports.sort(key=lambda l: price - l.price)
    resistances.sort(key=lambda l: l.price - price)

    return supports[:count], resistances[:count]


def is_near_level(
    price: float,
    level: SupportResistanceLevel,
    atr: float,
    threshold_atr_mult: float = 0.3,
) -> bool:
    """Check if price is within threshold of a S/R level (based on ATR)."""
    if atr <= 0:
        return False
    return abs(price - level.price) <= atr * threshold_atr_mult
