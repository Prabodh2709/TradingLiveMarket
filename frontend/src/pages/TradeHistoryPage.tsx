import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Loader2 } from "lucide-react";
import type { Trade, TradePair } from "../lib/types";

function pairTrades(trades: Trade[]): TradePair[] {
  const sorted = [...trades].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  const openEntries = new Map<string, Trade[]>();
  const pairs: TradePair[] = [];

  for (const trade of sorted) {
    const isEntry = trade.pnl == null;

    if (isEntry) {
      const bucket = openEntries.get(trade.token) || [];
      bucket.push(trade);
      openEntries.set(trade.token, bucket);
    } else {
      const bucket = openEntries.get(trade.token);
      let entryTrade: Trade | undefined;
      if (bucket && bucket.length > 0) {
        entryTrade = bucket.shift();
        if (bucket.length === 0) openEntries.delete(trade.token);
      }

      const side: "LONG" | "SHORT" =
        trade.action === "SELL" ? "LONG" : "SHORT";

      pairs.push({
        token: trade.token,
        symbol: trade.symbol,
        name: trade.name,
        strike: trade.strike,
        option_type: trade.option_type,
        expiry: trade.expiry,
        side,
        qty: trade.qty,
        lot_size: trade.lot_size,
        entry_time: entryTrade?.timestamp ?? trade.timestamp,
        entry_price: entryTrade?.price ?? 0,
        exit_time: trade.timestamp,
        exit_price: trade.price,
        pnl: trade.pnl,
        charges: (entryTrade?.charges ?? 0) + (trade.charges ?? 0),
        status: "CLOSED",
      });
    }
  }

    for (const [, bucket] of openEntries) {
    for (const trade of bucket) {
      pairs.push({
        token: trade.token,
        symbol: trade.symbol,
        name: trade.name,
        strike: trade.strike,
        option_type: trade.option_type,
        expiry: trade.expiry,
        side: trade.action === "BUY" ? "LONG" : "SHORT",
        qty: trade.qty,
        lot_size: trade.lot_size,
        entry_time: trade.timestamp,
        entry_price: trade.price,
        exit_time: null,
        exit_price: null,
        pnl: null,
        charges: trade.charges ?? 0,
        status: "OPEN",
      });
    }
  }

  pairs.sort(
    (a, b) =>
      new Date(b.exit_time ?? b.entry_time).getTime() -
      new Date(a.exit_time ?? a.entry_time).getTime()
  );

  return pairs;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function TradeHistoryPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["trades"],
    queryFn: () => api.portfolio.trades(200, 0),
    refetchInterval: 10000,
  });

  const pairs = useMemo(
    () => pairTrades(data?.trades || []),
    [data?.trades]
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        <Loader2 size={24} className="animate-spin mr-3" />
        Loading trades...
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Trade History</h2>
        <span className="text-sm text-gray-500">
          {pairs.length} trade{pairs.length !== 1 ? "s" : ""}
        </span>
      </div>

      {pairs.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center text-gray-500">
          <p className="text-lg mb-1">No trades yet</p>
          <p className="text-sm">Your executed trades will appear here.</p>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left px-5 py-3 font-medium">Symbol</th>
                  <th className="text-center px-5 py-3 font-medium">Type</th>
                  <th className="text-center px-5 py-3 font-medium">Side</th>
                  <th className="text-right px-5 py-3 font-medium">Lots</th>
                  <th className="text-left px-5 py-3 font-medium">Entry Time</th>
                  <th className="text-right px-5 py-3 font-medium">Entry Price</th>
                  <th className="text-left px-5 py-3 font-medium">Exit Time</th>
                  <th className="text-right px-5 py-3 font-medium">Exit Price</th>
                  <th className="text-right px-5 py-3 font-medium">Charges</th>
                  <th className="text-right px-5 py-3 font-medium">P&L</th>
                  <th className="text-center px-5 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {pairs.map((pair, i) => (
                  <tr
                    key={`${pair.token}-${pair.entry_time}-${i}`}
                    className="border-b border-gray-800/50 hover:bg-gray-800/30"
                  >
                    <td className="px-5 py-3">
                      <div className="font-medium">
                        {pair.name} {pair.strike}
                      </div>
                      <div className="text-xs text-gray-500">
                        {pair.expiry}
                      </div>
                    </td>
                    <td className="text-center px-5 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          pair.option_type === "CE"
                            ? "bg-green-500/10 text-green-400"
                            : "bg-red-500/10 text-red-400"
                        }`}
                      >
                        {pair.option_type}
                      </span>
                    </td>
                    <td className="text-center px-5 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          pair.side === "LONG"
                            ? "bg-blue-500/10 text-blue-400"
                            : "bg-orange-500/10 text-orange-400"
                        }`}
                      >
                        {pair.side}
                      </span>
                    </td>
                    <td className="text-right px-5 py-3">{pair.qty}</td>
                    <td className="px-5 py-3 text-gray-400 text-xs">
                      {formatTime(pair.entry_time)}
                    </td>
                    <td className="text-right px-5 py-3 font-mono">
                      &#8377;{pair.entry_price.toFixed(2)}
                    </td>
                    <td className="px-5 py-3 text-gray-400 text-xs">
                      {pair.exit_time ? formatTime(pair.exit_time) : (
                        <span className="text-gray-600">--</span>
                      )}
                    </td>
                    <td className="text-right px-5 py-3 font-mono">
                      {pair.exit_price != null ? (
                        <>&#8377;{pair.exit_price.toFixed(2)}</>
                      ) : (
                        <span className="text-gray-600">--</span>
                      )}
                    </td>
                    <td className="text-right px-5 py-3 font-mono text-yellow-500/80 text-xs">
                      {pair.charges > 0 ? (
                        <>&#8377;{pair.charges.toFixed(2)}</>
                      ) : (
                        <span className="text-gray-600">--</span>
                      )}
                    </td>
                    <td className="text-right px-5 py-3 font-mono">
                      {pair.pnl != null ? (
                        <span
                          className={
                            pair.pnl >= 0 ? "text-green-400" : "text-red-400"
                          }
                        >
                          {pair.pnl >= 0 ? "+" : ""}&#8377;
                          {pair.pnl.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-gray-600">--</span>
                      )}
                    </td>
                    <td className="text-center px-5 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          pair.status === "OPEN"
                            ? "bg-green-500/10 text-green-400"
                            : "bg-gray-500/10 text-gray-400"
                        }`}
                      >
                        {pair.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
