"use client";

import { useEffect, useState } from "react";
import Panel from "@/components/Panel";
import { Stat } from "@/components/ui";
import { getTearsheet, type PortfolioTearsheet as TS } from "@/lib/api";
import { num, signedPct, dirClass, errText } from "@/lib/format";

// Rigorous risk/return tear-sheet for the current basket (Sharpe/Sortino/Calmar, drawdown,
// VaR/CVaR, monthly returns, vs-SPY alpha/beta). Numbers are deterministic compute output.
export default function PortfolioTearsheet({ pid }: { pid: number }) {
  const [data, setData] = useState<TS | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setData(null); setErr(null);
    getTearsheet(pid).then(setData).catch((e) => setErr(errText(e)));
  }, [pid]);

  const t = data?.tearsheet;
  const monthTone = (v: number) => (v > 0 ? "text-up" : v < 0 ? "text-down" : "text-ink-dim");

  return (
    <Panel
      title="绩效 tear-sheet"
      hint={data?.ok ? `${data.start ?? ""} → ${data.end ?? ""} · vs ${data.benchmark}` : "当前组合 ~1年重构曲线"}
    >
      {err ? (
        <p className="text-sm text-ink-faint py-6 text-center">{err}</p>
      ) : !data ? (
        <p className="text-sm text-ink-faint py-6 text-center">加载中…(重构净值曲线)</p>
      ) : !data.ok || !t ? (
        <p className="text-sm text-ink-faint py-6 text-center">
          {data.error === "empty portfolio" ? "组合为空,先添加持仓。" : "价格历史不足,先同步数据。"}
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1">
            <Stat label="总回报" value={signedPct(t.total_return_pct)} tone={(t.total_return_pct ?? 0) >= 0 ? "up" : "down"} />
            <Stat label="年化 (CAGR)" value={signedPct(t.cagr_pct)} tone={(t.cagr_pct ?? 0) >= 0 ? "up" : "down"} />
            <Stat label="Sharpe" value={num(t.sharpe)} />
            <Stat label="Sortino" value={num(t.sortino)} />
            <Stat label="Calmar" value={num(t.calmar)} />
            <Stat label="年化波动" value={t.volatility_pct != null ? `${t.volatility_pct}%` : "—"} />
            <Stat label="最大回撤" value={t.max_drawdown_pct != null ? `-${t.max_drawdown_pct}%` : "—"} tone="down" />
            <Stat label="胜率" value={t.win_rate_pct != null ? `${t.win_rate_pct}%` : "—"} />
            {/* var95_pct is a positive loss magnitude; show the signed return at that
                percentile (−loss), so a rare all-gains tail doesn't render a double-negative. */}
            <Stat label="日 VaR(95%)" value={t.var95_pct != null ? signedPct(-t.var95_pct) : "—"} tone="down" />
            <Stat label="日 CVaR(95%)" value={t.cvar95_pct != null ? signedPct(-t.cvar95_pct) : "—"} tone="down" />
            <Stat label="盈亏比" value={num(t.profit_factor)} />
            {t.beta != null && <Stat label={`β / α vs ${data.benchmark}`} value={`${t.beta} / ${signedPct(t.alpha_pct)}`} />}
          </div>

          {t.benchmark_return_pct != null && (
            <div className="mt-3 text-xs text-ink-dim">
              同期 {data.benchmark}:<span className={dirClass(t.benchmark_return_pct)}>{signedPct(t.benchmark_return_pct)}</span>
              {t.total_return_pct != null && (
                <span className="ml-2">超额 <span className={dirClass(t.total_return_pct - t.benchmark_return_pct)}>{signedPct(t.total_return_pct - t.benchmark_return_pct)}</span></span>
              )}
            </div>
          )}

          {t.monthly_returns.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] text-ink-faint mb-1.5">月度回报</div>
              <div className="flex flex-wrap gap-1.5">
                {t.monthly_returns.map((m) => (
                  <span key={m.month} title={m.month}
                    className={`px-1.5 py-0.5 rounded text-[11px] tabular-nums bg-panel-2 border border-line ${monthTone(m.return_pct)}`}>
                    {m.month.slice(2)} {m.return_pct >= 0 ? "+" : ""}{m.return_pct}%
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
