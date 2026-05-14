from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.smartapi_client import session
from backend.strategy.config import strategy_settings
from backend.strategy.models import GreeksData

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

_greeks_cache: dict[str, tuple[float, dict[float, GreeksData]]] = {}
GREEKS_CACHE_TTL = 120.0  # seconds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_greeks_for_strike(
    instrument: str,
    expiry: str,
    strike: float,
    option_type: str,
    spot_price: float,
    option_ltp: float,
) -> GreeksData:
    """Return Greeks for a single strike, trying API first then BS fallback."""
    greeks_map = _fetch_greeks_map(instrument, expiry)

    if greeks_map:
        key = (strike, option_type)
        cached = greeks_map.get(key)  # type: ignore[arg-type]
        if cached:
            return cached

    return _bs_greeks_from_ltp(
        spot_price, strike, expiry, option_ltp, option_type,
    )


def is_decay_favorable(greeks: GreeksData, option_type: str) -> tuple[bool, str]:
    """Gate that checks whether selling this option is favorable from a decay
    perspective.  Returns ``(pass, reason)``."""
    reasons: list[str] = []

    if abs(greeks.theta) < strategy_settings.min_theta_for_sell:
        reasons.append(
            f"Theta too low ({greeks.theta:.3f}), "
            f"min {strategy_settings.min_theta_for_sell}"
        )

    if abs(greeks.delta) > strategy_settings.max_delta_for_sell:
        reasons.append(
            f"Delta too high ({greeks.delta:.3f}), "
            f"max {strategy_settings.max_delta_for_sell}"
        )

    if greeks.gamma > strategy_settings.max_gamma_for_sell:
        reasons.append(
            f"Gamma too high ({greeks.gamma:.4f}), "
            f"max {strategy_settings.max_gamma_for_sell}"
        )

    iv_pct = greeks.iv * 100 if greeks.iv <= 1.0 else greeks.iv
    if iv_pct > strategy_settings.max_iv_for_sell:
        reasons.append(
            f"IV too high ({iv_pct:.1f}%), "
            f"max {strategy_settings.max_iv_for_sell}%"
        )

    if reasons:
        return False, "; ".join(reasons)
    return True, "Decay favorable"


# ---------------------------------------------------------------------------
# Angel One API fetch
# ---------------------------------------------------------------------------

def _fetch_greeks_map(
    instrument: str,
    expiry: str,
) -> Optional[dict[tuple[float, str], GreeksData]]:
    """Fetch full Greeks chain from Angel One API with TTL caching."""
    cache_key = f"{instrument}:{expiry}"
    cached = _greeks_cache.get(cache_key)
    if cached:
        ts, data = cached
        if time.monotonic() - ts < GREEKS_CACHE_TTL:
            return data  # type: ignore[return-value]

    raw = session.get_option_greeks(instrument, expiry)
    if not raw:
        return None

    result: dict[tuple[float, str], GreeksData] = {}
    for row in raw:
        try:
            strike_val = float(row.get("strikePrice", 0))
            opt_type = row.get("optionType", "").upper()
            if opt_type not in ("CE", "PE") or strike_val <= 0:
                continue
            result[(strike_val, opt_type)] = GreeksData(
                delta=float(row.get("delta", 0)),
                gamma=float(row.get("gamma", 0)),
                theta=float(row.get("theta", 0)),
                vega=float(row.get("vega", 0)),
                iv=float(row.get("impliedVolatility", 0)),
            )
        except (ValueError, TypeError):
            continue

    if result:
        _greeks_cache[cache_key] = (time.monotonic(), result)  # type: ignore[assignment]
        logger.info(
            "Cached %d Greeks entries for %s expiry %s",
            len(result), instrument, expiry,
        )
        return result

    return None


# ---------------------------------------------------------------------------
# Black-Scholes fallback
# ---------------------------------------------------------------------------

def _bs_greeks_from_ltp(
    spot: float,
    strike: float,
    expiry: str,
    option_price: float,
    option_type: str,
) -> GreeksData:
    """Compute Greeks via Black-Scholes using IV implied from market price."""
    tte = _time_to_expiry_years(expiry)
    if tte <= 0 or option_price <= 0 or spot <= 0:
        return GreeksData()

    r = strategy_settings.risk_free_rate / 100.0
    iv = _implied_volatility(option_price, spot, strike, tte, r, option_type)

    if iv <= 0:
        return GreeksData(iv=0.0)

    return _compute_bs_greeks(spot, strike, tte, r, iv, option_type)


def _compute_bs_greeks(
    s: float,
    k: float,
    t: float,
    r: float,
    sigma: float,
    option_type: str,
) -> GreeksData:
    """Standard Black-Scholes Greeks for European options."""
    sqrt_t = math.sqrt(t)
    d1 = (math.log(s / k) + (r + 0.5 * sigma ** 2) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    nd1 = _norm_cdf(d1)
    nd2 = _norm_cdf(d2)
    nprime_d1 = _norm_pdf(d1)

    if option_type == "CE":
        delta = nd1
        theta = (
            -(s * nprime_d1 * sigma) / (2 * sqrt_t)
            - r * k * math.exp(-r * t) * nd2
        )
    else:
        delta = nd1 - 1.0
        theta = (
            -(s * nprime_d1 * sigma) / (2 * sqrt_t)
            + r * k * math.exp(-r * t) * _norm_cdf(-d2)
        )

    gamma = nprime_d1 / (s * sigma * sqrt_t)
    vega = s * nprime_d1 * sqrt_t / 100.0  # per 1% IV move
    theta_per_day = theta / 365.0

    return GreeksData(
        delta=round(delta, 4),
        gamma=round(gamma, 6),
        theta=round(theta_per_day, 4),
        vega=round(vega, 4),
        iv=round(sigma * 100, 2),
    )


def _implied_volatility(
    market_price: float,
    s: float,
    k: float,
    t: float,
    r: float,
    option_type: str,
    max_iter: int = 50,
    tol: float = 1e-5,
) -> float:
    """Newton-Raphson IV solver."""
    sigma = 0.25  # initial guess

    for _ in range(max_iter):
        price = _bs_price(s, k, t, r, sigma, option_type)
        vega = _bs_vega(s, k, t, r, sigma)

        if vega < 1e-10:
            break

        diff = price - market_price
        if abs(diff) < tol:
            return sigma

        sigma -= diff / vega
        sigma = max(0.01, min(sigma, 5.0))

    return max(sigma, 0.0)


def _bs_price(
    s: float, k: float, t: float, r: float, sigma: float, option_type: str,
) -> float:
    """Black-Scholes option price."""
    sqrt_t = math.sqrt(t)
    d1 = (math.log(s / k) + (r + 0.5 * sigma ** 2) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    if option_type == "CE":
        return s * _norm_cdf(d1) - k * math.exp(-r * t) * _norm_cdf(d2)
    else:
        return k * math.exp(-r * t) * _norm_cdf(-d2) - s * _norm_cdf(-d1)


def _bs_vega(s: float, k: float, t: float, r: float, sigma: float) -> float:
    """BS vega (sensitivity of price to sigma)."""
    sqrt_t = math.sqrt(t)
    d1 = (math.log(s / k) + (r + 0.5 * sigma ** 2) * t) / (sigma * sqrt_t)
    return s * _norm_pdf(d1) * sqrt_t


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _time_to_expiry_years(expiry_str: str) -> float:
    """Convert expiry date string to fractional years remaining."""
    now = datetime.now(IST)
    for fmt in ("%d%b%Y", "%d%b%y", "%Y-%m-%d"):
        try:
            exp = datetime.strptime(expiry_str.upper(), fmt).replace(tzinfo=IST)
            # Assume expiry at 15:30 IST
            exp = exp.replace(hour=15, minute=30)
            diff = (exp - now).total_seconds()
            return max(diff / (365.25 * 86400), 0.0)
        except ValueError:
            continue
    return 0.0


def _norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Probability density function for standard normal."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)
