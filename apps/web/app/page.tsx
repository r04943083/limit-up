"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Panel from "@/components/Panel";
import Heatmap from "@/components/Heatmap";
import {
  getBriefing, generateBriefing, getIndices, getOverview,
  type SavedBriefing, type IndexQuote, type OverviewRow,
} from "@/lib/api";
import { num, signedPct, sinceLabel, dirClass } from "@/lib/format";

const BUCKETS = [
  { label: "≤-7", lo: -Infinity, hi: -7, up: false },
  { label: "-7~-5", lo: -7, hi: -5, up: false },
  { label: "-5~-3", lo: -5, hi: -3, up: false },
  { label: "-3~0", lo: -3, hi: 0, up: false },
  { label: "0~3", lo: 0, hi: 3, up: true },
  { label: "3~5", lo: 3, hi: 5, up: true },
  { label: "5~7", lo: 5, hi: 7, up: true },
  { label: "≥7", lo: 7, hi: Infinity, up: true },
];

export default function DashboardPage() {
  const [b, setB] = useState<SavedBriefing | null>(null);
  const [indices, setIndices] = useState<IndexQuote[]>([]);
  const [overview, setOverview] = useState<OverviewRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getBriefing().then(setB).catch(() => {});
    getIndices().then(setIndices).catch(() => {});
    getOverview().then(setOverview).catch(() => {});
  }, []);

  const generate = () => {
    setBusy(true); setErr(null);
    generateBriefing().then(setB).catch((e) => setErr(String(e))).finally(() => setBusy(false));
  };

  const withPct = useMemo(() => overview.filter((r) => r.change_pct != null), [overview]);
  const dist = useMemo(() =>
    BUCKETS.map((bk) => ({
      ...bk,
      count: withPct.filter((r) => (r.change_pct ?? 0) > bk.lo && (r.change_pct ?? 0) <= bk.hi).length,
    })), [withPct]);
  const maxCount = Math.max(1, ...dist.map((d) => d.count));
  const upCount = withPct.filter((r) => (r.change_pct ?? 0) > 0).length;
  const downCount = withPct.filter((r) => (r.change_pct ?? 0) < 0).length;
  const gainers = useMemo(() => [...withPct].sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0)).slice(0, 8), [withPct]);
  const losers = useMemo(() => [...withPct].sort((a, b) => (a.change_pct ?? 0) - (b.change_pct ?? 0)).slice(0, 8), [withPct]);

  const r = b?.result;

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">机会 · 市场概览</h1>
          <p className="text-sm text-ink-dim">你的 AI 投资台 · US / HK / A-share{b ? ` · 简报生成于 ${sinceLabel(b.created_at)}` : ""}</p>
        </div>
        <button onClick={generate} disabled={busy}
          className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-50">
          {busy ? "生成中… (~60s)" : b ? "重新生成简报" : "生成今日简报"}
        </button>
      </div>

      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

      {/* Index cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {indices.map((q) => (
          <div key={q.symbol} className="rounded-lg border border-line bg-panel p-3">
            <div className="text-xs text-ink-dim">{q.name}</div>
            <div className={`text-lg font-semibold tnum ${dirClass(q.change_pct)}`}>{num(q.price)}</div>
            <div className={`text-xs tnum ${dirClass(q.change_pct)}`}>{signedPct(q.change_pct)}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Briefing */}
        <Panel title="AI 每日简报" hint={b ? b.provider : "claude -p"} className="lg:col-span-2">
          {r ? (
            <div className="space-y-4">
              <p className="text-base text-ink font-medium leading-relaxed">{r.headline}</p>
              <p className="text-sm text-ink-dim leading-relaxed">{r.market_summary}</p>
              {r.opportunities.length > 0 && <Section title="机会 · Opportunities" tone="up" items={r.opportunities} />}
              {r.risks.length > 0 && <Section title="风险 · Risks" tone="down" items={r.risks} />}
              {r.action_items.length > 0 && <Section title="行动 · Action items" tone="accent" items={r.action_items} />}
              <p className="text-[11px] text-ink-faint pt-1">AI 观点 · 非投资建议</p>
            </div>
          ) : (
            <p className="text-sm text-ink-faint">还没有简报。先到自选点「全部更新」拉取数据,再点右上角「生成今日简报」。每天早上 08:30 也会自动生成。</p>
          )}
        </Panel>

        {/* Distribution */}
        <Panel title="涨跌分布" hint={`${withPct.length} 标的`}>
          {withPct.length === 0 ? (
            <p className="text-sm text-ink-faint">先「全部更新」自选数据。</p>
          ) : (
            <>
              <div className="flex items-end gap-1 h-40">
                {dist.map((d) => (
                  <div key={d.label} className="flex-1 flex flex-col items-center justify-end gap-1">
                    <span className="text-[10px] tnum text-ink-dim">{d.count || ""}</span>
                    <div className="w-full rounded-t" style={{ height: `${(d.count / maxCount) * 100}%`, minHeight: d.count ? 2 : 0, background: d.up ? "#F6465D" : "#2EBD85" }} />
                    <span className="text-[9px] text-ink-faint whitespace-nowrap">{d.label}</span>
                  </div>
                ))}
              </div>
              <div className="flex justify-between text-xs mt-2 pt-2 border-t border-line/60">
                <span className="text-down">下跌 {downCount}</span>
                <span className="text-up">上涨 {upCount}</span>
              </div>
            </>
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Hot lists */}
        <Panel title="热度榜">
          <div className="grid grid-cols-2 gap-4">
            <HotList title="今日涨幅" rows={gainers} />
            <HotList title="今日跌幅" rows={losers} />
          </div>
        </Panel>

        {/* Heatmap */}
        <Panel title="行业热力图" hint="按行业 · 色深=涨跌幅" className="lg:col-span-2">
          <Heatmap rows={overview} />
        </Panel>
      </div>
    </div>
  );
}

function HotList({ title, rows }: { title: string; rows: OverviewRow[] }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">{title}</div>
      <div className="space-y-0.5">
        {rows.map((r) => (
          <Link key={r.symbol} href={`/research/${encodeURIComponent(r.symbol)}`}
            className="flex items-center justify-between py-1 border-b border-line/40 last:border-0 hover:bg-panel-2/40 px-1 -mx-1 rounded">
            <span className="text-xs text-ink truncate">{r.symbol}</span>
            <span className={`text-xs tnum ${dirClass(r.change_pct)}`}>{signedPct(r.change_pct)}</span>
          </Link>
        ))}
        {rows.length === 0 && <span className="text-xs text-ink-faint">暂无数据</span>}
      </div>
    </div>
  );
}

function Section({ title, tone, items }: { title: string; tone: "up" | "down" | "accent"; items: string[] }) {
  const color = tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-accent";
  return (
    <div>
      <div className={`text-[11px] uppercase tracking-wide mb-1.5 ${color}`}>{title}</div>
      <ul className="space-y-1">
        {items.map((it, i) => (
          <li key={i} className="text-sm text-ink-dim flex gap-2"><span className={color}>·</span>{it}</li>
        ))}
      </ul>
    </div>
  );
}
