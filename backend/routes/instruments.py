from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.instrument_service import fetch_instruments, get_option_chain, get_tokens_for_subscription
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

    for strike_key, strike_data in chain.get("strikes", {}).items():
        for opt_type in ("CE", "PE"):
            if opt_type in strike_data:
                token = strike_data[opt_type].get("token", "")
                ltp = market_data.get_ltp(token)
                strike_data[opt_type]["ltp"] = ltp

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

    token_list = [{"exchangeType": 2, "tokens": tokens}]

    try:
        if not market_data._running:
            market_data.start(token_list)
        else:
            market_data.update_subscription(token_list)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "success", "tokens_subscribed": len(tokens)}
