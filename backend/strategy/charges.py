"""
Realistic NSE F&O option charges and margin estimation for paper trading.

Rate card (as of 2024-25):
  Brokerage       : Rs 20 flat per executed order
  STT             : 0.0625% on sell-side premium turnover
  Exchange Txn    : 0.053% on turnover (both sides)
  GST             : 18% on (Brokerage + Exchange Txn)
  SEBI            : 0.0001% on turnover
  Stamp Duty      : 0.003% on buy-side turnover only
"""

from __future__ import annotations

from backend.strategy.config import strategy_settings

BROKERAGE_PER_ORDER = 20.0
STT_RATE = 0.000625
EXCHANGE_TXN_RATE = 0.00053
GST_RATE = 0.18
SEBI_RATE = 0.000001
STAMP_DUTY_RATE = 0.00003


def compute_charges(turnover: float, side: str) -> dict[str, float]:
    """
    Compute realistic NSE F&O charges for a single paper trade leg.

    Args:
        turnover: premium * qty * lot_size
        side: "SELL" for entry (sell-to-open) or "BUY" for exit (buy-to-close)

    Returns:
        Dict with individual charge components and total.
    """
    brokerage = BROKERAGE_PER_ORDER
    exchange_txn = turnover * EXCHANGE_TXN_RATE
    stt = turnover * STT_RATE if side == "SELL" else 0.0
    gst = (brokerage + exchange_txn) * GST_RATE
    sebi = turnover * SEBI_RATE
    stamp = turnover * STAMP_DUTY_RATE if side == "BUY" else 0.0

    total = brokerage + stt + exchange_txn + gst + sebi + stamp

    return {
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "exchange_txn": round(exchange_txn, 2),
        "gst": round(gst, 2),
        "sebi": round(sebi, 2),
        "stamp": round(stamp, 2),
        "total": round(total, 2),
    }


def estimate_margin(spot_price: float, lot_size: int, qty: int, instrument: str) -> float:
    """
    Approximate SPAN + Exposure margin required to sell index options.

    Uses a configurable percentage of the contract notional value:
        margin = spot_price * lot_size * qty * (margin_pct / 100)
    """
    if instrument.upper() == "BANKNIFTY":
        pct = strategy_settings.margin_pct_banknifty
    else:
        pct = strategy_settings.margin_pct_nifty

    return round(spot_price * lot_size * qty * (pct / 100), 2)
