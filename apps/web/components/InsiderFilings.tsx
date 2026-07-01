"use client";

import { useEffect, useState } from "react";
import Panel from "@/components/Panel";
import {
  getInsiders, getFilings, getFilingDiff,
  type InsiderReport, type FilingRow, type FilingDiffResult,
} from "@/lib/api";
import { num, compact, dirClass, errText } from "@/lib/format";
import { isUS } from "@/lib/market";

// SEC transaction code → Chinese label + tone (red=买入/up, green=卖出/down).
const CODE: Record<string, { label: string; cls: string }> = {
  P: { label: "买入", cls: "text-up" },
  S: { label: "卖出", cls: "text-down" },
  M: { label: "行权", cls: "text-ink-dim" },
  A: { label: "授予", cls: "text-ink-dim" },
  F: { label: "抵税", cls: "text-ink-dim" },
  G: { label: "赠与", cls: "text-ink-dim" },
};

// US-only: SEC Form 4 insider transactions (with cluster-buy signal) + recent filings.
// Rendered under the 股东 tab beneath institutional holders. First load is a slow SEC fetch,
// cached for the day thereafter.
export default function InsiderFilings({ symbol }: { symbol: string }) {
  const [report, setReport] = useState<InsiderReport | null>(null);
  const [filings, setFilings] = useState<FilingRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol || !isUS(symbol)) { setReport(null); setFilings(null); return; }
    setErr(null); setReport(null); setFilings(null);
    getInsiders(symbol)
      .then((r) => { setReport(r.report); if (!r.ok) setErr(errText(r.error) || "数据源暂不可用"); })
      .catch((e) => setErr(errText(e)));
    getFilings(symbol).then((r) => setFilings(r.filings)).catch(() => {});
  }, [symbol]);

  if (!isUS(symbol)) return null;  // EDGAR is US-only

  return (
    <>
      <Panel
        title="内部人交易"
        hint={report ? `近${report.window_days}天 · Form 4` : "SEC · 首次加载较慢"}
      >
        {!report && !err ? (
          <p className="text-sm text-ink-faint py-4 text-center">加载中…(SEC 首次抓取)</p>
        ) : err && !report ? (
          <p className="text-sm text-ink-faint py-4 text-center">{err}</p>
        ) : report ? (
          <>
            <div className="flex flex-wrap items-center gap-4 mb-3 text-sm">
              <span className="text-up">买入 {report.buy_count}<span className="text-ink-faint text-xs"> · {report.distinct_buyers}人</span></span>
              <span className="text-down">卖出 {report.sell_count}<span className="text-ink-faint text-xs"> · {report.distinct_sellers}人</span></span>
              {report.net_shares != null && (
                <span className={dirClass(report.net_shares)}>净 {compact(report.net_shares)} 股</span>
              )}
              {report.cluster_buy && (
                <span className="px-2 py-0.5 rounded-md bg-up/15 text-up text-xs font-medium">集群买入信号</span>
              )}
            </div>
            {report.transactions.length === 0 ? (
              <p className="text-sm text-ink-faint py-2">{err ? "数据源暂不可用,请稍后重试。" : "近期无内部人交易记录。"}</p>
            ) : (
              <div className="overflow-auto max-h-72">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[11px] text-ink-faint border-b border-line">
                      <th className="text-left font-normal py-1.5 pr-2">日期</th>
                      <th className="text-left font-normal py-1.5 pr-2">内部人</th>
                      <th className="text-left font-normal py-1.5 pr-2">类型</th>
                      <th className="text-right font-normal py-1.5 px-2">股数</th>
                      <th className="text-right font-normal py-1.5 pl-2">价格</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.transactions.map((t, i) => {
                      const c = CODE[t.code ?? ""] ?? { label: t.type ?? t.code ?? "—", cls: "text-ink-dim" };
                      return (
                        <tr key={i} className="border-b border-line/40">
                          <td className="py-1.5 pr-2 text-ink-dim tabular-nums">{t.date ?? "—"}</td>
                          <td className="py-1.5 pr-2 max-w-[140px] truncate" title={t.position ?? ""}>{t.insider ?? "—"}</td>
                          <td className={`py-1.5 pr-2 ${c.cls}`}>{c.label}</td>
                          <td className="py-1.5 px-2 text-right tabular-nums">{compact(t.shares)}</td>
                          <td className="py-1.5 pl-2 text-right tabular-nums text-ink-dim">{t.price != null ? num(t.price) : "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : null}
      </Panel>

      <Panel title="SEC 申报" hint={filings ? `${filings.length} 条` : undefined}>
        {!filings ? (
          <p className="text-sm text-ink-faint py-4 text-center">加载中…</p>
        ) : filings.length === 0 ? (
          <p className="text-sm text-ink-faint py-2">暂无申报记录。</p>
        ) : (
          <ul className="space-y-1.5">
            {filings.map((f, i) => (
              <li key={i} className="flex items-center gap-3 text-sm">
                <span className="inline-block min-w-[3.5rem] px-1.5 py-0.5 rounded bg-panel-2 border border-line text-[11px] text-ink-dim text-center">{f.form}</span>
                <span className="text-ink-dim tabular-nums text-xs">{f.date ?? "—"}</span>
                {f.url ? (
                  <a href={f.url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline truncate">
                    {f.title || "查看申报"}
                  </a>
                ) : (
                  <span className="text-ink-dim truncate">{f.title || "—"}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <FilingDiffBlock symbol={symbol} />
    </>
  );
}

const SECTIONS: { key: string; label: string }[] = [
  { key: "risk_factors", label: "风险因素" },
  { key: "management_discussion", label: "MD&A" },
  { key: "business", label: "业务" },
];

// 10-K red-line diff of a narrative section between the two most recent filings. Parsing two
// 10-Ks is slow, so this is button-triggered (not auto-loaded).
function FilingDiffBlock({ symbol }: { symbol: string }) {
  const [section, setSection] = useState("risk_factors");
  const [data, setData] = useState<FilingDiffResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = (sec: string) => {
    setSection(sec); setBusy(true); setErr(null); setData(null);
    getFilingDiff(symbol, "10-K", sec)
      .then((d) => { setData(d); if (!d.ok) setErr(d.error || "无法生成对比"); })
      .catch((e) => setErr(errText(e)))
      .finally(() => setBusy(false));
  };

  return (
    <Panel title="10-K 红线对比" hint={data?.ok ? `${data.old_date} → ${data.new_date} · +${data.diff.added_count}/-${data.diff.removed_count}` : "两期年报章节变化"}>
      <div className="flex flex-wrap items-center gap-1.5 mb-3">
        {SECTIONS.map((s) => (
          <button key={s.key} onClick={() => run(s.key)} disabled={busy}
            className={`px-2.5 py-1 rounded text-xs disabled:opacity-40 ${s.key === section && (data || busy) ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink border border-line"}`}>
            {s.label}
          </button>
        ))}
        <span className="text-[11px] text-ink-faint ml-1">SEC 首次抓取较慢</span>
      </div>
      {busy ? <p className="text-sm text-ink-faint py-4 text-center">对比中…(解析两期 10-K)</p>
        : err ? <p className="text-sm text-ink-faint py-4 text-center">{err}</p>
        : !data ? <p className="text-sm text-ink-faint py-2">选择章节对比最近两期年报的措辞变化。</p>
        : !data.diff.changed ? <p className="text-sm text-ink-faint py-2">该章节与上期基本一致。</p>
        : (
          <div className="max-h-96 overflow-auto text-sm leading-relaxed space-y-1">
            {data.diff.chunks.map((c, i) => {
              if (c.op === "added") return <p key={i} className="bg-accent/10 text-accent rounded px-1.5 py-0.5">＋ {c.text}</p>;
              if (c.op === "removed") return <p key={i} className="text-ink-faint line-through px-1.5">－ {c.text}</p>;
              return <p key={i} className="text-ink-dim px-1.5">{c.text}</p>;
            })}
          </div>
        )}
    </Panel>
  );
}
