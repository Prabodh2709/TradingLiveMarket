from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

from fastapi import WebSocket
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

from backend.smartapi_client import session as api_session

logger = logging.getLogger(__name__)


class MarketDataManager:
    """
    Bridges Angel One SmartWebSocketV2 feed to frontend WebSocket clients.
    Runs the SmartAPI WS in a background thread and broadcasts parsed
    market data to all connected FastAPI WebSocket clients.
    """

    NSE_FO = 2

    def __init__(self) -> None:
        self._sws: Optional[SmartWebSocketV2] = None
        self._thread: Optional[threading.Thread] = None
        self._clients: list[WebSocket] = []
        self._latest_prices: dict[str, dict] = {}
        self._subscribed_tokens: list[dict] = []
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def latest_prices(self) -> dict[str, dict]:
        return self._latest_prices

    def get_ltp(self, token: str) -> Optional[float]:
        data = self._latest_prices.get(token)
        if data:
            return data.get("ltp")
        return None

    async def connect_client(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)
        if self._latest_prices:
            try:
                await ws.send_json({
                    "type": "snapshot",
                    "data": self._latest_prices,
                })
            except Exception:
                pass

    def disconnect_client(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)

    def start(self, token_list: list[dict]) -> None:
        if not api_session.is_logged_in:
            raise RuntimeError("Not logged in to Angel One")

        self._subscribed_tokens = token_list
        self._loop = asyncio.get_event_loop()

        self._sws = SmartWebSocketV2(
            auth_token=api_session.auth_token,
            api_key=api_session.api_key,
            client_code=api_session.client_code,
            feed_token=api_session.feed_token,
            max_retry_attempt=5,
        )

        self._sws.on_open = self._on_open
        self._sws.on_data = self._on_data
        self._sws.on_error = self._on_error
        self._sws.on_close = self._on_close

        self._running = True
        self._thread = threading.Thread(target=self._run_ws, daemon=True)
        self._thread.start()
        logger.info("Market data WebSocket thread started")

    def stop(self) -> None:
        self._running = False
        if self._sws:
            try:
                self._sws.close_connection()
            except Exception:
                pass
        self._sws = None
        logger.info("Market data WebSocket stopped")

    def update_subscription(self, token_list: list[dict]) -> None:
        """Update which tokens we're subscribed to."""
        if not self._sws or not self._running:
            return
        try:
            if self._subscribed_tokens:
                self._sws.unsubscribe(
                    "unsub1",
                    SmartWebSocketV2.SNAP_QUOTE,
                    self._subscribed_tokens,
                )
            self._subscribed_tokens = token_list
            self._sws.subscribe(
                "sub1",
                SmartWebSocketV2.SNAP_QUOTE,
                token_list,
            )
        except Exception as e:
            logger.error("Subscription update failed: %s", e)

    def _run_ws(self) -> None:
        try:
            self._sws.connect()
        except Exception as e:
            logger.error("WebSocket connection error: %s", e)
            self._running = False

    def _on_open(self, wsapp) -> None:
        logger.info("Angel One WebSocket connected")
        if self._subscribed_tokens:
            # #region agent log
            import json as _dbg_json, time as _dbg_time
            try:
                with open("/Users/prabodh.shewalkar/Desktop/Personal/TradingLiveMarket/.cursor/debug-d38668.log", "a") as _f:
                    _dbg_tokens_preview = []
                    for tg in self._subscribed_tokens:
                        _dbg_tokens_preview.append({"exchangeType": tg.get("exchangeType"), "token_count": len(tg.get("tokens", [])), "first_5_tokens": tg.get("tokens", [])[:5]})
                    _f.write(_dbg_json.dumps({"sessionId":"d38668","hypothesisId":"H3","location":"websocket_manager.py:_on_open","message":"subscribing_tokens","data":{"token_groups":_dbg_tokens_preview},"timestamp":int(_dbg_time.time()*1000)}) + "\n")
            except Exception:
                pass
            # #endregion
            self._sws.subscribe(
                "sub1",
                SmartWebSocketV2.SNAP_QUOTE,
                self._subscribed_tokens,
            )
            logger.info(
                "Subscribed to %d token groups in SNAP_QUOTE mode",
                len(self._subscribed_tokens),
            )

    def _on_data(self, wsapp, message: dict) -> None:
        token = str(message.get("token", ""))
        if not token:
            return

        best_bid = 0.0
        best_ask = 0.0
        buy_data = message.get("best_5_buy_data") or []
        sell_data = message.get("best_5_sell_data") or []
        if buy_data:
            best_bid = buy_data[0].get("price", 0) / 100
        if sell_data:
            best_ask = sell_data[0].get("price", 0) / 100

        ltp = message.get("last_traded_price", 0) / 100

        price_data = {
            "token": token,
            "ltp": ltp,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "open": message.get("open_price_of_the_day", 0) / 100,
            "high": message.get("high_price_of_the_day", 0) / 100,
            "low": message.get("low_price_of_the_day", 0) / 100,
            "close": message.get("closed_price", 0) / 100,
            "volume": message.get("volume_trade_for_the_day", 0),
            "oi": message.get("open_interest", 0),
            "exchange_type": message.get("exchange_type", 0),
            "sequence": message.get("sequence_number", 0),
        }

        # #region agent log
        import json as _dbg_json, time as _dbg_time
        _dbg_tick_count = len(self._latest_prices)
        if _dbg_tick_count < 5 or _dbg_tick_count % 50 == 0:
            try:
                with open("/Users/prabodh.shewalkar/Desktop/Personal/TradingLiveMarket/.cursor/debug-d38668.log", "a") as _f:
                    _f.write(_dbg_json.dumps({"sessionId":"d38668","hypothesisId":"H1","location":"websocket_manager.py:_on_data","message":"snap_quote_tick","data":{"token":token,"ltp":ltp,"best_bid":best_bid,"best_ask":best_ask,"mid_price": round((best_bid+best_ask)/2, 2) if best_bid > 0 and best_ask > 0 else None,"ltp_vs_mid_diff": round((best_bid+best_ask)/2 - ltp, 2) if best_bid > 0 and best_ask > 0 else None,"oi":price_data["oi"],"tick_count":_dbg_tick_count},"timestamp":int(_dbg_time.time()*1000)}) + "\n")
            except Exception:
                pass
        # #endregion

        self._latest_prices[token] = price_data

        if self._loop and self._clients:
            asyncio.run_coroutine_threadsafe(
                self._broadcast(price_data), self._loop
            )

    def _on_error(self, wsapp, error) -> None:
        logger.error("Angel One WebSocket error: %s", error)

    def _on_close(self, wsapp) -> None:
        logger.info("Angel One WebSocket closed")
        self._running = False

    async def _broadcast(self, data: dict) -> None:
        dead: list[WebSocket] = []
        for client in self._clients:
            try:
                await client.send_json({"type": "tick", "data": data})
            except Exception:
                dead.append(client)
        for d in dead:
            self.disconnect_client(d)


market_data = MarketDataManager()
