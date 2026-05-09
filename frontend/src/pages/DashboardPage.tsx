import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useAppStore } from "../store/useAppStore";
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Briefcase,
  Loader2,
} from "lucide-react";

function formatCurrency(val: number): string {
  const abs = Math.abs(val);
  if (abs >= 10000000) return `${(val / 10000000).toFixed(2)} Cr`;
  if (abs >= 100000) return `${(val / 100000).toFixed(2)} L`;
  return val.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function PnlText({ value }: { value: number }) {
  const color =
    value > 0 ? "text-green-400" : value < 0 ? "text-red-400" : "text-gray-400";
  const prefix = value > 0 ? "+" : "";
  return (
    <span className={color}>
      {prefix}&#8377;{formatCurrency(value)}
    </span>
  );
}

export default function DashboardPage() {
  const setPortfolio = useAppStore((s) => s.setPortfolio);

  const { data: portfolio, isLoading } = useQuery({
    queryKey: ["portfolio"],
    queryFn: api.portfolio.get,
    refetchInterval: 5000,
  });

  useEffect(() => {
    if (portfolio) setPortfolio(portfolio);
  }, [portfolio, setPortfolio]);

  if (isLoading || !portfolio) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        <Loader2 size={24} className="animate-spin mr-3" />
        Loading portfolio...
      </div>
    );
  }

  const cards = [
    {
      label: "Balance",
      value: `\u20B9${formatCurrency(portfolio.balance)}`,
      icon: Wallet,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
    },
    {
      label: "Total P&L",
      value: portfolio.total_pnl,
      isPnl: true,
      icon: portfolio.total_pnl >= 0 ? TrendingUp : TrendingDown,
      color: portfolio.total_pnl >= 0 ? "text-green-400" : "text-red-400",
      bg:
        portfolio.total_pnl >= 0
          ? "bg-green-500/10"
          : "bg-red-500/10",
    },
    {
      label: "Realized P&L",
      value: portfolio.realized_pnl,
      isPnl: true,
      icon: BarChart3,
      color: portfolio.realized_pnl >= 0 ? "text-green-400" : "text-red-400",
      bg:
        portfolio.realized_pnl >= 0
          ? "bg-green-500/10"
          : "bg-red-500/10",
    },
    {
      label: "Open Positions",
      value: String(portfolio.position_count),
      icon: Briefcase,
      color: "text-purple-400",
      bg: "bg-purple-500/10",
    },
  ];

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Dashboard</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {cards.map((card) => (
          <div
            key={card.label}
            className="bg-gray-900 border border-gray-800 rounded-xl p-5"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-gray-500">{card.label}</span>
              <div className={`p-2 rounded-lg ${card.bg}`}>
                <card.icon size={18} className={card.color} />
              </div>
            </div>
            <div className="text-2xl font-bold">
              {card.isPnl ? (
                <PnlText value={card.value as number} />
              ) : (
                <span className={card.color}>{card.value as string}</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h3 className="text-sm font-medium text-gray-400 mb-1">
          Return on Capital
        </h3>
        <div className="flex items-baseline gap-2">
          <span
            className={`text-3xl font-bold ${
              portfolio.total_return_pct >= 0
                ? "text-green-400"
                : "text-red-400"
            }`}
          >
            {portfolio.total_return_pct >= 0 ? "+" : ""}
            {portfolio.total_return_pct.toFixed(2)}%
          </span>
          <span className="text-sm text-gray-600">
            on &#8377;{formatCurrency(portfolio.initial_balance)}
          </span>
        </div>
      </div>

      {portfolio.positions.length > 0 && (
        <div className="mt-6 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-800">
            <h3 className="text-sm font-medium text-gray-400">
              Open Positions
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 border-b border-gray-800">
                  <th className="text-left px-5 py-2.5 font-medium">Symbol</th>
                  <th className="text-right px-5 py-2.5 font-medium">Qty</th>
                  <th className="text-right px-5 py-2.5 font-medium">
                    Avg Price
                  </th>
                  <th className="text-right px-5 py-2.5 font-medium">LTP</th>
                  <th className="text-right px-5 py-2.5 font-medium">P&L</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.positions.map((pos) => (
                  <tr
                    key={pos.id}
                    className="border-b border-gray-800/50 hover:bg-gray-800/30"
                  >
                    <td className="px-5 py-3">
                      <span className="font-medium">{pos.name}</span>{" "}
                      <span className="text-gray-500">
                        {pos.strike} {pos.option_type}
                      </span>
                    </td>
                    <td className="text-right px-5 py-3">{pos.qty}L</td>
                    <td className="text-right px-5 py-3">
                      &#8377;{pos.avg_price.toFixed(2)}
                    </td>
                    <td className="text-right px-5 py-3">
                      &#8377;{pos.current_price.toFixed(2)}
                    </td>
                    <td className="text-right px-5 py-3">
                      <PnlText value={pos.unrealized_pnl} />
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
