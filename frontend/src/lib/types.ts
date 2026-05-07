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
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  oi: number;
}
