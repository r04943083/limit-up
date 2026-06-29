"use client";

import { useEffect, useRef, useState } from "react";
import { clearChat, getChatHistory, sendChat, type ChatTurn } from "@/lib/api";

const SUGGESTIONS = [
  "NVDA 现在的多空逻辑是什么?",
  "帮我比较 AMD 和 AVGO 的基本面",
  "我应该如何看待当前的半导体板块?",
];

export default function ChatPage() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => { getChatHistory().then(setTurns).catch(() => {}); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns, busy]);

  const send = (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || busy) return;
    setErr(null);
    setInput("");
    const optimistic: ChatTurn = { id: Date.now(), role: "user", content: msg, created_at: new Date().toISOString() };
    setTurns((t) => [...t, optimistic]);
    setBusy(true);
    sendChat(msg)
      .then((r) => setTurns((t) => [...t, { id: Date.now() + 1, role: "assistant", content: r.reply, created_at: new Date().toISOString() }]))
      .catch((e) => setErr(String(e).replace(/^Error:\s*/, "")))
      .finally(() => setBusy(false));
  };

  const clear = () => {
    if (turns.length === 0 || !confirm("清空所有对话记录?此操作不可撤销。")) return;
    clearChat().then(() => setTurns([])).catch(() => {});
  };

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex items-baseline justify-between px-5 py-4 border-b border-line">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">AI 对话</h1>
          <p className="text-sm text-ink-dim">投研助手 · 提到代码会自动注入 LU 的真实数据(红涨绿跌)</p>
        </div>
        <button onClick={clear} className="rounded-lg border border-line text-ink-dim text-sm px-3 py-1.5 hover:text-ink">清空</button>
      </div>

      <div className="flex-1 overflow-auto p-5 space-y-4">
        {turns.length === 0 && !busy && (
          <div className="max-w-2xl mx-auto text-center space-y-4 mt-10">
            <p className="text-ink-dim text-sm">问点什么开始吧 —— 例如:</p>
            <div className="flex flex-col gap-2 items-center">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)}
                  className="rounded-lg bg-panel-2 border border-line px-4 py-2 text-sm text-ink-dim hover:text-ink hover:border-accent/50">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t) => (
          <div key={t.id} className={`flex ${t.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-2xl rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
              t.role === "user" ? "bg-accent/15 text-ink" : "bg-panel border border-line text-ink-dim"
            }`}>
              {t.content}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="max-w-2xl rounded-2xl px-4 py-2.5 text-sm bg-panel border border-line text-ink-faint">
              思考中…(AI 生成,约 10–40 秒)
            </div>
          </div>
        )}
        {err && <div className="rounded-lg border border-down/40 bg-down/10 text-down text-sm px-4 py-2">{err}</div>}
        <div ref={endRef} />
      </div>

      <div className="border-t border-line p-4">
        <div className="flex gap-2 max-w-3xl mx-auto">
          <textarea value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            rows={1} placeholder="问 LU 任何投研问题…(Enter 发送,Shift+Enter 换行)"
            className="flex-1 resize-none rounded-xl bg-panel-2 border border-line px-4 py-2.5 text-sm outline-none focus:border-accent" />
          <button onClick={() => send()} disabled={busy || !input.trim()}
            className="rounded-xl bg-accent/15 text-accent text-sm font-medium px-5 hover:bg-accent/25 disabled:opacity-40">
            发送
          </button>
        </div>
        <p className="text-[11px] text-ink-faint text-center mt-2">AI 观点 · 非投资建议</p>
      </div>
    </div>
  );
}
