// Typed client for the LU local API. Calls go through Next's /api rewrite to FastAPI.
const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`API ${r.status}: ${path}`);
  return r.json();
}
async function post<T>(path: string, body?: unknown, asText = false): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "content-type": asText ? "text/plain" : "application/json" },
    body: body === undefined ? undefined : asText ? (body as string) : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`API ${r.status}: ${path}`);
  return r.json();
}

export type Health = {
  status: string;
  version: string;
  db: string;
  llm_provider: string;
  markets: string[];
};
export const getHealth = () => get<Health>("/health");

export type Quote = {
  symbol: string;
  market: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  currency: string | null;
  name: string | null;
};

export type Fundamentals = {
  symbol: string;
  name: string | null;
  sector: string | null;
  industry: string | null;
  currency: string | null;
  market_cap: number | null;
  pe_ttm: number | null;
  pe_fwd: number | null;
  pb: number | null;
  ps: number | null;
  peg: number | null;
  ev_ebitda: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  net_margin: number | null;
  roe: number | null;
  roa: number | null;
  revenue: number | null;
  revenue_growth: number | null;
  eps: number | null;
  earnings_growth: number | null;
  dividend_yield: number | null;
  payout_ratio: number | null;
  beta: number | null;
  week52_high: number | null;
  week52_low: number | null;
  avg_volume: number | null;
  recommendation: string | null;
  num_analysts: number | null;
  target_mean: number | null;
  target_high: number | null;
  target_low: number | null;
  target_median: number | null;
};

export type NewsItem = {
  title: string;
  publisher: string | null;
  url: string | null;
  published_at: string | null;
};

export type ResearchBundle = {
  symbol: string;
  market: string;
  quote: Quote;
  fundamentals: Fundamentals;
  technical_latest: Record<string, number | null>;
  technical_trend: string;
  technical_signals: string[];
  news: NewsItem[];
  generated_at: string;
};
export const getResearch = (s: string) => get<ResearchBundle>(`/stocks/${s}/research`);

export type Technical = {
  dates: string[];
  sma20: (number | null)[];
  sma50: (number | null)[];
  sma200: (number | null)[];
  bb_upper: (number | null)[];
  bb_lower: (number | null)[];
  rsi14: (number | null)[];
  macd: (number | null)[];
  macd_signal: (number | null)[];
  macd_hist: (number | null)[];
  latest: Record<string, number | null>;
  trend: string;
  signals: string[];
};
export const getTechnical = (s: string) => get<Technical>(`/stocks/${s}/technical`);
// The chart needs OHLCV; the research bundle technical omits bars, so fetch raw bars too.
export type OhlcvBar = { date: string; open: number; high: number; low: number; close: number; volume: number | null };
export const getOhlcv = (s: string, period = "1y") =>
  get<OhlcvBar[]>(`/stocks/${s}/ohlcv?period=${period}`);

export type AnalysisResult = {
  summary: string;
  recommendation: string;
  score: number;
  bull_case: string;
  bear_case: string;
  risks: string[];
  catalysts: string[];
  target_price: number | null;
  time_horizon: string | null;
};
export type SavedAnalysis = {
  id: number;
  symbol: string;
  provider: string;
  created_at: string;
  result: AnalysisResult;
};
export const getAnalysis = (s: string) => get<SavedAnalysis | null>(`/stocks/${s}/analysis`);
export const runAnalyze = (s: string) => post<SavedAnalysis>(`/stocks/${s}/analyze`);

export type WatchlistItem = {
  id: number;
  symbol: string;
  market: string;
  name: string | null;
  tags: string | null;
  note: string | null;
};
export type Watchlist = {
  id: number;
  name: string;
  description: string | null;
  items: WatchlistItem[];
};
export const getDefaultWatchlist = () => get<Watchlist>("/watchlists/default");
export const addItem = (wid: number, symbol: string, tags?: string) =>
  post<WatchlistItem>(`/watchlists/${wid}/items`, { symbol, tags });
export const removeItem = (itemId: number) =>
  fetch(`${BASE}/watchlists/items/${itemId}`, { method: "DELETE" }).then((r) => r.json());
export const importCsv = (wid: number, csv: string) =>
  post<{ added: number }>(`/watchlists/${wid}/import-csv`, csv, true);
