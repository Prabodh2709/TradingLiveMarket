import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  Play,
  Square,
  AlertTriangle,
  Zap,
  TrendingDown,
  TrendingUp,
  Activity,
  Settings,
  Shield,
  Clock,
  BarChart3,
} from "lucide-react";
import { api } from "../lib/api";
import type {
  StrategyStatus,
  StrategyConfig,
  StrategySignal,
  StrategyLogEntry,
  StrategyActiveTrade,
  AnalysisSnapshot,
} from "../lib/types";

export default function StrategyPage() {
  const [showConfig, setShowConfig] = useState(false);
  const queryClient = useQueryClient();

  const { data: statusData } = useQuery({
    queryKey: ["strategy-status"],
    queryFn: () => api.strategy.status(),
    refetchInterval: 3000,
  });

  const { data: signalsData } = useQuery({
    queryKey: ["strategy-signals"],
    queryFn: () => api.strategy.signals(),
    refetchInterval: 5000,
  });

  const { data: logData } = useQuery({
    queryKey: ["strategy-log"],
    queryFn: () => api.strategy.log(30),
    refetchInterval: 5000,
  });

  const { data: posData } = useQuery({
    queryKey: ["strategy-positions"],
    queryFn: () => api.strategy.positions(),
    refetchInterval: 3000,
  });

  const { data: analysisData } = useQuery({
    queryKey: ["strategy-analysis"],
    queryFn: () => api.strategy.analysis(),
    refetchInterval: 5000,
  });

  const startMutation = useMutation({
    mutationFn: () => api.strategy.start(),
    onSuccess: () => {
      toast.success("Strategy started");
      queryClient.invalidateQueries({ queryKey: ["strategy-status"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const stopMutation = useMutation({
    mutationFn: () => api.strategy.stop(false),
    onSuccess: () => {
      toast.success("Strategy stopped");
      queryClient.invalidateQueries({ queryKey: ["strategy-status"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const killMutation = useMutation({
    mutationFn: () => api.strategy.kill(),
    onSuccess: () => {
      toast.success("Kill switch activated - all positions closed");
      queryClient.invalidateQueries({ queryKey: ["strategy-status"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const status: StrategyStatus | undefined = statusData?.data;
  const signals: StrategySignal[] = signalsData?.data || [];
  const logEntries: StrategyLogEntry[] = logData?.data || [];
  const positions: StrategyActiveTrade[] = posData?.data || [];
  const analysisSnapshots: Record<string, AnalysisSnapshot> = analysisData?.data || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Autonomous Strategy</h1>
          <p className="text-sm text-gray-500 mt-1">
            Option selling system with multi-timeframe analysis
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowConfig(!showConfig)}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 text-gray-300 rounded-lg hover:bg-gray-700 transition-colors"
          >
            <Settings size={16} />
            Config
          </button>
          {status?.running ? (
            <>
              <button
                onClick={() => stopMutation.mutate()}
                disabled={stopMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
              >
                <Square size={16} />
                Stop
              </button>
              <button
                onClick={() => {
                  if (confirm("Kill switch: Stop strategy AND close all positions?")) {
                    killMutation.mutate();
                  }
                }}
                disabled={killMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                <AlertTriangle size={16} />
                Kill
              </button>
            </>
          ) : (
            <button
              onClick={() => startMutation.mutate()}
              disabled={startMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              <Play size={16} />
              Start
            </button>
          )}
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatusCard
          label="Status"
          value={status?.running ? "RUNNING" : "STOPPED"}
          icon={<Activity size={18} />}
          color={status?.running ? "text-green-400" : "text-gray-400"}
        />
        <StatusCard
          label="Today's P&L"
          value={`₹${(status?.realized_pnl_today || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`}
          icon={
            (status?.realized_pnl_today || 0) >= 0 ? (
              <TrendingUp size={18} />
            ) : (
              <TrendingDown size={18} />
            )
          }
          color={
            (status?.realized_pnl_today || 0) >= 0 ? "text-green-400" : "text-red-400"
          }
        />
        <StatusCard
          label="Open Positions"
          value={String(status?.open_positions || 0)}
          icon={<Zap size={18} />}
          color="text-blue-400"
        />
        <StatusCard
          label="Mode"
          value={(status?.execution_mode || "paper").toUpperCase()}
          icon={<Shield size={18} />}
          color={status?.execution_mode === "live" ? "text-red-400" : "text-cyan-400"}
        />
      </div>

      {/* Circuit Breaker Warning */}
      {status?.circuit_breaker_active && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 flex items-center gap-3">
          <AlertTriangle className="text-red-400" size={20} />
          <span className="text-red-300 text-sm font-medium">
            Circuit breaker active - daily loss limit exceeded. No new trades will be taken.
          </span>
        </div>
      )}

      {/* Config Panel */}
      {showConfig && <ConfigPanel />}

      {/* Market Analysis Panel */}
      {Object.keys(analysisSnapshots).length > 0 ? (
        <MarketAnalysisPanel snapshots={analysisSnapshots} />
      ) : status?.running ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex items-center gap-3">
          <BarChart3 size={18} className="text-blue-400 animate-pulse" />
          <span className="text-sm text-gray-400">
            Waiting for first analysis scan to complete... (requires market data connection)
          </span>
        </div>
      ) : null}

      {/* Active Positions */}
      {positions.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-800">
            <h2 className="text-sm font-semibold text-gray-300">Active Positions</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left px-4 py-2">Symbol</th>
                  <th className="text-center px-4 py-2">Type</th>
                  <th className="text-right px-4 py-2">Entry</th>
                  <th className="text-right px-4 py-2">Current</th>
                  <th className="text-right px-4 py-2">Target</th>
                  <th className="text-right px-4 py-2">SL</th>
                  <th className="text-right px-4 py-2">P&L</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((pos, i) => (
                  <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-4 py-2 text-gray-200 font-mono text-xs">
                      {pos.trade_plan.symbol}
                    </td>
                    <td className="text-center px-4 py-2">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          pos.trade_plan.option_type === "CE"
                            ? "bg-red-500/20 text-red-400"
                            : "bg-green-500/20 text-green-400"
                        }`}
                      >
                        {pos.trade_plan.option_type}
                      </span>
                    </td>
                    <td className="text-right px-4 py-2 text-gray-300">
                      ₹{pos.entry_filled_price.toFixed(2)}
                    </td>
                    <td className="text-right px-4 py-2 text-gray-300">
                      ₹{pos.current_price.toFixed(2)}
                    </td>
                    <td className="text-right px-4 py-2 text-green-400">
                      ₹{pos.trade_plan.target_price.toFixed(2)}
                    </td>
                    <td className="text-right px-4 py-2 text-red-400">
                      ₹{(pos.trailing_sl_price || pos.trade_plan.stop_loss_price).toFixed(2)}
                    </td>
                    <td
                      className={`text-right px-4 py-2 font-medium ${
                        pos.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      ₹{pos.unrealized_pnl.toFixed(0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Signals & Log side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Signals */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-800">
            <h2 className="text-sm font-semibold text-gray-300">Recent Signals</h2>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {signals.length === 0 ? (
              <p className="text-gray-500 text-sm p-4">No signals yet</p>
            ) : (
              signals.map((sig, i) => (
                <div
                  key={i}
                  className="px-4 py-3 border-b border-gray-800/50 hover:bg-gray-800/30"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-gray-400">
                        {sig.instrument}
                      </span>
                      <ActionBadge action={sig.action} />
                    </div>
                    <span className="text-xs text-gray-500">
                      {new Date(sig.timestamp).toLocaleTimeString("en-IN")}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-3">
                    <ConfidenceBar value={sig.confidence} />
                    {sig.strike_ce && (
                      <span className="text-xs text-red-400">CE: {sig.strike_ce}</span>
                    )}
                    {sig.strike_pe && (
                      <span className="text-xs text-green-400">PE: {sig.strike_pe}</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Decision Log */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-800">
            <h2 className="text-sm font-semibold text-gray-300">Decision Log</h2>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {logEntries.length === 0 ? (
              <p className="text-gray-500 text-sm p-4">No decisions yet</p>
            ) : (
              logEntries.map((entry, i) => (
                <div
                  key={i}
                  className="px-4 py-2.5 border-b border-gray-800/50 hover:bg-gray-800/30"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <LogActionBadge action={entry.action_taken} />
                      <span className="text-xs text-gray-400">{entry.instrument}</span>
                    </div>
                    <span className="text-xs text-gray-600">
                      {new Date(entry.timestamp).toLocaleTimeString("en-IN")}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1 truncate">{entry.reason}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Footer info */}
      {status?.last_scan_time && (
        <div className="flex items-center gap-2 text-xs text-gray-600">
          <Clock size={12} />
          Last scan: {new Date(status.last_scan_time).toLocaleTimeString("en-IN")}
        </div>
      )}
    </div>
  );
}

function MarketAnalysisPanel({ snapshots }: { snapshots: Record<string, AnalysisSnapshot> }) {
  const [activeTab, setActiveTab] = useState(Object.keys(snapshots)[0] || "NIFTY");
  const instruments = Object.keys(snapshots);
  const snap = snapshots[activeTab];

  if (!snap) return null;

  const resistances = snap.levels
    .filter((l) => l.price > snap.spot_price)
    .sort((a, b) => a.price - b.price)
    .slice(0, 5);
  const supports = snap.levels
    .filter((l) => l.price < snap.spot_price)
    .sort((a, b) => b.price - a.price)
    .slice(0, 5);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-gray-300">Market Analysis</h2>
          <span className="text-xs text-gray-600">
            {new Date(snap.timestamp).toLocaleTimeString("en-IN")}
          </span>
        </div>
        <div className="flex gap-1">
          {instruments.map((inst) => (
            <button
              key={inst}
              onClick={() => setActiveTab(inst)}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
                activeTab === inst
                  ? "bg-blue-500/20 text-blue-400"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {inst}
            </button>
          ))}
        </div>
      </div>

      <div className="p-5 space-y-5">
        {/* Decision Summary */}
        <div className="flex items-center gap-3 px-4 py-2.5 bg-gray-800/50 rounded-lg">
          <ActionBadge action={snap.signal_action} />
          <ConfidenceBar value={snap.signal_confidence} />
          <span className="text-xs text-gray-400">
            Spot: <span className="text-gray-200 font-mono font-medium">{snap.spot_price > 0 ? snap.spot_price.toFixed(2) : "N/A"}</span>
          </span>
          {(snap.signal_action === "NO_DATA" || snap.signal_action === "NO_CHAIN") && (
            <span className="ml-auto text-xs text-yellow-500 animate-pulse">
              {snap.signal_action === "NO_DATA" ? "Waiting for market data..." : "Waiting for option chain data..."}
            </span>
          )}
        </div>

        {/* Price Ladder + Analysis Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Price Ladder */}
          <div className="bg-gray-800/40 rounded-lg p-4">
            <h3 className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">S/R Levels</h3>
            <div className="space-y-1.5">
              {resistances.reverse().map((level, i) => (
                <div key={`r-${i}`} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-red-500/70" />
                    <span className="text-red-400 font-mono">{level.price.toFixed(0)}</span>
                  </div>
                  <span className="text-gray-600">
                    {level.level_type} <span className="text-gray-500">x{level.strength}</span>
                  </span>
                </div>
              ))}

              {/* Spot price marker */}
              <div className="flex items-center justify-between text-xs py-1.5 my-1 border-y border-dashed border-yellow-600/40">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-yellow-400 animate-pulse" />
                  <span className="text-yellow-300 font-mono font-bold">{snap.spot_price.toFixed(0)}</span>
                </div>
                <span className="text-yellow-500 text-xs font-medium">SPOT</span>
              </div>

              {supports.map((level, i) => (
                <div key={`s-${i}`} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500/70" />
                    <span className="text-green-400 font-mono">{level.price.toFixed(0)}</span>
                  </div>
                  <span className="text-gray-600">
                    {level.level_type} <span className="text-gray-500">x{level.strength}</span>
                  </span>
                </div>
              ))}

              {supports.length === 0 && resistances.length === 0 && (
                <p className="text-gray-600 text-xs">No levels detected yet</p>
              )}
            </div>
          </div>

          {/* Price Action Card */}
          <div className="bg-gray-800/40 rounded-lg p-4 space-y-3">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Price Action</h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Trend</span>
                <BiasBadge bias={snap.price_action.bias} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Strength</span>
                <span className="text-xs text-gray-300">{snap.price_action.trend_strength.toFixed(0)}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">ATR</span>
                <span className="text-xs text-gray-300 font-mono">{snap.price_action.atr.toFixed(1)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">At Support</span>
                <IndicatorDot active={snap.price_action.at_support} color="green" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">At Resistance</span>
                <IndicatorDot active={snap.price_action.at_resistance} color="red" />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Rejection</span>
                <IndicatorDot active={snap.price_action.rejection_detected} color="amber" />
              </div>
              {snap.price_action.pattern && (
                <div className="pt-1 border-t border-gray-700/50">
                  <span className="text-xs text-amber-400">{snap.price_action.pattern.replace(/_/g, " ")}</span>
                </div>
              )}
              <div className="pt-1 border-t border-gray-700/50 flex items-center justify-between">
                <span className="text-xs text-gray-500">Confidence</span>
                <ConfidenceBar value={snap.price_action.confidence} />
              </div>
            </div>
          </div>

          {/* Order Flow + Sentiment stacked */}
          <div className="space-y-4">
            {/* Order Flow */}
            <div className="bg-gray-800/40 rounded-lg p-4 space-y-2">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Order Flow</h3>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">PCR</span>
                <span className={`text-xs font-mono font-medium ${
                  snap.order_flow.pcr > 1.2 ? "text-green-400" : snap.order_flow.pcr < 0.7 ? "text-red-400" : "text-gray-300"
                }`}>{snap.order_flow.pcr.toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Max Pain</span>
                <span className="text-xs text-gray-300 font-mono">{snap.order_flow.max_pain_strike.toFixed(0)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">CE OI Wall</span>
                <span className="text-xs text-red-400 font-mono">{snap.order_flow.ce_oi_resistance.toFixed(0)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">PE OI Wall</span>
                <span className="text-xs text-green-400 font-mono">{snap.order_flow.pe_oi_support.toFixed(0)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">OI Bias</span>
                <BiasBadge bias={snap.order_flow.oi_buildup_bias} />
              </div>
              {snap.order_flow.volume_spike_detected && (
                <div className="text-xs text-amber-400 font-medium">Volume Spike Detected</div>
              )}
            </div>

            {/* Sentiment */}
            <div className="bg-gray-800/40 rounded-lg p-4 space-y-2">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Sentiment</h3>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">India VIX</span>
                <span className="text-xs text-gray-300 font-mono">
                  {snap.sentiment.vix.toFixed(1)}
                  <span className={`ml-1 ${snap.sentiment.vix_change_pct >= 0 ? "text-red-400" : "text-green-400"}`}>
                    ({snap.sentiment.vix_change_pct >= 0 ? "+" : ""}{snap.sentiment.vix_change_pct.toFixed(1)}%)
                  </span>
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Bias</span>
                <BiasBadge bias={snap.sentiment.market_bias} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Gap</span>
                <span className={`text-xs font-mono ${
                  snap.sentiment.gap_pct > 0 ? "text-green-400" : snap.sentiment.gap_pct < 0 ? "text-red-400" : "text-gray-400"
                }`}>{snap.sentiment.gap_pct >= 0 ? "+" : ""}{snap.sentiment.gap_pct.toFixed(2)}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function BiasBadge({ bias }: { bias: string }) {
  const colors: Record<string, string> = {
    BULLISH: "bg-green-500/20 text-green-400",
    BEARISH: "bg-red-500/20 text-red-400",
    NEUTRAL: "bg-gray-500/20 text-gray-400",
    VOLATILE: "bg-amber-500/20 text-amber-400",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[bias] || colors.NEUTRAL}`}>
      {bias}
    </span>
  );
}

function IndicatorDot({ active, color }: { active: boolean; color: "green" | "red" | "amber" }) {
  const activeColors = { green: "bg-green-400", red: "bg-red-400", amber: "bg-amber-400" };
  return (
    <div className={`w-2.5 h-2.5 rounded-full ${active ? activeColors[color] : "bg-gray-700"}`} />
  );
}

function StatusCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center gap-2 text-gray-500 text-xs mb-2">
        {icon}
        {label}
      </div>
      <p className={`text-lg font-bold ${color}`}>{value}</p>
    </div>
  );
}

function ActionBadge({ action }: { action: string }) {
  const colors: Record<string, string> = {
    SELL_CE: "bg-red-500/20 text-red-400",
    SELL_PE: "bg-green-500/20 text-green-400",
    SELL_STRANGLE: "bg-purple-500/20 text-purple-400",
    NO_TRADE: "bg-gray-500/20 text-gray-400",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[action] || colors.NO_TRADE}`}>
      {action.replace("_", " ")}
    </span>
  );
}

function LogActionBadge({ action }: { action: string }) {
  const colors: Record<string, string> = {
    TRADE_PLACED: "bg-green-500/20 text-green-400",
    TRADE_REJECTED: "bg-amber-500/20 text-amber-400",
    SIGNAL_SKIPPED: "bg-gray-500/20 text-gray-400",
    POSITION_EXITED: "bg-blue-500/20 text-blue-400",
    CIRCUIT_BREAKER: "bg-red-500/20 text-red-400",
    VIX_SPIKE: "bg-red-500/20 text-red-400",
    STRATEGY_STARTED: "bg-cyan-500/20 text-cyan-400",
    STRATEGY_STOPPED: "bg-gray-500/20 text-gray-400",
    EXECUTION_FAILED: "bg-red-500/20 text-red-400",
    ERROR: "bg-red-500/20 text-red-400",
  };
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${colors[action] || "bg-gray-500/20 text-gray-400"}`}
    >
      {action.replace(/_/g, " ")}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const color =
    value >= 70 ? "bg-green-500" : value >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-xs text-gray-500">{value.toFixed(0)}%</span>
    </div>
  );
}

function ConfigPanel() {
  const queryClient = useQueryClient();
  const { data: configData } = useQuery({
    queryKey: ["strategy-config"],
    queryFn: () => api.strategy.config(),
  });

  const updateMutation = useMutation({
    mutationFn: (data: Partial<StrategyConfig>) => api.strategy.updateConfig(data),
    onSuccess: () => {
      toast.success("Config updated");
      queryClient.invalidateQueries({ queryKey: ["strategy-config"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const config: StrategyConfig | undefined = configData?.data;

  if (!config) return null;

  const handleChange = (key: keyof StrategyConfig, value: number | string | boolean) => {
    updateMutation.mutate({ [key]: value });
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <h2 className="text-sm font-semibold text-gray-300 mb-4">Strategy Configuration</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ConfigField
          label="Execution Mode"
          value={config.execution_mode}
          type="select"
          options={["paper", "live"]}
          onChange={(v) => handleChange("execution_mode", v)}
        />
        <ConfigField
          label="Min Confidence Score"
          value={config.min_confidence_score}
          type="number"
          onChange={(v) => handleChange("min_confidence_score", Number(v))}
        />
        <ConfigField
          label="Scan Interval (sec)"
          value={config.scan_interval_seconds}
          type="number"
          onChange={(v) => handleChange("scan_interval_seconds", Number(v))}
        />
        <ConfigField
          label="Max Positions"
          value={config.max_positions}
          type="number"
          onChange={(v) => handleChange("max_positions", Number(v))}
        />
        <ConfigField
          label="Max Risk/Trade (%)"
          value={config.max_risk_per_trade_pct}
          type="number"
          onChange={(v) => handleChange("max_risk_per_trade_pct", Number(v))}
        />
        <ConfigField
          label="Max Daily Loss (%)"
          value={config.max_daily_loss_pct}
          type="number"
          onChange={(v) => handleChange("max_daily_loss_pct", Number(v))}
        />
        <ConfigField
          label="Target (%)"
          value={config.target_pct}
          type="number"
          onChange={(v) => handleChange("target_pct", Number(v))}
        />
        <ConfigField
          label="Stop Loss Multiplier"
          value={config.stop_loss_multiplier}
          type="number"
          onChange={(v) => handleChange("stop_loss_multiplier", Number(v))}
        />
        <ConfigField
          label="Min RR Ratio"
          value={config.min_risk_reward_ratio}
          type="number"
          onChange={(v) => handleChange("min_risk_reward_ratio", Number(v))}
        />
        <ConfigField
          label="No Trade Before"
          value={config.no_trade_before}
          type="text"
          onChange={(v) => handleChange("no_trade_before", v)}
        />
        <ConfigField
          label="No Trade After"
          value={config.no_trade_after}
          type="text"
          onChange={(v) => handleChange("no_trade_after", v)}
        />
        <ConfigField
          label="Min Premium (₹)"
          value={config.min_premium}
          type="number"
          onChange={(v) => handleChange("min_premium", Number(v))}
        />
        <ConfigField
          label="Max Premium (₹)"
          value={config.max_premium}
          type="number"
          onChange={(v) => handleChange("max_premium", Number(v))}
        />
        <ConfigField
          label="Trailing SL Trigger (%)"
          value={config.trailing_sl_trigger_pct}
          type="number"
          onChange={(v) => handleChange("trailing_sl_trigger_pct", Number(v))}
        />
        <ConfigField
          label="VIX Spike Pause (%)"
          value={config.vix_spike_pct}
          type="number"
          onChange={(v) => handleChange("vix_spike_pct", Number(v))}
        />
      </div>
    </div>
  );
}

function ConfigField({
  label,
  value,
  type,
  options,
  onChange,
}: {
  label: string;
  value: string | number | boolean;
  type: "number" | "text" | "select";
  options?: string[];
  onChange: (v: string) => void;
}) {
  const [localVal, setLocalVal] = useState(String(value));

  const handleBlur = () => {
    if (localVal !== String(value)) {
      onChange(localVal);
    }
  };

  if (type === "select" && options) {
    return (
      <div>
        <label className="block text-xs text-gray-500 mb-1">{label}</label>
        <select
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
        >
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt.toUpperCase()}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <input
        type={type}
        value={localVal}
        onChange={(e) => setLocalVal(e.target.value)}
        onBlur={handleBlur}
        onKeyDown={(e) => e.key === "Enter" && handleBlur()}
        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
      />
    </div>
  );
}
