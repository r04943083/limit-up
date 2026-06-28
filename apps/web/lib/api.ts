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
async function patch<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`API ${r.status}: ${path}`);
  return r.json();
}
async function del<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { method: "DELETE" });
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
  shares_outstanding: number | null;
  float_shares: number | null;
  recommendation: string | null;
  recommendation_mean: number | null;
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
  kdj_k: (number | null)[];
  kdj_d: (number | null)[];
  kdj_j: (number | null)[];
  latest: Record<string, number | null>;
  trend: string;
  signals: string[];
};
export const getTechnical = (s: string, period = "1y", interval = "1d") =>
  get<Technical>(`/stocks/${s}/technical?period=${period}&interval=${interval}`);
// The chart needs OHLCV; the research bundle technical omits bars, so fetch raw bars too.
export type OhlcvBar = { date: string; open: number; high: number; low: number; close: number; volume: number | null };
export const getOhlcv = (s: string, period = "1y", interval = "1d") =>
  get<OhlcvBar[]>(`/stocks/${s}/ohlcv?period=${period}&interval=${interval}`);

// ---- Deep research: financial statements + DCF ----
export type StatementRow = { label: string; values: (number | null)[] };
export type Statement = { periods: string[]; rows: StatementRow[] };
export type Financials = {
  symbol: string;
  market: string;
  currency: string | null;
  income: Statement; balance: Statement; cashflow: Statement;
  income_q: Statement; balance_q: Statement; cashflow_q: Statement;
  fcf_periods: string[]; fcf: (number | null)[];
  shares: number | null; cash: number | null; total_debt: number | null; net_debt: number | null;
};
export const getFinancials = (s: string) => get<Financials>(`/stocks/${s}/financials`);

export type DcfYear = { year: number; fcf: number; pv: number };
export type DcfResult = {
  fcf_base: number; growth: number; discount: number; terminal_growth: number; years: number;
  shares: number | null; net_debt: number;
  pv_explicit: number; terminal_value: number; pv_terminal: number;
  enterprise_value: number; equity_value: number; intrinsic_per_share: number | null;
  table: DcfYear[];
};
export type DcfView = {
  symbol: string; currency: string | null; price: number | null; upside_pct: number | null;
  has_fcf: boolean; result: DcfResult | null;
};
export type DcfParams = { growth?: number; discount?: number; terminal?: number; years?: number };
export const getDcf = (s: string, p: DcfParams = {}) => {
  const q = new URLSearchParams();
  for (const k of ["growth", "discount", "terminal", "years"] as const) {
    const v = p[k];
    if (v != null && !Number.isNaN(v)) q.set(k, String(v));
  }
  const qs = q.toString();
  return get<DcfView>(`/stocks/${s}/dcf${qs ? `?${qs}` : ""}`);
};

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

// ---- News sentiment ----
export type NewsSentiment = {
  overall: string;
  impact: string;
  summary: string;
  bull_points: string[];
  bear_points: string[];
  headlines_assessed: number;
};
export type SavedNewsAnalysis = {
  symbol: string;
  provider: string;
  created_at: string;
  headlines: NewsItem[];
  result: NewsSentiment;
};
export const getNewsAnalysis = (s: string) =>
  get<SavedNewsAnalysis | null>(`/stocks/${s}/news-analysis`);
export const runNewsAnalysis = (s: string) =>
  post<SavedNewsAnalysis>(`/stocks/${s}/news-analysis`);

export type WatchlistItem = {
  id: number;
  symbol: string;
  market: string;
  name: string | null;
  tags: string | null;
  note: string | null;
  sort_order: number;
};
export type Watchlist = {
  id: number;
  name: string;
  description: string | null;
  sort_order: number;
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

// ---- Daily briefing + health ----
export type BriefingResult = {
  headline: string;
  market_summary: string;
  watchlist_highlights: string[];
  opportunities: string[];
  risks: string[];
  action_items: string[];
};
export type SavedBriefing = {
  date: string;
  provider: string;
  created_at: string;
  result: BriefingResult;
  facts: {
    tracked_count?: number;
    top_gainers?: { symbol: string; change_pct: number | null; price: number | null }[];
    top_losers?: { symbol: string; change_pct: number | null; price: number | null }[];
  };
};
export const getBriefing = () => get<SavedBriefing | null>("/briefing");
export const generateBriefing = () => post<SavedBriefing>("/briefing/generate");

export type HealthOut = { symbol: string; score: number; label: string; factors: string[] };
export const getWatchlistHealth = () => get<HealthOut[]>("/briefing/health");

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

// ---- Indices (status bar) ----
export type IndexQuote = {
  symbol: string;
  name: string;
  market: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
};
export const getIndices = () => get<IndexQuote[]>("/markets/indices");

export type OverviewRow = {
  symbol: string;
  name: string | null;
  market: string | null;
  sector: string | null;
  price: number | null;
  change_pct: number | null;
  market_cap: number | null;
};
export const getOverview = () => get<OverviewRow[]>("/markets/overview");

// ---- Dense watchlist quotes + groups ----
export type QuoteRow = {
  item_id: number;
  symbol: string;
  market: string;
  name: string | null;
  tags: string | null;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  currency: string | null;
  spark: number[];
  synced_at: string | null;
};
export const getWatchlists = () => get<Watchlist[]>("/watchlists");
export const createWatchlist = (name: string, description?: string) =>
  post<Watchlist>("/watchlists", { name, description });
export const getWatchlistQuotes = (wid: number) => get<QuoteRow[]>(`/watchlists/${wid}/quotes`);

// ---- Futu .ebk import (one group per file) ----
export type EbkSkipped = { raw: string; reason: string };
export type EbkGroupResult = {
  group: string;
  watchlist_id: number;
  parsed: number;
  added: number;
  skipped: EbkSkipped[];
};
export type EbkImportResult = { groups: EbkGroupResult[]; total_added: number };
export const importEbk = (files: { name: string; content: string }[]) =>
  post<EbkImportResult>("/watchlists/import-ebk", files);

export type EbkExport = { filename: string; content: string; count: number };
export const exportEbk = (wid: number) => get<EbkExport>(`/watchlists/${wid}/export-ebk`);

// ---- JSON backup (whole-library export / import) ----
export type JsonImportGroupResult = { group: string; added: number; skipped: number };
export type JsonImportResult = {
  mode: string;
  groups: JsonImportGroupResult[];
  total_added: number;
};
export const exportAllJson = () => get<Record<string, unknown>>("/watchlists/export-json");
export const importJson = (mode: "merge" | "replace", data: unknown) =>
  post<JsonImportResult>("/watchlists/import-json", { mode, data });

export const getDefaultWatchlist = () => get<Watchlist>("/watchlists/default");
export const addItem = (wid: number, symbol: string, tags?: string) =>
  post<WatchlistItem>(`/watchlists/${wid}/items`, { symbol, tags });
export const removeItem = (itemId: number) =>
  del<{ removed: boolean }>(`/watchlists/items/${itemId}`);

// ---- Watchlist management: groups + items reorder / rename / delete / move / tags ----
export const renameWatchlist = (wid: number, name: string, description?: string) =>
  patch<Watchlist>(`/watchlists/${wid}`, { name, description });
export const deleteWatchlist = (wid: number) =>
  del<{ removed: boolean }>(`/watchlists/${wid}`);
export const reorderWatchlists = (orderedIds: number[]) =>
  post<{ ok: boolean }>(`/watchlists/reorder`, { ordered_ids: orderedIds });
export const reorderItems = (wid: number, orderedItemIds: number[]) =>
  post<{ ok: boolean }>(`/watchlists/${wid}/reorder-items`, { ordered_item_ids: orderedItemIds });
export const moveItem = (itemId: number, watchlistId: number) =>
  post<{ ok: boolean }>(`/watchlists/items/${itemId}/move`, { watchlist_id: watchlistId });
export const updateItem = (itemId: number, patch_: { tags?: string; note?: string }) =>
  patch<WatchlistItem>(`/watchlists/items/${itemId}`, patch_);
