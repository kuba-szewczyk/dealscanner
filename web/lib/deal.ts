// Shared deal-card constants and formatters, used by the Deals board and the Search modal.

export const FLAG_LABEL: Record<string, string> = {
  geo_t1: "Tier-1 metro", geo_t2: "Tier-2 state", margin_gt_20: "20%+ EBITDA margin",
  owner_retiring: "Owner retiring", recurring_40: "40%+ recurring",
  low_margin_lt_15: "Low margin (<15%)", overpriced: "Overpriced", franchise_resale: "Franchise resale",
  partial: "Minority / partial sale",
};

export const CAT_CLASS: Record<string, string> = {
  "Healthcare": "c-teal", "Restaurant & Food": "c-pink", "Construction & Trades": "c-amber",
  "Manufacturing": "c-purple", "Retail & E-commerce": "c-rose", "Professional Services": "c-blue",
  "Personal Care & Fitness": "c-green", "Real Estate & Property": "c-slate",
  "Distribution & Wholesale": "c-indigo", "Auto & Transport": "c-orange",
  "Education & Childcare": "c-cyan", "Cleaning & Facilities": "c-lime",
  "Hospitality & Lodging": "c-brown", "Services": "c-blue", "Software": "c-purple",
  "E-commerce": "c-rose", "Other": "c-gray",
};

// Short single-word labels for the tight Search category column.
export const CAT_SHORT: Record<string, string> = {
  "Restaurant & Food": "Food", "Construction & Trades": "Trades", "Retail & E-commerce": "Retail",
  "Professional Services": "Services", "Personal Care & Fitness": "Personal Care",
  "Real Estate & Property": "Real Estate", "Distribution & Wholesale": "Distribution",
  "Auto & Transport": "Auto", "Education & Childcare": "Education",
  "Cleaning & Facilities": "Cleaning", "Hospitality & Lodging": "Hospitality",
};
export const catShort = (c?: string | null) => (c ? (CAT_SHORT[c] || c) : "");

export const fmtM = (v?: number | null) => (v == null ? "—" : `$${(v / 1e6).toFixed(1)}M`);

export function parseDate(s?: string): Date | null {
  if (!s) return null;
  let m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(s);
  if (m) return new Date(+m[3], +m[1] - 1, +m[2]);
  return null;
}

export const fmtDate = (s?: string) => {
  const d = parseDate(s);
  if (!d) return "";
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${mm}-${dd}-${d.getFullYear()}`;
};
