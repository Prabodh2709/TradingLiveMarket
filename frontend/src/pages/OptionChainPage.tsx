import { useEffect, useState, useCallback, useMemo, useRef } from "react";
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
    if (!chain) return;
    const price = getLtp(contract);
    if (!price) {
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
        price,
      });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    } catch (err) {
      alert(err instanceof Error ? err.message : "Buy failed");
    }
  };

  const getLtp = (contract: OptionContract | undefined): number | null => {
    if (!contract) return null;
    const wsPrice = prices[contract.token];
    if (wsPrice) {
      return wsPrice.ltp;
    }
    return contract.ltp;
  };

  const getOi = (contract: OptionContract | undefined): number | null => {
    if (!contract) return null;
    const wsPrice = prices[contract.token];
    return wsPrice?.oi ?? null;
  };

  const spotPrice = chain
    ? prices[chain.index_token]?.ltp ?? chain.spot_price
    : null;

  const atmStrike = useMemo(() => {
    if (!spotPrice || !chain) return null;
    const strikes = Object.keys(chain.strikes).map(Number);
    if (strikes.length === 0) return null;
    return strikes.reduce((prev, curr) =>
      Math.abs(curr - spotPrice) < Math.abs(prev - spotPrice) ? curr : prev
    );
  }, [spotPrice, chain]);

  const atmRowRef = useRef<HTMLTableRowElement>(null);
  const hasScrolled = useRef(false);

  useEffect(() => {
    if (atmRowRef.current && !hasScrolled.current) {
      atmRowRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
      hasScrolled.current = true;
    }
  }, [atmStrike]);

  useEffect(() => {
    hasScrolled.current = false;
  }, [selectedIndex, selectedExpiry]);

  // #region agent log
  useEffect(() => {
    if (!chain) return;
    const allEntries = Object.entries(chain.strikes);
    const mid = Math.floor(allEntries.length / 2);
    const atmEntries = allEntries.slice(Math.max(0, mid - 3), mid + 3);
    const firstEntries = allEntries.slice(0, 2);
    const sampleEntries = [...firstEntries, ...atmEntries];
    const samples = sampleEntries.map(([strike, data]) => {
      const ceWs = data.CE ? prices[data.CE.token] : null;
      const peWs = data.PE ? prices[data.PE.token] : null;
      const ceMid = ceWs && ceWs.best_bid > 0 && ceWs.best_ask > 0 ? (ceWs.best_bid + ceWs.best_ask) / 2 : null;
      const peMid = peWs && peWs.best_bid > 0 && peWs.best_ask > 0 ? (peWs.best_bid + peWs.best_ask) / 2 : null;
      const ceDisplayed = getLtp(data.CE);
      const peDisplayed = getLtp(data.PE);
      return {
        strike,
        ce_actual_ltp: ceWs?.ltp, ce_mid: ceMid?.toFixed(2), ce_displayed: ceDisplayed?.toFixed(2), ce_ltp_vs_mid_diff: ceMid && ceWs?.ltp ? (ceMid - ceWs.ltp).toFixed(2) : null,
        pe_actual_ltp: peWs?.ltp, pe_mid: peMid?.toFixed(2), pe_displayed: peDisplayed?.toFixed(2), pe_ltp_vs_mid_diff: peMid && peWs?.ltp ? (peMid - peWs.ltp).toFixed(2) : null,
        ce_oi: ceWs?.oi, pe_oi: peWs?.oi,
      };
    });
    if (Object.keys(prices).length > 100) {
      fetch('http://127.0.0.1:7432/ingest/4b8cbc52-306c-4d35-811a-7a74e1cad4e5',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d38668'},body:JSON.stringify({sessionId:'d38668',hypothesisId:'H1',location:'OptionChainPage.tsx',message:'ltp_vs_midprice_comparison',data:{total_strikes:allEntries.length,sample_strikes:samples,total_price_entries:Object.keys(prices).length},timestamp:Date.now()})}).catch(()=>{});
    }
  }, [chain, prices]);
  // #endregion

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

        {spotPrice != null && (
          <div className="ml-auto flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-1.5">
            <span className="text-xs text-gray-500">SPOT</span>
            <span className="text-sm font-semibold text-yellow-300 font-mono">
              {spotPrice.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
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
          <div className="overflow-auto max-h-[calc(100vh-220px)]">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-gray-900">
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
                  <th className="px-2 py-2 text-right bg-green-500/5">OI</th>
                  <th className="px-2 py-2 text-right bg-green-500/5">LTP</th>
                  <th className="px-2 py-2 text-center bg-green-500/5">Buy</th>
                  <th className="px-3 py-2 text-center bg-gray-800/50"></th>
                  <th className="px-2 py-2 text-center bg-red-500/5">Buy</th>
                  <th className="px-2 py-2 text-left bg-red-500/5">LTP</th>
                  <th className="px-2 py-2 text-left bg-red-500/5">OI</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(chain.strikes).map(([strike, data]) => {
                  const ce = data.CE;
                  const pe = data.PE;
                  const cePrice = getLtp(ce);
                  const pePrice = getLtp(pe);
                  const ceOi = getOi(ce);
                  const peOi = getOi(pe);
                  const isAtm = atmStrike != null && parseFloat(strike) === atmStrike;

                  const formatOi = (oi: number | null) => {
                    if (oi == null || oi === 0) return "--";
                    if (oi >= 10000000) return (oi / 10000000).toFixed(2) + " Cr";
                    if (oi >= 100000) return (oi / 100000).toFixed(2) + " L";
                    if (oi >= 1000) return (oi / 1000).toFixed(1) + "K";
                    return oi.toString();
                  };

                  return (
                    <tr
                      key={strike}
                      ref={isAtm ? atmRowRef : undefined}
                      className={`border-b border-gray-800/50 hover:bg-gray-800/20 ${
                        isAtm ? "bg-yellow-500/10 ring-1 ring-inset ring-yellow-500/30" : ""
                      }`}
                    >
                      <td className="px-2 py-2 text-right bg-green-500/5 text-xs text-gray-500 font-mono">
                        {formatOi(ceOi)}
                      </td>
                      <td className="px-2 py-2 text-right bg-green-500/5 font-mono">
                        {cePrice != null ? (
                          <span className="text-green-300">
                            {cePrice.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-gray-600">--</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 text-center bg-green-500/5">
                        {ce && cePrice ? (
                          <button
                            onClick={() => handleBuy(ce, "CE")}
                            className="inline-flex items-center gap-1 bg-green-600/20 hover:bg-green-600/40 text-green-400 px-2 py-1 rounded text-xs"
                          >
                            <ShoppingCart size={12} />B
                          </button>
                        ) : null}
                      </td>
                      <td className={`px-4 py-2 text-center font-bold bg-gray-800/50 ${
                        isAtm ? "text-yellow-300" : "text-gray-300"
                      }`}>
                        {parseFloat(strike).toFixed(0)}
                        {isAtm && <span className="ml-1 text-[10px] text-yellow-400/70 font-normal">ATM</span>}
                      </td>
                      <td className="px-2 py-1.5 text-center bg-red-500/5">
                        {pe && pePrice ? (
                          <button
                            onClick={() => handleBuy(pe, "PE")}
                            className="inline-flex items-center gap-1 bg-red-600/20 hover:bg-red-600/40 text-red-400 px-2 py-1 rounded text-xs"
                          >
                            <ShoppingCart size={12} />B
                          </button>
                        ) : null}
                      </td>
                      <td className="px-2 py-2 text-left bg-red-500/5 font-mono">
                        {pePrice != null ? (
                          <span className="text-red-300">
                            {pePrice.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-gray-600">--</span>
                        )}
                      </td>
                      <td className="px-2 py-2 text-left bg-red-500/5 text-xs text-gray-500 font-mono">
                        {formatOi(peOi)}
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
