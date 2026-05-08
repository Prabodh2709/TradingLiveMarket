from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.instrument_service import fetch_instruments, get_option_chain, get_tokens_for_subscription, get_index_token
from backend.websocket_manager import market_data

router = APIRouter(prefix="/api/instruments", tags=["instruments"])


@router.post("/refresh")
async def refresh_instruments():
    instruments = await fetch_instruments(force=True)
    return {"status": "success", "count": len(instruments)}


@router.get("/option-chain")
async def option_chain(
    name: str = Query("NIFTY", description="NIFTY or BANKNIFTY"),
    expiry: Optional[str] = Query(None, description="Expiry date string"),
):
    chain = get_option_chain(name, expiry)
    if not chain:
        raise HTTPException(
            status_code=404,
            detail=f"No option chain data for {name}. Try refreshing instruments first.",
        )

    # #region agent log
    import json as _dbg_json, time as _dbg_time
    _dbg_samples = []
    _dbg_prices_snapshot = list(market_data.latest_prices.keys())[:10]
    # #endregion

    for strike_key, strike_data in chain.get("strikes", {}).items():
        for opt_type in ("CE", "PE"):
            if opt_type in strike_data:
                token = strike_data[opt_type].get("token", "")
                ltp = market_data.get_ltp(token)
                strike_data[opt_type]["ltp"] = ltp
                # #region agent log
                if len(_dbg_samples) < 10:
                    _dbg_samples.append({"strike": strike_key, "opt_type": opt_type, "token": token, "token_type": str(type(token)), "ltp": ltp, "symbol": strike_data[opt_type].get("symbol", "")})
                # #endregion

    # #region agent log
    try:
        with open("/Users/prabodh.shewalkar/Desktop/Personal/TradingLiveMarket/.cursor/debug-d38668.log", "a") as _f:
            _f.write(_dbg_json.dumps({"sessionId":"d38668","hypothesisId":"H1","location":"instruments.py:option_chain","message":"chain_ltp_merge","data":{"name": name, "expiry": expiry, "sample_strikes": _dbg_samples, "latest_prices_keys_sample": _dbg_prices_snapshot, "total_latest_prices": len(market_data.latest_prices)},"timestamp":int(_dbg_time.time()*1000)}) + "\n")
    except Exception:
        pass
    # #endregion

    index_token = get_index_token(name)
    chain["index_token"] = index_token
    chain["spot_price"] = market_data.get_ltp(index_token)

    return chain


@router.post("/subscribe")
async def subscribe_tokens(
    name: str = Query("NIFTY"),
    expiry: str = Query(...),
):
    """Subscribe to WebSocket feed for a specific expiry's tokens."""
    tokens = get_tokens_for_subscription(name, expiry)
    if not tokens:
        raise HTTPException(status_code=404, detail="No tokens found for subscription")

    index_token = get_index_token(name)
    token_list = [
        {"exchangeType": 2, "tokens": tokens},
        {"exchangeType": 1, "tokens": [index_token]},
    ]

    try:
        if not market_data._running:
            market_data.start(token_list)
        else:
            market_data.update_subscription(token_list)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "success", "tokens_subscribed": len(tokens)}
