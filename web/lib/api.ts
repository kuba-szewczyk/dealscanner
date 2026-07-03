const BASE = process.env.NEXT_PUBLIC_API ?? "http://localhost:8099";

async function get(path: string) {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store", credentials: "include" });
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return r.json();
}
async function post(path: string, body: any) {
  return fetch(`${BASE}${path}`, {
    method: "POST", headers: { "content-type": "application/json" },
    credentials: "include", body: JSON.stringify(body),
  });
}

export const api = {
  accounts: () => get("/accounts"),
  board: (account: string, sections = "in", limit = 200) =>
    get(`/board?account=${account}&sections=${sections}&limit=${limit}`),
  settings: (account: string) => get(`/settings/${account}`),
  runs: () => get("/runs"),
  search: (q: string, sort = "accuracy") => get(`/search?q=${encodeURIComponent(q)}&sort=${sort}`),
  activity: (hours = 24) => get(`/activity?hours=${hours}`),
  brokers: () => get("/brokers"),
  logs: () => get("/logs"),
  votesList: () => get("/votes/list"),
  me: () => get("/auth/me"),
  brokerAdd: (name: string, url: string) => post("/brokers/add", { name, url }).then((r) => r.status),
  brokerStatus: (name: string, status: string) => post("/brokers/status", { name, status }).then((r) => r.status),
  brokerEdit: (name: string, new_name: string, url: string) => post("/brokers/edit", { name, new_name, url }).then((r) => r.status),
  requestLink: (email: string) => post("/auth/request", { email }).then((r) => r.json()),
  logout: () => post("/auth/logout", {}).then(() => undefined),
  async putSettings(account: string, settings: any) {
    const r = await fetch(`${BASE}/settings/${account}`, {
      method: "PUT", headers: { "content-type": "application/json" },
      credentials: "include", body: JSON.stringify(settings),
    });
    return r.json();
  },
  vote: (account: string, listing_id: number, verdict: string) =>
    post("/votes", { account, listing_id, verdict }).then((r) => r.status),
  unvote: (account: string, listing_id: number) =>
    post("/votes/clear", { account, listing_id }).then((r) => r.status),
  recategorize: (account: string, listing_id: number, verdict: string) =>
    post("/votes/recategorize", { account, listing_id, verdict }).then((r) => r.status),
};

// Only allow http(s) URLs into an <a href>. Listing/broker URLs come from scraped
// pages (attacker-influencable), and React does NOT block `javascript:`/`data:`
// schemes in href — so a hostile scrape could otherwise inject a click-to-run link.
// Anything not clearly http(s) becomes a harmless no-op ("#").
export function safeHref(url: string | null | undefined): string {
  if (!url) return "#";
  try {
    const u = new URL(url, "https://dealscanner.us");
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : "#";
  } catch {
    return "#";
  }
}

export type Deal = {
  id: number; broker: string; business_name: string; category: string;
  state: string; city: string; sde: number; ebitda: number; revenue: number;
  asking_price: number; multiple: number; listing_url: string; tier: string; relevance: number;
  fit_score: number; matched_keywords: string; one_line_take: string;
  positive_flags: string[]; negative_flags: string[]; flag_score: number; first_seen: string;
};
