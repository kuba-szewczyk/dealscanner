const BASE = process.env.NEXT_PUBLIC_API ?? "http://localhost:8099";

async function get(path: string) {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store", credentials: "include" });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}

export const api = {
  accounts: () => get("/accounts"),
  board: (account: string, sections = "in", limit = 100) =>
    get(`/board?account=${account}&sections=${sections}&limit=${limit}`),
  settings: (account: string) => get(`/settings/${account}`),
  runs: () => get("/runs"),
  brokers: () => get("/brokers"),
  logs: () => get("/logs"),
  instinct: () => get("/instinct"),
  me: () => get("/auth/me"),
  async requestLink(email: string) {
    const r = await fetch(`${BASE}/auth/request`, {
      method: "POST", headers: { "content-type": "application/json" },
      credentials: "include", body: JSON.stringify({ email }),
    });
    return r.json();
  },
  async logout() {
    await fetch(`${BASE}/auth/logout`, { method: "POST", credentials: "include" });
  },
  async putSettings(account: string, settings: any) {
    const r = await fetch(`${BASE}/settings/${account}`, {
      method: "PUT", headers: { "content-type": "application/json" },
      credentials: "include", body: JSON.stringify(settings),
    });
    return r.json();
  },
  async vote(account: string, listing_id: number, verdict: string) {
    const r = await fetch(`${BASE}/votes`, {
      method: "POST", headers: { "content-type": "application/json" },
      credentials: "include", body: JSON.stringify({ account, listing_id, verdict }),
    });
    return r.status; // 200 ok, 403 = not signed in
  },
};

export type Deal = {
  id: number; broker: string; business_name: string; category: string;
  state: string; city: string; sde: number; ebitda: number; revenue: number;
  multiple: number; listing_url: string; tier: string; relevance: number;
  fit_score: number; matched_keywords: string; one_line_take: string;
  positive_flags: string[]; negative_flags: string[]; flag_score: number;
};
