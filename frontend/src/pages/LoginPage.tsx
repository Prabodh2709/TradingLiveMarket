import { useState } from "react";
import { api } from "../lib/api";
import { useAppStore } from "../store/useAppStore";
import { TrendingUp } from "lucide-react";

export default function LoginPage() {
  const setLoggedIn = useAppStore((s) => s.setLoggedIn);
  const [clientCode, setClientCode] = useState("");
  const [pin, setPin] = useState("");
  const [totp, setTotp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.auth.login({
        client_code: clientCode,
        pin,
        totp,
      });
      setLoggedIn(true, res.data.client_code);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-blue-500/10 rounded-2xl mb-4">
            <TrendingUp size={28} className="text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold">PaperTrader</h1>
          <p className="text-gray-500 text-sm mt-1">
            Nifty & BankNifty Options Paper Trading
          </p>
        </div>

        <form
          onSubmit={handleLogin}
          className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4"
        >
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 text-sm text-red-400">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1.5">
              Client Code
            </label>
            <input
              type="text"
              value={clientCode}
              onChange={(e) => setClientCode(e.target.value)}
              placeholder="Your Angel One client code"
              className="w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1.5">
              PIN
            </label>
            <input
              type="password"
              value={pin}
              onChange={(e) => setPin(e.target.value)}
              placeholder="Your trading PIN"
              className="w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1.5">
              TOTP
            </label>
            <input
              type="text"
              value={totp}
              onChange={(e) => setTotp(e.target.value)}
              placeholder="Leave blank for auto-generate"
              className="w-full"
            />
            <p className="text-xs text-gray-600 mt-1">
              Auto-generated from .env if TOTP secret is set
            </p>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-medium mt-2"
          >
            {loading ? "Connecting..." : "Connect to Angel One"}
          </button>
        </form>

        <p className="text-center text-xs text-gray-600 mt-4">
          Paper trading only. No real orders will be placed.
        </p>
      </div>
    </div>
  );
}
