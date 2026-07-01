"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Panel from "@/components/Panel";
import SymbolInput from "@/components/SymbolInput";
import { Chip, RecBadge, ScoreMeter, Stat } from "@/components/ui";
import {
  analyzeAsPersona, getCoach, getCouncil, getDebate, getDna, getPanel, getPersonas, getReflections,
  runCoach, runCouncil, runDebate, runDna, runPanel,
  type CoachResult, type CouncilResult, type DebateResult, type DnaResult, type MultiAgentResult,
  type Persona, type PositionSuggestion, type ReflectionSummary, type SavedAnalysis,
} from "@/lib/api";
import { errText, recTone } from "@/lib/format";

// Stance → app palette (红=看多/up · 绿=看空/down · amber=中性), Futu convention.
const STANCE: Record<string, { label: string; tone: "up" | "down" | "amber" }> = {
  bullish: { label: "看多", tone: "up" },
  bearish: { label: "看空", tone: "down" },
  neutral: { label: "中性", tone: "amber" },
};
const stanceOf = (s: string) => STANCE[s] ?? STANCE.neutral;

type Tab = "debate" | "panel" | "persona" | "coach" | "dna";
const TABS: { key: Tab; label: string }[] = [
  { key: "debate", label: "多空辩论" },
  { key: "panel", label: "多智能体" },
  { key: "persona", label: "投资人格" },
  { key: "coach", label: "AI 教练" },
  { key: "dna", label: "投资 DNA" },
];

export default function StudioPage() {
  const [tab, setTab] = useState<Tab>("debate");
  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">AI 工作室</h1>
        <p className="text-sm text-ink-dim">多空辩论 · 多智能体投研 · 投资人格 · AI 教练 · 投资 DNA</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              t.key === tab ? "bg-panel-2 text-ink border border-line" : "text-ink-dim hover:text-ink"
            }`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "debate" && <DebateTab />}
      {tab === "panel" && <PanelTab />}
      {tab === "persona" && <PersonaTab />}
      {tab === "coach" && <CoachTab />}
      {tab === "dna" && <DnaTab />}
      <p className="text-[11px] text-ink-faint">AI 观点 · 非投资建议</p>
    </div>
  );
}

function SymbolBar({ symbol, setSymbol, onRun, busy, label }: {
  symbol: string; setSymbol: (s: string) => void; onRun: () => void; busy: boolean; label: string;
}) {
  return (
    <div className="flex gap-2">
      <SymbolInput value={symbol} onChange={setSymbol} onEnter={onRun} className="flex-1" />
      <button onClick={onRun} disabled={busy || !symbol.trim()}
        className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-40">
        {busy ? "生成中…(约 30–90 秒)" : label}
      </button>
    </div>
  );
}

function DebateTab() {
  const [symbol, setSymbol] = useState("NVDA");
  const [data, setData] = useState<DebateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [bull, setBull] = useState("");  // persona key seated on the bull side ("" = generic)
  const [bear, setBear] = useState("");

  const load = useCallback((s: string) => {
    getDebate(s.trim().toUpperCase()).then((d) => setData(d?.result ?? null)).catch(() => setData(null));
  }, []);
  useEffect(() => { load("NVDA"); }, [load]);
  useEffect(() => { getPersonas().then(setPersonas).catch(() => {}); }, []);

  const run = () => {
    setBusy(true); setErr(null);
    runDebate(symbol.trim().toUpperCase(), bull, bear).then((d) => setData(d.result))
      .catch((e) => setErr(errText(e))).finally(() => setBusy(false));
  };

  const winTone = data?.winner === "bull" ? "up" : data?.winner === "bear" ? "down" : "amber";
  const seat = (v: string, set: (s: string) => void, side: "多头" | "空头") => (
    <select value={v} onChange={(e) => set(e.target.value)}
      className="rounded-lg bg-panel-2 border border-line px-2 py-2 text-sm outline-none focus:border-accent">
      <option value="">{side}席位:通用</option>
      {personas.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
    </select>
  );
  return (
    <div className="space-y-4">
      <Panel title="多空辩论" hint="同一组事实 · 多空对辩 · 法官裁决">
        <div className="flex flex-wrap gap-2">
          {seat(bull, setBull, "多头")}
          {seat(bear, setBear, "空头")}
          <SymbolBar symbol={symbol} setSymbol={setSymbol} onRun={run} busy={busy} label="开始辩论" />
        </div>
        <p className="text-[11px] text-ink-faint mt-2">可给多空席位各选一位投资大师(如 巴菲特 🐂 vs 木头姐 🐻),或留「通用」由 AI 自由对辩。</p>
      </Panel>
      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}
      {data ? (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Panel title="多头 🐂" hint={data.bull_persona_name || "Bull"}>
              <p className="text-sm text-ink leading-relaxed">{data.bull_case}</p>
              {data.bull_rebuttal && <p className="text-xs text-ink-dim mt-2 leading-relaxed">反驳:{data.bull_rebuttal}</p>}
            </Panel>
            <Panel title="空头 🐻" hint={data.bear_persona_name || "Bear"}>
              <p className="text-sm text-ink leading-relaxed">{data.bear_case}</p>
              {data.bear_rebuttal && <p className="text-xs text-ink-dim mt-2 leading-relaxed">反驳:{data.bear_rebuttal}</p>}
            </Panel>
          </div>
          <Panel title="法官裁决" hint={`胜方置信度 ${data.confidence?.toFixed(1)}/10`}>
            <div className="flex items-center gap-2 mb-2">
              <RecBadge rec={data.winner === "bull" ? "多头胜" : data.winner === "bear" ? "空头胜" : "平局"} tone={winTone} />
            </div>
            <p className="text-sm text-ink leading-relaxed">{data.verdict}</p>
            {data.key_question && <p className="text-xs text-ink-dim mt-2">关键问题:{data.key_question}</p>}
          </Panel>
        </>
      ) : !busy && <p className="text-sm text-ink-faint">还没有该标的的辩论。点「开始辩论」生成。</p>}
    </div>
  );
}

function PanelTab() {
  const [symbol, setSymbol] = useState("NVDA");
  const [data, setData] = useState<MultiAgentResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const LABELS: Record<string, string> = { fundamental: "基本面", technical: "技术面", sentiment: "情绪/新闻", risk: "风险", macro: "宏观" };

  const load = useCallback((s: string) => {
    getPanel(s.trim().toUpperCase()).then((d) => setData(d?.result ?? null)).catch(() => setData(null));
  }, []);
  useEffect(() => { load("NVDA"); }, [load]);
  const run = () => {
    setBusy(true); setErr(null);
    runPanel(symbol.trim().toUpperCase()).then((d) => setData(d.result))
      .catch((e) => setErr(String(e).replace(/^Error:\s*/, ""))).finally(() => setBusy(false));
  };
  const tone = (st: string) => (st === "bullish" ? "up" : st === "bearish" ? "down" : "amber");

  return (
    <div className="space-y-4">
      <Panel title="多智能体投研" hint="基本面/技术/情绪/风险/宏观 + 首席综合"><SymbolBar symbol={symbol} setSymbol={setSymbol} onRun={run} busy={busy} label="召集专家组" /></Panel>
      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}
      {data ? (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {data.agents.map((a) => (
              <Panel key={a.agent} title={LABELS[a.agent] ?? a.agent} hint={`${a.stance} · ${a.score.toFixed(1)}/10`}>
                <div className="mb-2"><ScoreMeter score={a.score} /></div>
                <RecBadge rec={a.stance} tone={tone(a.stance)} />
                <p className="text-sm text-ink-dim leading-relaxed mt-2">{a.rationale}</p>
              </Panel>
            ))}
          </div>
          <Panel title="首席综合" hint={`${data.recommendation} · 共识 ${data.consensus_score.toFixed(1)}/10`}>
            <div className="mb-2"><ScoreMeter score={data.consensus_score} /></div>
            <p className="text-sm text-ink leading-relaxed">{data.synthesis}</p>
            {data.disagreement && <p className="text-xs text-warn mt-2">分歧:{data.disagreement}</p>}
          </Panel>
        </>
      ) : !busy && <p className="text-sm text-ink-faint">还没有该标的的专家组结论。点「召集专家组」生成。</p>}
    </div>
  );
}

// Deterministic sized recommendation (portfolio-manager step). buy/add → red/up,
// sell/trim → green/down, hold → amber.
function RecoBanner({ rec }: { rec: PositionSuggestion | undefined }) {
  if (!rec) return null;
  const tone = ["buy", "add"].includes(rec.action) ? "up"
    : ["sell", "trim"].includes(rec.action) ? "down" : "warn";
  const cls = tone === "up" ? "text-up bg-up/10 border-up/30"
    : tone === "down" ? "text-down bg-down/10 border-down/30"
    : "text-warn bg-warn/10 border-warn/30";
  return (
    <div className={`mb-3 rounded-lg border px-3 py-2 flex flex-wrap items-center gap-x-3 gap-y-1 ${cls}`}>
      <span className="font-medium">建议仓位:{rec.label}</span>
      {rec.target_weight_pct > 0 && <span className="text-sm">目标 {rec.target_weight_pct}%</span>}
      <span className="ml-auto text-[11px] text-ink-faint">{rec.note}</span>
    </div>
  );
}

function CouncilBoard({ result }: { result: CouncilResult }) {
  const total = result.verdicts.length || 1;
  return (
    <Panel title="大师会诊" hint={`${stanceOf(result.consensus).label} · 均分 ${result.avg_score.toFixed(1)}/10`}>
      {/* Vote tally bar: red=看多 / amber=中性 / green=看空 */}
      <div className="flex items-center gap-3 mb-3 text-xs">
        <span className="text-up">看多 {result.bullish}</span>
        <span className="text-warn">中性 {result.neutral}</span>
        <span className="text-down">看空 {result.bearish}</span>
        <div className="flex-1 h-1.5 rounded-full overflow-hidden flex bg-panel-2">
          <div className="h-full bg-up" style={{ width: `${(result.bullish / total) * 100}%` }} />
          <div className="h-full bg-warn" style={{ width: `${(result.neutral / total) * 100}%` }} />
          <div className="h-full bg-down" style={{ width: `${(result.bearish / total) * 100}%` }} />
        </div>
      </div>
      <RecoBanner rec={result.recommendation} />
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-ink-faint border-b border-line">
            <th className="text-left font-medium py-2">大师</th>
            <th className="text-left font-medium">立场</th>
            <th className="text-right font-medium">评分</th>
            <th className="text-left font-medium pl-3">理由</th>
          </tr>
        </thead>
        <tbody>
          {result.verdicts.map((v) => {
            const st = stanceOf(v.stance);
            const tclass = st.tone === "up" ? "text-up" : st.tone === "down" ? "text-down" : "text-warn";
            return (
              <tr key={v.key} className="border-b border-line/60 align-top">
                <td className="py-2 whitespace-nowrap"><span className="text-ink">{v.name}</span></td>
                <td className={`${tclass} whitespace-nowrap`}>{st.label}</td>
                <td className="text-right tnum text-ink-dim">{v.score.toFixed(1)}</td>
                <td className="pl-3 text-ink-dim leading-relaxed">{v.rationale}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}

function PersonaTab() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [symbol, setSymbol] = useState("NVDA");
  const [active, setActive] = useState<string | null>(null);
  const [result, setResult] = useState<SavedAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [council, setCouncil] = useState<CouncilResult | null>(null);
  const [councilBusy, setCouncilBusy] = useState(false);

  useEffect(() => { getPersonas().then(setPersonas).catch(() => {}); }, []);
  // Load any cached council for the default symbol so the board isn't empty on first paint.
  const loadCouncil = useCallback((s: string) => {
    getCouncil(s.trim().toUpperCase()).then((d) => setCouncil(d?.result ?? null)).catch(() => setCouncil(null));
  }, []);
  useEffect(() => { loadCouncil("NVDA"); }, [loadCouncil]);

  const run = (key: string) => {
    setActive(key); setBusy(true); setErr(null); setResult(null);
    analyzeAsPersona(key, symbol.trim().toUpperCase()).then(setResult)
      .catch((e) => setErr(errText(e))).finally(() => setBusy(false));
  };
  const convene = () => {
    setCouncilBusy(true); setErr(null);
    runCouncil(symbol.trim().toUpperCase()).then((d) => setCouncil(d.result))
      .catch((e) => setErr(errText(e))).finally(() => setCouncilBusy(false));
  };
  return (
    <div className="space-y-4">
      <Panel title="投资人格" hint="全员会诊,或选一位大师单独深挖">
        <div className="flex gap-2">
          {/* Clear the stale board when the symbol changes so it never shows another stock's council. */}
          <SymbolInput value={symbol} onChange={(s) => { setSymbol(s); setCouncil(null); }} onEnter={convene} className="flex-1" />
          <button onClick={convene} disabled={councilBusy || !symbol.trim()}
            className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-40 whitespace-nowrap">
            {councilBusy ? "会诊中…(约 30–90 秒)" : `全员会诊 ${symbol.trim().toUpperCase()}`}
          </button>
        </div>
      </Panel>
      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}
      {council && <CouncilBoard result={council} />}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {personas.map((p) => (
          <Panel key={p.key} title={p.name} hint={p.style}>
            <p className="text-sm text-ink-dim leading-relaxed min-h-[2.5rem]">{p.tagline}</p>
            <button onClick={() => run(p.key)} disabled={busy || !symbol.trim()}
              className="mt-3 w-full rounded-lg bg-accent/15 text-accent text-sm font-medium px-3 py-1.5 hover:bg-accent/25 disabled:opacity-40">
              {busy && active === p.key ? "分析中…" : `以此视角分析 ${symbol.toUpperCase()}`}
            </button>
          </Panel>
        ))}
      </div>
      {result && (
        <Panel title={`${result.symbol} · 人格分析`} hint={result.provider}>
          <div className="flex items-center gap-2 mb-2">
            <RecBadge rec={result.result.recommendation} tone={recTone(result.result.recommendation)} />
            <div className="flex-1"><ScoreMeter score={result.result.score} /></div>
          </div>
          <p className="text-sm text-ink leading-relaxed">{result.result.summary}</p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-3">
            {result.result.bull_case && <div><span className="text-xs text-up">多头</span><p className="text-sm text-ink-dim">{result.result.bull_case}</p></div>}
            {result.result.bear_case && <div><span className="text-xs text-down">空头</span><p className="text-sm text-ink-dim">{result.result.bear_case}</p></div>}
          </div>
          <Link href={`/research/${result.symbol}`} className="text-accent text-xs mt-2 inline-block">查看研究 →</Link>
        </Panel>
      )}
    </div>
  );
}

function CoachTab() {
  const [data, setData] = useState<CoachResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getCoach().then((d) => setData(d?.result ?? null)).catch(() => {}); }, []);
  const run = () => {
    setBusy(true); setErr(null);
    runCoach().then((d) => setData(d.result)).catch((e) => setErr(String(e).replace(/^Error:\s*/, ""))).finally(() => setBusy(false));
  };
  return (
    <div className="space-y-4">
      <Panel title="AI 投资教练" hint="基于你的组合 / 日志 / 模拟交易,点评「决策过程」">
        <button onClick={run} disabled={busy}
          className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-40">
          {busy ? "教练分析中…(约 30–90 秒)" : "生成教练点评"}
        </button>
      </Panel>
      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}
      {data ? (
        <Panel title="过程评级" hint={`等级 ${data.grade} · 纪律 ${data.discipline_score.toFixed(1)}/10`}>
          <div className="mb-2"><ScoreMeter score={data.discipline_score} /></div>
          <p className="text-sm text-ink leading-relaxed">{data.headline}</p>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-3">
            <Block title="好习惯" tone="up" items={data.good_habits} />
            <Block title="行为偏差" tone="down" items={data.biases} />
            <Block title="训练建议" tone="accent" items={data.drills} />
            <Block title="行动清单" tone="accent" items={data.action_items} />
          </div>
        </Panel>
      ) : !busy && <p className="text-sm text-ink-faint">还没有教练点评。先在组合/日志/模拟交易里积累一些数据,再点「生成教练点评」。</p>}
    </div>
  );
}

// Decision reflection: past AI (council) calls graded against realized price moves.
const GRADE_CLS: Record<string, string> = {
  hit: "text-up", miss: "text-down", open: "text-ink-dim", na: "text-ink-faint",
};
const GRADE_LABEL: Record<string, string> = { hit: "命中", miss: "落空", open: "观望", na: "待定" };

function ReflectionsPanel() {
  const [data, setData] = useState<ReflectionSummary | null>(null);
  useEffect(() => { getReflections().then(setData).catch(() => setData(null)); }, []);
  if (!data) return null;
  return (
    <Panel
      title="决策复盘记忆"
      hint={data.hit_rate_pct != null ? `命中率 ${data.hit_rate_pct}% · 均实现 ${data.avg_return_pct ?? 0}%` : "AI 历史决策 vs 实际走势"}
    >
      {data.rows.length === 0 ? (
        <p className="text-sm text-ink-faint py-2">还没有可复盘的决策。跑一次「大师会诊」即会记录。</p>
      ) : (
        <div className="overflow-auto max-h-80">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-ink-faint border-b border-line">
                <th className="text-left font-medium py-2">日期</th>
                <th className="text-left font-medium">标的</th>
                <th className="text-left font-medium">决策</th>
                <th className="text-right font-medium">决策价</th>
                <th className="text-right font-medium">现价</th>
                <th className="text-right font-medium">实现</th>
                <th className="text-right font-medium pr-1">结果</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={i} className="border-b border-line/50">
                  <td className="py-1.5 text-ink-dim tabular-nums">{r.decided_on}</td>
                  <td className="py-1.5 font-medium text-accent">{r.symbol}</td>
                  <td className="py-1.5 text-ink-dim">{r.action}</td>
                  <td className="py-1.5 text-right tabular-nums text-ink-dim">{r.price != null ? r.price.toFixed(2) : "—"}</td>
                  <td className="py-1.5 text-right tabular-nums text-ink-dim">{r.current_price != null ? r.current_price.toFixed(2) : "—"}</td>
                  <td className={`py-1.5 text-right tabular-nums ${r.return_pct == null ? "text-ink-faint" : r.return_pct >= 0 ? "text-up" : "text-down"}`}>
                    {r.return_pct != null ? `${r.return_pct >= 0 ? "+" : ""}${r.return_pct}%` : "—"}
                  </td>
                  <td className={`py-1.5 text-right pr-1 ${GRADE_CLS[r.grade]}`}>{GRADE_LABEL[r.grade]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function DnaTab() {
  const [data, setData] = useState<DnaResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getDna().then((d) => setData(d?.result ?? null)).catch(() => {}); }, []);
  const run = () => {
    setBusy(true); setErr(null);
    runDna().then((d) => setData(d.result)).catch((e) => setErr(String(e).replace(/^Error:\s*/, ""))).finally(() => setBusy(false));
  };
  return (
    <div className="space-y-4">
      <Panel title="投资 DNA" hint="从你的真实行为里提炼投资画像">
        <button onClick={run} disabled={busy}
          className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-40">
          {busy ? "解析中…(约 30–90 秒)" : "解析我的投资 DNA"}
        </button>
      </Panel>
      <ReflectionsPanel />
      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}
      {data ? (
        <Panel title={data.archetype || "投资画像"} hint={`风险偏好 ${data.risk_tolerance} · ${data.time_horizon}`}>
          <p className="text-sm text-ink leading-relaxed">{data.summary}</p>
          <div className="mt-3 space-y-2">
            <Slider label="价值 ↔ 成长" v={data.growth_vs_value} left="深度价值" right="极致成长" />
            <Slider label="分散 ↔ 集中" v={data.conviction} left="高度分散" right="高度集中" />
          </div>
          <div className="flex flex-wrap gap-1.5 mt-3">
            {data.sector_tilt.map((s, i) => <Chip key={i}>{s}</Chip>)}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-3">
            <Block title="优势" tone="up" items={data.strengths} />
            <Block title="需注意" tone="down" items={data.watchouts} />
          </div>
        </Panel>
      ) : !busy && <p className="text-sm text-ink-faint">还没有 DNA。点「解析我的投资 DNA」生成。</p>}
    </div>
  );
}

function Slider({ label, v, left, right }: { label: string; v: number; left: string; right: string }) {
  return (
    <div>
      <div className="flex justify-between text-[11px] text-ink-faint mb-1"><span>{left}</span><span>{label}</span><span>{right}</span></div>
      <div className="h-1.5 rounded-full bg-panel-2 relative">
        <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-accent" style={{ left: `calc(${Math.max(0, Math.min(100, v))}% - 6px)` }} />
      </div>
    </div>
  );
}

function Block({ title, tone, items }: { title: string; tone: "up" | "down" | "accent"; items: string[] }) {
  if (!items || items.length === 0) return null;
  const color = tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-accent";
  return (
    <div>
      <span className={`text-xs ${color}`}>{title}</span>
      <ul className="mt-1 text-sm text-ink-dim list-disc pl-5 space-y-1">{items.map((it, i) => <li key={i}>{it}</li>)}</ul>
    </div>
  );
}
