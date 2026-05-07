from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.trading_engine import buy_option, sell_option

router = APIRouter(prefix="/api/trade", tags=["trading"])


class BuyRequest(BaseModel):
    symbol: str
    token: str
    name: str  # NIFTY or BANKNIFTY
    strike: float
    option_type: str  # CE or PE
    expiry: str
    qty: int  # number of lots
    price: float


class SellRequest(BaseModel):
    token: str
    qty: int
    price: float


@router.post("/buy")
async def execute_buy(req: BuyRequest):
    try:
        result = buy_option(
            symbol=req.symbol,
            token=req.token,
            name=req.name,
            strike=req.strike,
            option_type=req.option_type,
            expiry=req.expiry,
            qty=req.qty,
            price=req.price,
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sell")
async def execute_sell(req: SellRequest):
    try:
        result = sell_option(
            token=req.token,
            qty=req.qty,
            price=req.price,
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
