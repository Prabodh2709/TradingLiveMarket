from fastapi import APIRouter, HTTPException, Query

from backend.db.store import reset_system, list_history_versions, load_history_version

router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/reset")
async def reset():
    meta = reset_system()
    return {
        "status": "success",
        "message": "System reset complete. Previous session archived.",
        "data": meta.model_dump(),
    }


@router.get("/history")
async def history_versions():
    return list_history_versions()


@router.get("/history/{folder}")
async def history_detail(folder: str):
    try:
        return load_history_version(folder)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
