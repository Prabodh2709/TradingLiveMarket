from __future__ import annotations

import logging
from typing import Optional

import pyotp
from SmartApi.smartConnect import SmartConnect

from backend.config import settings

logger = logging.getLogger(__name__)


class SmartAPISession:
    """Manages Angel One SmartAPI authentication and session lifecycle."""

    def __init__(self) -> None:
        self._obj: Optional[SmartConnect] = None
        self._auth_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._feed_token: Optional[str] = None
        self._client_code: str = settings.angel_client_code
        self._is_logged_in: bool = False

    @property
    def is_logged_in(self) -> bool:
        return self._is_logged_in

    @property
    def auth_token(self) -> Optional[str]:
        return self._auth_token

    @property
    def feed_token(self) -> Optional[str]:
        return self._feed_token

    @property
    def api_key(self) -> str:
        return settings.angel_api_key

    @property
    def client_code(self) -> str:
        return self._client_code

    def login(self, client_code: str = "", pin: str = "", totp_value: str = "") -> dict:
        """
        Authenticate with Angel One. Uses provided params or falls back to .env values.
        If totp_value is empty, generates it from the TOTP secret in .env.
        """
        code = client_code or settings.angel_client_code
        password = pin or settings.angel_pin
        self._client_code = code

        if not totp_value and settings.angel_totp_secret:
            totp_value = pyotp.TOTP(settings.angel_totp_secret).now()

        self._obj = SmartConnect(api_key=settings.angel_api_key)

        try:
            data = self._obj.generateSession(code, password, totp_value)
        except Exception as e:
            logger.error("Login failed: %s", e)
            raise RuntimeError(f"Angel One login failed: {e}") from e

        if not data or data.get("status") is False:
            msg = data.get("message", "Unknown error") if data else "No response"
            raise RuntimeError(f"Angel One login failed: {msg}")

        tokens = data.get("data", {})
        self._auth_token = tokens.get("jwtToken")
        self._refresh_token = tokens.get("refreshToken")
        self._feed_token = self._obj.getfeedToken()
        self._is_logged_in = True

        logger.info("SmartAPI login successful for client %s", code)
        return {
            "status": "success",
            "client_code": code,
        }

    def logout(self) -> None:
        if self._obj and self._is_logged_in:
            try:
                self._obj.terminateSession(self._client_code)
            except Exception:
                pass
        self._is_logged_in = False
        self._auth_token = None
        self._feed_token = None
        self._refresh_token = None

    def get_ltp(self, exchange: str, symbol: str, token: str) -> Optional[float]:
        if not self._obj or not self._is_logged_in:
            return None
        try:
            resp = self._obj.ltpData(exchange, symbol, token)
            if resp and resp.get("data"):
                return resp["data"].get("ltp")
        except Exception as e:
            logger.error("LTP fetch failed for %s: %s", symbol, e)
        return None

    def get_option_greeks(self, name: str, expiry_date: str) -> Optional[list[dict]]:
        """Fetch option Greeks from Angel One's Option Greeks API.

        Args:
            name: Underlying name (e.g. "NIFTY", "BANKNIFTY").
            expiry_date: Expiry in Angel format (e.g. "29MAY2026").

        Returns:
            List of dicts with delta, gamma, theta, vega, iv per strike,
            or None on failure.
        """
        if not self._obj or not self._is_logged_in:
            return None
        try:
            payload = {"name": name, "expirydate": expiry_date}
            resp = self._obj._postRequest(
                "api.market.optiongreeks", payload
            )
            if resp and resp.get("status") is not False and resp.get("data"):
                return resp["data"]
        except Exception as e:
            logger.warning("Option Greeks API failed for %s %s: %s", name, expiry_date, e)
        return None


session = SmartAPISession()
