import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useAppStore } from "../store/useAppStore";
import { XCircle } from "lucide-react";
import type { Position } from "../lib/types";

export default function PositionsPage() {
  const queryClient = useQueryClient();
  const prices = useAppStore((s) => s.prices);

  const { data: portfolio, isLoading } = useQuery({
    queryKey: ["portfolio"],
    queryFn: api.portfolio.get,
    refetchInterval: 3000,
  });

  const handleSquareOff = async (pos: Position) => {
    const wsPrice = prices[pos.token];
    const sellPrice = wsPrice?.best_bid > 0 ? wsPrice.best_bid : (wsPrice?.ltp || pos.current_price);
    if (!sellPrice) {
      alert("No price available for square-off");
      return;
    }
    if (!confirm(`Square off ${pos.qty} lot(s) of ${pos.symbol} at ₹${sellPrice.toFixed(2)}?`)) {
      return;
    }
    try {
      await api.trade.sell({
        token: pos.token,
        qty: pos.qty,
        price: sellPrice,
      });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Square-off failed");
    }
  };

  const getPosition = (pos: Position): Position => {
    const wsPrice = prices[pos.token];
    if (wsPrice) {
      let currentPrice = wsPrice.ltp;
      if (wsPrice.best_bid > 0 && wsPrice.best_ask > 0) {
        currentPrice = (wsPrice.best_bid + wsPrice.best_ask) / 2;
      }
      const unrealizedPnl = (currentPrice - pos.avg_price) * pos.qty * pos.lot_size;
      return { ...pos, current_price: currentPrice, unrealized_pnl: unrealizedPnl };
    }
    return pos;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        Loading positions...
      </div>
    );
  }

  const positions = (portfolio?.positions || []).map(getPosition);

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Open Positions</h2>

      {positions.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center text-gray-500">
          <p className="text-lg mb-1">No open positions</p>
          <p className="text-sm">
            Go to the Option Chain to place your first trade.
          </p>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left px-5 py-3 font-medium">Symbol</th>
                  <th className="text-center px-5 py-3 font-medium">Type</th>
                  <th className="text-right px-5 py-3 font-medium">Lots</th>
                  <th className="text-right px-5 py-3 font-medium">
                    Avg Price
                  </th>
                  <th className="text-right px-5 py-3 font-medium">LTP</th>
                  <th className="text-right px-5 py-3 font-medium">P&L</th>
                  <th className="text-center px-5 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((pos) => {
                  const pnlColor =
                    pos.unrealized_pnl > 0
                      ? "text-green-400"
                      : pos.unrealized_pnl < 0
                      ? "text-red-400"
                      : "text-gray-400";
                  return (
                    <tr
                      key={pos.id}
                      className="border-b border-gray-800/50 hover:bg-gray-800/30"
                    >
                      <td className="px-5 py-3">
                        <div className="font-medium">
                          {pos.name} {pos.strike}
                        </div>
                        <div className="text-xs text-gray-500">{pos.expiry}</div>
                      </td>
                      <td className="text-center px-5 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            pos.option_type === "CE"
                              ? "bg-green-500/10 text-green-400"
                              : "bg-red-500/10 text-red-400"
                          }`}
                        >
                          {pos.option_type}
                        </span>
                      </td>
                      <td className="text-right px-5 py-3">{pos.qty}</td>
                      <td className="text-right px-5 py-3 font-mono">
                        &#8377;{pos.avg_price.toFixed(2)}
                      </td>
                      <td className="text-right px-5 py-3 font-mono">
                        &#8377;{pos.current_price.toFixed(2)}
                      </td>
                      <td className={`text-right px-5 py-3 font-mono ${pnlColor}`}>
                        {pos.unrealized_pnl > 0 ? "+" : ""}
                        &#8377;{pos.unrealized_pnl.toFixed(2)}
                      </td>
                      <td className="text-center px-5 py-3">
                        <button
                          onClick={() => handleSquareOff(pos)}
                          className="inline-flex items-center gap-1 bg-red-600/20 hover:bg-red-600/40 text-red-400 px-3 py-1.5 rounded text-xs font-medium"
                        >
                          <XCircle size={14} />
                          Square Off
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="px-5 py-3 border-t border-gray-800 flex justify-between text-sm">
            <span className="text-gray-500">
              Total Unrealized P&L
            </span>
            <span
              className={`font-mono font-medium ${
                (portfolio?.unrealized_pnl ?? 0) >= 0
                  ? "text-green-400"
                  : "text-red-400"
              }`}
            >
              {(portfolio?.unrealized_pnl ?? 0) >= 0 ? "+" : ""}&#8377;
              {(portfolio?.unrealized_pnl ?? 0).toFixed(2)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
