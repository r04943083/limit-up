"use client";

import { useCallback, useEffect, useState } from "react";
import Terminal from "@/components/Terminal";
import DeepResearch from "@/components/DeepResearch";
import Panel from "@/components/Panel";
import { Stat } from "@/components/ui";
import { getProfile, getResearch, syncSymbol, type CompanyProfile, type ResearchBundle } from "@/lib/api";
import { compact, num, pct, signedPct, dirClass } from "@/lib/format";

const TABS = ["行情", "财报", "分红", "股东", "概况"] as const;
type Tab = (typeof TABS)[number];

/**
 * Futu-style individual-stock page: a persistent quote header (always visible across
 * sub-tabs) + a tab bar over a dense content area. 行情 reuses the Terminal (chart +
 * quote/AI/news panel); 财报 reuses DeepResearch (statements + DCF); 分红/股东/概况
 * render the cached CompanyProfile.
 */
export default function StockPage({ symbol }: { symbol: string | null }) {
  const [tab, setTab] = useState<Tab>("行情");
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [profLoading, setProfLoading] = useState(false);
  const [rb, setRb] = useState<ResearchBundle | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [syncing, setSyncing] = useState(false);

  const needsProfile = tab === "分红" || tab === "股东" || tab === "概况";

  useEffect(() => {
    setProfile(null);
    setRb(null);
  }, [symbol]);

  // Header quote (cache-first; refreshed when the user hits ↻ 更新).
  useEffect(() => {
    if (!symbol) return;
    getResearch(symbol).then(setRb).catch(() => setRb(null));
  }, [symbol, reloadKey]);

  useEffect(() => {
    if (!symbol || !needsProfile || profile) return;
    setProfLoading(true);
    getProfile(symbol).then(setProfile).catch(() => setProfile(null)).finally(() => setProfLoading(false));
  }, [symbol, needsProfile, profile]);

  const sync = useCallback(() => {
    if (!symbol) return;
    setSyncing(true);
    syncSymbol(symbol).then(() => setReloadKey((k) => k + 1)).catch(() => {}).finally(() => setSyncing(false));
  }, [symbol]);

  if (!symbol) {
    return (
      <div className="flex-1 grid place-items-center text-ink-faint text-sm">
        从左侧选择一个自选标的查看行情与分析。
      </div>
    );
  }

  const q = rb?.quote;
  const f = rb?.fundamentals;

  return (
    <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
      {/* Persistent Futu-style quote header — visible on every sub-tab. */}
      <div className="flex items-center justify-between gap-4 px-4 h-14 border-b border-line shrink-0">
        <div className="flex items-baseline gap-2.5 min-w-0">
          <h1 className="text-lg font-semibold tracking-tight truncate">{f?.name ?? q?.name ?? symbol}</h1>
          <span className="text-sm text-ink-dim">{symbol}</span>
          {rb && <span className="px-1.5 py-0.5 rounded bg-panel-2 text-[10px] text-ink-faint">{rb.market}</span>}
          <span className={`text-xl font-semibold tnum ml-1 ${dirClass(q?.change_pct)}`}>{q?.price != null ? num(q.price) : "—"}</span>
          <span className={`text-sm tnum ${dirClass(q?.change_pct)}`}>
            {q?.change != null ? (q.change >= 0 ? "+" : "") + num(q.change) : ""} {signedPct(q?.change_pct)}
          </span>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <div className="hidden xl:flex items-center gap-4 text-[11px] text-ink-faint">
            <HdrStat k="总市值" v={compact(f?.market_cap)} />
            <HdrStat k="PE(TTM)" v={num(f?.pe_ttm)} />
            <HdrStat k="P/B" v={num(f?.pb)} />
            <HdrStat k="股息率" v={pct(f?.dividend_yield)} />
            <HdrStat k="52周高" v={num(f?.week52_high)} />
            <HdrStat k="52周低" v={num(f?.week52_low)} />
          </div>
          <button onClick={sync} disabled={syncing}
            className="rounded-lg border border-line text-xs px-3 py-1.5 text-ink-dim hover:text-ink hover:border-accent/40 disabled:opacity-50">
            {syncing ? "更新中…" : "↻ 更新"}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1 px-4 h-11 border-b border-line shrink-0">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-3.5 py-1.5 text-sm rounded-lg transition-colors ${
              t === tab ? "bg-panel-2 text-ink border border-line" : "text-ink-dim hover:text-ink"
            }`}>
            {t}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0 flex">
        {tab === "行情" && <Terminal symbol={symbol} reloadKey={reloadKey} />}
        {tab === "财报" && <DeepResearch symbol={symbol} />}
        {needsProfile && (
          <div className="flex-1 min-w-0 overflow-auto p-5 space-y-5">
            {profLoading && !profile && <p className="text-sm text-ink-faint py-6 text-center">加载中…</p>}
            {tab === "分红" && profile && <Dividends p={profile} />}
            {tab === "股东" && profile && <Holders p={profile} />}
            {tab === "概况" && profile && <Profile p={profile} />}
            {!profLoading && !profile && <p className="text-sm text-ink-faint py-6 text-center">暂无数据。</p>}
          </div>
        )}
      </div>
    </div>
  );
}

function HdrStat({ k, v }: { k: string; v: string }) {
  return <span className="whitespace-nowrap"><span className="text-ink-faint">{k}</span> <span className="tnum text-ink-dim">{v}</span></span>;
}

// Group dividends by calendar year (sum) for a compact annual bar row.
function annualTotals(p: CompanyProfile): { year: string; total: number }[] {
  const m = new Map<string, number>();
  for (const d of p.dividends) {
    const y = d.ex_date.slice(0, 4);
    m.set(y, (m.get(y) ?? 0) + d.amount);
  }
  return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([year, total]) => ({ year, total }));
}

function Dividends({ p }: { p: CompanyProfile }) {
  const years = annualTotals(p);
  const max = Math.max(1, ...years.map((y) => y.total));
  if (!p.dividends.length) {
    return (
      <Panel title="分红">
        <p className="text-sm text-ink-faint py-4">该标的无分红记录(或数据源未提供)。{p.dividend_yield != null ? `当前股息率 ${pct(p.dividend_yield)}。` : ""}</p>
      </Panel>
    );
  }
  return (
    <>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <div className="rounded-lg border border-line bg-panel p-4">
          <div className="text-xs text-ink-faint mb-1">股息率</div>
          <div className="text-2xl font-semibold tnum">{pct(p.dividend_yield)}</div>
        </div>
        <div className="rounded-lg border border-line bg-panel p-4">
          <div className="text-xs text-ink-faint mb-1">派息率</div>
          <div className="text-2xl font-semibold tnum">{pct(p.payout_ratio)}</div>
        </div>
        <div className="rounded-lg border border-line bg-panel p-4">
          <div className="text-xs text-ink-faint mb-1">最近一期每股派息</div>
          <div className="text-2xl font-semibold tnum">{num(p.dividends[0].amount)} <span className="text-sm text-ink-dim">{p.currency ?? ""}</span></div>
        </div>
      </div>

      {years.length > 1 && (
        <Panel title="年度每股分红" hint={`${years.length} 年`}>
          <div className="flex items-end gap-2 h-28">
            {years.map((y) => (
              <div key={y.year} className="flex-1 flex flex-col items-center justify-end gap-1">
                <span className="text-[10px] tnum text-ink-dim">{num(y.total)}</span>
                <div className="w-full rounded-t bg-up/70" style={{ height: `${(y.total / max) * 100}%` }} />
                <span className="text-[10px] text-ink-faint">{y.year}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <Panel title="分红明细" hint={`${p.dividends.length} 期`}>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[11px] text-ink-faint border-b border-line">
              <th className="text-left font-medium py-2">除息日</th>
              <th className="text-right font-medium">每股派息 {p.currency ? `(${p.currency})` : ""}</th>
            </tr>
          </thead>
          <tbody>
            {p.dividends.map((d) => (
              <tr key={d.ex_date} className="border-b border-line/50 hover:bg-panel-2/40">
                <td className="py-1.5 text-ink-dim">{d.ex_date}</td>
                <td className="text-right tnum text-ink">{num(d.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </>
  );
}

function Holders({ p }: { p: CompanyProfile }) {
  const hasOwnership = p.insiders_pct != null || p.institutions_pct != null;
  if (!hasOwnership && !p.top_institutions.length) {
    return <Panel title="股东"><p className="text-sm text-ink-faint py-4">暂无股东 / 持股数据(数据源未提供)。</p></Panel>;
  }
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border border-line bg-panel p-4">
          <div className="text-xs text-ink-faint mb-1">机构持股</div>
          <div className="text-2xl font-semibold tnum text-accent">{pct(p.institutions_pct)}</div>
        </div>
        <div className="rounded-lg border border-line bg-panel p-4">
          <div className="text-xs text-ink-faint mb-1">内部人持股</div>
          <div className="text-2xl font-semibold tnum">{pct(p.insiders_pct)}</div>
        </div>
      </div>

      {p.top_institutions.length > 0 && (
        <Panel title="主要机构股东" hint={`Top ${p.top_institutions.length}`}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] text-ink-faint border-b border-line">
                <th className="text-left font-medium py-2">机构</th>
                <th className="text-right font-medium">占比</th>
                <th className="text-right font-medium">持股数</th>
                <th className="text-right font-medium">市值</th>
                <th className="text-right font-medium">披露日</th>
              </tr>
            </thead>
            <tbody>
              {p.top_institutions.map((h) => (
                <tr key={h.name} className="border-b border-line/50 hover:bg-panel-2/40">
                  <td className="py-1.5 text-ink whitespace-nowrap pr-3">{h.name}</td>
                  <td className="text-right tnum text-ink-dim">{pct(h.pct)}</td>
                  <td className="text-right tnum text-ink-dim">{compact(h.shares)}</td>
                  <td className="text-right tnum text-ink-dim">{compact(h.value)}</td>
                  <td className="text-right tnum text-ink-faint">{h.date_reported ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </>
  );
}

function Profile({ p }: { p: CompanyProfile }) {
  return (
    <>
      <Panel title="公司概况" hint={p.symbol}>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-x-6">
          <Stat label="板块" value={p.sector ?? "—"} />
          <Stat label="行业" value={p.industry ?? "—"} />
          <Stat label="国家 / 地区" value={p.country ?? "—"} />
          <Stat label="员工人数" value={p.employees != null ? compact(p.employees) : "—"} />
          <Stat label="货币" value={p.currency ?? "—"} />
          <Stat label="股息率" value={pct(p.dividend_yield)} />
        </div>
        {p.website && (
          <a href={p.website} target="_blank" rel="noreferrer"
            className="inline-block mt-3 text-sm text-accent hover:underline">{p.website} ↗</a>
        )}
      </Panel>

      {p.summary && (
        <Panel title="业务简介">
          <p className="text-sm text-ink-dim leading-relaxed whitespace-pre-line">{p.summary}</p>
          <p className="text-[11px] text-ink-faint mt-3">资料来源:公开数据源 · 仅供参考</p>
        </Panel>
      )}
    </>
  );
}
