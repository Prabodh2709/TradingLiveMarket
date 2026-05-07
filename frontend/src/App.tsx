import { Routes, Route, Navigate } from "react-router-dom";
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
    return <LoginPage />;
  }

  return (
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
  );
}

export default App;
