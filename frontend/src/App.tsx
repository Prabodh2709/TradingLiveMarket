import { Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { useAppStore } from "./store/useAppStore";
import { useMarketWebSocket } from "./lib/useWebSocket";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import OptionChainPage from "./pages/OptionChainPage";
import PositionsPage from "./pages/PositionsPage";
import TradeHistoryPage from "./pages/TradeHistoryPage";
import ArchivePage from "./pages/ArchivePage";

function App() {
  const isLoggedIn = useAppStore((s) => s.isLoggedIn);
  useMarketWebSocket();

  if (!isLoggedIn) {
    return (
      <>
        <Toaster position="top-right" toastOptions={{ duration: 3000, style: { background: "#1f2937", color: "#f3f4f6", border: "1px solid #374151" } }} />
        <LoginPage />
      </>
    );
  }

  return (
    <>
      <Toaster position="top-right" toastOptions={{ duration: 3000, style: { background: "#1f2937", color: "#f3f4f6", border: "1px solid #374151" } }} />
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/option-chain" element={<OptionChainPage />} />
          <Route path="/positions" element={<PositionsPage />} />
          <Route path="/trades" element={<TradeHistoryPage />} />
          <Route path="/archive" element={<ArchivePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </>
  );
}

export default App;
