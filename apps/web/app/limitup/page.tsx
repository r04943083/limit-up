"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Panel from "@/components/Panel";
import {
  getLimitUp, getDragonTiger, getHsgtSummary, getZtReview, runZtReview,
  type LimitUpPool, type DragonTiger, type HsgtSummary, type SavedZtReview, type LimitUpStock,
} from "@/lib/api";
import { num, signedPct, dirClass } from "@/lib/format";

// CN amounts come in 元 — show 亿 / 万 like Chinese terminals.
function yi(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (a >= 1e4) return `${(v / 1e4).toFixed(0)}万`;
  return v.toFixed(0);
}
// HSGT values are already in 亿元.
const yiUnit = (v: number | null | undefined) => (v == null ? "—" : `${v.toFixed(2)}亿`);

function toApiDate(d: string): string {
  return d.replaceAll("-", "");
}
function todayISO(): string {
  // Local date (not UTC) so it matches the server's dt.date.today().
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
// A-share code → yfinance symbol (6→上证 .SS, else 深证 .SZ; 8/4 北交所 unsupported).
function toSymbol(code: string): string | null {
  if (/^6/.test(code)) return `${code}.SS`;
  if (/^[03]/.test(code)) return `${code}.SZ`;
  return null;
}

export default function LimitUpPage() {
  const router = useRouter();
  const [date, setDate] = useState(todayISO());
  const [pool, setPool] = useState<LimitUpPool | null>(null);
  const [lhb, setLhb] = useState<DragonTiger | null>(null);
  const [hsgt, setHsgt] = useState<HsgtSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [review, setReview] = useState<SavedZtReview | null>(null);
  const [reviewing, setReviewing] = useState(false);

  const load = useCallback((iso: string) => {
    const d = toApiDate(iso);
    setLoading(true); setErr(null); setPool(null); setLhb(null); setReview(null);
    Promise.all([getLimitUp(d), getDragonTiger(d)])
      .then(([z, l]) => {
        setPool(z.pool);
        setLhb(l.data);
        if (!z.ok && !z.pool.count) setErr(z.error || "数据源暂不可用");
      })
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
    getZtReview(d).then(setReview).catch(() => setReview(null));
  }, []);

  useEffect(() => { load(date); }, [date, load]);
  useEffect(() => { getHsgtSummary().then((r) => setHsgt(r.summary)).catch(() => {}); }, []);

  const doReview = () => {
    setReviewing(true);
    runZtReview(toApiDate(date)).then(setReview).catch((e) => setErr(String(e))).finally(() => setReviewing(false));
  };

  const open = (code: string) => {
    const sym = toSymbol(code);
    if (sym) router.push(`/research/${encodeURIComponent(sym)}`);
  };

  // Sort limit-up by 连板 desc then 封板资金 desc — surface the 连板龙头 first.
  const stocks = pool?.stocks.slice().sort((a, b) =>
    (b.boards ?? 0) - (a.boards ?? 0) || (b.seal_fund ?? 0) - (a.seal_fund ?? 0)) ?? [];

  // 连板天梯: group by board height, highest first (stocks already sorted within tier by seal fund).
  const tierMap = new Map<number, LimitUpStock[]>();
  for (const s of stocks) {
    const b = s.boards && s.boards >= 1 ? s.boards : 1;
    if (!tierMap.has(b)) tierMap.set(b, []);
    tierMap.get(b)!.push(s);
  }
  const tiers = [...tierMap.entries()].sort((a, b) => b[0] - a[0]);

  return (
    <div className="flex-1 overflow-auto p-5 space-y-5">
      <div className="flex items-baseline justify-between gap-4 flex-wrap">
        <div className="flex items-baseline gap-3">
          <h1 className="text-xl font-semibold tracking-tight">涨停复盘</h1>
          <span className="text-sm text-ink-dim">A 股涨停板池 · 龙虎榜 · 沪深港通 · 数据 akshare</span>
        </div>
        <div className="flex items-center gap-2">
          <input type="date" value={date} max={todayISO()} onChange={(e) => setDate(e.target.value)}
            className="bg-base border border-line rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-accent/60" />
          {pool && <span className="text-xs text-ink-faint">涨停 {pool.count} 家</span>}
        </div>
      </div>

      {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}

      {/* AI 复盘 */}
      <Panel title="AI 复盘解读" hint={review ? review.provider : "AI 生成"}>
        <button onClick={doReview} disabled={reviewing || loading || !pool?.count}
          className="w-full rounded-lg bg-accent/15 text-accent text-sm font-medium py-2 hover:bg-accent/25 disabled:opacity-50">
          {reviewing ? "复盘中…(约 20–40 秒)" : review ? "重新复盘" : "AI 复盘解读"}
        </button>
        {review ? (
          <div className="space-y-3 mt-3">
            <div className="text-sm text-accent font-medium leading-relaxed">{review.result.sentiment}</div>
            <p className="text-sm text-ink-dim leading-relaxed">{review.result.summary}</p>
            {review.result.ladder_read && (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">连板梯队</div>
                <p className="text-xs text-ink-dim leading-relaxed">{review.result.ladder_read}</p>
              </div>
            )}
            {review.result.leaders.length > 0 && (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">主线 / 方向</div>
                <ul className="list-disc list-inside text-xs text-ink-dim space-y-0.5">
                  {review.result.leaders.map((l, i) => <li key={i}>{l}</li>)}
                </ul>
              </div>
            )}
            {review.result.capital && (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1">资金面</div>
                <p className="text-xs text-ink-dim leading-relaxed">{review.result.capital}</p>
              </div>
            )}
            {review.result.risks.length > 0 && (
              <div>
                <div className="text-[11px] uppercase tracking-wide text-down mb-1">退潮 / 风险</div>
                <ul className="list-disc list-inside text-xs text-ink-dim space-y-0.5">
                  {review.result.risks.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            )}
            <p className="text-[11px] text-ink-faint">AI 观点 · 非投资建议 · {review.provider}</p>
          </div>
        ) : (
          <p className="text-sm text-ink-faint mt-2">基于当日涨停梯队、龙虎榜与南向资金,生成中文复盘(情绪 / 梯队 / 主线 / 资金 / 风险)。</p>
        )}
      </Panel>

      {/* 连板天梯 */}
      {!loading && stocks.length > 0 && (
        <Panel title="连板天梯" hint="高度板在左 · 点标的看研究">
          <Ladder tiers={tiers} onOpen={open} />
        </Panel>
      )}

      {/* HSGT summary */}
      {hsgt && hsgt.rows.length > 0 && (
        <Panel title="沪深港通资金" hint={hsgt.northbound_suspended ? "北向实时净额自 2024-08 已停发" : (hsgt.date ?? undefined)}>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {hsgt.rows.map((r) => (
              <div key={`${r.market}-${r.direction}`} className="rounded-lg border border-line bg-panel p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-ink">{r.market}</span>
                  <span className="text-[10px] text-ink-faint px-1.5 py-0.5 rounded bg-panel-2">{r.direction}</span>
                </div>
                <div className={`text-lg font-semibold tnum mt-1 ${dirClass(r.net)}`}>{yiUnit(r.net)}</div>
                <div className="text-[11px] text-ink-faint mt-1">
                  {r.index_name} <span className={dirClass(r.index_pct)}>{signedPct(r.index_pct)}</span>
                </div>
                {(r.up != null || r.down != null) && (
                  <div className="text-[11px] mt-1">
                    <span className="text-up">涨 {r.up ?? "—"}</span> · <span className="text-ink-faint">平 {r.flat ?? "—"}</span> · <span className="text-down">跌 {r.down ?? "—"}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Limit-up pool */}
      <Panel title="涨停板池" hint={loading ? "加载中…" : `${stocks.length} 家 · 按连板数排序`}>
        {loading ? <p className="text-sm text-ink-faint py-6 text-center">加载中…</p>
          : stocks.length === 0 ? <p className="text-sm text-ink-faint py-6 text-center">该日无涨停数据(或为非交易日 / 数据源未更新)。</p>
          : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-ink-faint border-b border-line">
                    <th className="text-left font-medium py-2 pr-3">代码 / 名称</th>
                    <th className="text-right font-medium px-2">涨跌幅</th>
                    <th className="text-right font-medium px-2">最新价</th>
                    <th className="text-center font-medium px-2">连板</th>
                    <th className="text-right font-medium px-2">封板资金</th>
                    <th className="text-right font-medium px-2">炸板</th>
                    <th className="text-right font-medium px-2">换手</th>
                    <th className="text-center font-medium px-2">首封</th>
                    <th className="text-left font-medium px-2">行业</th>
                  </tr>
                </thead>
                <tbody>
                  {stocks.map((s) => (
                    <tr key={s.code} onClick={() => open(s.code)}
                      className="border-b border-line/50 hover:bg-panel-2/40 cursor-pointer">
                      <td className="py-1.5 pr-3 whitespace-nowrap">
                        <span className="text-ink">{s.name}</span>
                        <span className="text-ink-faint text-xs ml-2">{s.code}</span>
                      </td>
                      <td className={`text-right tnum px-2 ${dirClass(s.pct)}`}>{signedPct(s.pct)}</td>
                      <td className="text-right tnum px-2 text-ink-dim">{num(s.price)}</td>
                      <td className="text-center px-2">
                        {s.boards && s.boards >= 2
                          ? <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-medium ${s.boards >= 4 ? "bg-up/25 text-up" : "bg-up/15 text-up"}`}>{s.boards}连板</span>
                          : <span className="text-ink-faint text-xs">首板</span>}
                      </td>
                      <td className="text-right tnum px-2 text-ink-dim">{yi(s.seal_fund)}</td>
                      <td className="text-right tnum px-2 text-ink-faint">{s.broken_times ?? 0}</td>
                      <td className="text-right tnum px-2 text-ink-faint">{s.turnover != null ? `${s.turnover.toFixed(1)}%` : "—"}</td>
                      <td className="text-center tnum px-2 text-ink-faint">{s.first_seal ?? "—"}</td>
                      <td className="px-2 text-ink-dim whitespace-nowrap">{s.industry ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Panel>

      {/* Dragon-tiger */}
      <Panel title="龙虎榜" hint={lhb ? `${lhb.count} 条` : undefined}>
        {loading ? <p className="text-sm text-ink-faint py-6 text-center">加载中…</p>
          : !lhb || lhb.rows.length === 0 ? <p className="text-sm text-ink-faint py-6 text-center">该日无龙虎榜数据。</p>
          : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-ink-faint border-b border-line">
                    <th className="text-left font-medium py-2 pr-3">代码 / 名称</th>
                    <th className="text-right font-medium px-2">涨跌幅</th>
                    <th className="text-right font-medium px-2">净买额</th>
                    <th className="text-right font-medium px-2">占成交</th>
                    <th className="text-left font-medium px-2">上榜原因</th>
                  </tr>
                </thead>
                <tbody>
                  {lhb.rows.map((r, i) => (
                    <tr key={`${r.code}-${i}`} onClick={() => open(r.code)}
                      className="border-b border-line/50 hover:bg-panel-2/40 cursor-pointer">
                      <td className="py-1.5 pr-3 whitespace-nowrap">
                        <span className="text-ink">{r.name}</span>
                        <span className="text-ink-faint text-xs ml-2">{r.code}</span>
                      </td>
                      <td className={`text-right tnum px-2 ${dirClass(r.pct)}`}>{signedPct(r.pct)}</td>
                      <td className={`text-right tnum px-2 ${dirClass(r.net_buy)}`}>{yi(r.net_buy)}</td>
                      <td className="text-right tnum px-2 text-ink-faint">{r.net_pct != null ? `${r.net_pct.toFixed(1)}%` : "—"}</td>
                      <td className="px-2 text-ink-dim">{r.reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Panel>

      <p className="text-[11px] text-ink-faint">数据来源:akshare(东方财富)· 仅供研究参考,非投资建议。</p>
    </div>
  );
}

// 连板天梯: one column per board height (高度板在左), stocks sorted by 封板资金 within a tier.
function Ladder({ tiers, onOpen }: { tiers: [number, LimitUpStock[]][]; onOpen: (code: string) => void }) {
  return (
    <div className="flex gap-3 overflow-x-auto pb-1">
      {tiers.map(([boards, list]) => {
        const hi = boards >= 2;
        return (
          <div key={boards} className="shrink-0 w-40">
            <div className="flex items-center justify-between mb-2 sticky top-0">
              <span className={`text-xs font-semibold ${hi ? "text-up" : "text-ink-dim"}`}>
                {hi ? `${boards}连板` : "首板"}
              </span>
              <span className="text-[11px] text-ink-faint tnum">{list.length}</span>
            </div>
            <div className="space-y-1 max-h-[22rem] overflow-y-auto no-scrollbar pr-0.5">
              {list.map((s) => (
                <button key={s.code} onClick={() => onOpen(s.code)}
                  className={`w-full text-left rounded-md border px-2 py-1 transition-colors ${
                    hi ? "border-up/30 bg-up/5 hover:bg-up/10" : "border-line bg-panel hover:bg-panel-2/60"
                  }`}>
                  <div className="text-[12px] text-ink truncate">{s.name}</div>
                  <div className="text-[10px] text-ink-faint flex items-center justify-between gap-1">
                    <span className="tnum">{s.code}</span>
                    <span className="truncate">{s.industry ?? ""}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
