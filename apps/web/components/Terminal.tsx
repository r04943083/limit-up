"use client";

import { useEffect, useState, useCallback } from "react";
import Chart from "@/components/Chart";
import { Stat, RecBadge, ScoreMeter } from "@/components/ui";
import {
  getResearch, getTechnical, getOhlcv, getAnalysis, runAnalyze, syncSymbol,
  getNewsAnalysis, runNewsAnalysis,
  type ResearchBundle, type Technical, type OhlcvBar, type SavedAnalysis,
  type SavedNewsAnalysis,
} from "@/lib/api";
import { num, compact, pct, signedPct, recTone, sinceLabel, dirClass } from "@/lib/format";

const KLINES = [
  { label: "日K", period: "1y", interval: "1d" },
  { label: "周K", period: "5y", interval: "1wk" },
  { label: "月K", period: "max", interval: "1mo" },
] as const;

type Tab = "解读" | "报价估值" | "新闻舆情";

// The Futu-style three-column terminal body (center chart + right tab panel) for one symbol.
// The left WatchlistPane is rendered by the page so it can drive symbol selection.
export default function Terminal({ symbol }: { symbol: string | null }) {
  const sym = symbol?.toUpperCase() ?? "";

  const [rb, setRb] = useState<ResearchBundle | null>(null);
  const [ta, setTa] = useState<Technical | null>(null);
  const [ohlcv, setOhlcv] = useState<OhlcvBar[] | null>(null);
  const [analysis, setAnalysis] = useState<SavedAnalysis | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [newsAna, setNewsAna] = useState<SavedNewsAnalysis | null>(null);
  const [analyzingNews, setAnalyzingNews] = useState(false);
  const [kidx, setKidx] = useState(0);
  const [tab, setTab] = useState<Tab>("解读");
  const [chartLoading, setChartLoading] = useState(false);

  const loadBundle = useCallback(() => {
    if (!sym) return;
    setErr(null); setRb(null);
    getResearch(sym).then(setRb).catch((e) => setErr(String(e)));
  }, [sym]);

  const loadChart = useCallback(() => {
    if (!sym) return;
    const k = KLINES[kidx];
    setChartLoading(true);
    Promise.all([getOhlcv(sym, k.period, k.interval), getTechnical(sym, k.period, k.interval)])
      .then(([o, t]) => { setOhlcv(o); setTa(t); })
      .catch((e) => setErr(String(e)))
      .finally(() => setChartLoading(false));
  }, [sym, kidx]);

  useEffect(() => {
    if (!sym) return;
    loadBundle();
    getAnalysis(sym).then(setAnalysis).catch(() => {});
    setNewsAna(null);
    getNewsAnalysis(sym).then(setNewsAna).catch(() => {});
  }, [sym, loadBundle]);

  // Keep the previous chart visible while the next loads (avoids a jarring blank);
  // a subtle badge signals the refresh.
  useEffect(() => { loadChart(); }, [loadChart]);

  const sync = useCallback(() => {
    setSyncing(true);
    syncSymbol(sym).then(() => { loadBundle(); loadChart(); })
      .catch((e) => setErr(String(e))).finally(() => setSyncing(false));
  }, [sym, loadBundle, loadChart]);

  const analyze = useCallback(() => {
    setAnalyzing(true);
    runAnalyze(sym).then(setAnalysis).catch((e) => setErr(String(e))).finally(() => setAnalyzing(false));
  }, [sym]);

  const analyzeNews = useCallback(() => {
    setAnalyzingNews(true);
    runNewsAnalysis(sym).then(setNewsAna).catch((e) => setErr(String(e))).finally(() => setAnalyzingNews(false));
  }, [sym]);

  const f = rb?.fundamentals;
  const q = rb?.quote;
  const upside = f?.target_mean && q?.price ? ((f.target_mean - q.price) / q.price) * 100 : null;
  // Today's O/H/L/Vol from the last daily bar (we don't have a separate intraday feed).
  const last = kidx === 0 && ohlcv && ohlcv.length ? ohlcv[ohlcv.length - 1] : null;
  const prev = kidx === 0 && ohlcv && ohlcv.length > 1 ? ohlcv[ohlcv.length - 2] : null;
  // 换手率 = 成交量 / 流通股本.
  const turnover = last?.volume && f?.float_shares ? (last.volume / f.float_shares) * 100 : null;

  if (!sym) {
    return (
      <div className="flex-1 grid place-items-center text-ink-faint text-sm">
        从左侧选择一个自选标的查看行情与分析。
      </div>
    );
  }

  return (
    <>
      {/* Center: header + chart */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-4 px-5 h-14 border-b border-line">
          <div className="flex items-baseline gap-3 min-w-0">
            <h1 className="text-lg font-semibold tracking-tight truncate">{f?.name ?? q?.name ?? sym}</h1>
            <span className="text-sm text-ink-dim">{sym}</span>
            {rb && <span className="px-1.5 py-0.5 rounded bg-panel-2 text-[10px] text-ink-faint">{rb.market}</span>}
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <span className={`text-xl font-semibold tnum ${dirClass(q?.change_pct)}`}>
                {q?.price != null ? num(q.price) : "—"}
              </span>{" "}
              <span className={`text-sm tnum ${dirClass(q?.change_pct)}`}>
                {q?.change != null ? (q.change >= 0 ? "+" : "") + num(q.change) : ""} {signedPct(q?.change_pct)}
              </span>
            </div>
            <button onClick={sync} disabled={syncing}
              className="rounded-lg border border-line text-xs px-3 py-1.5 text-ink-dim hover:text-ink hover:border-accent/40 disabled:opacity-50">
              {syncing ? "更新中…" : "↻ 更新"}
            </button>
          </div>
        </div>

        {err && <div className="mx-5 mt-3 rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

        <div className="flex items-center gap-1 px-5 h-9 border-b border-line/60">
          {KLINES.map((k, i) => (
            <button key={k.label} onClick={() => setKidx(i)}
              className={`px-2.5 py-1 rounded text-xs transition-colors ${i === kidx ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink"}`}>
              {k.label}
            </button>
          ))}
          <span className="ml-auto text-[11px] text-ink-faint">
            {rb ? `数据更新于 ${sinceLabel(rb.generated_at)}` : ""}
          </span>
        </div>

        <div className="flex-1 overflow-auto p-4 relative">
          {chartLoading && (
            <span className="absolute top-5 right-6 z-10 text-[11px] text-ink-faint bg-panel/80 border border-line rounded px-2 py-0.5">加载中…</span>
          )}
          {ohlcv && ta ? <Chart ohlcv={ohlcv} technical={ta} /> : (
            <div className="h-[420px] grid place-items-center text-ink-faint text-sm">
              {err ? "图表加载失败" : "图表加载中…"}
            </div>
          )}
          {rb && rb.technical_signals.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {rb.technical_signals.map((s) => (
                <span key={s} className="px-2 py-0.5 rounded-md bg-panel-2 border border-line text-[11px] text-ink-dim">{s}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right: header + tabbed panel */}
      <div className="w-[340px] shrink-0 border-l border-line flex flex-col overflow-hidden">
        {/* Futu-style quote header */}
        <div className="px-4 pt-3 pb-2 border-b border-line">
          <div className="flex items-baseline gap-2">
            <span className="text-base font-semibold truncate">{f?.name ?? q?.name ?? sym}</span>
            <span className="text-xs text-ink-faint">{sym}</span>
          </div>
          <div className="flex items-baseline gap-2 mt-1">
            <span className={`text-2xl font-semibold tnum ${dirClass(q?.change_pct)}`}>{q?.price != null ? num(q.price) : "—"}</span>
            <span className={`text-sm tnum ${dirClass(q?.change_pct)}`}>
              {q?.change != null ? (q.change >= 0 ? "+" : "") + num(q.change) : ""} {signedPct(q?.change_pct)}
            </span>
          </div>
          <div className="text-[11px] text-ink-faint mt-1">
            昨收 {num(prev?.close)} · 今开 {num(last?.open)} · 最高 {num(last?.high)} · 最低 {num(last?.low)}
          </div>
        </div>

        <div className="flex items-center border-b border-line h-10 px-2">
          {(["解读", "报价估值", "新闻舆情"] as Tab[]).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-3 py-1.5 text-sm rounded transition-colors ${t === tab ? "text-accent" : "text-ink-dim hover:text-ink"}`}>
              {t}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-4 space-y-4">
          {tab === "解读" && (
            <>
              <button onClick={analyze} disabled={analyzing}
                className="w-full rounded-lg bg-accent/15 text-accent text-sm font-medium py-2 hover:bg-accent/25 disabled:opacity-50">
                {analyzing ? "分析中… (~30–60s)" : analysis ? "重新分析" : "AI 解读"}
              </button>
              {analysis ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <RecBadge rec={analysis.result.recommendation} tone={recTone(analysis.result.recommendation)} />
                    {analysis.result.target_price != null && (
                      <span className="text-xs text-ink-dim tnum">目标 {num(analysis.result.target_price)} · {analysis.result.time_horizon}</span>
                    )}
                  </div>
                  <ScoreMeter score={analysis.result.score} />
                  <p className="text-sm text-ink-dim leading-relaxed">{analysis.result.summary}</p>
                  {analysis.result.bull_case && <p className="text-xs text-ink-dim"><span className="text-up font-medium">多头 · </span>{analysis.result.bull_case}</p>}
                  {analysis.result.bear_case && <p className="text-xs text-ink-dim"><span className="text-down font-medium">空头 · </span>{analysis.result.bear_case}</p>}
                  {analysis.result.risks.length > 0 && (
                    <div>
                      <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">风险</div>
                      <ul className="list-disc list-inside text-xs text-ink-dim space-y-0.5">{analysis.result.risks.map((r, i) => <li key={i}>{r}</li>)}</ul>
                    </div>
                  )}
                  {analysis.result.catalysts.length > 0 && (
                    <div>
                      <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">催化剂</div>
                      <ul className="list-disc list-inside text-xs text-ink-dim space-y-0.5">{analysis.result.catalysts.map((c, i) => <li key={i}>{c}</li>)}</ul>
                    </div>
                  )}
                  <p className="text-[11px] text-ink-faint pt-1">AI 观点 · 非投资建议 · {analysis.provider}</p>
                </div>
              ) : (
                <p className="text-sm text-ink-faint">运行 AI 大脑,得到有依据的论点、评分、风险与催化剂(中文)。</p>
              )}
            </>
          )}

          {tab === "报价估值" && (
            <>
              {/* Dense quote grid (Futu 报价-style), from the latest daily bar + quote */}
              <div className="rounded-lg border border-line bg-panel/40 p-3">
                <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-2">报价</div>
                <div className="grid grid-cols-2 gap-x-4">
                  <Stat label="最新价" value={num(q?.price)} tone={(q?.change_pct ?? 0) >= 0 ? "up" : "down"} />
                  <Stat label="涨跌幅" value={signedPct(q?.change_pct)} tone={(q?.change_pct ?? 0) >= 0 ? "up" : "down"} />
                  <Stat label="今开" value={num(last?.open)} />
                  <Stat label="昨收" value={num(prev?.close)} />
                  <Stat label="最高" value={num(last?.high)} />
                  <Stat label="最低" value={num(last?.low)} />
                  <Stat label="成交量" value={compact(last?.volume ?? null)} />
                  <Stat label="均量(日)" value={compact(f?.avg_volume)} />
                  <Stat label="换手率" value={turnover != null ? `${turnover.toFixed(2)}%` : "—"} />
                  <Stat label="总股本" value={compact(f?.shares_outstanding)} />
                  <Stat label="流通股" value={compact(f?.float_shares)} />
                  <Stat label="52周高" value={num(f?.week52_high)} />
                  <Stat label="52周低" value={num(f?.week52_low)} />
                </div>
              </div>

              <div className="rounded-lg border border-line bg-panel/40 p-3">
                <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-2">估值</div>
                <div className="grid grid-cols-2 gap-x-4">
                  <Stat label="市值" value={compact(f?.market_cap)} />
                  <Stat label="P/E (TTM)" value={num(f?.pe_ttm)} />
                  <Stat label="P/E (Fwd)" value={num(f?.pe_fwd)} />
                  <Stat label="P/B" value={num(f?.pb)} />
                  <Stat label="P/S" value={num(f?.ps)} />
                  <Stat label="PEG" value={num(f?.peg)} />
                  <Stat label="EV/EBITDA" value={num(f?.ev_ebitda)} />
                  <Stat label="股息率" value={pct(f?.dividend_yield)} />
                </div>
              </div>

              <div className="rounded-lg border border-line bg-panel/40 p-3">
                <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-2">盈利能力</div>
                <div className="grid grid-cols-2 gap-x-4">
                  <Stat label="毛利率" value={pct(f?.gross_margin)} />
                  <Stat label="营业利润率" value={pct(f?.operating_margin)} />
                  <Stat label="净利率" value={pct(f?.net_margin)} />
                  <Stat label="ROE" value={pct(f?.roe)} />
                  <Stat label="ROA" value={pct(f?.roa)} />
                  <Stat label="营收增速" value={pct(f?.revenue_growth)} />
                  <Stat label="EPS" value={num(f?.eps)} />
                  <Stat label="Beta" value={num(f?.beta)} />
                </div>
              </div>

              <div className="rounded-lg border border-line bg-panel/40 p-3">
                <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-2">分析师评级</div>
                {f?.recommendation ? (
                  <>
                    <div className="flex items-center justify-between mb-2">
                      <RecBadge rec={f.recommendation.replace(/_/g, " ")} tone={recTone(f.recommendation)} />
                      <span className="text-xs text-ink-dim tnum">{f.num_analysts ?? "—"} 位分析师</span>
                    </div>
                    <AnalystGauge mean={f.recommendation_mean} />
                    <div className="mt-2">
                      <Stat label="目标价(均值)" value={num(f.target_mean)} />
                      <Stat label="上行空间" value={signedPct(upside)} tone={upside != null && upside >= 0 ? "up" : "down"} />
                      <Stat label="目标区间" value={`${num(f.target_low)} – ${num(f.target_high)}`} />
                    </div>
                  </>
                ) : <p className="text-sm text-ink-faint">暂无分析师覆盖。</p>}
              </div>
            </>
          )}

          {tab === "新闻舆情" && (
            <>
              <div className="rounded-lg border border-line bg-panel/40 p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {newsAna ? (
                      <>
                        <RecBadge
                          rec={newsAna.result.overall === "bullish" ? "偏多" : newsAna.result.overall === "bearish" ? "偏空" : "中性"}
                          tone={newsAna.result.overall === "bullish" ? "up" : newsAna.result.overall === "bearish" ? "down" : "amber"}
                        />
                        <span className="text-[11px] text-ink-faint">影响 {newsAna.result.impact}</span>
                      </>
                    ) : <span className="text-xs text-ink-faint">AI 尚未分析舆情</span>}
                  </div>
                  <button onClick={analyzeNews} disabled={analyzingNews}
                    className="rounded-md bg-accent/15 text-accent text-xs font-medium px-3 py-1.5 hover:bg-accent/25 disabled:opacity-50">
                    {analyzingNews ? "分析中…" : newsAna ? "重新分析" : "AI 分析舆情"}
                  </button>
                </div>
                {newsAna && (
                  <div className="space-y-2">
                    <p className="text-sm text-ink-dim leading-relaxed">{newsAna.result.summary}</p>
                    {newsAna.result.bull_points.length > 0 && (
                      <div>
                        <div className="text-[11px] uppercase tracking-wide text-up mb-1">利好</div>
                        <ul className="list-disc list-inside text-xs text-ink-dim space-y-0.5">{newsAna.result.bull_points.map((p, i) => <li key={i}>{p}</li>)}</ul>
                      </div>
                    )}
                    {newsAna.result.bear_points.length > 0 && (
                      <div>
                        <div className="text-[11px] uppercase tracking-wide text-down mb-1">利空</div>
                        <ul className="list-disc list-inside text-xs text-ink-dim space-y-0.5">{newsAna.result.bear_points.map((p, i) => <li key={i}>{p}</li>)}</ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <ul className="space-y-2">
                {rb?.news.map((n, i) => (
                  <li key={i} className="text-sm border-b border-line/40 pb-2 last:border-0">
                    <a href={n.url ?? "#"} target="_blank" rel="noreferrer" className="text-ink hover:text-accent">{n.title}</a>
                    <div className="text-ink-faint text-[11px] mt-0.5">{n.publisher ?? ""}{n.published_at ? ` · ${sinceLabel(n.published_at)}` : ""}</div>
                  </li>
                ))}
                {rb && rb.news.length === 0 && <li className="text-sm text-ink-faint">暂无近期新闻。</li>}
              </ul>
            </>
          )}
        </div>
      </div>
    </>
  );
}

// Futu-style consensus gauge from yfinance recommendationMean (1=Strong Buy … 5=Sell).
function AnalystGauge({ mean }: { mean: number | null }) {
  if (mean == null) return null;
  const m = Math.max(1, Math.min(5, mean));
  const posPct = ((m - 1) / 4) * 100; // 0% = strong buy (left), 100% = sell (right)
  const label = m <= 1.5 ? "强力买入" : m <= 2.5 ? "买入" : m <= 3.5 ? "持有" : m <= 4.5 ? "减持" : "卖出";
  const tone = m <= 2.5 ? "text-up" : m >= 3.5 ? "text-down" : "text-warn";
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className={`text-sm font-medium ${tone}`}>{label}</span>
        <span className="text-[11px] text-ink-faint tnum">评级 {m.toFixed(2)} / 5</span>
      </div>
      <div className="relative h-1.5 rounded-full overflow-hidden" style={{ background: "linear-gradient(90deg,#F6465D,#E0A33E,#2EBD85)" }}>
        <span className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-white ring-1 ring-black/40" style={{ left: `${posPct}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-ink-faint mt-0.5"><span>买入</span><span>持有</span><span>卖出</span></div>
    </div>
  );
}
