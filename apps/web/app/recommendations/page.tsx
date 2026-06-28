"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import Panel from "@/components/Panel";
import { ScoreMeter, RecBadge, Chip } from "@/components/ui";
import {
  getRecCategories, getRecommendations, generateRecommendations,
  type Recommendation,
} from "@/lib/api";
import { num } from "@/lib/format";

const LABELS: Record<string, string> = {
  growth: "Growth", value: "Value", momentum: "Momentum", dividend: "Dividend",
  ai: "AI / Semis", quality: "Quality", swing: "Swing",
};

function convTone(c: string | null): "up" | "down" | "amber" {
  return c === "high" ? "up" : c === "low" ? "down" : "amber";
}

export default function RecommendationsPage() {
  const [cats, setCats] = useState<string[]>([]);
  const [cat, setCat] = useState<string>("ai");
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback((c: string) => {
    getRecommendations(c).then(setRecs).catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    getRecCategories().then(setCats).catch(() => {});
  }, []);
  useEffect(() => {
    load(cat);
  }, [cat, load]);

  const generate = () => {
    setBusy(true);
    setErr(null);
    generateRecommendations(cat)
      .then((r) => setRecs(r))
      .catch((e) => setErr(String(e)))
      .finally(() => setBusy(false));
  };

  return (
    <div className="space-y-5">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">AI Recommendations</h1>
          <p className="text-sm text-ink-dim">Screened by LU, scored by the AI brain</p>
        </div>
        <button onClick={generate} disabled={busy}
          className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-50">
          {busy ? "Generating… (~30–90s)" : `Generate ${LABELS[cat] ?? cat}`}
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {cats.map((c) => (
          <button key={c} onClick={() => setCat(c)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              c === cat ? "bg-panel-2 text-ink border border-line" : "text-ink-dim hover:text-ink"
            }`}>
            {LABELS[c] ?? c}
          </button>
        ))}
      </div>

      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

      {recs.length === 0 ? (
        <p className="text-sm text-ink-faint">
          No {LABELS[cat] ?? cat} recommendations yet. Click Generate to screen the universe and have the AI score the survivors.
        </p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {recs.map((r) => (
            <Panel key={`${r.category}-${r.symbol}`} title={r.symbol} hint={LABELS[r.category] ?? r.category}>
              <div className="flex items-center justify-between mb-2">
                <Link href={`/research/${encodeURIComponent(r.symbol)}`} className="text-accent text-sm">
                  View research →
                </Link>
                <div className="flex items-center gap-2">
                  {r.conviction && <RecBadge rec={r.conviction} tone={convTone(r.conviction)} />}
                  {r.target_price != null && (
                    <span className="text-xs text-ink-dim tnum">tgt {num(r.target_price)} · {r.time_horizon}</span>
                  )}
                </div>
              </div>
              {r.ai_score != null && <ScoreMeter score={r.ai_score} />}
              <p className="text-sm text-ink-dim leading-relaxed mt-2">{r.thesis}</p>
              {(r.risks.length > 0 || r.catalysts.length > 0) && (
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {r.catalysts.slice(0, 2).map((c, i) => <Chip key={`c${i}`}>+ {c}</Chip>)}
                  {r.risks.slice(0, 2).map((c, i) => <Chip key={`r${i}`}>! {c}</Chip>)}
                </div>
              )}
            </Panel>
          ))}
        </div>
      )}
      <p className="text-[11px] text-ink-faint">AI opinion · not financial advice</p>
    </div>
  );
}
