from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"


class Trade(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    symbol: str
    token: str
    name: str  # NIFTY or BANKNIFTY
    strike: float
    option_type: OptionType
    expiry: str
    action: TradeAction
    qty: int  # number of lots
    lot_size: int
    price: float
    total_value: float = 0.0
    pnl: Optional[float] = None  # set on exit trades
    charges: float = 0.0

    def model_post_init(self, __context) -> None:
        if self.total_value == 0.0:
            self.total_value = self.qty * self.lot_size * self.price


class Position(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    symbol: str
    token: str
    name: str
    strike: float
    option_type: OptionType
    expiry: str
    side: PositionSide = PositionSide.LONG
    qty: int  # lots
    lot_size: int
    avg_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    entry_charges: float = 0.0
    opened_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Portfolio(BaseModel):
    balance: float = 700000.0
    initial_balance: float = 700000.0
    realized_pnl: float = 0.0
    margin_used: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class HistoryMeta(BaseModel):
    version: int
    reset_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    final_balance: float
    total_pnl: float
    total_trades: int
