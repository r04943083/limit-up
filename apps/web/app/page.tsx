"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Panel from "@/components/Panel";
import {
  getBriefing, generateBriefing, getWatchlistHealth,
  type SavedBriefing, type HealthOut,
} from "@/lib/api";
import { signedPct, sinceLabel } from "@/lib/format";

function healthTone(label: string): string {
  if (label === "strong" || label === "healthy") return "text-up";
  if (label === "weak" || label === "poor") return "text-down";
  return "text-[#E0A33E]";
}

export default function DashboardPage() {
  const [b, setB] = useState<SavedBriefing | null>(null);
  const [health, setHealthState] = useState<HealthOut[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getBriefing().then(setB).catch(() => {});
    getWatchlistHealth().then(setHealthState).catch(() => {});
  }, []);

  const generate = () => {
    setBusy(true);
    setErr(null);
    generateBriefing()
      .then((res) => {
        setB(res);
        return getWatchlistHealth().then(setHealthState);
      })
      .catch((e) => setErr(String(e)))
      .finally(() => setBusy(false));
  };

  const r = b?.result;
  const gainers = b?.facts.top_gainers ?? [];
  const losers = b?.facts.top_losers ?? [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">每日简报 · Daily Briefing</h1>
          <p className="text-sm text-ink-dim">
            你的 AI 投资台 · US / HK / A-share
            {b ? ` · 生成于 ${sinceLabel(b.created_at)}` : ""}
          </p>
        </div>
        <button
          onClick={generate}
          disabled={busy}
          className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-50 transition-colors"
        >
          {busy ? "生成中… (~60s)" : b ? "重新生成" : "生成今日简报"}
        </button>
      </div>

      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Briefing narrative */}
        <Panel title="AI 简报" hint={b ? b.provider : "claude -p"} className="lg:col-span-2">
          {r ? (
            <div className="space-y-4">
              <p className="text-base text-ink font-medium leading-relaxed">{r.headline}</p>
              <p className="text-sm text-ink-dim leading-relaxed">{r.market_summary}</p>

              {r.opportunities.length > 0 && (
                <Section title="机会 · Opportunities" tone="up" items={r.opportunities} />
              )}
              {r.risks.length > 0 && <Section title="风险 · Risks" tone="down" items={r.risks} />}
              {r.action_items.length > 0 && (
                <Section title="行动 · Action items" tone="accent" items={r.action_items} />
              )}
              <p className="text-[11px] text-ink-faint pt-1">AI 观点 · 非投资建议</p>
            </div>
          ) : (
            <p className="text-sm text-ink-faint">
              还没有简报。先到 Watchlist 点击「全部更新」拉取数据,然后点右上角「生成今日简报」,
              AI 会基于自选股的行情、健康分、推荐与新闻写出当天要点。每天早上也会自动生成。
            </p>
          )}
        </Panel>

        {/* Movers */}
        <Panel title="今日异动" hint={b ? `${b.facts.tracked_count ?? 0} 标的` : ""}>
          {gainers.length === 0 && losers.length === 0 ? (
            <p className="text-sm text-ink-faint">暂无数据。</p>
          ) : (
            <div className="space-y-1">
              {[...gainers, ...losers].map((m) => (
                <Link
                  key={m.symbol}
                  href={`/research/${encodeURIComponent(m.symbol)}`}
                  className="flex items-center justify-between py-1.5 border-b border-line/60 last:border-0 hover:bg-panel-2/40 -mx-1 px-1 rounded"
                >
                  <span className="text-sm text-accent">{m.symbol}</span>
                  <span className={`text-sm tnum ${(m.change_pct ?? 0) >= 0 ? "text-up" : "text-down"}`}>
                    {signedPct(m.change_pct)}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </Panel>
      </div>

      {/* Watchlist health + highlights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Panel title="自选健康分 · Health" hint="#D3" className="lg:col-span-2">
          {health.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
              {health.map((h) => (
                <div key={h.symbol} className="flex items-center justify-between py-1.5 border-b border-line/60">
                  <Link href={`/research/${encodeURIComponent(h.symbol)}`} className="text-sm text-accent w-20">
                    {h.symbol}
                  </Link>
                  <div className="flex-1 h-1.5 rounded-full bg-panel-2 overflow-hidden mx-3">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${h.score}%`,
                        background: h.score >= 60 ? "#22C55E" : h.score >= 45 ? "#E0A33E" : "#EF4444",
                      }}
                    />
                  </div>
                  <span className={`text-xs tnum w-24 text-right ${healthTone(h.label)}`}>
                    {h.score.toFixed(0)} · {h.label}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-faint">先「全部更新」数据后即可计算健康分。</p>
          )}
        </Panel>

        <Panel title="关注要点 · Highlights">
          {r && r.watchlist_highlights.length > 0 ? (
            <ul className="space-y-2">
              {r.watchlist_highlights.map((h, i) => (
                <li key={i} className="text-xs text-ink-dim flex gap-2">
                  <span className="text-accent">·</span>
                  {h}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-faint">生成简报后这里显示关注要点。</p>
          )}
        </Panel>
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
          <li key={i} className="text-sm text-ink-dim flex gap-2">
            <span className={color}>·</span>
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}
