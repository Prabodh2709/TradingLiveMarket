import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import { useQueryClient } from "@tanstack/react-query";

interface Props {
  onClose: () => void;
}

export default function ResetModal({ onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const queryClient = useQueryClient();

  const handleReset = async () => {
    setLoading(true);
    try {
      await api.system.reset();
      setDone(true);
      queryClient.invalidateQueries();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-md w-full mx-4">
        {done ? (
          <>
            <h2 className="text-lg font-semibold text-green-400 mb-2">
              Reset Complete
            </h2>
            <p className="text-gray-400 text-sm mb-4">
              Your previous session has been archived. The system has been reset
              to the initial balance.
            </p>
            <button
              onClick={onClose}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 text-sm font-medium"
            >
              Continue
            </button>
          </>
        ) : (
          <>
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-amber-500/10 rounded-lg">
                <AlertTriangle size={24} className="text-amber-400" />
              </div>
              <h2 className="text-lg font-semibold">Reset System</h2>
            </div>
            <p className="text-gray-400 text-sm mb-2">
              This will archive your current trading session and reset the
              system:
            </p>
            <ul className="text-sm text-gray-500 list-disc list-inside mb-6 space-y-1">
              <li>All open positions will be closed</li>
              <li>Trade history will be archived with a version number</li>
              <li>Balance will reset to &#8377;7,00,000</li>
            </ul>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg py-2.5 text-sm font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleReset}
                disabled={loading}
                className="flex-1 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white rounded-lg py-2.5 text-sm font-medium"
              >
                {loading ? "Resetting..." : "Confirm Reset"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
