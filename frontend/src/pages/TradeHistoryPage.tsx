import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export default function TradeHistoryPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["trades"],
    queryFn: () => api.portfolio.trades(200, 0),
    refetchInterval: 10000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        Loading trades...
      </div>
    );
  }

  const trades = data?.trades || [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Trade History</h2>
        <span className="text-sm text-gray-500">
          {data?.total || 0} total trades
        </span>
      </div>

      {trades.length === 0 ? (
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
                  <th className="text-left px-5 py-3 font-medium">Time</th>
                  <th className="text-left px-5 py-3 font-medium">Action</th>
                  <th className="text-left px-5 py-3 font-medium">Symbol</th>
                  <th className="text-center px-5 py-3 font-medium">Type</th>
                  <th className="text-right px-5 py-3 font-medium">Lots</th>
                  <th className="text-right px-5 py-3 font-medium">Price</th>
                  <th className="text-right px-5 py-3 font-medium">Value</th>
                  <th className="text-right px-5 py-3 font-medium">P&L</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade) => {
                  const time = new Date(trade.timestamp);
                  const timeStr = time.toLocaleString("en-IN", {
                    day: "2-digit",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  });
                  return (
                    <tr
                      key={trade.id}
                      className="border-b border-gray-800/50 hover:bg-gray-800/30"
                    >
                      <td className="px-5 py-3 text-gray-400 text-xs">
                        {timeStr}
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            trade.action === "BUY"
                              ? "bg-blue-500/10 text-blue-400"
                              : "bg-orange-500/10 text-orange-400"
                          }`}
                        >
                          {trade.action}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <div className="font-medium">
                          {trade.name} {trade.strike}
                        </div>
                        <div className="text-xs text-gray-500">
                          {trade.expiry}
                        </div>
                      </td>
                      <td className="text-center px-5 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            trade.option_type === "CE"
                              ? "bg-green-500/10 text-green-400"
                              : "bg-red-500/10 text-red-400"
                          }`}
                        >
                          {trade.option_type}
                        </span>
                      </td>
                      <td className="text-right px-5 py-3">{trade.qty}</td>
                      <td className="text-right px-5 py-3 font-mono">
                        &#8377;{trade.price.toFixed(2)}
                      </td>
                      <td className="text-right px-5 py-3 font-mono">
                        &#8377;{trade.total_value.toFixed(2)}
                      </td>
                      <td className="text-right px-5 py-3 font-mono">
                        {trade.pnl != null ? (
                          <span
                            className={
                              trade.pnl >= 0
                                ? "text-green-400"
                                : "text-red-400"
                            }
                          >
                            {trade.pnl >= 0 ? "+" : ""}&#8377;
                            {trade.pnl.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-gray-600">--</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
