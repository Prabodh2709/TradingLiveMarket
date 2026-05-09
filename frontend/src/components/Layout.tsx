import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Table2,
  Briefcase,
  History,
  Archive,
  LogOut,
  RotateCcw,
  Loader2,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { useAppStore } from "../store/useAppStore";
import { api } from "../lib/api";
import ResetModal from "./ResetModal";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/option-chain", label: "Option Chain", icon: Table2 },
  { to: "/positions", label: "Positions", icon: Briefcase },
  { to: "/trades", label: "Trade History", icon: History },
  { to: "/archive", label: "Archives", icon: Archive },
];

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const setLoggedIn = useAppStore((s) => s.setLoggedIn);
  const clientCode = useAppStore((s) => s.clientCode);
  const [showReset, setShowReset] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await api.auth.logout();
    } catch {
      // proceed anyway
    }
    setLoggedIn(false);
    setLoggingOut(false);
  };

  return (
    <div className="flex h-screen">
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <h1 className="text-lg font-bold text-blue-400">PaperTrader</h1>
          <p className="text-xs text-gray-500 mt-0.5">{clientCode}</p>
        </div>

        <nav className="flex-1 py-3">
          {NAV.map((item) => {
            const active = location.pathname === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  active
                    ? "bg-blue-500/10 text-blue-400 border-r-2 border-blue-400"
                    : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                }`}
              >
                <item.icon size={18} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t border-gray-800 space-y-2">
          <button
            onClick={() => setShowReset(true)}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-amber-400 hover:bg-amber-500/10 rounded-lg"
          >
            <RotateCcw size={16} />
            Reset System
          </button>
          <button
            onClick={handleLogout}
            disabled={loggingOut}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loggingOut ? <Loader2 size={16} className="animate-spin" /> : <LogOut size={16} />}
            {loggingOut ? "Logging out..." : "Logout"}
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto p-6">{children}</main>

      {showReset && <ResetModal onClose={() => setShowReset(false)} />}
    </div>
  );
}
