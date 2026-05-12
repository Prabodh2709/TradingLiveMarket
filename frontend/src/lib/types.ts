export interface Portfolio {
  balance: number;
  initial_balance: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  total_return_pct: number;
  positions: Position[];
  position_count: number;
}

export interface Position {
  id: string;
  symbol: string;
  token: string;
  name: string;
  strike: number;
  option_type: "CE" | "PE";
  expiry: string;
  side: "LONG" | "SHORT";
  qty: number;
  lot_size: number;
  avg_price: number;
  current_price: number;
  unrealized_pnl: number;
  opened_at: string;
}

export interface Trade {
  id: string;
  timestamp: string;
  symbol: string;
  token: string;
  name: string;
  strike: number;
  option_type: "CE" | "PE";
  expiry: string;
  action: "BUY" | "SELL";
  qty: number;
  lot_size: number;
  price: number;
  total_value: number;
  pnl: number | null;
  charges: number;
}

export interface TradePair {
  token: string;
  symbol: string;
  name: string;
  strike: number;
  option_type: "CE" | "PE";
  expiry: string;
  side: "LONG" | "SHORT";
  qty: number;
  lot_size: number;
  entry_time: string;
  entry_price: number;
  exit_time: string | null;
  exit_price: number | null;
  pnl: number | null;
  charges: number;
  status: "OPEN" | "CLOSED";
}

export interface OptionStrike {
  CE?: OptionContract;
  PE?: OptionContract;
}

export interface OptionContract {
  token: string;
  symbol: string;
  lotsize: number;
  tick_size: string;
  ltp: number | null;
}

export interface OptionChain {
  name: string;
  expiry: string;
  available_expiries: string[];
  strikes: Record<string, OptionStrike>;
  spot_price: number | null;
  index_token: string;
}

export interface HistoryMeta {
  version: number;
  reset_timestamp: string;
  final_balance: number;
  total_pnl: number;
  total_trades: number;
  folder: string;
}

export interface HistoryDetail {
  meta: HistoryMeta;
  portfolio: Record<string, unknown>;
  trades: Trade[];
  positions: Position[];
}

export interface TickData {
  token: string;
  ltp: number;
  best_bid: number;
  best_ask: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  oi: number;
}

// Strategy types
export interface StrategyStatus {
  running: boolean;
  started_at: string | null;
  stopped_at: string | null;
  total_trades_today: number;
  realized_pnl_today: number;
  open_positions: number;
  circuit_breaker_active: boolean;
  last_scan_time: string | null;
  execution_mode: "paper" | "live";
}

export interface StrategyConfig {
  enabled: boolean;
  execution_mode: "paper" | "live";
  instruments: string[];
  min_confidence_score: number;
  scan_interval_seconds: number;
  max_positions: number;
  max_risk_per_trade_pct: number;
  max_total_risk_pct: number;
  max_daily_loss_pct: number;
  min_risk_reward_ratio: number;
  target_pct: number;
  stop_loss_multiplier: number;
  trailing_sl_trigger_pct: number;
  trailing_sl_pct: number;
  limit_order_timeout_s: number;
  no_trade_before: string;
  no_trade_after: string;
  min_dte: number;
  preferred_dte_min: number;
  preferred_dte_max: number;
  otm_offset_points_nifty: number;
  otm_offset_points_banknifty: number;
  min_premium: number;
  max_premium: number;
  vix_pause_threshold: number;
  vix_spike_pct: number;
}

export interface StrategySignal {
  timestamp: string;
  instrument: string;
  action: string;
  strike_ce: number | null;
  strike_pe: number | null;
  expiry: string;
  confidence: number;
  rationale: string;
}

export interface StrategyLogEntry {
  timestamp: string;
  instrument: string;
  action_taken: string;
  reason: string;
  signal: StrategySignal | null;
  details: Record<string, unknown>;
}

export interface SRLevel {
  price: number;
  strength: number;
  timeframe: string;
  level_type: string;
}

export interface AnalysisSnapshot {
  timestamp: string;
  instrument: string;
  spot_price: number;
  levels: SRLevel[];
  nearest_support: number | null;
  nearest_resistance: number | null;
  price_action: {
    bias: string;
    trend_strength: number;
    at_support: boolean;
    at_resistance: boolean;
    rejection_detected: boolean;
    pattern: string;
    atr: number;
    confidence: number;
  };
  order_flow: {
    pcr: number;
    max_pain_strike: number;
    ce_oi_resistance: number;
    pe_oi_support: number;
    oi_buildup_bias: string;
    volume_spike_detected: boolean;
    confidence: number;
  };
  sentiment: {
    vix: number;
    vix_change_pct: number;
    market_bias: string;
    gap_pct: number;
    confidence: number;
  };
  signal_action: string;
  signal_confidence: number;
}

export interface StrategyActiveTrade {
  trade_plan: {
    token: string;
    symbol: string;
    strike: number;
    option_type: "CE" | "PE";
    expiry: string;
    qty: number;
    entry_price: number;
    target_price: number;
    stop_loss_price: number;
    risk_reward_ratio: number;
    max_loss: number;
    signal: StrategySignal;
  };
  entry_time: string;
  entry_filled_price: number;
  current_price: number;
  unrealized_pnl: number;
  highest_profit: number;
  trailing_sl_price: number | null;
  status: string;
}
