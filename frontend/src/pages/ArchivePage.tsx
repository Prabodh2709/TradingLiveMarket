import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Archive, ChevronRight, ArrowLeft } from "lucide-react";
import Spinner from "../components/Spinner";
import type { HistoryDetail, HistoryMeta } from "../lib/types";

export default function ArchivePage() {
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);

  const { data: versions, isLoading } = useQuery({
    queryKey: ["history-versions"],
    queryFn: api.system.history,
  });

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ["history-detail", selectedFolder],
    queryFn: () => api.system.historyDetail(selectedFolder!),
    enabled: !!selectedFolder,
  });

  if (selectedFolder && detailLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size={24} label="Loading session details..." />
      </div>
    );
  }

  if (selectedFolder && detail) {
    return <VersionDetail detail={detail} onBack={() => setSelectedFolder(null)} />;
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Archived Sessions</h2>

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <Spinner size={24} label="Loading archives..." />
        </div>
      ) : !versions || versions.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center text-gray-500">
          <Archive size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-lg mb-1">No archived sessions</p>
          <p className="text-sm">
            When you reset the system, previous sessions will be saved here.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {versions.map((v: HistoryMeta) => {
            const resetDate = new Date(v.reset_timestamp);
            return (
              <button
                key={v.folder}
                onClick={() => setSelectedFolder(v.folder)}
                className="w-full bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center justify-between hover:border-gray-700 transition-colors text-left"
              >
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded font-medium">
                      v{v.version}
                    </span>
                    <span className="text-sm text-gray-400">
                      {resetDate.toLocaleDateString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                      })}{" "}
                      {resetDate.toLocaleTimeString("en-IN", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-500">
                      Final: &#8377;{v.final_balance.toLocaleString("en-IN")}
                    </span>
                    <span
                      className={
                        v.total_pnl >= 0 ? "text-green-400" : "text-red-400"
                      }
                    >
                      P&L: {v.total_pnl >= 0 ? "+" : ""}&#8377;
                      {v.total_pnl.toLocaleString("en-IN")}
                    </span>
                    <span className="text-gray-500">
                      {v.total_trades} trades
                    </span>
                  </div>
                </div>
                <ChevronRight size={18} className="text-gray-600" />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function VersionDetail({
  detail,
  onBack,
}: {
  detail: HistoryDetail;
  onBack: () => void;
}) {
  const meta = detail.meta;

  return (
    <div>
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-gray-400 hover:text-gray-200 text-sm mb-4"
      >
        <ArrowLeft size={16} />
        Back to Archives
      </button>

      <div className="flex items-center gap-3 mb-6">
        <h2 className="text-xl font-semibold">Session v{meta.version}</h2>
        <span className="text-sm text-gray-500">
          Reset on{" "}
          {new Date(meta.reset_timestamp).toLocaleString("en-IN")}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <span className="text-sm text-gray-500">Final Balance</span>
          <div className="text-xl font-bold mt-1">
            &#8377;{meta.final_balance.toLocaleString("en-IN")}
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <span className="text-sm text-gray-500">Total P&L</span>
          <div
            className={`text-xl font-bold mt-1 ${
              meta.total_pnl >= 0 ? "text-green-400" : "text-red-400"
            }`}
          >
            {meta.total_pnl >= 0 ? "+" : ""}&#8377;
            {meta.total_pnl.toLocaleString("en-IN")}
          </div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <span className="text-sm text-gray-500">Total Trades</span>
          <div className="text-xl font-bold mt-1">{meta.total_trades}</div>
        </div>
      </div>

      {detail.trades.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-800">
            <h3 className="text-sm font-medium text-gray-400">Trades</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left px-5 py-2 font-medium">Time</th>
                  <th className="text-left px-5 py-2 font-medium">Action</th>
                  <th className="text-left px-5 py-2 font-medium">Symbol</th>
                  <th className="text-right px-5 py-2 font-medium">Lots</th>
                  <th className="text-right px-5 py-2 font-medium">Price</th>
                  <th className="text-right px-5 py-2 font-medium">P&L</th>
                </tr>
              </thead>
              <tbody>
                {detail.trades.map((t, i) => (
                  <tr
                    key={i}
                    className="border-b border-gray-800/50 hover:bg-gray-800/30"
                  >
                    <td className="px-5 py-2 text-xs text-gray-400">
                      {new Date(t.timestamp).toLocaleString("en-IN", {
                        day: "2-digit",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-5 py-2">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          t.action === "BUY"
                            ? "bg-blue-500/10 text-blue-400"
                            : "bg-orange-500/10 text-orange-400"
                        }`}
                      >
                        {t.action}
                      </span>
                    </td>
                    <td className="px-5 py-2">{t.symbol}</td>
                    <td className="text-right px-5 py-2">{t.qty}</td>
                    <td className="text-right px-5 py-2 font-mono">
                      &#8377;{t.price.toFixed(2)}
                    </td>
                    <td className="text-right px-5 py-2 font-mono">
                      {t.pnl != null ? (
                        <span
                          className={
                            t.pnl >= 0 ? "text-green-400" : "text-red-400"
                          }
                        >
                          {t.pnl >= 0 ? "+" : ""}&#8377;{t.pnl.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-gray-600">--</span>
                      )}
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
