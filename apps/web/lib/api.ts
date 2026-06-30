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

// ---- Symbol search (autocomplete over the downloaded universe) ----
export type SymbolHit = { symbol: string; name: string | null; market: string | null };
export const searchSymbols = (q: string, limit = 20) =>
  get<SymbolHit[]>(`/stocks/search?q=${encodeURIComponent(q)}&limit=${limit}`);

// ---- Data sync (pull live → DB so pages load fast) ----
export type SyncResult = {
  requested: number;
  synced: number;
  failed: string[];
  synced_at: string;
  financials_synced?: number;
  profiles_synced?: number;
  skipped_fresh?: number;
  feeds?: Record<string, boolean>;
};
export const syncSymbol = (s: string) => post<SyncResult>(`/stocks/${s}/sync`);
export const syncAll = () => post<SyncResult>(`/sync/all`);
export type FreshnessRow = { symbol: string; synced_at: string | null };
export const getFreshness = () => get<FreshnessRow[]>(`/sync/freshness`);

// ---- Data inventory (how much we've downloaded, per market) ----
export type MarketInventory = {
  market: string;
  label: string;
  stocks: number;
  with_bars: number;
  with_snapshot: number;
  with_financials: number;
  with_profile: number;
  bars: number;
};
export type Inventory = {
  markets: MarketInventory[];
  total_stocks: number;
  total_bars: number;
  total_snapshots: number;
  db_bytes: number | null;
  last_synced_at: string | null;
};
export const getInventory = () => get<Inventory>(`/sync/inventory`);

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
export type IntradayPoint = { t: string; price: number; volume: number | null };
export const getIntraday = (s: string, range: "1d" | "5d" = "1d") =>
  get<IntradayPoint[]>(`/stocks/${s}/intraday?range=${range}`);

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

// ---- Valuation bands (历史估值带) + analyst consensus ----
export type RatioPoint = { date: string; value: number };
export type ValuationBand = {
  metric: string;
  points: RatioPoint[];
  current: number | null;
  mean: number | null;
  median: number | null;
  low: number | null;
  high: number | null;
  percentile: number | null;
};
export type AnalystConsensus = {
  recommendation: string | null;
  recommendation_mean: number | null;
  num_analysts: number | null;
  price: number | null;
  target_mean: number | null;
  target_high: number | null;
  target_low: number | null;
  target_median: number | null;
  upside_pct: number | null;
  strong_buy: number | null;
  buy: number | null;
  hold: number | null;
  sell: number | null;
  strong_sell: number | null;
};
export type IndustryAvg = { pe: number | null; pb: number | null; ps: number | null; peers: number };
export type ValuationOut = {
  symbol: string;
  currency: string | null;
  pe: ValuationBand;
  pb: ValuationBand;
  ps: ValuationBand;
  analyst: AnalystConsensus;
  industry: string | null;
  industry_avg: IndustryAvg;
  short_percent: number | null;
};
export const getValuation = (s: string) => get<ValuationOut>(`/stocks/${s}/valuation`);

// ---- Company profile: overview + dividends + ownership ----
export type Dividend = { ex_date: string; amount: number };
export type HolderRow = {
  name: string; pct: number | null; shares: number | null;
  value: number | null; date_reported: string | null;
};
export type CompanyProfile = {
  symbol: string; market: string;
  name: string | null; sector: string | null; industry: string | null;
  country: string | null; website: string | null; employees: number | null;
  summary: string | null; currency: string | null;
  dividends: Dividend[]; dividend_yield: number | null; payout_ratio: number | null;
  insiders_pct: number | null; institutions_pct: number | null;
  top_institutions: HolderRow[];
};
export const getProfile = (s: string) => get<CompanyProfile>(`/stocks/${s}/profile`);

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
  sort_order?: number;
  // Futu-style extra columns (ratios are fractions; market_cap/amount/volume are raw)
  market_cap: number | null;
  pe_ttm: number | null;
  dividend_yield: number | null;
  beta: number | null;
  volume: number | null;
  amount: number | null;
  turnover_rate: number | null;
  volume_ratio: number | null;
  amplitude: number | null;
  pct_from_high: number | null;
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

// ---- A-share breadth (akshare): limit-up pool / dragon-tiger / HSGT ----
export type LimitUpStock = {
  code: string; name: string; pct: number | null; price: number | null;
  amount: number | null; float_cap: number | null; turnover: number | null;
  seal_fund: number | null; first_seal: string | null; last_seal: string | null;
  broken_times: number | null; boards: number | null; streak: string | null; industry: string | null;
};
export type LimitUpPool = { date: string; count: number; stocks: LimitUpStock[] };
export type LimitUpResult = { ok: boolean; error: string | null; pool: LimitUpPool };
export const getLimitUp = (date?: string) =>
  get<LimitUpResult>(`/cn/limit-up${date ? `?date=${date}` : ""}`);

export type DragonTigerRow = {
  code: string; name: string; date: string | null; interpret: string | null;
  close: number | null; pct: number | null; net_buy: number | null; buy: number | null;
  sell: number | null; net_pct: number | null; turnover: number | null; reason: string | null;
};
export type DragonTiger = { date: string; count: number; rows: DragonTigerRow[] };
export type DragonTigerResult = { ok: boolean; error: string | null; data: DragonTiger };
export const getDragonTiger = (date?: string) =>
  get<DragonTigerResult>(`/cn/dragon-tiger${date ? `?date=${date}` : ""}`);

export type HsgtFlowRow = {
  date: string | null; market: string | null; direction: string | null;
  net: number | null; inflow: number | null; up: number | null; flat: number | null;
  down: number | null; index_name: string | null; index_pct: number | null;
};
export type HsgtSummary = { date: string | null; northbound_suspended: boolean; rows: HsgtFlowRow[] };
export type HsgtResult = { ok: boolean; error: string | null; summary: HsgtSummary };
export const getHsgtSummary = () => get<HsgtResult>(`/cn/hsgt-summary`);

// ---- AI 涨停复盘 (limit-up review, claude -p) ----
export type ZtReviewResult = {
  sentiment: string; summary: string; ladder_read: string;
  leaders: string[]; capital: string; risks: string[];
};
export type SavedZtReview = {
  date: string; provider: string; created_at: string;
  result: ZtReviewResult; facts: Record<string, unknown>;
};
export const getZtReview = (date?: string) =>
  get<SavedZtReview | null>(`/cn/review${date ? `?date=${date}` : ""}`);
export const runZtReview = (date?: string) =>
  post<SavedZtReview>(`/cn/review${date ? `?date=${date}` : ""}`);

// ---- #11 投资日志 Journal ----
export type JournalReview = {
  score: number;
  verdict: string;
  strengths: string[];
  blind_spots: string[];
  biases: string[];
};
export type JournalEntry = {
  id: number;
  symbol: string | null;
  action: string;
  title: string;
  body: string | null;
  conviction: string | null;
  ai_score: number | null;
  ai_review: JournalReview | null;
  created_at: string;
};
export const getJournal = (symbol?: string) =>
  get<JournalEntry[]>(`/journal${symbol ? `?symbol=${symbol}` : ""}`);
export const addJournal = (body: {
  title: string; body?: string; symbol?: string; action?: string; conviction?: string;
}) => post<JournalEntry>("/journal", body);
export const deleteJournal = (id: number) => del<{ removed: boolean }>(`/journal/${id}`);
export const reviewJournal = (id: number) => post<JournalEntry>(`/journal/${id}/review`);

// ---- #8 模拟交易 Paper trading ----
export type PaperPosition = {
  symbol: string; quantity: number; avg_cost: number; price: number | null;
  market_value: number; cost_basis: number; pnl: number; pnl_pct: number | null; weight: number;
};
export type PaperTrade = {
  id: number; symbol: string; side: string; quantity: number; price: number;
  note: string | null; created_at: string;
};
export type PaperAccount = {
  id: number; name: string; cash: number; starting_cash: number; base_currency: string;
  positions: PaperPosition[]; invested: number; equity: number;
  total_pnl: number; total_return_pct: number | null; trades: PaperTrade[];
};
export const getPaper = () => get<PaperAccount>("/paper/account");
export const paperTrade = (symbol: string, side: "buy" | "sell", quantity: number, note?: string) =>
  post<PaperAccount>("/paper/trade", { symbol, side, quantity, note });
export const resetPaper = () => post<PaperAccount>("/paper/reset");

// ---- #8 + #13 AI 竞技场 Arena (persona-driven paper accounts that compete) ----
export type PerfMetrics = {
  total_return_pct: number | null; max_drawdown_pct: number | null; sharpe: number | null;
  cagr_pct: number | null; volatility_pct: number | null;
  best_day_pct: number | null; worst_day_pct: number | null;
};
export type ArenaPosition = {
  symbol: string; name: string | null; sector: string | null; quantity: number; avg_cost: number;
  price: number | null; market_value: number; weight: number; pnl: number; pnl_pct: number | null;
  last_reason: string | null;
};
export type CurvePoint = { date: string; value: number };
export type ArenaTrade = {
  symbol: string; name: string | null; side: "buy" | "sell"; quantity: number;
  price: number; amount: number; reason: string | null; at: string | null;
};
export type ArenaAgent = {
  persona: string; name: string; tagline: string; style: string;
  cash: number; invested: number; equity: number; starting_cash: number;
  metrics: PerfMetrics; positions: ArenaPosition[]; trades_count: number;
  last_decision_at: string | null; rank: number; curve: CurvePoint[]; trades: ArenaTrade[];
};
export type ArenaBenchmark = { symbol: string; name: string; return_pct: number | null; curve: CurvePoint[] };
export type ArenaOut = {
  agents: ArenaAgent[]; benchmark: ArenaBenchmark; universe_size: number; updated_at: string | null;
};
export const getArena = () => get<ArenaOut>("/arena");
export const arenaTick = () => post<ArenaOut>("/arena/tick", {});
export const resetArena = () => post<ArenaOut>("/arena/reset", {});

// ---- #9 策略构建器 Strategy backtest ----
export type StrategySpec = {
  kind: string;
  rsi_period?: number; rsi_buy?: number; rsi_sell?: number;
  fast?: number; slow?: number;
  lookback?: number; exit_lookback?: number;
  starting_cash?: number;
};
export type BacktestPoint = { date: string; equity: number; buy_hold: number };
export type BacktestTrade = {
  entry_date: string; exit_date: string | null; entry_price: number;
  exit_price: number | null; return_pct: number | null; bars_held: number;
};
export type BacktestStats = {
  total_return_pct: number; buy_hold_return_pct: number; cagr_pct: number | null;
  max_drawdown_pct: number; win_rate: number | null; trades: number;
  sharpe: number | null; exposure_pct: number;
};
export type BacktestResult = {
  symbol: string; kind: string; bars: number; spec: StrategySpec;
  stats: BacktestStats; curve: BacktestPoint[]; trade_log: BacktestTrade[];
};
export const getStrategyKinds = () => get<string[]>("/strategy/kinds");
export const runBacktest = (symbol: string, spec: StrategySpec, period = "3y") =>
  post<BacktestResult>(`/strategy/backtest?symbol=${symbol}&period=${period}`, spec);
export type StrategyRead = { summary: string; verdict: string; observations: string[]; cautions: string[] };
export const explainBacktest = (symbol: string, spec: StrategySpec, period = "3y") =>
  post<StrategyRead>(`/strategy/explain?symbol=${symbol}&period=${period}`, spec);

// ---- #1 AI 对话 Chat ----
export type ChatTurn = { id: number; role: string; content: string; created_at: string };
export type ChatReply = { reply: string; provider: string; symbols_used: string[] };
export const getChatHistory = (session = "default") =>
  get<ChatTurn[]>(`/chat/history?session_id=${session}`);
export const sendChat = (message: string, session = "default") =>
  post<ChatReply>("/chat/send", { message, session_id: session });
export const clearChat = (session = "default") =>
  del<{ cleared: number }>(`/chat/history?session_id=${session}`);

// ---- AI Studio: personas (#13) / debate (#19) / panel (#14) / coach (#12) / DNA (#16) ----
export type Persona = { key: string; name: string; tagline: string; style: string; system: string };
export const getPersonas = () => get<Persona[]>("/studio/personas");
export const analyzeAsPersona = (key: string, symbol: string) =>
  post<SavedAnalysis>(`/studio/personas/${key}/analyze/${symbol}`);

export type DebateResult = {
  bull_case: string; bear_case: string; bull_rebuttal: string; bear_rebuttal: string;
  winner: string; confidence: number; verdict: string; key_question: string;
};
export type SavedDebate = { symbol: string; provider: string; created_at: string; result: DebateResult };
export const getDebate = (s: string) => get<SavedDebate | null>(`/studio/debate/${s}`);
export const runDebate = (s: string) => post<SavedDebate>(`/studio/debate/${s}`);

export type AgentView = { agent: string; stance: string; score: number; rationale: string };
export type MultiAgentResult = {
  agents: AgentView[]; consensus_score: number; recommendation: string;
  synthesis: string; disagreement: string;
};
export type SavedMultiAgent = { symbol: string; provider: string; created_at: string; result: MultiAgentResult };
export const getPanel = (s: string) => get<SavedMultiAgent | null>(`/studio/panel/${s}`);
export const runPanel = (s: string) => post<SavedMultiAgent>(`/studio/panel/${s}`);

export type CoachResult = {
  grade: string; discipline_score: number; headline: string;
  good_habits: string[]; biases: string[]; drills: string[]; action_items: string[];
};
export type SavedCoach = { provider: string; created_at: string; result: CoachResult };
export const getCoach = () => get<SavedCoach | null>("/studio/coach");
export const runCoach = () => post<SavedCoach>("/studio/coach");

export type DnaResult = {
  archetype: string; risk_tolerance: string; time_horizon: string; sector_tilt: string[];
  strengths: string[]; watchouts: string[]; summary: string;
  growth_vs_value: number; conviction: number;
};
export type SavedDna = { provider: string; created_at: string; facts: Record<string, unknown>; result: DnaResult };
export const getDna = () => get<SavedDna | null>("/studio/dna");
export const runDna = () => post<SavedDna>("/studio/dna");

// --- Screener + universe seeding -------------------------------------------
export type ScreenerField = { key: string; label: string; group: string; unit: string; better: string };
export type IndexInfo = { key: string; label: string; market: string };
export type ScreenerMeta = { fields: ScreenerField[]; indices: IndexInfo[] };
export const getScreenerMeta = () => get<ScreenerMeta>("/screener/meta");

export type ScreenFilter = { field: string; min?: number | null; max?: number | null };
export type ScreenSpec = {
  filters?: ScreenFilter[];
  markets?: string[];
  sectors?: string[];
  limit_up_only?: boolean;
  sort_field?: string;
  sort_desc?: boolean;
  limit?: number;
};
export type ScreenHit = {
  symbol: string; name: string | null; market: string | null;
  sector: string | null; industry: string | null;
  metrics: Record<string, number | null>;
};
export type ScreenResult = { universe: number; matched: number; results: ScreenHit[]; sectors: string[] };
export const runScreen = (spec: ScreenSpec) => post<ScreenResult>("/screener/run", spec);

export type SeedProgress = {
  running: boolean; done: number; total: number; failed: number;
  started_at: string | null; finished_at: string | null;
};
export type IndexSeed = { key: string; label: string; market: string; fetched: number };
export type SeedResult = { indices: IndexSeed[]; total_fetched: number; added: number; universe_size: number };
export type SeedResponse = { seed: SeedResult; progress: SeedProgress };
export const seedUniverse = (keys: string[], fill = true) =>
  post<SeedResponse>("/screener/universe/seed", { keys, fill });
export const getSeedProgress = (kind: "snapshot" | "financials" = "snapshot") =>
  get<SeedProgress>(`/screener/universe/progress?kind=${kind}`);
export const fillFinancials = () => post<SeedProgress>("/screener/universe/fill-financials");
