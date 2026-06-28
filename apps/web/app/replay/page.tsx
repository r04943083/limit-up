"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Panel from "@/components/Panel";
import { Stat } from "@/components/ui";
import { getOhlcv, type OhlcvBar } from "@/lib/api";
import { dirClass, num, pct } from "@/lib/format";

const WINDOW = 80; // visible candles

function Candles({ bars }: { bars: OhlcvBar[] }) {
  const W = 760, H = 280, pad = 6;
  const view = bars.slice(-WINDOW);
  if (view.length < 2) return <div className="h-72 grid place-items-center text-ink-faint text-sm">加载中…</div>;
  const lo = Math.min(...view.map((b) => b.low));
  const hi = Math.max(...view.map((b) => b.high));
  const span = hi - lo || 1;
  const cw = (W - 2 * pad) / view.length;
  const y = (v: number) => H - pad - ((v - lo) / span) * (H - 2 * pad);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-72" preserveAspectRatio="none">
      {view.map((b, i) => {
        const up = b.close >= b.open;
        const color = up ? "#F6465D" : "#2EBD85";
        const cx = pad + i * cw + cw / 2;
        const bodyTop = y(Math.max(b.open, b.close));
        const bodyBot = y(Math.min(b.open, b.close));
        return (
          <g key={i}>
            <line x1={cx} x2={cx} y1={y(b.high)} y2={y(b.low)} stroke={color} strokeWidth="1" />
            <rect x={cx - cw * 0.35} y={bodyTop} width={cw * 0.7} height={Math.max(1, bodyBot - bodyTop)} fill={color} />
          </g>
        );
      })}
    </svg>
  );
}

export default function ReplayPage() {
  const [symbol, setSymbol] = useState("NVDA");
  const [bars, setBars] = useState<OhlcvBar[]>([]);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [score, setScore] = useState({ correct: 0, total: 0 });
  const [pending, setPending] = useState<"up" | "down" | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback((sym: string) => {
    setLoading(true); setErr(null); setPlaying(false);
    getOhlcv(sym.trim().toUpperCase(), "2y", "1d")
      .then((b) => {
        setBars(b);
        setCursor(Math.max(WINDOW, Math.floor(b.length / 2)));
        setScore({ correct: 0, total: 0 }); setPending(null);
      })
      .catch((e) => setErr(String(e).replace(/^Error:\s*/, "")))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load("NVDA"); }, [load]);

  const step = useCallback(() => {
    setCursor((c) => {
      if (c >= bars.length - 1) { setPlaying(false); return c; }
      // resolve a pending prediction against the newly revealed bar
      setPending((p) => {
        if (p) {
          const went = bars[c + 1].close >= bars[c].close ? "up" : "down";
          setScore((s) => ({ correct: s.correct + (p === went ? 1 : 0), total: s.total + 1 }));
        }
        return null;
      });
      return c + 1;
    });
  }, [bars]);

  useEffect(() => {
    if (playing) {
      timer.current = setInterval(step, 600);
      return () => { if (timer.current) clearInterval(timer.current); };
    }
  }, [playing, step]);

  const visible = useMemo(() => bars.slice(0, cursor + 1), [bars, cursor]);
  const cur = visible[visible.length - 1];
  const prev = visible[visible.length - 2];
  const dayChg = cur && prev ? cur.close / prev.close - 1 : null;
  const atEnd = cursor >= bars.length - 1;

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">复盘 Replay</h1>
        <p className="text-sm text-ink-dim">逐根回放历史行情 · 隐藏未来 · 边看边猜涨跌训练盘感</p>
      </div>

      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

      <Panel title="选择标的">
        <div className="flex gap-3">
          <input value={symbol} onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load(symbol)}
            placeholder="代码 如 NVDA"
            className="flex-1 rounded-lg bg-panel-2 border border-line px-3 py-2 text-sm outline-none focus:border-accent" />
          <button onClick={() => load(symbol)} disabled={loading}
            className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-2 hover:bg-accent/25 disabled:opacity-40">
            {loading ? "加载中…" : "载入"}
          </button>
        </div>
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        <Panel title="行情回放" hint={cur ? cur.date : ""} className="lg:col-span-3">
          <Candles bars={visible} />
          <div className="flex items-center gap-2 mt-3">
            <button onClick={() => setCursor((c) => Math.max(WINDOW, c - 1))}
              className="rounded-lg border border-line text-ink-dim px-3 py-1.5 text-sm hover:text-ink">⏮ 上一根</button>
            <button onClick={() => setPlaying((p) => !p)} disabled={atEnd}
              className="rounded-lg bg-accent/15 text-accent px-4 py-1.5 text-sm font-medium hover:bg-accent/25 disabled:opacity-40">
              {playing ? "⏸ 暂停" : "▶ 播放"}
            </button>
            <button onClick={step} disabled={atEnd}
              className="rounded-lg border border-line text-ink-dim px-3 py-1.5 text-sm hover:text-ink disabled:opacity-40">⏭ 下一根</button>
            <span className="text-xs text-ink-faint ml-2 tnum">{cursor + 1} / {bars.length}</span>
            {atEnd && <span className="text-xs text-warn ml-1">已到末尾</span>}
          </div>
        </Panel>

        <div className="space-y-5">
          <Panel title="当前K线" hint={cur ? cur.date : ""}>
            {cur && (<>
              <Stat label="收盘" value={<span className="tnum">{num(cur.close)}</span>} />
              <Stat label="开/高/低" value={<span className="tnum">{num(cur.open)} / {num(cur.high)} / {num(cur.low)}</span>} />
              <Stat label="当日涨跌" value={<span className={dirClass(dayChg)}>{pct(dayChg)}</span>} />
            </>)}
          </Panel>
          <Panel title="猜涨跌" hint={`正确率 ${score.total ? Math.round((score.correct / score.total) * 100) : 0}%`}>
            <p className="text-xs text-ink-dim mb-2">预测下一根的方向,再点「下一根」揭晓:</p>
            <div className="flex gap-2">
              <button onClick={() => setPending("up")} disabled={atEnd}
                className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-40 ${
                  pending === "up" ? "bg-up/30 text-up" : "bg-up/10 text-up hover:bg-up/20"}`}>看涨</button>
              <button onClick={() => setPending("down")} disabled={atEnd}
                className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium disabled:opacity-40 ${
                  pending === "down" ? "bg-down/30 text-down" : "bg-down/10 text-down hover:bg-down/20"}`}>看跌</button>
            </div>
            <p className="text-xs text-ink-faint mt-2 tnum">{score.correct} / {score.total} 命中</p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
