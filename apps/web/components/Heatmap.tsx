"use client";

import { useRouter } from "next/navigation";
import type { OverviewRow } from "@/lib/api";
import { signedPct } from "@/lib/format";

// Color a tile by change% — CN/Futu convention: red = up, green = down.
function tileColor(pct: number | null): string {
  if (pct == null) return "#1B232B";
  const c = Math.max(-3, Math.min(3, pct)) / 3; // -1..1
  if (c >= 0) {
    const a = 0.18 + c * 0.55;
    return `rgba(246,70,93,${a.toFixed(3)})`;
  }
  const a = 0.18 + -c * 0.55;
  return `rgba(46,189,133,${a.toFixed(3)})`;
}

export default function Heatmap({ rows }: { rows: OverviewRow[] }) {
  const router = useRouter();
  // Group by sector; size tiles by market cap (fallback equal).
  const bySector = new Map<string, OverviewRow[]>();
  for (const r of rows) {
    const key = r.sector || "其他";
    (bySector.get(key) ?? bySector.set(key, []).get(key)!).push(r);
  }
  const sectors = [...bySector.entries()]
    .map(([sector, items]) => ({
      sector,
      items: [...items].sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0)),
      cap: items.reduce((s, r) => s + (r.market_cap ?? 0), 0),
    }))
    .sort((a, b) => b.items.length - a.items.length);

  if (rows.length === 0) {
    return <p className="text-sm text-ink-faint">先到自选「全部更新」拉取数据后,这里按行业显示热力图。</p>;
  }

  return (
    <div className="space-y-3">
      {sectors.map((s) => (
        <div key={s.sector}>
          <div className="text-[11px] text-ink-faint mb-1">{s.sector} · {s.items.length}</div>
          <div className="flex flex-wrap gap-1">
            {s.items.map((r) => (
              <button
                key={r.symbol}
                onClick={() => router.push(`/research/${encodeURIComponent(r.symbol)}`)}
                title={`${r.name ?? r.symbol} ${signedPct(r.change_pct)}`}
                className="rounded px-2 py-1.5 text-left min-w-[84px] hover:ring-1 hover:ring-accent/50 transition-shadow"
                style={{ background: tileColor(r.change_pct) }}
              >
                <div className="text-[11px] text-ink font-medium truncate max-w-[120px]">{r.symbol}</div>
                <div className="text-[11px] tnum text-ink/90">{signedPct(r.change_pct)}</div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
