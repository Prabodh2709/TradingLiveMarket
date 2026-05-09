import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "../store/useAppStore";
import type { TickData } from "./types";

export function useMarketWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const updatePrice = useAppStore((s) => s.updatePrice);
  const setPrices = useAppStore((s) => s.setPrices);
  const mergePrices = useAppStore((s) => s.mergePrices);
  const isLoggedIn = useAppStore((s) => s.isLoggedIn);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/market-data`);

    ws.onopen = () => {
      console.log("Market data WS connected");
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "batch") {
          mergePrices(msg.data as Record<string, TickData>);
        } else if (msg.type === "tick") {
          updatePrice(msg.data as TickData);
        } else if (msg.type === "snapshot") {
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
  }, [updatePrice, setPrices, mergePrices, isLoggedIn]);

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
