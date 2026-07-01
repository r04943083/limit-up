"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Panel from "@/components/Panel";
import {
  getScreenerMeta, runScreen, seedUniverse, getSeedProgress, fillFinancials,
  type ScreenerField, type IndexInfo, type ScreenFilter, type ScreenHit,
  type ScreenResult, type SeedProgress,
} from "@/lib/api";
import { compact, dirClass } from "@/lib/format";

const MARKETS = [
  { key: "US", label: "美股" },
  { key: "HK", label: "港股" },
  { key: "CN", label: "A股" },
];

// Columns always shown in the results table (besides 名称/代码), in order.
const DEFAULT_COLS = ["market_cap", "pe_ttm", "pb", "roe", "revenue_growth", "change_pct"];

function fmtMetric(field: ScreenerField | undefined, v: number | null | undefined): string {
  if (v == null || !field) return "—";
  if (field.key === "market_cap") return compact(v * 1e8); // 亿 → raw for compact()
  if (field.unit === "%") return `${v.toFixed(1)}%`;
  if (field.unit === "x") return `${v.toFixed(1)}x`;
  if (field.unit === "板") return String(Math.round(v));
  return v.toFixed(2);
}

// One-click preset strategies — each sets the filter ranges + sort. Values are in the
// units the screener returns (x 倍 · % 百分比 · 亿).
type Preset = {
  key: string; label: string; hint: string;
  ranges: Record<string, { min?: string; max?: string }>;
  sort: string; desc: boolean; sectors?: string[];
};
const PRESETS: Preset[] = [
  {
    key: "value", label: "低估值", hint: "PE≤20 · PB≤3 · 有盈利",
    ranges: { pe_ttm: { min: "0", max: "20" }, pb: { max: "3" } },
    sort: "pe_ttm", desc: false,
  },
  {
    key: "growth", label: "高成长", hint: "营收增速≥20% · 盈利增速≥15%",
    ranges: { revenue_growth: { min: "20" }, earnings_growth: { min: "15" } },
    sort: "revenue_growth", desc: true,
  },
  {
    key: "dividend", label: "高股息", hint: "股息率≥3% · PE≤25",
    ranges: { dividend_yield: { min: "3" }, pe_ttm: { min: "0", max: "25" } },
    sort: "dividend_yield", desc: true,
  },
  {
    key: "quality", label: "优质白马", hint: "ROE≥15% · 净利率≥12%",
    ranges: { roe: { min: "15" }, net_margin: { min: "12" } },
    sort: "roe", desc: true,
  },
  {
    key: "ai", label: "AI / 科技成长", hint: "科技板块 · 营收增速≥15%",
    ranges: { revenue_growth: { min: "15" } },
    sort: "market_cap", desc: true, sectors: ["Technology"],
  },
];

export default function ScreenerPage() {
  const router = useRouter();
  const [fields, setFields] = useState<ScreenerField[]>([]);
  const [indices, setIndices] = useState<IndexInfo[]>([]);
  const [ranges, setRanges] = useState<Record<string, { min?: string; max?: string }>>({});
  const [markets, setMarkets] = useState<string[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [sort, setSort] = useState("market_cap");
  const [desc, setDesc] = useState(true);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [res, setRes] = useState<ScreenResult | null>(null);
  const [busy, setBusy] = useState(false);

  // Seeding
  const [seedKeys, setSeedKeys] = useState<string[]>([]);
  const [progress, setProgress] = useState<SeedProgress | null>(null);
  const [seedMsg, setSeedMsg] = useState<string | null>(null);
  const [finProgress, setFinProgress] = useState<SeedProgress | null>(null);

  useEffect(() => {
    getScreenerMeta().then((m) => { setFields(m.fields); setIndices(m.indices); }).catch(() => {});
    getSeedProgress("snapshot").then(setProgress).catch(() => {});
    getSeedProgress("financials").then(setFinProgress).catch(() => {});
  }, []);

  const fieldByKey = useMemo(() => Object.fromEntries(fields.map((f) => [f.key, f])), [fields]);
  const groups = useMemo(() => {
    const g: Record<string, ScreenerField[]> = {};
    for (const f of fields) (g[f.group] ??= []).push(f);
    return g;
  }, [fields]);

  const runWith = useCallback((
    rs: Record<string, { min?: string; max?: string }>,
    mk: string[], sec: string[], sf: string, sd: boolean,
  ) => {
    setBusy(true);
    const filters: ScreenFilter[] = [];
    for (const [field, r] of Object.entries(rs)) {
      const min = r.min !== undefined && r.min !== "" ? Number(r.min) : null;
      const max = r.max !== undefined && r.max !== "" ? Number(r.max) : null;
      if (min != null || max != null) filters.push({ field, min, max });
    }
    runScreen({ filters, markets: mk, sectors: sec, sort_field: sf, sort_desc: sd, limit: 100 })
      .then(setRes).catch(() => setRes(null)).finally(() => setBusy(false));
  }, []);

  const run = useCallback(() => runWith(ranges, markets, sectors, sort, desc),
    [runWith, ranges, markets, sectors, sort, desc]);

  const applyPreset = (p: Preset) => {
    setRanges(p.ranges);
    setSectors(p.sectors ?? []);
    setSort(p.sort);
    setDesc(p.desc);
    setActivePreset(p.key);
    runWith(p.ranges, markets, p.sectors ?? [], p.sort, p.desc);
  };

  // Poll seed progress while a fill is running.
  useEffect(() => {
    if (!progress?.running) return;
    const t = setInterval(() => getSeedProgress("snapshot").then(setProgress).catch(() => {}), 2500);
    return () => clearInterval(t);
  }, [progress?.running]);

  useEffect(() => {
    if (!finProgress?.running) return;
    const t = setInterval(() => getSeedProgress("financials").then(setFinProgress).catch(() => {}), 3000);
    return () => clearInterval(t);
  }, [finProgress?.running]);

  const doFillFinancials = () => fillFinancials().then(setFinProgress).catch(() => {});

  const doSeed = () => {
    if (seedKeys.length === 0) return;
    setSeedMsg("正在拉取成分股清单…");
    seedUniverse(seedKeys, true).then((r) => {
      setSeedMsg(`已加入 ${r.seed.added} 只新标的(池子共 ${r.seed.universe_size} 只)· 正在后台拉取快照,完成后即可筛选`);
      setProgress(r.progress);
    }).catch((e) => setSeedMsg(String(e).replace(/^Error:\s*/, "")));
  };

  const cols = useMemo(() => {
    const set = new Set<string>(DEFAULT_COLS);
    set.add(sort);
    Object.entries(ranges).forEach(([k, r]) => { if (r.min || r.max) set.add(k); });
    return [...set];
  }, [sort, ranges]);

  const toggle = (arr: string[], set: (v: string[]) => void, k: string) =>
    set(arr.includes(k) ? arr.filter((x) => x !== k) : [...arr, k]);

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">条件选股</h1>
        <p className="text-sm text-ink-dim">在已下载的大指数成分股里,按估值 / 行情 / 基本面 / 涨停题材多条件筛选 · 全部为确定性计算</p>
      </div>

      {/* Seed universe */}
      <Panel title="股票池 · 灌入指数成分股" hint="首次较慢(后台拉取),之后缓存命中很快">
        <div className="flex flex-wrap gap-1.5">
          {indices.map((i) => (
            <button key={i.key} onClick={() => toggle(seedKeys, setSeedKeys, i.key)}
              className={`px-2.5 py-1 rounded-lg text-xs border transition-colors ${
                seedKeys.includes(i.key) ? "border-accent text-accent bg-accent/10" : "border-line text-ink-dim hover:text-ink"
              }`}>
              {i.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 mt-3">
          <button onClick={doSeed} disabled={seedKeys.length === 0 || progress?.running}
            className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-1.5 hover:bg-accent/25 disabled:opacity-40">
            {progress?.running ? "后台拉取中…" : "灌入成分股"}
          </button>
          {progress?.running && (
            <span className="text-xs text-ink-dim tnum">
              快照 {progress.done}/{progress.total}{progress.failed ? ` · 失败 ${progress.failed}` : ""}
            </span>
          )}
          {seedMsg && !progress?.running && <span className="text-xs text-ink-faint">{seedMsg}</span>}
        </div>
        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-line">
          <button onClick={doFillFinancials} disabled={finProgress?.running}
            className="rounded-lg border border-line text-ink-dim text-sm px-4 py-1.5 hover:text-ink disabled:opacity-40">
            {finProgress?.running ? "补全财报中…" : "补全财报三表"}
          </button>
          {finProgress?.running ? (
            <span className="text-xs text-ink-dim tnum">
              财报 {finProgress.done}/{finProgress.total}{finProgress.failed ? ` · 失败 ${finProgress.failed}` : ""}
            </span>
          ) : (
            <span className="text-[11px] text-ink-faint">让估值带 / 历史分位全池可用(较慢,后台拉取,可关页)</span>
          )}
        </div>
      </Panel>

      {/* Preset strategies */}
      <Panel title="预设策略" hint="一键套用常见选股思路 · 套用后可再微调条件">
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button key={p.key} onClick={() => applyPreset(p)} title={p.hint}
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                activePreset === p.key ? "border-accent text-accent bg-accent/10" : "border-line text-ink-dim hover:text-ink"
              }`}>
              {p.label}
              <span className="block text-[10px] text-ink-faint leading-tight">{p.hint}</span>
            </button>
          ))}
        </div>
      </Panel>

      {/* Filters */}
      <Panel title="筛选条件" hint="留空表示不限;数值单位见标签(x 倍 · % 百分比 · 亿)">
        <div className="flex flex-wrap items-center gap-1.5 mb-3">
          <span className="text-xs text-ink-faint mr-1">市场</span>
          {MARKETS.map((m) => (
            <button key={m.key} onClick={() => toggle(markets, setMarkets, m.key)}
              className={`px-2.5 py-1 rounded-lg text-xs border transition-colors ${
                markets.includes(m.key) ? "border-accent text-accent bg-accent/10" : "border-line text-ink-dim hover:text-ink"
              }`}>
              {m.label}
            </button>
          ))}
          <span className="text-xs text-ink-faint">{markets.length === 0 ? "(全部)" : ""}</span>
          {/* Presets (e.g. AI / 科技成长) set a sector filter that otherwise has no on-screen
              control — surface it as a removable chip so results aren't silently constrained. */}
          {sectors.length > 0 && (
            <>
              <span className="text-xs text-ink-faint ml-2 mr-0.5">行业</span>
              {sectors.map((sec) => (
                <button key={sec} onClick={() => { setActivePreset(null); setSectors((xs) => xs.filter((x) => x !== sec)); }}
                  title="点击移除该行业限制"
                  className="px-2.5 py-1 rounded-lg text-xs border border-accent text-accent bg-accent/10 hover:bg-accent/20">
                  {sec} ✕
                </button>
              ))}
            </>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-6 gap-y-1">
          {Object.entries(groups).map(([group, fs]) => (
            <div key={group} className="py-1">
              <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">{group}</div>
              <div className="space-y-1">
                {fs.map((f) => (
                  <div key={f.key} className="flex items-center gap-2 text-sm">
                    <span className="w-28 shrink-0 text-ink-dim truncate">{f.label}<span className="text-ink-faint text-[11px]"> {f.unit}</span></span>
                    <input inputMode="decimal" placeholder="≥ 最小"
                      value={ranges[f.key]?.min ?? ""}
                      onChange={(e) => { setActivePreset(null); setRanges((p) => ({ ...p, [f.key]: { ...p[f.key], min: e.target.value } })); }}
                      className="w-24 rounded-md bg-panel-2 border border-line px-2 py-1 text-xs outline-none focus:border-accent" />
                    <input inputMode="decimal" placeholder="≤ 最大"
                      value={ranges[f.key]?.max ?? ""}
                      onChange={(e) => { setActivePreset(null); setRanges((p) => ({ ...p, [f.key]: { ...p[f.key], max: e.target.value } })); }}
                      className="w-24 rounded-md bg-panel-2 border border-line px-2 py-1 text-xs outline-none focus:border-accent" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-4 pt-3 border-t border-line">
          <span className="text-xs text-ink-faint">排序</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)}
            className="rounded-lg bg-panel-2 border border-line px-2 py-1 text-xs outline-none focus:border-accent">
            {fields.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
          </select>
          <button onClick={() => setDesc((d) => !d)}
            className="rounded-lg border border-line text-ink-dim text-xs px-2 py-1 hover:text-ink">
            {desc ? "从高到低 ↓" : "从低到高 ↑"}
          </button>
          <button onClick={() => { setRanges({}); setMarkets([]); setSectors([]); setActivePreset(null); }}
            className="rounded-lg border border-line text-ink-dim text-xs px-3 py-1 hover:text-ink ml-auto">重置</button>
          <button onClick={run} disabled={busy}
            className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-5 py-1.5 hover:bg-accent/25 disabled:opacity-40">
            {busy ? "筛选中…" : "运行筛选"}
          </button>
        </div>
      </Panel>

      {/* Results */}
      {res && (
        <Panel title="筛选结果" hint={`命中 ${res.matched} / 池 ${res.universe} 只${res.matched > res.results.length ? ` · 显示前 ${res.results.length}` : ""}`}>
          {res.results.length === 0 ? (
            <p className="text-sm text-ink-faint">没有符合条件的标的。放宽条件,或先到上方「灌入成分股」扩大股票池。</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wide text-ink-faint border-b border-line">
                    <th className="text-left font-medium py-2 px-2">名称 / 代码</th>
                    <th className="text-left font-medium px-2">市场</th>
                    {cols.map((c) => (
                      <th key={c} className="text-right font-medium px-3 whitespace-nowrap">{fieldByKey[c]?.label ?? c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {res.results.map((h: ScreenHit) => (
                    <tr key={h.symbol} onClick={() => router.push(`/research/${encodeURIComponent(h.symbol)}`)}
                      className="border-b border-line/40 hover:bg-panel-2/50 cursor-pointer">
                      <td className="py-1.5 px-2">
                        <div className="text-ink truncate max-w-[14rem]">{h.name ?? h.symbol}</div>
                        <div className="text-[11px] text-ink-faint tnum">{h.symbol}{h.sector ? ` · ${h.sector}` : ""}</div>
                      </td>
                      <td className="px-2 text-ink-dim text-xs">{MARKETS.find((m) => m.key === h.market)?.label ?? h.market ?? "—"}</td>
                      {cols.map((c) => {
                        const v = h.metrics[c];
                        const cls = c === "change_pct" ? dirClass(v) : "text-ink-dim";
                        return <td key={c} className={`px-3 text-right tnum whitespace-nowrap ${cls}`}>{fmtMetric(fieldByKey[c], v)}</td>;
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}

      <p className="text-[11px] text-ink-faint">
        数据来自已下载快照(估值/行情/基本面取自 yfinance 概况)· 行业平均与 N 年估值分位见个股「分析」页 · 连板数取自当日 A 股涨停池
      </p>
    </div>
  );
}
