import { useEffect, useState } from "react";
import { api } from "./api";

export type Thesis = { slug: string; name: string; updated_at?: string; digest_emails?: string };

// Water/healthcare keep their brand hues; new theses cycle a distinct palette.
const PALETTE = ["#0e7c86", "#4f46e5", "#b45309", "#be185d", "#15803d", "#0369a1", "#a21caf", "#c2410c"];
export function thesisColor(slug: string, i: number): string {
  if (slug === "water") return "var(--water)";
  if (slug === "healthcare") return "var(--health)";
  return PALETTE[i % PALETTE.length];
}

// Shared, cached-per-mount thesis list + a name lookup. Every page that shows the thesis
// lens uses this so adding/renaming a thesis reflects everywhere without code changes.
export function useAccounts() {
  const [accounts, setAccounts] = useState<Thesis[]>([]);
  function reload() { return api.accounts().then((d: Thesis[]) => setAccounts(d || [])).catch(() => {}); }
  useEffect(() => { reload(); }, []);
  const labelOf = (slug: string) => accounts.find((a) => a.slug === slug)?.name || slug;
  return { accounts, labelOf, reload };
}
