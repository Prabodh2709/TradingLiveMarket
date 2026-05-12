from __future__ import annotations

import logging
from typing import Optional

from backend.instrument_service import get_option_chain
from backend.strategy.models import MarketBias, OrderFlowSignal
from backend.websocket_manager import market_data

logger = logging.getLogger(__name__)


def analyze_order_flow(
    instrument: str,
    expiry: str,
    spot_price: float,
    chain: dict | None = None,
) -> OrderFlowSignal:
    """
    Analyze order flow using OI and volume data from the live WebSocket feed.
    Computes PCR, max pain, OI-based S/R, and detects volume anomalies.
    """
    if chain is None:
        chain = get_option_chain(instrument, expiry)
    if not chain or not chain.get("strikes"):
        logger.warning("No option chain data for %s expiry %s", instrument, expiry)
        return OrderFlowSignal()

    strikes_data = chain["strikes"]
    ce_oi_map: dict[float, int] = {}
    pe_oi_map: dict[float, int] = {}
    ce_volume_map: dict[float, int] = {}
    pe_volume_map: dict[float, int] = {}
    total_ce_oi = 0
    total_pe_oi = 0

    for strike_str, opts in strikes_data.items():
        strike = float(strike_str)
        ce_data = opts.get("CE", {})
        pe_data = opts.get("PE", {})

        ce_token = ce_data.get("token", "")
        pe_token = pe_data.get("token", "")

        ce_tick = market_data.latest_prices.get(ce_token, {})
        pe_tick = market_data.latest_prices.get(pe_token, {})

        ce_oi = ce_tick.get("oi", 0)
        pe_oi = pe_tick.get("oi", 0)
        ce_vol = ce_tick.get("volume", 0)
        pe_vol = pe_tick.get("volume", 0)

        ce_oi_map[strike] = ce_oi
        pe_oi_map[strike] = pe_oi
        ce_volume_map[strike] = ce_vol
        pe_volume_map[strike] = pe_vol
        total_ce_oi += ce_oi
        total_pe_oi += pe_oi

    pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 1.0
    max_pain = _compute_max_pain(ce_oi_map, pe_oi_map)
    ce_resistance = _highest_oi_strike(ce_oi_map, above=spot_price)
    pe_support = _highest_oi_strike(pe_oi_map, below=spot_price)
    bias = _determine_oi_bias(pcr, spot_price, max_pain)
    volume_spike = _detect_volume_spike(ce_volume_map, pe_volume_map)

    confidence = _compute_confidence(pcr, max_pain, spot_price, ce_resistance, pe_support, bias)

    signal = OrderFlowSignal(
        pcr=round(pcr, 3),
        max_pain_strike=max_pain,
        ce_oi_resistance=ce_resistance,
        pe_oi_support=pe_support,
        oi_buildup_bias=bias,
        volume_spike_detected=volume_spike,
        confidence=confidence,
    )

    logger.info(
        "Order flow for %s: PCR=%.2f MaxPain=%.0f CE_Res=%.0f PE_Sup=%.0f Bias=%s Conf=%.0f",
        instrument, pcr, max_pain, ce_resistance, pe_support, bias.value, confidence,
    )
    return signal


def _compute_max_pain(
    ce_oi: dict[float, int],
    pe_oi: dict[float, int],
) -> float:
    """
    Max pain is the strike where total option buyer loss is maximum
    (i.e., option writers' profit is maximum).
    """
    all_strikes = sorted(set(ce_oi.keys()) | set(pe_oi.keys()))
    if not all_strikes:
        return 0.0

    min_pain = float("inf")
    max_pain_strike = all_strikes[0]

    for settle_strike in all_strikes:
        total_pain = 0.0
        for strike in all_strikes:
            ce_loss = max(0, settle_strike - strike) * ce_oi.get(strike, 0)
            pe_loss = max(0, strike - settle_strike) * pe_oi.get(strike, 0)
            total_pain += ce_loss + pe_loss

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = settle_strike

    return max_pain_strike


def _highest_oi_strike(oi_map: dict[float, int], above: float = 0, below: float = float("inf")) -> float:
    """Find strike with highest OI within a price range."""
    filtered = {k: v for k, v in oi_map.items() if above < k < below}
    if not filtered:
        filtered = {k: v for k, v in oi_map.items() if k > above} if above else oi_map

    if not filtered:
        return 0.0

    return max(filtered, key=filtered.get)  # type: ignore[arg-type]


def _determine_oi_bias(pcr: float, spot: float, max_pain: float) -> MarketBias:
    """Determine directional bias from PCR and max pain relative to spot."""
    if pcr > 1.3:
        bias = MarketBias.BULLISH
    elif pcr < 0.7:
        bias = MarketBias.BEARISH
    elif spot < max_pain * 0.995:
        bias = MarketBias.BULLISH  # likely to revert up toward max pain
    elif spot > max_pain * 1.005:
        bias = MarketBias.BEARISH  # likely to revert down toward max pain
    else:
        bias = MarketBias.NEUTRAL

    return bias


def _detect_volume_spike(
    ce_volume: dict[float, int],
    pe_volume: dict[float, int],
) -> bool:
    """Detect if any strike has unusual volume (>3x average)."""
    all_volumes = list(ce_volume.values()) + list(pe_volume.values())
    all_volumes = [v for v in all_volumes if v > 0]

    if len(all_volumes) < 5:
        return False

    avg_vol = sum(all_volumes) / len(all_volumes)
    if avg_vol == 0:
        return False

    return any(v > avg_vol * 3 for v in all_volumes)


def _compute_confidence(
    pcr: float,
    max_pain: float,
    spot: float,
    ce_resistance: float,
    pe_support: float,
    bias: MarketBias,
) -> float:
    """Compute order flow confidence (0-100)."""
    score = 30.0

    if 0.8 <= pcr <= 1.5:
        score += 15.0  # healthy range for selling
    elif pcr > 1.5 or pcr < 0.5:
        score += 5.0  # extreme, directional risk

    if max_pain > 0 and abs(spot - max_pain) / max_pain < 0.01:
        score += 20.0  # spot near max pain = ideal for sellers
    elif max_pain > 0 and abs(spot - max_pain) / max_pain < 0.02:
        score += 10.0

    if ce_resistance > 0 and pe_support > 0:
        range_defined = ce_resistance - pe_support
        if range_defined > 0 and pe_support < spot < ce_resistance:
            score += 15.0  # spot within defined OI range

    if bias != MarketBias.VOLATILE:
        score += 5.0

    return min(score, 100.0)
