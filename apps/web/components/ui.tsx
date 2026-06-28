import type { ReactNode } from "react";

export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: "up" | "down" }) {
  const color = tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-ink";
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-line/60 last:border-0">
      <span className="text-xs text-ink-dim">{label}</span>
      <span className={`text-xs tnum ${color}`}>{value}</span>
    </div>
  );
}

export function RecBadge({ rec, tone }: { rec: string; tone: "up" | "down" | "amber" }) {
  const cls =
    tone === "up"
      ? "bg-up/15 text-up"
      : tone === "down"
        ? "bg-down/15 text-down"
        : "bg-[#E0A33E]/15 text-[#E0A33E]";
  return <span className={`px-2 py-0.5 rounded-md text-xs font-medium ${cls}`}>{rec}</span>;
}

export function ScoreMeter({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(10, score)) * 10;
  const color = score >= 6.5 ? "#2EBD85" : score >= 4 ? "#E0A33E" : "#F6465D";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-panel-2 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-xs tnum text-ink-dim">{score.toFixed(1)}</span>
    </div>
  );
}

export function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="px-2 py-0.5 rounded-md bg-panel-2 border border-line text-[11px] text-ink-dim">
      {children}
    </span>
  );
}
