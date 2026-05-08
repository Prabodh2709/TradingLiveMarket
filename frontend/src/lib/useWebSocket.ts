import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "../store/useAppStore";
import type { TickData } from "./types";

export function useMarketWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const updatePrice = useAppStore((s) => s.updatePrice);
  const setPrices = useAppStore((s) => s.setPrices);
  const isLoggedIn = useAppStore((s) => s.isLoggedIn);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/market-data`);

    ws.onopen = () => {
      console.log("Market data WS connected");
    };

    // #region agent log
    let _dbgTickCount = 0;
    // #endregion
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "tick") {
          // #region agent log
          _dbgTickCount++;
          if (_dbgTickCount <= 3 || _dbgTickCount % 50 === 0) {
            fetch('http://127.0.0.1:7432/ingest/4b8cbc52-306c-4d35-811a-7a74e1cad4e5',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d38668'},body:JSON.stringify({sessionId:'d38668',hypothesisId:'H1',location:'useWebSocket.ts:onmessage',message:'ws_tick_received',data:{token:msg.data?.token,ltp:msg.data?.ltp,best_bid:msg.data?.best_bid,best_ask:msg.data?.best_ask,mid_price: msg.data?.best_bid > 0 && msg.data?.best_ask > 0 ? ((msg.data.best_bid + msg.data.best_ask)/2).toFixed(2) : null,tick_count:_dbgTickCount},timestamp:Date.now()})}).catch(()=>{});
          }
          // #endregion
          updatePrice(msg.data as TickData);
        } else if (msg.type === "snapshot") {
          // #region agent log
          const snapKeys = Object.keys(msg.data || {}).slice(0, 5);
          const snapSample = snapKeys.map(k => ({token: k, ltp: msg.data[k]?.ltp, best_bid: msg.data[k]?.best_bid, best_ask: msg.data[k]?.best_ask}));
          fetch('http://127.0.0.1:7432/ingest/4b8cbc52-306c-4d35-811a-7a74e1cad4e5',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'d38668'},body:JSON.stringify({sessionId:'d38668',hypothesisId:'H1',location:'useWebSocket.ts:onmessage',message:'ws_snapshot_received',data:{total_tokens:Object.keys(msg.data||{}).length,sample:snapSample},timestamp:Date.now()})}).catch(()=>{});
          // #endregion
          setPrices(msg.data);
        }
      } catch {
        // ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      console.log("Market data WS closed, reconnecting in 3s...");
      setTimeout(() => {
        if (isLoggedIn) connect();
      }, 3000);
    };

    wsRef.current = ws;
  }, [updatePrice, setPrices, isLoggedIn]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  useEffect(() => {
    if (isLoggedIn) {
      connect();
    }
    return () => disconnect();
  }, [isLoggedIn, connect, disconnect]);

  return { connect, disconnect };
}
