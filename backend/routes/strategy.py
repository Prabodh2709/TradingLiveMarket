from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.strategy.config import (
    StrategySettings,
    load_strategy_settings,
    save_strategy_settings,
    strategy_settings,
)
from backend.strategy.orchestrator import get_state, start_strategy, stop_strategy

router = APIRouter(prefix="/api/strategy", tags=["strategy"])


class StartRequest(BaseModel):
    pass


class StopRequest(BaseModel):
    close_positions: bool = False


class ConfigUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    execution_mode: Optional[str] = None
    instruments: Optional[list[str]] = None
    min_confidence_score: Optional[int] = None
    scan_interval_seconds: Optional[int] = None
    max_positions: Optional[int] = None
    max_risk_per_trade_pct: Optional[float] = None
    max_total_risk_pct: Optional[float] = None
    max_daily_loss_pct: Optional[float] = None
    min_risk_reward_ratio: Optional[float] = None
    target_pct: Optional[float] = None
    stop_loss_multiplier: Optional[float] = None
    trailing_sl_trigger_pct: Optional[float] = None
    trailing_sl_pct: Optional[float] = None
    limit_order_timeout_s: Optional[int] = None
    no_trade_before: Optional[str] = None
    no_trade_after: Optional[str] = None
    min_dte: Optional[int] = None
    preferred_dte_min: Optional[int] = None
    preferred_dte_max: Optional[int] = None
    otm_offset_points_nifty: Optional[float] = None
    otm_offset_points_banknifty: Optional[float] = None
    min_premium: Optional[float] = None
    max_premium: Optional[float] = None
    vix_pause_threshold: Optional[float] = None
    vix_spike_pct: Optional[float] = None


@router.post("/start")
async def api_start():
    try:
        result = start_strategy()
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def api_stop(req: StopRequest):
    try:
        result = stop_strategy(close_positions=req.close_positions)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def api_status():
    state = get_state()
    open_trades = [t for t in state.active_trades if t.status == "OPEN"]
    return {
        "status": "success",
        "data": {
            "running": state.running,
            "started_at": state.started_at,
            "stopped_at": state.stopped_at,
            "total_trades_today": state.total_trades_today,
            "realized_pnl_today": state.realized_pnl_today,
            "open_positions": len(open_trades),
            "circuit_breaker_active": state.circuit_breaker_active,
            "last_scan_time": state.last_scan_time,
            "execution_mode": strategy_settings.execution_mode,
        },
    }


@router.get("/config")
async def api_get_config():
    settings = load_strategy_settings()
    return {"status": "success", "data": settings.model_dump()}


@router.put("/config")
async def api_update_config(req: ConfigUpdateRequest):
    import backend.strategy.config as cfg

    current = load_strategy_settings()
    update_data = req.model_dump(exclude_none=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    merged = current.model_dump()
    merged.update(update_data)

    try:
        new_settings = StrategySettings(**merged)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid config: {e}")

    save_strategy_settings(new_settings)
    cfg.strategy_settings = new_settings

    return {"status": "success", "data": new_settings.model_dump()}


@router.get("/signals")
async def api_signals():
    state = get_state()
    signals = [s.model_dump() for s in state.recent_signals[:20]]
    return {"status": "success", "data": signals}


@router.get("/log")
async def api_log(limit: int = 50):
    state = get_state()
    log_entries = [e.model_dump() for e in state.decision_log[:limit]]
    return {"status": "success", "data": log_entries}


@router.get("/positions")
async def api_active_positions():
    state = get_state()
    open_trades = [t.model_dump() for t in state.active_trades if t.status == "OPEN"]
    return {"status": "success", "data": open_trades}


@router.get("/analysis")
async def api_analysis():
    state = get_state()
    snapshots = {k: v.model_dump() for k, v in state.analysis_snapshots.items()}
    return {"status": "success", "data": snapshots}


@router.post("/kill")
async def api_kill_switch():
    """Emergency: stop strategy and close all positions immediately."""
    result = stop_strategy(close_positions=True)
    return {"status": "success", "data": result}
