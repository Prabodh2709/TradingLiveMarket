import { useEffect, useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useAppStore } from "../store/useAppStore";
import { RefreshCw, ShoppingCart } from "lucide-react";
import type { OptionContract } from "../lib/types";

export default function OptionChainPage() {
  const queryClient = useQueryClient();
  const selectedIndex = useAppStore((s) => s.selectedIndex);
  const setSelectedIndex = useAppStore((s) => s.setSelectedIndex);
  const selectedExpiry = useAppStore((s) => s.selectedExpiry);
  const setSelectedExpiry = useAppStore((s) => s.setSelectedExpiry);
  const prices = useAppStore((s) => s.prices);

  const [refreshing, setRefreshing] = useState(false);
  const [buyQty, setBuyQty] = useState(1);

  const {
    data: chain,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["option-chain", selectedIndex, selectedExpiry],
    queryFn: () => api.instruments.optionChain(selectedIndex, selectedExpiry || undefined),
    enabled: true,
    retry: false,
  });

  useEffect(() => {
    if (chain?.expiry && !selectedExpiry) {
      setSelectedExpiry(chain.expiry);
    }
  }, [chain, selectedExpiry, setSelectedExpiry]);

  const handleRefreshInstruments = async () => {
    setRefreshing(true);
    try {
      await api.instruments.refresh();
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  };

  const handleSubscribe = useCallback(async () => {
    if (!selectedExpiry) return;
    try {
      await api.instruments.subscribe(selectedIndex, selectedExpiry);
    } catch (err) {
      console.error("Subscribe failed:", err);
    }
  }, [selectedIndex, selectedExpiry]);

  useEffect(() => {
    if (selectedExpiry) handleSubscribe();
  }, [selectedExpiry, handleSubscribe]);

  const handleBuy = async (contract: OptionContract, optionType: "CE" | "PE") => {
    if (!chain || !contract.ltp) return;
    const ltp = getLtp(contract);
    if (!ltp) {
      alert("No live price available");
      return;
    }
    try {
      await api.trade.buy({
        symbol: contract.symbol,
        token: contract.token,
        name: selectedIndex,
        strike: parseFloat(
          Object.entries(chain.strikes).find(([_, s]) =>
            s[optionType]?.token === contract.token
          )?.[0] || "0"
        ),
        option_type: optionType,
        expiry: chain.expiry,
        qty: buyQty,
        price: ltp,
      });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Buy failed");
    }
  };

  const getLtp = (contract: OptionContract | undefined): number | null => {
    if (!contract) return null;
    const wsPrice = prices[contract.token];
    if (wsPrice) return wsPrice.ltp;
    return contract.ltp;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">Option Chain</h2>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-sm">
            <label className="text-gray-500">Lots:</label>
            <input
              type="number"
              min={1}
              max={100}
              value={buyQty}
              onChange={(e) => setBuyQty(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-16 text-center text-sm"
            />
          </div>
          <button
            onClick={handleRefreshInstruments}
            disabled={refreshing}
            className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-2 rounded-lg text-sm"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex items-center gap-4 mb-4">
        <div className="flex bg-gray-800 rounded-lg p-0.5">
          {(["NIFTY", "BANKNIFTY"] as const).map((idx) => (
            <button
              key={idx}
              onClick={() => {
                setSelectedIndex(idx);
                setSelectedExpiry("");
              }}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                selectedIndex === idx
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              {idx}
            </button>
          ))}
        </div>

        {chain?.available_expiries && (
          <select
            value={selectedExpiry}
            onChange={(e) => setSelectedExpiry(e.target.value)}
            className="text-sm"
          >
            {chain.available_expiries.map((exp) => (
              <option key={exp} value={exp}>
                {exp}
              </option>
            ))}
          </select>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">
          Loading option chain...
        </div>
      ) : !chain || Object.keys(chain.strikes).length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-gray-500">
          <p className="mb-2">No option chain data available.</p>
          <button
            onClick={handleRefreshInstruments}
            className="text-blue-400 hover:text-blue-300 text-sm"
          >
            Click here to refresh instruments
          </button>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th
                    colSpan={3}
                    className="text-center px-3 py-2.5 text-green-400 font-medium bg-green-500/5"
                  >
                    CALLS (CE)
                  </th>
                  <th className="px-3 py-2.5 text-center font-medium text-gray-400 bg-gray-800/50">
                    Strike
                  </th>
                  <th
                    colSpan={3}
                    className="text-center px-3 py-2.5 text-red-400 font-medium bg-red-500/5"
                  >
                    PUTS (PE)
                  </th>
                </tr>
                <tr className="border-b border-gray-800 text-gray-500 text-xs">
                  <th className="px-3 py-2 text-right bg-green-500/5">LTP</th>
                  <th className="px-3 py-2 text-center bg-green-500/5">
                    Symbol
                  </th>
                  <th className="px-3 py-2 text-center bg-green-500/5">Buy</th>
                  <th className="px-3 py-2 text-center bg-gray-800/50"></th>
                  <th className="px-3 py-2 text-center bg-red-500/5">Buy</th>
                  <th className="px-3 py-2 text-center bg-red-500/5">Symbol</th>
                  <th className="px-3 py-2 text-left bg-red-500/5">LTP</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(chain.strikes).map(([strike, data]) => {
                  const ce = data.CE;
                  const pe = data.PE;
                  const ceLtp = getLtp(ce);
                  const peLtp = getLtp(pe);

                  return (
                    <tr
                      key={strike}
                      className="border-b border-gray-800/50 hover:bg-gray-800/20"
                    >
                      <td className="px-3 py-2 text-right bg-green-500/5 font-mono">
                        {ceLtp != null ? (
                          <span className="text-green-300">
                            {ceLtp.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-gray-600">--</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-center bg-green-500/5 text-xs text-gray-500 truncate max-w-[120px]">
                        {ce?.symbol || "--"}
                      </td>
                      <td className="px-3 py-1.5 text-center bg-green-500/5">
                        {ce && ceLtp ? (
                          <button
                            onClick={() => handleBuy(ce, "CE")}
                            className="inline-flex items-center gap-1 bg-green-600/20 hover:bg-green-600/40 text-green-400 px-2 py-1 rounded text-xs"
                          >
                            <ShoppingCart size={12} />B
                          </button>
                        ) : null}
                      </td>
                      <td className="px-4 py-2 text-center font-bold text-gray-300 bg-gray-800/50">
                        {parseFloat(strike).toFixed(0)}
                      </td>
                      <td className="px-3 py-1.5 text-center bg-red-500/5">
                        {pe && peLtp ? (
                          <button
                            onClick={() => handleBuy(pe, "PE")}
                            className="inline-flex items-center gap-1 bg-red-600/20 hover:bg-red-600/40 text-red-400 px-2 py-1 rounded text-xs"
                          >
                            <ShoppingCart size={12} />B
                          </button>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 text-center bg-red-500/5 text-xs text-gray-500 truncate max-w-[120px]">
                        {pe?.symbol || "--"}
                      </td>
                      <td className="px-3 py-2 text-left bg-red-500/5 font-mono">
                        {peLtp != null ? (
                          <span className="text-red-300">
                            {peLtp.toFixed(2)}
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
