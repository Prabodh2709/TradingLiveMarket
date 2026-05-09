from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.trading_engine import buy_option, sell_option, sell_option_open

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


class SellOpenRequest(BaseModel):
    symbol: str
    token: str
    name: str
    strike: float
    option_type: str
    expiry: str
    qty: int
    price: float


class SquareOffRequest(BaseModel):
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


@router.post("/sell-open")
async def execute_sell_open(req: SellOpenRequest):
    try:
        result = sell_option_open(
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
async def execute_sell(req: SquareOffRequest):
    try:
        result = sell_option(
            token=req.token,
            qty=req.qty,
            price=req.price,
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
