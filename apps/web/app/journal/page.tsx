"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Panel from "@/components/Panel";
import SymbolInput from "@/components/SymbolInput";
import { Chip, ScoreMeter } from "@/components/ui";
import {
  addJournal, deleteJournal, getJournal, reviewJournal, type JournalEntry,
} from "@/lib/api";
import { sinceLabel } from "@/lib/format";

const ACTIONS: Record<string, string> = {
  buy: "买入", sell: "卖出", add: "加仓", trim: "减仓", watch: "观察", note: "笔记",
};
const ACTION_KEYS = Object.keys(ACTIONS);

export default function JournalPage() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ title: "", body: "", symbol: "", action: "note", conviction: "medium" });

  const load = useCallback(() => {
    getJournal().then(setEntries).catch((e) => setErr(String(e)));
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = () => {
    if (!form.title.trim() || saving) return;  // in-flight guard: a double-click must not create two entries
    setErr(null);
    setSaving(true);
    addJournal({
      title: form.title, body: form.body || undefined,
      symbol: form.symbol.trim().toUpperCase() || undefined,
      action: form.action, conviction: form.conviction,
    })
      .then(() => { setForm({ title: "", body: "", symbol: "", action: "note", conviction: "medium" }); load(); })
      .catch((e) => setErr(String(e)))
      .finally(() => setSaving(false));
  };

  const review = (id: number) => {
    setBusy(id);
    reviewJournal(id)
      .then((u) => setEntries((prev) => prev.map((e) => (e.id === id ? u : e))))
      .catch((e) => setErr(String(e)))
      .finally(() => setBusy(null));
  };

  const remove = (id: number) => {
    if (!confirm("删除这条日志?此操作不可撤销。")) return;
    deleteJournal(id).then(() => setEntries((prev) => prev.filter((e) => e.id !== id))).catch((e) => setErr(String(e)));
  };

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">投资日志</h1>
        <p className="text-sm text-ink-dim">记录每一次决策的理由 · AI 复盘你的「决策质量」(非结果)</p>
      </div>

      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

      <Panel title="新增记录" hint="记录决策与理由">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
          <SymbolInput value={form.symbol} onChange={(s) => setForm({ ...form, symbol: s })}
            placeholder="代码(选填)如 NVDA" />
          <select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}
            className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent">
            {ACTION_KEYS.map((a) => <option key={a} value={a}>{ACTIONS[a]}</option>)}
          </select>
          <select value={form.conviction} onChange={(e) => setForm({ ...form, conviction: e.target.value })}
            className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent">
            <option value="low">信念 低</option>
            <option value="medium">信念 中</option>
            <option value="high">信念 高</option>
          </select>
          <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="标题:这次决策是什么"
            className="rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent" />
        </div>
        <textarea value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })}
          placeholder="理由 / 逻辑 / 风险:为什么这么做?预期与退出条件是什么?"
          rows={3}
          className="mt-3 w-full rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent" />
        <div className="mt-3 flex justify-end">
          <button onClick={submit} disabled={!form.title.trim() || saving}
            className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-40">
            {saving ? "添加中…" : "添加记录"}
          </button>
        </div>
      </Panel>

      {entries.length === 0 ? (
        <p className="text-sm text-ink-faint">还没有日志。在上方记录你的第一笔决策与理由。</p>
      ) : (
        <div className="space-y-3">
          {entries.map((e) => (
            <Panel key={e.id} title={e.title}
              hint={`${ACTIONS[e.action] ?? e.action}${e.symbol ? " · " + e.symbol : ""} · ${sinceLabel(e.created_at)}`}>
              {e.body && <p className="text-sm text-ink-dim leading-relaxed whitespace-pre-wrap">{e.body}</p>}
              <div className="flex flex-wrap items-center gap-2 mt-2">
                {e.symbol && <Link href={`/research/${e.symbol}`} className="text-accent text-xs">查看研究 →</Link>}
                {e.conviction && <Chip>信念 {e.conviction}</Chip>}
              </div>
              {e.ai_review ? (
                <div className="mt-3 rounded-lg border border-line bg-panel-2/50 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-ink-faint uppercase tracking-wide">AI 决策质量评分</span>
                    <div className="w-40"><ScoreMeter score={e.ai_review.score} /></div>
                  </div>
                  <p className="text-sm text-ink">{e.ai_review.verdict}</p>
                  {e.ai_review.strengths.length > 0 && (
                    <p className="text-xs text-ink-dim">优点:{e.ai_review.strengths.join("、")}</p>
                  )}
                  {e.ai_review.blind_spots.length > 0 && (
                    <p className="text-xs text-ink-dim">盲点:{e.ai_review.blind_spots.join("、")}</p>
                  )}
                  {e.ai_review.biases.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">{e.ai_review.biases.map((b, i) => <Chip key={i}>偏差 · {b}</Chip>)}</div>
                  )}
                </div>
              ) : (
                <div className="mt-3 flex gap-2">
                  <button onClick={() => review(e.id)} disabled={busy === e.id}
                    className="rounded-lg bg-accent/15 text-accent text-xs font-medium px-3 py-1.5 hover:bg-accent/25 disabled:opacity-40">
                    {busy === e.id ? "AI 复盘中…" : "AI 复盘决策质量"}
                  </button>
                  <button onClick={() => remove(e.id)}
                    className="rounded-lg border border-line text-ink-dim text-xs px-3 py-1.5 hover:text-ink">删除</button>
                </div>
              )}
              {e.ai_review && (
                <button onClick={() => remove(e.id)}
                  className="mt-2 text-xs text-ink-faint hover:text-down">删除</button>
              )}
            </Panel>
          ))}
        </div>
      )}
      <p className="text-[11px] text-ink-faint">AI 观点 · 非投资建议</p>
    </div>
  );
}
