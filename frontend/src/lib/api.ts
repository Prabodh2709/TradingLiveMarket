const BASE = "";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  auth: {
    login: (data: { client_code?: string; pin?: string; totp?: string }) =>
      request<{ status: string; data: { client_code: string } }>(
        "/api/auth/login",
        { method: "POST", body: JSON.stringify(data) }
      ),
    status: () =>
      request<{ logged_in: boolean; client_code: string | null }>(
        "/api/auth/status"
      ),
    logout: () =>
      request<{ status: string }>("/api/auth/logout", { method: "POST" }),
  },

  instruments: {
    refresh: () =>
      request<{ status: string; count: number }>(
        "/api/instruments/refresh",
        { method: "POST" }
      ),
    optionChain: (name: string, expiry?: string) => {
      const params = new URLSearchParams({ name });
      if (expiry) params.set("expiry", expiry);
      return request<import("./types").OptionChain>(
        `/api/instruments/option-chain?${params}`
      );
    },
    subscribe: (name: string, expiry: string) =>
      request<{ status: string; tokens_subscribed: number }>(
        `/api/instruments/subscribe?name=${name}&expiry=${expiry}`,
        { method: "POST" }
      ),
  },

  trade: {
    buy: (data: {
      symbol: string;
      token: string;
      name: string;
      strike: number;
      option_type: string;
      expiry: string;
      qty: number;
      price: number;
    }) =>
      request<{ status: string; data: Record<string, unknown> }>(
        "/api/trade/buy",
        { method: "POST", body: JSON.stringify(data) }
      ),
    sellOpen: (data: {
      symbol: string;
      token: string;
      name: string;
      strike: number;
      option_type: string;
      expiry: string;
      qty: number;
      price: number;
    }) =>
      request<{ status: string; data: Record<string, unknown> }>(
        "/api/trade/sell-open",
        { method: "POST", body: JSON.stringify(data) }
      ),
    sell: (data: { token: string; qty: number; price: number }) =>
      request<{ status: string; data: Record<string, unknown> }>(
        "/api/trade/sell",
        { method: "POST", body: JSON.stringify(data) }
      ),
  },

  portfolio: {
    get: () => request<import("./types").Portfolio>("/api/portfolio"),
    positions: () =>
      request<import("./types").Position[]>("/api/portfolio/positions"),
    trades: (limit = 100, offset = 0) =>
      request<{ total: number; trades: import("./types").Trade[] }>(
        `/api/portfolio/trades?limit=${limit}&offset=${offset}`
      ),
  },

  system: {
    reset: () =>
      request<{ status: string; message: string; data: Record<string, unknown> }>(
        "/api/system/reset",
        { method: "POST" }
      ),
    history: () =>
      request<import("./types").HistoryMeta[]>("/api/system/history"),
    historyDetail: (folder: string) =>
      request<import("./types").HistoryDetail>(`/api/system/history/${folder}`),
  },
};
