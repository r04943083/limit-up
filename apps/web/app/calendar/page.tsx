"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Panel from "@/components/Panel";
import { getCalendar, type CalendarEvent } from "@/lib/api";
import { errText } from "@/lib/format";

// 财经日历: upcoming earnings / ex-dividend for the symbols the user follows.
const TYPE_CLS: Record<string, string> = {
  earnings: "bg-accent/15 text-accent",
  ex_dividend: "bg-warn/15 text-warn",
};

export default function CalendarPage() {
  const router = useRouter();
  const [within, setWithin] = useState(30);
  const [events, setEvents] = useState<CalendarEvent[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setEvents(null); setErr(null);
    getCalendar(within).then((r) => setEvents(r.events)).catch((e) => setErr(errText(e)));
  }, [within]);

  // Group by date for a day-by-day agenda.
  const byDate: Record<string, CalendarEvent[]> = {};
  (events ?? []).forEach((e) => { (byDate[e.date] ||= []).push(e); });
  const days = Object.keys(byDate).sort();

  return (
    <div className="p-5 space-y-4 overflow-auto">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-medium text-ink">财经日历</h1>
        <span className="text-[11px] text-ink-faint">自选 + 持仓的财报 / 除息</span>
        <div className="ml-auto flex gap-1">
          {[14, 30, 60].map((d) => (
            <button key={d} onClick={() => setWithin(d)}
              className={`px-2.5 py-1 rounded text-xs ${within === d ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink border border-line"}`}>
              {d}天
            </button>
          ))}
        </div>
      </div>

      <Panel title={`未来 ${within} 天`} hint={events ? `${events.length} 项` : undefined}>
        {err ? (
          <p className="text-sm text-ink-faint py-8 text-center">{err}</p>
        ) : !events ? (
          <p className="text-sm text-ink-faint py-8 text-center">加载中…</p>
        ) : days.length === 0 ? (
          <p className="text-sm text-ink-faint py-8 text-center">未来 {within} 天内暂无财报 / 除息事件(或数据未同步)。</p>
        ) : (
          <div className="space-y-4">
            {days.map((date) => (
              <div key={date} className="flex gap-4">
                <div className="min-w-[5.5rem] text-sm text-ink-dim tabular-nums pt-0.5">{date}</div>
                <ul className="flex-1 space-y-1.5">
                  {byDate[date].map((e, i) => (
                    <li key={i} className="flex items-center gap-2.5 text-sm">
                      <span className={`inline-block min-w-[2.6rem] px-1.5 py-0.5 rounded text-[11px] text-center ${TYPE_CLS[e.type] ?? "bg-panel-2 text-ink-dim"}`}>{e.label}</span>
                      <button onClick={() => router.push(`/research/${e.symbol}`)} className="font-medium text-accent hover:underline">{e.symbol}</button>
                      {e.detail && <span className="text-ink-faint text-xs">{e.detail}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
