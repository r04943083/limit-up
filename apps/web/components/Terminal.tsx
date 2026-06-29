"use client";

import { useEffect, useState, useCallback } from "react";
import Chart from "@/components/Chart";
import IntradayChart from "@/components/IntradayChart";
import ValuationPanel from "@/components/ValuationPanel";
import { Stat, RecBadge, ScoreMeter } from "@/components/ui";
import {
  getResearch, getTechnical, getOhlcv, getIntraday, getAnalysis, runAnalyze,
  getNewsAnalysis, runNewsAnalysis,
  type ResearchBundle, type Technical, type OhlcvBar, type IntradayPoint, type SavedAnalysis,
  type SavedNewsAnalysis,
} from "@/lib/api";
import { num, compact, pct, signedPct, recTone, sinceLabel, dirClass } from "@/lib/format";

// 分时/5日 are live intraday lines; 日K/周K/月K are cached candlesticks.
const TIMEFRAMES = [
  { label: "分时", kind: "intraday", range: "1d" },
  { label: "5日", kind: "intraday", range: "5d" },
  { label: "日K", kind: "kline", period: "1y", interval: "1d" },
  { label: "周K", kind: "kline", period: "5y", interval: "1wk" },
  { label: "月K", kind: "kline", period: "max", interval: "1mo" },
] as const;

// Futu's right-panel forms (报价 / 分析 / 资讯 / 评论) + LU's AI 解读.
type Tab = "报价" | "分析" | "资讯" | "评论" | "解读";

// The Futu-style three-column terminal body (center chart + right tab panel) for one symbol.
// The left WatchlistPane is rendered by the page so it can drive symbol selection.
export default function Terminal({ symbol, reloadKey = 0 }: { symbol: string | null; reloadKey?: number }) {
  const sym = symbol?.toUpperCase() ?? "";

  const [rb, setRb] = useState<ResearchBundle | null>(null);
  const [ta, setTa] = useState<Technical | null>(null);
  const [ohlcv, setOhlcv] = useState<OhlcvBar[] | null>(null);
  const [intra, setIntra] = useState<IntradayPoint[] | null>(null);
  const [daily, setDaily] = useState<OhlcvBar[] | null>(null);
  const [analysis, setAnalysis] = useState<SavedAnalysis | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [newsAna, setNewsAna] = useState<SavedNewsAnalysis | null>(null);
  const [analyzingNews, setAnalyzingNews] = useState(false);
  const [kidx, setKidx] = useState(2);  // default to 日K
  const [tab, setTab] = useState<Tab>("报价");
  const [chartLoading, setChartLoading] = useState(false);

  const tf = TIMEFRAMES[kidx];

  const loadBundle = useCallback(() => {
    if (!sym) return;
    setErr(null); setRb(null);
    getResearch(sym).then(setRb).catch((e) => setErr(String(e)));
  }, [sym]);

  const loadChart = useCallback(() => {
    if (!sym) return;
    const k = TIMEFRAMES[kidx];
    setChartLoading(true);
    if (k.kind === "intraday") {
      getIntraday(sym, k.range)
        .then((pts) => { setIntra(pts); })
        .catch((e) => setErr(String(e)))
        .finally(() => setChartLoading(false));
    } else {
      Promise.all([getOhlcv(sym, k.period, k.interval), getTechnical(sym, k.period, k.interval)])
        .then(([o, t]) => { setOhlcv(o); setTa(t); })
        .catch((e) => setErr(String(e)))
        .finally(() => setChartLoading(false));
    }
  }, [sym, kidx]);

  // Daily bars for the 报价 stats (今开/最高/最低/成交量/振幅) — independent of the chart timeframe.
  useEffect(() => {
    if (!sym) { setDaily(null); return; }
    getOhlcv(sym, "5d", "1d").then(setDaily).catch(() => setDaily(null));
  }, [sym, reloadKey]);

  useEffect(() => {
    if (!sym) return;
    loadBundle();
    getAnalysis(sym).then(setAnalysis).catch(() => {});
    setNewsAna(null);
    getNewsAnalysis(sym).then(setNewsAna).catch(() => {});
    // reloadKey is bumped by StockPage's ↻ 更新 so the chart + bundle refresh together
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sym, loadBundle, reloadKey]);

  // Keep the previous chart visible while the next loads (avoids a jarring blank);
  // a subtle badge signals the refresh.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadChart(); }, [loadChart, reloadKey]);

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
  // Today's O/H/L/Vol from the latest daily bar (loaded independently of the chart timeframe).
  const last = daily && daily.length ? daily[daily.length - 1] : null;
  const prev = daily && daily.length > 1 ? daily[daily.length - 2] : null;
  // 换手率 = 成交量 / 流通股本.
  const turnover = last?.volume && f?.float_shares ? (last.volume / f.float_shares) * 100 : null;
  const amount = last?.volume && q?.price ? last.volume * q.price : null;  // 成交额
  const avgPrice = amount && last?.volume ? amount / last.volume : null;   // 均价 = 成交额 / 成交量
  const floatValue = q?.price && f?.float_shares ? q.price * f.float_shares : null;  // 流通值
  const amplitude = last?.high != null && last?.low != null && prev?.close
    ? ((last.high - last.low) / prev.close) * 100 : null;  // 振幅

  if (!sym) {
    return (
      <div className="flex-1 grid place-items-center text-ink-faint text-sm">
        从左侧选择一个自选标的查看行情与分析。
      </div>
    );
  }

  return (
    <>
      {/* Center: chart (the quote header lives in StockPage, always visible across tabs) */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {err && <div className="mx-5 mt-3 rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

        <div className="flex items-center gap-1 px-5 h-9 border-t border-line/60">
          {TIMEFRAMES.map((k, i) => (
            <button key={k.label} onClick={() => setKidx(i)}
              className={`px-2.5 py-1 rounded text-xs transition-colors ${i === kidx ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink"}`}>
              {k.label}
            </button>
          ))}
          <span className="ml-auto text-[11px] text-ink-faint">
            {tf.kind === "intraday" ? "分时为实时数据" : rb ? `数据更新于 ${sinceLabel(rb.generated_at)}` : ""}
          </span>
        </div>

        <div className="flex-1 overflow-auto p-4 relative">
          {chartLoading && (
            <span className="absolute top-5 right-6 z-10 text-[11px] text-ink-faint bg-panel/80 border border-line rounded px-2 py-0.5">加载中…</span>
          )}
          {tf.kind === "intraday" ? (
            intra ? <IntradayChart data={intra} baseline={prev?.close ?? null} /> : (
              <div className="h-[420px] grid place-items-center text-ink-faint text-sm">{err ? "分时加载失败" : "分时加载中…"}</div>
            )
          ) : ohlcv && ta ? <Chart ohlcv={ohlcv} technical={ta} /> : (
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

      {/* Right: Futu-style forms (报价 / 分析 / 资讯 / 评论) + LU AI 解读 */}
      <div className="w-[360px] shrink-0 border-l border-line flex flex-col overflow-hidden">
        {/* Futu-style quote header */}
        <div className="px-4 pt-3 pb-2 border-b border-line">
          <div className="text-base font-semibold text-ink truncate" title={f?.name ?? q?.name ?? sym}>
            {f?.name ?? q?.name ?? sym}
          </div>
          <div className="text-xs text-ink-faint mt-0.5">
            {sym}{rb?.market ? ` · ${rb.market}` : ""}
          </div>
          <div className="flex items-baseline gap-2 mt-1.5">
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
          {(["报价", "分析", "资讯", "评论", "解读"] as Tab[]).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-2.5 py-1.5 text-sm rounded transition-colors ${t === tab ? "text-accent font-medium" : "text-ink-dim hover:text-ink"}`}>
              {t}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-4 space-y-4">
          {/* 报价 — fu2.png: dense quote table + 盘口/资金/异动 (Level-2 数据缺口诚实占位) */}
          {tab === "报价" && (
            <>
              <div className="rounded-lg border border-line bg-panel/40 p-3">
                <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                  <Stat label="最高" value={num(last?.high)} />
                  <Stat label="开盘" value={num(last?.open)} />
                  <Stat label="最低" value={num(last?.low)} />
                  <Stat label="昨收" value={num(prev?.close)} />
                  <Stat label="均价" value={num(avgPrice)} />
                  <Stat label="市盈率TTM" value={num(f?.pe_ttm)} />
                  <Stat label="振幅" value={amplitude != null ? `${amplitude.toFixed(2)}%` : "—"} />
                  <Stat label="市盈率(动)" value={num(f?.pe_fwd)} />
                  <Stat label="换手率" value={turnover != null ? `${turnover.toFixed(2)}%` : "—"} />
                  <Stat label="市净率" value={num(f?.pb)} />
                  <Stat label="成交量" value={compact(last?.volume ?? null)} />
                  <Stat label="市销率" value={num(f?.ps)} />
                  <Stat label="成交额" value={compact(amount)} />
                  <Stat label="市值" value={compact(f?.market_cap)} />
                  <Stat label="52周最高" value={num(f?.week52_high)} />
                  <Stat label="总股本" value={compact(f?.shares_outstanding)} />
                  <Stat label="52周最低" value={num(f?.week52_low)} />
                  <Stat label="流通股" value={compact(f?.float_shares)} />
                  <Stat label="股息率TTM" value={pct(f?.dividend_yield)} />
                  <Stat label="流通值" value={compact(floatValue)} />
                  <Stat label="Beta" value={num(f?.beta)} />
                  <Stat label="均量(日)" value={compact(f?.avg_volume)} />
                </div>
              </div>

              {/* 盘口 / 资金 / 异动 — these need Level-2 (free sources can't supply) */}
              <div className="rounded-lg border border-line bg-panel/40 p-3">
                <div className="flex items-center gap-3 mb-2 text-[11px]">
                  {["盘口逐笔", "资金流向", "异动"].map((t) => (
                    <span key={t} className="text-ink-dim">{t}</span>
                  ))}
                </div>
                <div className="flex items-center gap-1 mb-2">
                  <div className="h-2 rounded-l-full bg-up/60" style={{ width: "50%" }} />
                  <div className="h-2 rounded-r-full bg-down/60" style={{ width: "50%" }} />
                </div>
                <div className="flex justify-between text-[11px] text-ink-faint mb-2">
                  <span>买盘 —%</span><span>卖盘 —%</span>
                </div>
                <p className="text-[11px] text-ink-faint leading-relaxed">
                  买卖五档 / 盘口逐笔(Level-2)、主力 / 超大单资金流、实时异动需专业行情源,免费数据源(yfinance / akshare)不提供,暂以占位显示。
                </p>
              </div>
            </>
          )}

          {/* 分析 — fu.png: 公司估值 (PE/PB/PS 估值带 + 行业平均 + 超过历史) + 分析师评级 + 卖空 */}
          {tab === "分析" && <ValuationPanel symbol={sym} />}

          {/* 资讯 — fu3.png: 个股新闻流 + AI 舆情 */}
          {tab === "资讯" && (
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
              <ul className="space-y-2.5">
                {rb?.news.map((n, i) => (
                  <li key={i} className="text-sm border-b border-line/40 pb-2.5 last:border-0">
                    <a href={n.url ?? "#"} target="_blank" rel="noreferrer" className="text-ink hover:text-accent leading-snug block">{n.title}</a>
                    <div className="text-ink-faint text-[11px] mt-1">{n.publisher ?? ""}{n.published_at ? ` · ${sinceLabel(n.published_at)}` : ""}</div>
                  </li>
                ))}
                {rb && rb.news.length === 0 && <li className="text-sm text-ink-faint">暂无近期新闻。</li>}
              </ul>
            </>
          )}

          {/* 评论 — fu4.png: 社区贴文(需富途社区数据源,暂未接入) */}
          {tab === "评论" && (
            <div className="rounded-lg border border-line bg-panel/40 p-4 text-center space-y-2">
              <div className="text-sm text-ink-dim">社区评论</div>
              <p className="text-[12px] text-ink-faint leading-relaxed">
                富途牛牛圈 / 社区贴文需富途社区数据源,暂未接入。
                可先到「资讯」看新闻舆情,或用「解读」获取 AI 多空观点。
              </p>
            </div>
          )}

          {/* 解读 — LU AI 大脑(富途没有,LU 原生增益) */}
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
        </div>
      </div>
    </>
  );
}
