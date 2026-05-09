import { useEffect, useState, useCallback, useMemo, useRef, memo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { api } from "../lib/api";
import { useAppStore } from "../store/useAppStore";
import { RefreshCw, ShoppingCart, TrendingDown, Loader2 } from "lucide-react";
import type { OptionContract, TickData } from "../lib/types";

const LOT_SIZES: Record<string, number> = { NIFTY: 65, BANKNIFTY: 30 };

function formatOi(oi: number | null) {
  if (oi == null || oi === 0) return "--";
  if (oi >= 10000000) return (oi / 10000000).toFixed(2) + " Cr";
  if (oi >= 100000) return (oi / 100000).toFixed(2) + " L";
  if (oi >= 1000) return (oi / 1000).toFixed(1) + "K";
  return oi.toString();
}

function getLtpFromTick(
  contract: OptionContract | undefined,
  tick: TickData | undefined,
): number | null {
  if (!contract) return null;
  if (tick) return tick.ltp;
  return contract.ltp;
}

interface StrikeRowProps {
  strike: string;
  ce: OptionContract | undefined;
  pe: OptionContract | undefined;
  isAtm: boolean;
  pendingAction: string | null;
  onBuy: (contract: OptionContract, optionType: "CE" | "PE") => void;
  onSell: (contract: OptionContract, optionType: "CE" | "PE") => void;
  atmRowRef: React.RefObject<HTMLTableRowElement | null>;
}

const StrikeRow = memo(function StrikeRow({
  strike,
  ce,
  pe,
  isAtm,
  pendingAction,
  onBuy,
  onSell,
  atmRowRef,
}: StrikeRowProps) {
  const ceTick = useAppStore((s) => (ce ? s.prices[ce.token] : undefined));
  const peTick = useAppStore((s) => (pe ? s.prices[pe.token] : undefined));

  const cePrice = getLtpFromTick(ce, ceTick);
  const pePrice = getLtpFromTick(pe, peTick);
  const ceOi = ceTick?.oi ?? null;
  const peOi = peTick?.oi ?? null;

  return (
    <tr
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
          <span className="text-green-300">{cePrice.toFixed(2)}</span>
        ) : (
          <span className="text-gray-600">--</span>
        )}
      </td>
      <td className="px-1 py-1.5 text-center bg-green-500/5">
        {ce && cePrice ? (
          <button
            onClick={() => onBuy(ce, "CE")}
            disabled={!!pendingAction}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
              pendingAction === `buy-${ce.token}`
                ? "bg-green-600/40 text-green-300"
                : pendingAction
                ? "bg-green-600/10 text-green-600 cursor-not-allowed"
                : "bg-green-600/20 hover:bg-green-600/40 text-green-400"
            }`}
            title="Buy CE"
          >
            {pendingAction === `buy-${ce.token}` ? (
              <Loader2 size={11} className="animate-spin" />
            ) : (
              <ShoppingCart size={11} />
            )}
            B
          </button>
        ) : null}
      </td>
      <td className="px-1 py-1.5 text-center bg-green-500/5">
        {ce && cePrice ? (
          <button
            onClick={() => onSell(ce, "CE")}
            disabled={!!pendingAction}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
              pendingAction === `sell-${ce.token}`
                ? "bg-orange-600/40 text-orange-300"
                : pendingAction
                ? "bg-orange-600/10 text-orange-600 cursor-not-allowed"
                : "bg-orange-600/20 hover:bg-orange-600/40 text-orange-400"
            }`}
            title="Sell CE"
          >
            {pendingAction === `sell-${ce.token}` ? (
              <Loader2 size={11} className="animate-spin" />
            ) : (
              <TrendingDown size={11} />
            )}
            S
          </button>
        ) : null}
      </td>
      <td
        className={`px-4 py-2 text-center font-bold bg-gray-800/50 ${
          isAtm ? "text-yellow-300" : "text-gray-300"
        }`}
      >
        {parseFloat(strike).toFixed(0)}
        {isAtm && (
          <span className="ml-1 text-[10px] text-yellow-400/70 font-normal">
            ATM
          </span>
        )}
      </td>
      <td className="px-1 py-1.5 text-center bg-red-500/5">
        {pe && pePrice ? (
          <button
            onClick={() => onBuy(pe, "PE")}
            disabled={!!pendingAction}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
              pendingAction === `buy-${pe.token}`
                ? "bg-red-600/40 text-red-300"
                : pendingAction
                ? "bg-red-600/10 text-red-600 cursor-not-allowed"
                : "bg-red-600/20 hover:bg-red-600/40 text-red-400"
            }`}
            title="Buy PE"
          >
            {pendingAction === `buy-${pe.token}` ? (
              <Loader2 size={11} className="animate-spin" />
            ) : (
              <ShoppingCart size={11} />
            )}
            B
          </button>
        ) : null}
      </td>
      <td className="px-1 py-1.5 text-center bg-red-500/5">
        {pe && pePrice ? (
          <button
            onClick={() => onSell(pe, "PE")}
            disabled={!!pendingAction}
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
              pendingAction === `sell-${pe.token}`
                ? "bg-orange-600/40 text-orange-300"
                : pendingAction
                ? "bg-orange-600/10 text-orange-600 cursor-not-allowed"
                : "bg-orange-600/20 hover:bg-orange-600/40 text-orange-400"
            }`}
            title="Sell PE"
          >
            {pendingAction === `sell-${pe.token}` ? (
              <Loader2 size={11} className="animate-spin" />
            ) : (
              <TrendingDown size={11} />
            )}
            S
          </button>
        ) : null}
      </td>
      <td className="px-2 py-2 text-left bg-red-500/5 font-mono">
        {pePrice != null ? (
          <span className="text-red-300">{pePrice.toFixed(2)}</span>
        ) : (
          <span className="text-gray-600">--</span>
        )}
      </td>
      <td className="px-2 py-2 text-left bg-red-500/5 text-xs text-gray-500 font-mono">
        {formatOi(peOi)}
      </td>
    </tr>
  );
});

export default function OptionChainPage() {
  const queryClient = useQueryClient();
  const selectedIndex = useAppStore((s) => s.selectedIndex);
  const setSelectedIndex = useAppStore((s) => s.setSelectedIndex);
  const selectedExpiry = useAppStore((s) => s.selectedExpiry);
  const setSelectedExpiry = useAppStore((s) => s.setSelectedExpiry);

  const [refreshing, setRefreshing] = useState(false);
  const [buyQty, setBuyQty] = useState(1);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const {
    data: chain,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["option-chain", selectedIndex, selectedExpiry],
    queryFn: () =>
      api.instruments.optionChain(selectedIndex, selectedExpiry || undefined),
    enabled: true,
    retry: 2,
    retryDelay: 1000,
    staleTime: 5 * 60 * 1000,
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
      toast.error(err instanceof Error ? err.message : "Refresh failed");
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

  const handleBuy = useCallback(
    async (contract: OptionContract, optionType: "CE" | "PE") => {
      if (!chain || pendingAction) return;
      const prices = useAppStore.getState().prices;
      const tick = prices[contract.token];
      const price = tick ? tick.ltp : contract.ltp;
      if (!price) {
        toast.error("No live price available");
        return;
      }
      const strikeVal = parseFloat(
        Object.entries(chain.strikes).find(
          ([, s]) => s[optionType]?.token === contract.token,
        )?.[0] || "0",
      );
      const actionKey = `buy-${contract.token}`;
      setPendingAction(actionKey);
      try {
        await api.trade.buy({
          symbol: contract.symbol,
          token: contract.token,
          name: selectedIndex,
          strike: strikeVal,
          option_type: optionType,
          expiry: chain.expiry,
          qty: buyQty,
          price,
        });
        queryClient.invalidateQueries({ queryKey: ["portfolio"] });
        toast.success(`Bought ${buyQty} lot(s) of ${contract.symbol}`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Buy failed");
      } finally {
        setPendingAction(null);
      }
    },
    [chain, pendingAction, selectedIndex, buyQty, queryClient],
  );

  const handleSell = useCallback(
    async (contract: OptionContract, optionType: "CE" | "PE") => {
      if (!chain || pendingAction) return;
      const prices = useAppStore.getState().prices;
      const tick = prices[contract.token];
      const price =
        tick?.best_bid > 0
          ? tick.best_bid
          : tick
          ? tick.ltp
          : contract.ltp;
      if (!price) {
        toast.error("No live price available");
        return;
      }
      const strikeVal = parseFloat(
        Object.entries(chain.strikes).find(
          ([, s]) => s[optionType]?.token === contract.token,
        )?.[0] || "0",
      );
      const actionKey = `sell-${contract.token}`;
      setPendingAction(actionKey);
      try {
        await api.trade.sellOpen({
          symbol: contract.symbol,
          token: contract.token,
          name: selectedIndex,
          strike: strikeVal,
          option_type: optionType,
          expiry: chain.expiry,
          qty: buyQty,
          price,
        });
        queryClient.invalidateQueries({ queryKey: ["portfolio"] });
        toast.success(`Sold ${buyQty} lot(s) of ${contract.symbol}`);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Sell failed");
      } finally {
        setPendingAction(null);
      }
    },
    [chain, pendingAction, selectedIndex, buyQty, queryClient],
  );

  const spotPrice = useAppStore((s) =>
    chain ? (s.prices[chain.index_token]?.ltp ?? chain.spot_price) : null,
  );

  const atmStrike = useMemo(() => {
    if (!spotPrice || !chain) return null;
    const strikes = Object.keys(chain.strikes).map(Number);
    if (strikes.length === 0) return null;
    return strikes.reduce((prev, curr) =>
      Math.abs(curr - spotPrice) < Math.abs(prev - spotPrice) ? curr : prev,
    );
  }, [spotPrice, chain]);

  const atmRowRef = useRef<HTMLTableRowElement>(null);
  const hasScrolled = useRef(false);

  useEffect(() => {
    if (atmRowRef.current && !hasScrolled.current) {
      atmRowRef.current.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
      hasScrolled.current = true;
    }
  }, [atmStrike]);

  useEffect(() => {
    hasScrolled.current = false;
  }, [selectedIndex, selectedExpiry]);

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
              onChange={(e) =>
                setBuyQty(Math.max(1, parseInt(e.target.value) || 1))
              }
              className="w-16 text-center text-sm"
            />
            <span className="text-gray-600 text-xs font-mono">
              = {buyQty * (LOT_SIZES[selectedIndex] ?? 25)} qty
            </span>
          </div>
          <button
            onClick={handleRefreshInstruments}
            disabled={refreshing}
            className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-2 rounded-lg text-sm"
          >
            <RefreshCw
              size={14}
              className={refreshing ? "animate-spin" : ""}
            />
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
              {spotPrice.toLocaleString("en-IN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">
          <Loader2 size={24} className="animate-spin mr-3" />
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
                    colSpan={4}
                    className="text-center px-3 py-2.5 text-green-400 font-medium bg-green-500/5"
                  >
                    CALLS (CE)
                  </th>
                  <th className="px-3 py-2.5 text-center font-medium text-gray-400 bg-gray-800/50">
                    Strike
                  </th>
                  <th
                    colSpan={4}
                    className="text-center px-3 py-2.5 text-red-400 font-medium bg-red-500/5"
                  >
                    PUTS (PE)
                  </th>
                </tr>
                <tr className="border-b border-gray-800 text-gray-500 text-xs">
                  <th className="px-2 py-2 text-right bg-green-500/5">OI</th>
                  <th className="px-2 py-2 text-right bg-green-500/5">LTP</th>
                  <th className="px-2 py-2 text-center bg-green-500/5">B</th>
                  <th className="px-2 py-2 text-center bg-green-500/5">S</th>
                  <th className="px-3 py-2 text-center bg-gray-800/50"></th>
                  <th className="px-2 py-2 text-center bg-red-500/5">B</th>
                  <th className="px-2 py-2 text-center bg-red-500/5">S</th>
                  <th className="px-2 py-2 text-left bg-red-500/5">LTP</th>
                  <th className="px-2 py-2 text-left bg-red-500/5">OI</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(chain.strikes).map(([strike, data]) => (
                  <StrikeRow
                    key={strike}
                    strike={strike}
                    ce={data.CE}
                    pe={data.PE}
                    isAtm={
                      atmStrike != null &&
                      parseFloat(strike) === atmStrike
                    }
                    pendingAction={pendingAction}
                    onBuy={handleBuy}
                    onSell={handleSell}
                    atmRowRef={atmRowRef}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
