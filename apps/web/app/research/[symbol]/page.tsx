"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Panel from "@/components/Panel";
import Chart from "@/components/Chart";
import { Stat, RecBadge, ScoreMeter, Chip } from "@/components/ui";
import {
  getResearch, getTechnical, getOhlcv, getAnalysis, runAnalyze, syncSymbol,
  type ResearchBundle, type Technical, type OhlcvBar, type SavedAnalysis,
} from "@/lib/api";
import { num, compact, pct, signedPct, recTone, sinceLabel } from "@/lib/format";

export default function ResearchPage() {
  const params = useParams<{ symbol: string }>();
  const sym = decodeURIComponent(params.symbol).toUpperCase();

  const [rb, setRb] = useState<ResearchBundle | null>(null);
  const [ta, setTa] = useState<Technical | null>(null);
  const [ohlcv, setOhlcv] = useState<OhlcvBar[] | null>(null);
  const [analysis, setAnalysis] = useState<SavedAnalysis | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const loadAll = useCallback(() => {
    setErr(null);
    setRb(null);
    Promise.all([getResearch(sym), getTechnical(sym), getOhlcv(sym)])
      .then(([r, t, o]) => {
        setRb(r);
        setTa(t);
        setOhlcv(o);
      })
      .catch((e) => setErr(String(e)));
  }, [sym]);

  useEffect(() => {
    loadAll();
    getAnalysis(sym).then(setAnalysis).catch(() => {});
  }, [sym, loadAll]);

  const sync = useCallback(() => {
    setSyncing(true);
    syncSymbol(sym)
      .then(() => loadAll())
      .catch((e) => setErr(String(e)))
      .finally(() => setSyncing(false));
  }, [sym, loadAll]);

  const analyze = useCallback(() => {
    setAnalyzing(true);
    runAnalyze(sym)
      .then(setAnalysis)
      .catch((e) => setErr(String(e)))
      .finally(() => setAnalyzing(false));
  }, [sym]);

  const f = rb?.fundamentals;
  const q = rb?.quote;
  const upside =
    f?.target_mean && q?.price ? ((f.target_mean - q.price) / q.price) * 100 : null;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-baseline gap-3">
          <Link href="/watchlist" className="text-ink-faint hover:text-ink text-sm">
            ← Watchlist
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight">{sym}</h1>
          <span className="text-sm text-ink-dim">{f?.name ?? rb?.quote.name ?? ""}</span>
          {rb && <Chip>{rb.market}</Chip>}
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-2xl font-semibold tnum">
              {q?.price != null ? num(q.price) : "—"}{" "}
              <span className="text-sm text-ink-dim">{q?.currency}</span>
            </div>
            <div className={`text-sm tnum ${(q?.change_pct ?? 0) >= 0 ? "text-up" : "text-down"}`}>
              {signedPct(q?.change_pct)}
            </div>
          </div>
          <div className="text-right">
            <button
              onClick={sync}
              disabled={syncing}
              className="rounded-lg border border-line text-sm px-3 py-1.5 text-ink-dim hover:text-ink hover:border-accent/40 disabled:opacity-50 transition-colors"
            >
              {syncing ? "更新中…" : "↻ 更新数据"}
            </button>
            <div className="text-[11px] text-ink-faint mt-1">
              {rb ? `数据更新于 ${sinceLabel(rb.generated_at)}` : ""}
            </div>
          </div>
        </div>
      </div>

      {err && (
        <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Left: chart + signals + news */}
        <div className="xl:col-span-2 space-y-5">
          <Panel title="Price & Technicals" hint={rb ? rb.technical_trend : ""}>
            {ohlcv && ta ? (
              <Chart ohlcv={ohlcv} technical={ta} />
            ) : (
              <div className="h-[420px] grid place-items-center text-ink-faint text-sm">
                {err ? "Failed to load chart" : "Loading chart…"}
              </div>
            )}
            {rb && (
              <div className="flex flex-wrap gap-2 mt-3">
                {rb.technical_signals.map((s) => (
                  <Chip key={s}>{s}</Chip>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Recent News" hint={rb ? `${rb.news.length}` : ""}>
            <ul className="space-y-2">
              {rb?.news.map((n, i) => (
                <li key={i} className="text-sm">
                  <a
                    href={n.url ?? "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="text-ink hover:text-accent"
                  >
                    {n.title}
                  </a>
                  <span className="text-ink-faint text-xs"> · {n.publisher ?? ""}</span>
                </li>
              ))}
              {rb && rb.news.length === 0 && <li className="text-sm text-ink-faint">No recent news.</li>}
            </ul>
          </Panel>
        </div>

        {/* Right: stats + analyst + AI */}
        <div className="space-y-5">
          <Panel title="Key Stats">
            <Stat label="Market Cap" value={compact(f?.market_cap)} />
            <Stat label="P/E (TTM)" value={num(f?.pe_ttm)} />
            <Stat label="P/E (Fwd)" value={num(f?.pe_fwd)} />
            <Stat label="P/S" value={num(f?.ps)} />
            <Stat label="P/B" value={num(f?.pb)} />
            <Stat label="PEG" value={num(f?.peg)} />
            <Stat label="Gross Margin" value={pct(f?.gross_margin)} />
            <Stat label="Net Margin" value={pct(f?.net_margin)} />
            <Stat label="ROE" value={pct(f?.roe)} />
            <Stat label="Rev Growth" value={pct(f?.revenue_growth)} />
            <Stat label="Beta" value={num(f?.beta)} />
            <Stat label="52w Range" value={`${num(f?.week52_low)} – ${num(f?.week52_high)}`} />
          </Panel>

          <Panel title="Analyst Consensus">
            {f?.recommendation ? (
              <>
                <div className="flex items-center justify-between mb-3">
                  <RecBadge rec={f.recommendation.replace(/_/g, " ")} tone={recTone(f.recommendation)} />
                  <span className="text-xs text-ink-dim tnum">{f.num_analysts ?? "—"} analysts</span>
                </div>
                <Stat label="Target (mean)" value={num(f.target_mean)} />
                <Stat label="Upside" value={signedPct(upside)} tone={upside != null && upside >= 0 ? "up" : "down"} />
                <Stat label="Target range" value={`${num(f.target_low)} – ${num(f.target_high)}`} />
              </>
            ) : (
              <p className="text-sm text-ink-faint">No analyst coverage.</p>
            )}
          </Panel>

          <Panel title="AI Analysis" hint={analysis ? analysis.provider : "claude -p"}>
            <button
              onClick={analyze}
              disabled={analyzing}
              className="w-full mb-3 rounded-lg bg-accent/15 text-accent text-sm font-medium py-2 hover:bg-accent/25 disabled:opacity-50 transition-colors"
            >
              {analyzing ? "Analyzing… (~30–60s)" : analysis ? "Re-analyze" : "Analyze with AI"}
            </button>
            {analysis ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <RecBadge
                    rec={analysis.result.recommendation}
                    tone={recTone(analysis.result.recommendation)}
                  />
                  {analysis.result.target_price != null && (
                    <span className="text-xs text-ink-dim tnum">
                      target {num(analysis.result.target_price)} · {analysis.result.time_horizon}
                    </span>
                  )}
                </div>
                <ScoreMeter score={analysis.result.score} />
                <p className="text-sm text-ink-dim leading-relaxed">{analysis.result.summary}</p>
                {analysis.result.bull_case && (
                  <p className="text-xs text-ink-dim">
                    <span className="text-up font-medium">Bull · </span>
                    {analysis.result.bull_case}
                  </p>
                )}
                {analysis.result.bear_case && (
                  <p className="text-xs text-ink-dim">
                    <span className="text-down font-medium">Bear · </span>
                    {analysis.result.bear_case}
                  </p>
                )}
                {analysis.result.risks.length > 0 && (
                  <div>
                    <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">Risks</div>
                    <ul className="list-disc list-inside text-xs text-ink-dim space-y-0.5">
                      {analysis.result.risks.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {analysis.result.catalysts.length > 0 && (
                  <div>
                    <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">Catalysts</div>
                    <ul className="list-disc list-inside text-xs text-ink-dim space-y-0.5">
                      {analysis.result.catalysts.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className="text-[11px] text-ink-faint pt-1">AI opinion · not financial advice</p>
              </div>
            ) : (
              <p className="text-sm text-ink-faint">
                Run the AI brain to get a grounded thesis, score, risks and catalysts.
              </p>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
