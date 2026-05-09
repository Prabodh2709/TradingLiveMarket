import { create } from "zustand";
import type { Portfolio, OptionChain, TickData } from "../lib/types";

interface AppState {
  isLoggedIn: boolean;
  clientCode: string | null;
  setLoggedIn: (loggedIn: boolean, clientCode?: string) => void;

  portfolio: Portfolio | null;
  setPortfolio: (p: Portfolio) => void;

  optionChain: OptionChain | null;
  setOptionChain: (oc: OptionChain) => void;

  selectedIndex: "NIFTY" | "BANKNIFTY";
  setSelectedIndex: (idx: "NIFTY" | "BANKNIFTY") => void;

  selectedExpiry: string;
  setSelectedExpiry: (exp: string) => void;

  prices: Record<string, TickData>;
  updatePrice: (tick: TickData) => void;
  setPrices: (snapshot: Record<string, TickData>) => void;
  mergePrices: (batch: Record<string, TickData>) => void;
}

export const useAppStore = create<AppState>((set) => ({
  isLoggedIn: false,
  clientCode: null,
  setLoggedIn: (loggedIn, clientCode) =>
    set({ isLoggedIn: loggedIn, clientCode: clientCode ?? null }),

  portfolio: null,
  setPortfolio: (p) => set({ portfolio: p }),

  optionChain: null,
  setOptionChain: (oc) => set({ optionChain: oc }),

  selectedIndex: "NIFTY",
  setSelectedIndex: (idx) => set({ selectedIndex: idx }),

  selectedExpiry: "",
  setSelectedExpiry: (exp) => set({ selectedExpiry: exp }),

  prices: {},
  updatePrice: (tick) =>
    set((state) => ({
      prices: { ...state.prices, [tick.token]: tick },
    })),
  setPrices: (snapshot) => set({ prices: snapshot }),
  mergePrices: (batch) =>
    set((state) => ({
      prices: { ...state.prices, ...batch },
    })),
}));
