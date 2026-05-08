from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

INSTRUMENT_MASTER_URL = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
)

SUPPORTED_NAMES = {"NIFTY", "BANKNIFTY"}

INDEX_TOKENS: dict[str, str] = {
    "NIFTY": "99926000",
    "BANKNIFTY": "99926009",
}

_instruments_cache: dict = {}
_option_chain_cache: dict = {}
_last_fetch: Optional[datetime] = None


def _cache_path() -> Path:
    return settings.data_path / "instruments_cache.json"


async def fetch_instruments(force: bool = False) -> list[dict]:
    """Download instrument master and filter for NIFTY/BANKNIFTY NFO options."""
    global _instruments_cache, _option_chain_cache, _last_fetch

    if not force and _instruments_cache:
        return _instruments_cache.get("instruments", [])

    if not force and _cache_path().exists():
        try:
            with open(_cache_path(), "r") as f:
                cached = json.load(f)
            if cached.get("date") == datetime.now().strftime("%Y-%m-%d"):
                _instruments_cache = cached
                _build_option_chain(cached["instruments"])
                _last_fetch = datetime.now()
                logger.info("Loaded %d instruments from cache", len(cached["instruments"]))
                return cached["instruments"]
        except Exception:
            pass

    logger.info("Downloading instrument master from Angel One...")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(INSTRUMENT_MASTER_URL)
        resp.raise_for_status()
        all_instruments = resp.json()

    nfo_options = [
        inst for inst in all_instruments
        if inst.get("exch_seg") == "NFO"
        and inst.get("name") in SUPPORTED_NAMES
        and inst.get("instrumenttype") in ("OPTIDX",)
    ]

    for inst in nfo_options:
        try:
            inst["strike_price"] = float(inst.get("strike", 0)) / 100
        except (ValueError, TypeError):
            inst["strike_price"] = 0.0

        symbol = inst.get("symbol", "")
        if symbol.endswith("CE"):
            inst["option_type"] = "CE"
        elif symbol.endswith("PE"):
            inst["option_type"] = "PE"
        else:
            inst["option_type"] = "UNKNOWN"

    nfo_options = [i for i in nfo_options if i["option_type"] != "UNKNOWN"]

    cache_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "instruments": nfo_options,
    }
    _instruments_cache = cache_data

    try:
        with open(_cache_path(), "w") as f:
            json.dump(cache_data, f)
        logger.info("Cached %d NFO option instruments to disk", len(nfo_options))
    except Exception as e:
        logger.warning("Failed to write instrument cache: %s", e)

    _build_option_chain(nfo_options)
    _last_fetch = datetime.now()
    return nfo_options


def _build_option_chain(instruments: list[dict]) -> None:
    global _option_chain_cache
    chain: dict = {}

    for inst in instruments:
        name = inst["name"]
        expiry = inst.get("expiry", "")
        strike = inst["strike_price"]
        opt_type = inst["option_type"]

        if name not in chain:
            chain[name] = {}
        if expiry not in chain[name]:
            chain[name][expiry] = {}
        if strike not in chain[name][expiry]:
            chain[name][expiry][strike] = {}

        chain[name][expiry][strike][opt_type] = {
            "token": inst.get("token", ""),
            "symbol": inst.get("symbol", ""),
            "lotsize": int(inst.get("lotsize", 1)),
            "tick_size": inst.get("tick_size", "0.05"),
        }

    _option_chain_cache = chain


def get_option_chain(name: str, expiry: Optional[str] = None) -> dict:
    """
    Return the option chain for NIFTY or BANKNIFTY.
    If expiry is None, returns the nearest available expiry.
    """
    name = name.upper()
    if name not in _option_chain_cache:
        return {}

    expiries = _option_chain_cache[name]
    if not expiries:
        return {}

    if expiry and expiry in expiries:
        strikes = expiries[expiry]
    else:
        sorted_expiries = sorted(expiries.keys(), key=_parse_expiry)
        expiry = sorted_expiries[0]
        strikes = expiries[expiry]

    result = {
        "name": name,
        "expiry": expiry,
        "available_expiries": sorted(expiries.keys(), key=_parse_expiry),
        "strikes": {},
    }

    for strike in sorted(strikes.keys()):
        result["strikes"][str(strike)] = strikes[strike]

    return result


def get_instrument_by_token(token: str) -> Optional[dict]:
    instruments = _instruments_cache.get("instruments", [])
    for inst in instruments:
        if inst.get("token") == token:
            return inst
    return None


def get_tokens_for_subscription(name: str, expiry: str, strikes: Optional[list[float]] = None) -> list[str]:
    """Get list of tokens for WebSocket subscription."""
    if name not in _option_chain_cache or expiry not in _option_chain_cache[name]:
        return []

    chain = _option_chain_cache[name][expiry]
    tokens = []
    for strike, opts in chain.items():
        if strikes and strike not in strikes:
            continue
        for opt_type in ("CE", "PE"):
            if opt_type in opts and opts[opt_type].get("token"):
                tokens.append(opts[opt_type]["token"])
    return tokens


def get_index_token(name: str) -> str:
    """Return the Angel One token for the underlying index (NSE Cash segment)."""
    return INDEX_TOKENS[name.upper()]


def _parse_expiry(exp_str: str) -> datetime:
    for fmt in ("%d%b%Y", "%d%b%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(exp_str.upper(), fmt)
        except ValueError:
            continue
    return datetime.max
