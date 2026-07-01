// Market inference for the web UI — mirrors backend `lucore.markets.infer_market` so
// market-aware UI (discovery page, extended-hours toggle, color conventions) has one
// source of truth instead of re-deriving suffix rules per page.

export type Market = "US" | "HK" | "CN";

/**
 * Best-effort market from a ticker.
 *   700.HK / 0700.HK → HK ; 600519.SS / 000001.SZ → CN ; plain alpha (NVDA) → US.
 *   Bare numerics: 6 digits → CN A-share, 1–5 digits → HK.
 */
export function inferMarket(symbol: string): Market {
  const s = (symbol || "").trim().toUpperCase();
  if (s.endsWith(".HK")) return "HK";
  if (s.endsWith(".SS") || s.endsWith(".SZ") || s.endsWith(".SH")) return "CN";
  const head = s.split(".")[0];
  if (/^\d+$/.test(head)) return head.length === 6 ? "CN" : "HK";
  return "US";
}

export const isUS = (symbol: string) => inferMarket(symbol) === "US";

export const MARKET_LABEL: Record<Market, string> = { US: "美股", HK: "港股", CN: "A股" };
