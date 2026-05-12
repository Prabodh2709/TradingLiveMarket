from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Timeframe(str, Enum):
    DAILY = "ONE_DAY"
    FIFTEEN_MIN = "FIFTEEN_MINUTE"
    FIVE_MIN = "FIVE_MINUTE"


class MarketBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    VOLATILE = "VOLATILE"


class SignalAction(str, Enum):
    SELL_CE = "SELL_CE"
    SELL_PE = "SELL_PE"
    SELL_STRANGLE = "SELL_STRANGLE"
    NO_TRADE = "NO_TRADE"


class ExitReason(str, Enum):
    TARGET_HIT = "TARGET_HIT"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    TRAILING_SL_HIT = "TRAILING_SL_HIT"
    TIME_EXIT = "TIME_EXIT"
    EXPIRY_PROTECTION = "EXPIRY_PROTECTION"
    KILL_SWITCH = "KILL_SWITCH"
    MANUAL = "MANUAL"


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class SupportResistanceLevel(BaseModel):
    price: float
    strength: int = 1  # number of touches/confluences
    timeframe: Timeframe = Timeframe.DAILY
    level_type: str = "swing"  # swing, pivot, vwap, pdh, pdl, pdc


class PriceActionSignal(BaseModel):
    bias: MarketBias = MarketBias.NEUTRAL
    trend_strength: float = 0.0  # 0-100
    at_support: bool = False
    at_resistance: bool = False
    rejection_detected: bool = False
    pattern: str = ""
    atr: float = 0.0
    confidence: float = 0.0  # 0-100


class OrderFlowSignal(BaseModel):
    pcr: float = 1.0
    max_pain_strike: float = 0.0
    ce_oi_resistance: float = 0.0  # strike with highest CE OI
    pe_oi_support: float = 0.0  # strike with highest PE OI
    oi_buildup_bias: MarketBias = MarketBias.NEUTRAL
    volume_spike_detected: bool = False
    confidence: float = 0.0


class SentimentSignal(BaseModel):
    vix: float = 0.0
    vix_change_pct: float = 0.0
    market_bias: MarketBias = MarketBias.NEUTRAL
    gap_pct: float = 0.0
    confidence: float = 0.0


class TradeSignal(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    instrument: str  # NIFTY or BANKNIFTY
    action: SignalAction
    strike_ce: Optional[float] = None
    strike_pe: Optional[float] = None
    expiry: str = ""
    confidence: float = 0.0  # 0-100 combined score
    rationale: str = ""
    price_action: Optional[PriceActionSignal] = None
    order_flow: Optional[OrderFlowSignal] = None
    sentiment: Optional[SentimentSignal] = None


class TradePlan(BaseModel):
    """Validated trade ready for execution after risk checks."""
    signal: TradeSignal
    token: str
    symbol: str
    strike: float
    option_type: str  # CE or PE
    expiry: str
    qty: int  # lots
    entry_price: float
    target_price: float
    stop_loss_price: float
    risk_reward_ratio: float
    max_loss: float


class ActiveTrade(BaseModel):
    """Tracks an open autonomous position for management."""
    trade_plan: TradePlan
    entry_time: str = Field(default_factory=lambda: datetime.now().isoformat())
    entry_filled_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    highest_profit: float = 0.0
    trailing_sl_price: Optional[float] = None
    status: str = "OPEN"  # OPEN, CLOSED


class DecisionLogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    instrument: str
    action_taken: str  # TRADE_PLACED, SIGNAL_SKIPPED, POSITION_EXITED, etc.
    reason: str
    signal: Optional[TradeSignal] = None
    details: dict = Field(default_factory=dict)


class AnalysisSnapshot(BaseModel):
    """Stores the latest analysis for one instrument for UI display."""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    instrument: str
    spot_price: float
    levels: list[SupportResistanceLevel] = Field(default_factory=list)
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    price_action: PriceActionSignal = Field(default_factory=PriceActionSignal)
    order_flow: OrderFlowSignal = Field(default_factory=OrderFlowSignal)
    sentiment: SentimentSignal = Field(default_factory=SentimentSignal)
    signal_action: str = "NO_TRADE"
    signal_confidence: float = 0.0


class StrategyState(BaseModel):
    """Runtime state of the strategy orchestrator."""
    running: bool = False
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    total_trades_today: int = 0
    realized_pnl_today: float = 0.0
    active_trades: list[ActiveTrade] = Field(default_factory=list)
    recent_signals: list[TradeSignal] = Field(default_factory=list)
    decision_log: list[DecisionLogEntry] = Field(default_factory=list)
    circuit_breaker_active: bool = False
    last_scan_time: Optional[str] = None
    last_trade_time: Optional[str] = None
    analysis_snapshots: dict[str, AnalysisSnapshot] = Field(default_factory=dict)
