from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timezone, timedelta

from backend.config import settings
from backend.db import store
from backend.trading_engine import sell_option
from backend.websocket_manager import market_data

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
CHECK_INTERVAL_S = 30


def _parse_sqoff_time() -> time:
    parts = settings.auto_sqoff_time.split(":")
    return time(int(parts[0]), int(parts[1]))


async def auto_squareoff_loop() -> None:
    """Background loop that squares off all positions at the configured IST time."""
    sqoff_time = _parse_sqoff_time()
    triggered_date: str | None = None

    logger.info("Auto square-off scheduler started (trigger at %s IST)", settings.auto_sqoff_time)

    while True:
        await asyncio.sleep(CHECK_INTERVAL_S)

        now_ist = datetime.now(IST)
        today_str = now_ist.strftime("%Y-%m-%d")
        current_time = now_ist.time()

        if triggered_date == today_str:
            continue

        if current_time < sqoff_time:
            continue

        positions = store.load_positions()
        if not positions:
            triggered_date = today_str
            logger.info("Auto sq-off triggered at %s but no open positions", now_ist.strftime("%H:%M:%S"))
            continue

        logger.info(
            "Auto sq-off triggered at %s IST — closing %d position(s)",
            now_ist.strftime("%H:%M:%S"),
            len(positions),
        )

        for pos in positions:
            ltp = market_data.get_ltp(pos.token)
            if not ltp:
                logger.warning(
                    "No LTP for %s (token %s), using last known price %.2f",
                    pos.symbol, pos.token, pos.current_price,
                )
                ltp = pos.current_price

            if ltp <= 0:
                logger.error("Cannot sq-off %s — no valid price available", pos.symbol)
                continue

            try:
                result = sell_option(token=pos.token, qty=pos.qty, price=ltp)
                logger.info(
                    "Auto sq-off %s: %d lots @ %.2f, P&L=%.2f",
                    pos.symbol, pos.qty, ltp, result["pnl"],
                )
            except Exception:
                logger.exception("Failed to auto sq-off %s", pos.symbol)

        triggered_date = today_str
        logger.info("Auto sq-off cycle complete for %s", today_str)
