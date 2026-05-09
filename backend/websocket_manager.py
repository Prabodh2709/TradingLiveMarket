from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from fastapi import WebSocket
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

from backend.smartapi_client import session as api_session

logger = logging.getLogger(__name__)

BATCH_INTERVAL_S = 0.3


class MarketDataManager:
    """
    Bridges Angel One SmartWebSocketV2 feed to frontend WebSocket clients.
    Runs the SmartAPI WS in a background thread and broadcasts parsed
    market data to all connected FastAPI WebSocket clients.

    Ticks are buffered and flushed every BATCH_INTERVAL_S seconds to avoid
    per-tick broadcast overhead on high-frequency feeds.
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
        self._tick_buffer: dict[str, dict] = {}
        self._buffer_lock = threading.Lock()
        self._flush_task: Optional[asyncio.Task[None]] = None

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

        if self._loop and not self._flush_task:
            self._flush_task = self._loop.create_task(self._flush_loop())

        logger.info("Market data WebSocket thread started")

    def stop(self) -> None:
        self._running = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
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

        self._latest_prices[token] = price_data

        with self._buffer_lock:
            self._tick_buffer[token] = price_data

    def _on_error(self, wsapp, error) -> None:
        logger.error("Angel One WebSocket error: %s", error)

    def _on_close(self, wsapp) -> None:
        logger.info("Angel One WebSocket closed")
        self._running = False

    async def _flush_loop(self) -> None:
        """Periodically drain the tick buffer and broadcast a single batch."""
        while self._running:
            await asyncio.sleep(BATCH_INTERVAL_S)
            with self._buffer_lock:
                if not self._tick_buffer:
                    continue
                batch = self._tick_buffer.copy()
                self._tick_buffer.clear()
            await self._broadcast_batch(batch)

    async def _broadcast_batch(self, batch: dict[str, dict]) -> None:
        dead: list[WebSocket] = []
        msg = {"type": "batch", "data": batch}
        for client in self._clients:
            try:
                await client.send_json(msg)
            except Exception:
                dead.append(client)
        for d in dead:
            self.disconnect_client(d)


market_data = MarketDataManager()
