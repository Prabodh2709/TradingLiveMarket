from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from backend.smartapi_client import session
from backend.strategy.models import Candle, Timeframe

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

TIMEFRAME_LOOKBACK = {
    Timeframe.DAILY: timedelta(days=60),
    Timeframe.FIFTEEN_MIN: timedelta(days=5),
    Timeframe.FIVE_MIN: timedelta(days=2),
}

ANGEL_INTERVAL_MAP = {
    Timeframe.DAILY: "ONE_DAY",
    Timeframe.FIFTEEN_MIN: "FIFTEEN_MINUTE",
    Timeframe.FIVE_MIN: "FIVE_MINUTE",
}

CANDLE_CACHE_TTL: dict[Timeframe, float] = {
    Timeframe.DAILY: 3600.0,
    Timeframe.FIFTEEN_MIN: 300.0,
    Timeframe.FIVE_MIN: 120.0,
}

_candle_cache: dict[tuple[str, Timeframe], tuple[float, list[Candle]]] = {}

EXCHANGE_NSE = "NSE"
EXCHANGE_NFO = "NFO"


def fetch_candles(
    token: str,
    exchange: str,
    timeframe: Timeframe,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> list[Candle]:
    """
    Fetch historical candle data from Angel One SmartAPI with TTL caching.
    Daily candles are cached for 1 hour, 15-min for 5 minutes, 5-min for 2 minutes.
    """
    cache_key = (token, timeframe)
    ttl = CANDLE_CACHE_TTL.get(timeframe, 60.0)
    cached = _candle_cache.get(cache_key)
    if cached:
        cached_at, cached_candles = cached
        if time.monotonic() - cached_at < ttl:
            logger.debug("Cache hit for %s %s (%d candles)", token, timeframe.value, len(cached_candles))
            return cached_candles

    if not session.is_logged_in or not session._obj:
        logger.error("Cannot fetch candles: not logged in to Angel One")
        return []

    now_ist = datetime.now(IST)
    if to_date is None:
        to_date = now_ist
    if from_date is None:
        from_date = now_ist - TIMEFRAME_LOOKBACK[timeframe]

    from_str = from_date.strftime("%Y-%m-%d %H:%M")
    to_str = to_date.strftime("%Y-%m-%d %H:%M")

    params = {
        "exchange": exchange,
        "symboltoken": token,
        "interval": ANGEL_INTERVAL_MAP[timeframe],
        "fromdate": from_str,
        "todate": to_str,
    }

    try:
        response = session._obj.getCandleData(params)
    except Exception as e:
        logger.error("getCandleData failed for token %s (%s): %s", token, timeframe.value, e)
        return []

    if not response or response.get("status") is False:
        msg = response.get("message", "Unknown") if response else "No response"
        logger.warning("getCandleData returned error for %s: %s", token, msg)
        return []

    raw_candles = response.get("data", [])
    if not raw_candles:
        logger.info("No candle data returned for token %s (%s)", token, timeframe.value)
        return []

    candles: list[Candle] = []
    for row in raw_candles:
        try:
            candles.append(Candle(
                timestamp=datetime.fromisoformat(row[0]),
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=int(row[5]),
            ))
        except (IndexError, ValueError, TypeError) as e:
            logger.debug("Skipping malformed candle row: %s (%s)", row, e)
            continue

    _candle_cache[cache_key] = (time.monotonic(), candles)
    logger.info(
        "Fetched %d %s candles for token %s (%s to %s), cached for %ds",
        len(candles), timeframe.value, token, from_str, to_str, int(ttl),
    )
    return candles


def fetch_index_candles(
    index_name: str,
    timeframe: Timeframe,
) -> list[Candle]:
    """Convenience wrapper to fetch candles for NIFTY or BANKNIFTY index."""
    from backend.instrument_service import get_index_token

    token = get_index_token(index_name)
    return fetch_candles(token, EXCHANGE_NSE, timeframe)


def fetch_multi_timeframe(index_name: str) -> dict[Timeframe, list[Candle]]:
    """Fetch daily, 15-min, and 5-min candles for an index (with TTL caching)."""
    result: dict[Timeframe, list[Candle]] = {}
    for tf in (Timeframe.DAILY, Timeframe.FIFTEEN_MIN, Timeframe.FIVE_MIN):
        result[tf] = fetch_index_candles(index_name, tf)
        time.sleep(0.35)  # rate-limit guard for cache misses
    return result


def resolve_ltp(token: str, exchange: str = "NSE", symbol: str = "") -> float | None:
    """Resolve LTP via WebSocket first, then REST API fallback."""
    from backend.websocket_manager import market_data

    ltp = market_data.get_ltp(token)
    if ltp:
        return ltp

    if symbol and session.is_logged_in:
        return session.get_ltp(exchange, symbol, token)

    return None


def get_spot_price(index_name: str) -> float | None:
    """Get current spot price from WebSocket or fallback to API LTP."""
    from backend.instrument_service import get_index_token

    token = get_index_token(index_name)
    return resolve_ltp(token, EXCHANGE_NSE, index_name)
