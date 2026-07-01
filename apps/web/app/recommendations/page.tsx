"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import Panel from "@/components/Panel";
import { ScoreMeter, RecBadge, Chip } from "@/components/ui";
import {
  getRecCategories, getRecommendations, generateRecommendations,
  type Recommendation,
} from "@/lib/api";
import { num, errText } from "@/lib/format";

const LABELS: Record<string, string> = {
  growth: "成长", value: "价值", momentum: "动量", dividend: "红利",
  ai: "AI 半导体", quality: "质量", swing: "波段",
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
    getRecommendations(c).then(setRecs).catch((e) => setErr(errText(e)));
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
      .catch((e) => setErr(errText(e)))
      .finally(() => setBusy(false));
  };

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">AI 推荐</h1>
          <p className="text-sm text-ink-dim">LU 量化筛选 · AI 大脑评分(中文)</p>
        </div>
        <button onClick={generate} disabled={busy}
          className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-50">
          {busy ? "生成中…(约 30–90 秒)" : `生成「${LABELS[cat] ?? cat}」推荐`}
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
          还没有「{LABELS[cat] ?? cat}」类推荐。点上方「生成」按钮,先量化筛选股池,再由 AI 给入选标的评分。
        </p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {recs.map((r) => (
            <Panel key={`${r.category}-${r.symbol}`} title={r.symbol} hint={LABELS[r.category] ?? r.category}>
              <div className="flex items-center justify-between mb-2">
                <Link href={`/research/${encodeURIComponent(r.symbol)}`} className="text-accent text-sm">
                  查看研究 →
                </Link>
                <div className="flex items-center gap-2">
                  {r.conviction && <RecBadge rec={r.conviction} tone={convTone(r.conviction)} />}
                  {r.target_price != null && (
                    <span className="text-xs text-ink-dim tnum">目标 {num(r.target_price)} · {r.time_horizon}</span>
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
      <p className="text-[11px] text-ink-faint">AI 观点 · 非投资建议</p>
    </div>
  );
}
