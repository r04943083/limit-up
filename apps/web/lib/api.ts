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
// Cached-first by default (loads the stored snapshot → instant). Pass cached=false to force live.
export const getResearch = (s: string, cached = true) =>
  get<ResearchBundle>(`/stocks/${s}/research?cached=${cached}`);

// ---- Data sync (pull live → DB so pages load fast) ----
export type SyncResult = {
  requested: number;
  synced: number;
  failed: string[];
  synced_at: string;
};
export const syncSymbol = (s: string) => post<SyncResult>(`/stocks/${s}/sync`);
export const syncAll = () => post<SyncResult>(`/sync/all`);
export type FreshnessRow = { symbol: string; synced_at: string | null };
export const getFreshness = () => get<FreshnessRow[]>(`/sync/freshness`);

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
// ---- Portfolio ----
export type Holding = {
  id: number;
  symbol: string;
  market: string;
  name: string | null;
  quantity: number;
  avg_cost: number | null;
  source: string | null;
};
export type Position = {
  symbol: string;
  name: string | null;
  market: string;
  sector: string | null;
  quantity: number;
  avg_cost: number | null;
  price: number | null;
  currency: string;
  market_value: number;
  cost_basis: number;
  pnl: number;
  pnl_pct: number | null;
  weight: number;
};
export type PortfolioAnalytics = {
  base_currency: string;
  positions: Position[];
  total_value: number;
  total_cost: number;
  total_pnl: number;
  total_pnl_pct: number | null;
  sector_alloc: Record<string, number>;
  market_alloc: Record<string, number>;
  top_weight: number;
  hhi: number;
  correlation_symbols: string[];
  correlation_matrix: (number | null)[][];
};
export type PortfolioReview = {
  summary: string;
  strengths: string[];
  concerns: string[];
  suggestions: string[];
  risk_level: string;
  diversification: string;
};
export const getPortfolio = () => get<{ id: number; holdings: Holding[] }>("/portfolio/default");
export const addHolding = (pid: number, symbol: string, quantity: number, avg_cost?: number) =>
  post<{ holdings: Holding[] }>(`/portfolio/${pid}/holdings`, { symbol, quantity, avg_cost });
export const removeHolding = (id: number) =>
  fetch(`${BASE}/portfolio/holdings/${id}`, { method: "DELETE" }).then((r) => r.json());
export const importPortfolioCsv = (pid: number, csv: string) =>
  post<{ added: number }>(`/portfolio/${pid}/import-csv`, csv, true);
export const getAnalytics = (pid: number) => get<PortfolioAnalytics>(`/portfolio/${pid}/analytics`);
export const getReview = (pid: number) => get<PortfolioReview | null>(`/portfolio/${pid}/review`);
export const runReview = (pid: number) => post<PortfolioReview>(`/portfolio/${pid}/review`);

// ---- Recommendations ----
export type Recommendation = {
  symbol: string;
  category: string;
  name: string | null;
  ai_score: number | null;
  conviction: string | null;
  thesis: string | null;
  risks: string[];
  catalysts: string[];
  target_price: number | null;
  time_horizon: string | null;
  provider: string;
};
export const getRecCategories = () => get<string[]>("/recommendations/categories");
export const getRecommendations = (category?: string) =>
  get<Recommendation[]>(`/recommendations${category ? `?category=${category}` : ""}`);
export const generateRecommendations = (category: string) =>
  post<Recommendation[]>(`/recommendations/generate?category=${category}`);

// ---- LLM usage ----
export type UsageCall = {
  id: number;
  provider: string;
  model: string | null;
  kind: string;
  symbol: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  duration_ms: number;
  created_at: string;
};
export type UsageDay = { date: string; calls: number; total_tokens: number; cost_usd: number };
export type UsageSummary = {
  today_calls: number;
  today_tokens: number;
  today_cost_usd: number;
  total_calls: number;
  total_tokens: number;
  total_cost_usd: number;
  by_kind: Record<string, number>;
  by_day: UsageDay[];
  recent: UsageCall[];
};
export const getUsageSummary = () => get<UsageSummary>("/usage/summary");

export const getDefaultWatchlist = () => get<Watchlist>("/watchlists/default");
export const addItem = (wid: number, symbol: string, tags?: string) =>
  post<WatchlistItem>(`/watchlists/${wid}/items`, { symbol, tags });
export const removeItem = (itemId: number) =>
  fetch(`${BASE}/watchlists/items/${itemId}`, { method: "DELETE" }).then((r) => r.json());
export const importCsv = (wid: number, csv: string) =>
  post<{ added: number }>(`/watchlists/${wid}/import-csv`, csv, true);
