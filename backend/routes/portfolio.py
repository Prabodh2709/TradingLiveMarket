from fastapi import APIRouter, HTTPException, Query

from backend.trading_engine import get_portfolio_summary
from backend.db.store import load_trades, load_positions

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
async def portfolio():
    return get_portfolio_summary()


@router.get("/positions")
async def positions():
    pos = load_positions()
    return [p.model_dump() for p in pos]


@router.get("/trades")
async def trades(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    all_trades = load_trades()
    all_trades.reverse()
    page = all_trades[offset : offset + limit]
    return {
        "total": len(all_trades),
        "trades": [t.model_dump() for t in page],
    }
