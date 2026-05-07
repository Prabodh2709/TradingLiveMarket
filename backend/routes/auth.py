from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.smartapi_client import session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    client_code: Optional[str] = ""
    pin: Optional[str] = ""
    totp: Optional[str] = ""


@router.post("/login")
async def login(req: LoginRequest):
    try:
        result = session.login(
            client_code=req.client_code or "",
            pin=req.pin or "",
            totp_value=req.totp or "",
        )
        return {"status": "success", "data": result}
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/status")
async def auth_status():
    return {
        "logged_in": session.is_logged_in,
        "client_code": session.client_code if session.is_logged_in else None,
    }


@router.post("/logout")
async def logout():
    session.logout()
    return {"status": "success"}
