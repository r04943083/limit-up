"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getWatchlists, getWatchlistQuotes, addItem, removeItem, importCsv, importEbk,
  createWatchlist, syncAll, renameWatchlist, deleteWatchlist, reorderWatchlists,
  reorderItems, moveItem, updateItem, exportEbk,
  type Watchlist, type QuoteRow, type EbkImportResult,
} from "@/lib/api";
import { num, signedPct, dirClass } from "@/lib/format";

function reorderBy<T>(arr: T[], idOf: (x: T) => number, fromId: number, toId: number): T[] {
  if (fromId === toId) return arr;
  const from = arr.findIndex((x) => idOf(x) === fromId);
  const to = arr.findIndex((x) => idOf(x) === toId);
  if (from < 0 || to < 0) return arr;
  const next = [...arr];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}
const parseTags = (t: string | null | undefined): string[] =>
  (t ?? "").split(",").map((s) => s.trim()).filter(Boolean);

function downloadFile(filename: string, content: string) {
  const blob = new Blob(["﻿", content.replace(/^﻿/, "")], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function ManageWatchlistModal({
  open, onClose, onChanged, initialGid,
}: {
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
  initialGid?: number | null;
}) {
  const [groups, setGroups] = useState<Watchlist[]>([]);
  const [gid, setGid] = useState<number | null>(initialGid ?? null);
  const [rows, setRows] = useState<QuoteRow[]>([]);
  const [symbol, setSymbol] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [ebkResult, setEbkResult] = useState<EbkImportResult | null>(null);
  const [renaming, setRenaming] = useState<number | null>(null);
  const [renameText, setRenameText] = useState("");
  const [tagEditFor, setTagEditFor] = useState<number | null>(null);
  const dragGroup = useRef<number | null>(null);
  const dragItem = useRef<number | null>(null);
  const [dropGroup, setDropGroup] = useState<number | null>(null);
  const ebkRef = useRef<HTMLInputElement>(null);
  const csvRef = useRef<HTMLInputElement>(null);

  const group = groups.find((g) => g.id === gid) ?? null;
  const changed = useCallback(() => onChanged?.(), [onChanged]);

  const loadGroups = useCallback(async () => {
    const gs = await getWatchlists();
    setGroups(gs);
    setGid((cur) => (cur && gs.some((g) => g.id === cur) ? cur : gs[0]?.id ?? null));
  }, []);
  const loadRows = useCallback(() => {
    if (gid == null) { setRows([]); return; }
    getWatchlistQuotes(gid).then(setRows).catch(() => setRows([]));
  }, [gid]);

  useEffect(() => { if (open) loadGroups().catch(() => {}); }, [open, loadGroups]);
  useEffect(() => { if (open) loadRows(); }, [open, loadRows]);

  if (!open) return null;

  const newGroup = async () => {
    const name = window.prompt("新建分组名称");
    if (!name?.trim()) return;
    const wl = await createWatchlist(name.trim());
    await loadGroups(); setGid(wl.id); changed();
  };
  const startRename = (g: Watchlist) => { setRenaming(g.id); setRenameText(g.name); };
  const commitRename = async () => {
    if (renaming == null) return;
    const name = renameText.trim(); setRenaming(null);
    if (name) { await renameWatchlist(renaming, name); await loadGroups(); changed(); }
  };
  const removeGroup = async (g: Watchlist) => {
    if (!window.confirm(`删除分组「${g.name}」?组内 ${g.items.length} 个标的也会移出。`)) return;
    await deleteWatchlist(g.id); await loadGroups(); changed();
  };
  const onGroupDrop = async (targetId: number) => {
    const fromId = dragGroup.current; dragGroup.current = null; setDropGroup(null);
    if (fromId == null || fromId === targetId) return;
    const next = reorderBy(groups, (g) => g.id, fromId, targetId);
    setGroups(next); await reorderWatchlists(next.map((g) => g.id)); changed();
  };
  const onItemDropOnGroup = async (targetGid: number) => {
    const itemId = dragItem.current; dragItem.current = null; setDropGroup(null);
    if (itemId == null || targetGid === gid) return;
    await moveItem(itemId, targetGid); loadRows(); await loadGroups(); changed();
  };
  const onItemRowDrop = async (targetItemId: number) => {
    const fromId = dragItem.current; dragItem.current = null;
    if (fromId == null || gid == null || fromId === targetItemId) return;
    const next = reorderBy(rows, (r) => r.item_id, fromId, targetItemId);
    setRows(next); await reorderItems(gid, next.map((r) => r.item_id)); changed();
  };
  const add = async () => {
    const s = symbol.trim().toUpperCase(); if (!s || gid == null) return;
    setBusy(true);
    try { await addItem(gid, s); setSymbol(""); loadRows(); await loadGroups(); changed(); }
    catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  };
  const remove = async (id: number) => { await removeItem(id); loadRows(); await loadGroups(); changed(); };
  const onCsv = async (file: File) => {
    if (gid == null) return; setBusy(true);
    try {
      const { added } = await importCsv(gid, await file.text());
      setMsg(`已从 CSV 导入 ${added} 个标的到「${group?.name}」。`); loadRows(); await loadGroups(); changed();
    } catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  };
  const onEbk = async (files: FileList) => {
    setBusy(true); setMsg("正在解析富途 .ebk(每个文件 = 一个分组)…");
    try {
      const payload = await Promise.all(Array.from(files).map(async (f) => ({ name: f.name, content: await f.text() })));
      const res = await importEbk(payload); setEbkResult(res); setMsg(null); await loadGroups(); loadRows(); changed();
    } catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  };
  const exportOne = async (wid: number) => {
    const e = await exportEbk(wid); downloadFile(e.filename, e.content);
  };
  const exportAll = async () => {
    for (const g of groups) { const e = await exportEbk(g.id); downloadFile(e.filename, e.content); }
    setMsg(`已导出 ${groups.length} 个分组的 .ebk(可重新导入富途)。`);
  };
  const updateAll = async () => {
    setBusy(true); setMsg("正在更新所有标的数据到本地数据库…(并发抓取,稍候)");
    try {
      const r = await syncAll();
      setMsg(`已更新 ${r.synced}/${r.requested} 个标的${r.failed.length ? `,失败 ${r.failed.length} 个` : ""}。`);
      loadRows(); changed();
    } catch (e) { setMsg(String(e)); } finally { setBusy(false); }
  };
  const saveTags = async (itemId: number, tags: string[]) => {
    await updateItem(itemId, { tags: tags.join(",") }); setTagEditFor(null); loadRows(); changed();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6" onClick={onClose}>
      <div className="bg-base border border-line rounded-xl w-full max-w-5xl h-[80vh] flex flex-col overflow-hidden shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 h-12 border-b border-line">
          <h2 className="text-sm font-semibold">管理自选 · 分组 / 标的 / 标签 · 汇入汇出</h2>
          <div className="flex items-center gap-2">
            <button onClick={() => ebkRef.current?.click()} disabled={busy} className="rounded-lg border border-line text-xs px-3 py-1.5 text-ink-dim hover:text-ink hover:border-accent/40 disabled:opacity-50">导入富途 .ebk</button>
            <button onClick={() => csvRef.current?.click()} disabled={busy} className="rounded-lg border border-line text-xs px-3 py-1.5 text-ink-dim hover:text-ink hover:border-accent/40 disabled:opacity-50">导入 CSV</button>
            <button onClick={exportAll} disabled={busy || groups.length === 0} className="rounded-lg border border-line text-xs px-3 py-1.5 text-ink-dim hover:text-ink hover:border-accent/40 disabled:opacity-50">导出全部 .ebk</button>
            <button onClick={updateAll} disabled={busy} className="rounded-lg bg-accent/15 text-accent text-xs font-medium px-3 py-1.5 hover:bg-accent/25 disabled:opacity-50">{busy ? "更新中…" : "↻ 全部更新"}</button>
            <button onClick={onClose} className="text-ink-faint hover:text-ink text-lg leading-none ml-1">✕</button>
          </div>
          <input ref={ebkRef} type="file" accept=".ebk,text/plain" multiple className="hidden" onChange={(e) => e.target.files?.length && onEbk(e.target.files)} />
          <input ref={csvRef} type="file" accept=".csv,text/csv,text/plain" className="hidden" onChange={(e) => e.target.files?.[0] && onCsv(e.target.files[0])} />
        </div>

        <div className="flex-1 flex min-h-0">
          {/* Groups column */}
          <div className="w-[220px] shrink-0 border-r border-line flex flex-col">
            <div className="flex items-center justify-between px-3 h-9 border-b border-line">
              <span className="text-[10px] uppercase tracking-wide text-ink-faint">分组 · 拖拽排序</span>
              <button onClick={newGroup} className="text-accent text-lg leading-none hover:opacity-80" title="新建分组">+</button>
            </div>
            <div className="flex-1 overflow-y-auto py-1">
              {groups.map((g) => {
                const active = g.id === gid;
                return (
                  <div key={g.id}
                    draggable={renaming !== g.id}
                    onDragStart={() => { dragGroup.current = g.id; }}
                    onDragOver={(e) => { e.preventDefault(); if (dragItem.current != null || dragGroup.current != null) setDropGroup(g.id); }}
                    onDragLeave={() => setDropGroup((d) => (d === g.id ? null : d))}
                    onDrop={(e) => { e.preventDefault(); if (dragItem.current != null) onItemDropOnGroup(g.id); else onGroupDrop(g.id); }}
                    onClick={() => setGid(g.id)}
                    className={`group mx-1.5 my-0.5 px-2 py-1.5 rounded-lg flex items-center gap-1.5 cursor-pointer transition-colors ${active ? "bg-panel-2" : "hover:bg-panel-2/50"} ${dropGroup === g.id ? "ring-1 ring-accent/60" : ""}`}>
                    <span className="text-ink-faint/50 cursor-grab select-none text-xs">⠿</span>
                    {renaming === g.id ? (
                      <input autoFocus value={renameText} onChange={(e) => setRenameText(e.target.value)} onBlur={commitRename}
                        onKeyDown={(e) => { if (e.key === "Enter") commitRename(); if (e.key === "Escape") setRenaming(null); }}
                        onClick={(e) => e.stopPropagation()}
                        className="flex-1 min-w-0 bg-base border border-accent/50 rounded px-1.5 py-0.5 text-sm focus:outline-none" />
                    ) : (
                      <>
                        <span className={`flex-1 min-w-0 truncate text-sm ${active ? "text-ink" : "text-ink-dim"}`} onDoubleClick={() => startRename(g)}>{g.name}</span>
                        <span className="text-[10px] tnum text-ink-faint">{g.items.length}</span>
                        <span className="hidden group-hover:flex items-center gap-1">
                          <button onClick={(e) => { e.stopPropagation(); exportOne(g.id); }} className="text-ink-faint hover:text-accent text-xs" title="导出该分组 .ebk">⤓</button>
                          <button onClick={(e) => { e.stopPropagation(); startRename(g); }} className="text-ink-faint hover:text-ink text-xs" title="重命名">✎</button>
                          <button onClick={(e) => { e.stopPropagation(); removeGroup(g); }} className="text-ink-faint hover:text-down text-xs" title="删除分组">✕</button>
                        </span>
                      </>
                    )}
                  </div>
                );
              })}
              {groups.length === 0 && <p className="text-xs text-ink-faint p-3">还没有分组。点 + 新建,或导入富途 .ebk。</p>}
            </div>
          </div>

          {/* Items column */}
          <div className="flex-1 min-w-0 flex flex-col">
            <div className="flex items-center gap-2 px-4 h-11 border-b border-line">
              <input value={symbol} onChange={(e) => setSymbol(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()}
                placeholder="加入标的 · NVDA · 0700.HK · 600519.SS"
                className="flex-1 max-w-xs bg-base border border-line rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-accent/60" />
              <button onClick={add} disabled={busy || gid == null} className="rounded-lg bg-accent/15 text-accent text-sm font-medium px-4 py-1.5 hover:bg-accent/25 disabled:opacity-50">加入</button>
              <span className="text-xs text-ink-faint ml-auto">{rows.length} 标的 · 拖 ⠿ 排序 / 拖到左侧分组移动</span>
            </div>
            {msg && <p className="text-xs text-ink-dim px-4 pt-2">{msg}</p>}
            {ebkResult && (
              <div className="mx-4 mt-2 rounded-lg border border-line bg-panel p-3 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-ink">导入完成 · 共加入 {ebkResult.total_added} · 建立/更新 {ebkResult.groups.length} 个分组</span>
                  <button onClick={() => setEbkResult(null)} className="text-ink-faint hover:text-ink">关闭</button>
                </div>
                {ebkResult.groups.map((g) => (
                  <div key={g.watchlist_id} className="text-ink-dim border-t border-line/60 pt-1">
                    <span className="text-accent">{g.group}</span> · 加入 {g.added}/{g.parsed} · 跳过 {g.skipped.length}
                  </div>
                ))}
              </div>
            )}
            <div className="flex-1 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-base">
                  <tr className="text-[10px] uppercase tracking-wide text-ink-faint border-b border-line">
                    <th className="w-6 px-2"></th>
                    <th className="text-left font-medium py-2 px-2">名称 / 代码</th>
                    <th className="text-right font-medium px-3">最新价</th>
                    <th className="text-right font-medium px-3">涨跌幅</th>
                    <th className="text-left font-medium px-3">标签</th>
                    <th className="px-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const tags = parseTags(r.tags);
                    return (
                      <tr key={r.item_id} draggable onDragStart={() => { dragItem.current = r.item_id; }}
                        onDragOver={(e) => { if (dragItem.current != null) e.preventDefault(); }}
                        onDrop={(e) => { e.preventDefault(); onItemRowDrop(r.item_id); }}
                        className="border-b border-line/50 hover:bg-panel-2/40">
                        <td className="px-2 text-ink-faint/50 cursor-grab select-none text-center">⠿</td>
                        <td className="py-1.5 px-2"><div className="text-ink">{r.name ?? r.symbol}</div><div className="text-[11px] text-ink-faint">{r.symbol}</div></td>
                        <td className="text-right tnum px-3 text-ink">{num(r.price)}</td>
                        <td className={`text-right tnum px-3 ${dirClass(r.change_pct)}`}>{signedPct(r.change_pct)}</td>
                        <td className="px-3 relative">
                          <div className="flex items-center gap-1 flex-wrap">
                            {tags.map((t) => <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-panel-2 text-ink-dim">{t}</span>)}
                            <button onClick={() => setTagEditFor(tagEditFor === r.item_id ? null : r.item_id)} className="text-[10px] text-ink-faint hover:text-accent border border-dashed border-line rounded px-1 py-0.5">{tags.length ? "✎" : "+ 标签"}</button>
                          </div>
                          {tagEditFor === r.item_id && <TagEditor initial={tags} onCancel={() => setTagEditFor(null)} onSave={(t) => saveTags(r.item_id, t)} />}
                        </td>
                        <td className="text-right px-3 whitespace-nowrap">
                          <MoveMenu groups={groups} currentGid={gid} onMove={async (target) => { await moveItem(r.item_id, target); loadRows(); await loadGroups(); changed(); }} />
                          <button onClick={() => remove(r.item_id)} className="text-ink-faint hover:text-down text-xs ml-2">移除</button>
                        </td>
                      </tr>
                    );
                  })}
                  {rows.length === 0 && <tr><td colSpan={6} className="text-center text-ink-faint text-sm py-8">此分组暂无标的。</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TagEditor({ initial, onSave, onCancel }: { initial: string[]; onSave: (t: string[]) => void; onCancel: () => void }) {
  const [tags, setTags] = useState<string[]>(initial);
  const [input, setInput] = useState("");
  const dragIdx = useRef<number | null>(null);
  const addTag = () => { const t = input.trim(); if (t && !tags.includes(t)) setTags([...tags, t]); setInput(""); };
  const reorder = (to: number) => {
    const from = dragIdx.current; dragIdx.current = null;
    if (from == null || from === to) return;
    const next = [...tags]; const [m] = next.splice(from, 1); next.splice(to, 0, m); setTags(next);
  };
  return (
    <div className="absolute z-20 mt-1 left-3 w-64 rounded-lg border border-line bg-panel shadow-xl p-3 space-y-2">
      <div className="text-[11px] text-ink-faint">标签 · 拖拽排序</div>
      <div className="flex flex-wrap gap-1 min-h-[24px]">
        {tags.map((t, i) => (
          <span key={t} draggable onDragStart={() => { dragIdx.current = i; }} onDragOver={(e) => e.preventDefault()} onDrop={() => reorder(i)}
            className="text-[11px] px-1.5 py-0.5 rounded bg-panel-2 text-ink-dim flex items-center gap-1 cursor-grab">
            {t}<button onClick={() => setTags(tags.filter((x) => x !== t))} className="text-ink-faint hover:text-down">×</button>
          </span>
        ))}
        {tags.length === 0 && <span className="text-[11px] text-ink-faint">暂无标签</span>}
      </div>
      <div className="flex gap-1">
        <input autoFocus value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") addTag(); }}
          placeholder="新增标签…" className="flex-1 bg-base border border-line rounded px-2 py-1 text-xs focus:outline-none focus:border-accent/60" />
        <button onClick={addTag} className="text-xs px-2 rounded bg-panel-2 text-ink-dim hover:text-ink">加</button>
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <button onClick={onCancel} className="text-xs text-ink-faint hover:text-ink">取消</button>
        <button onClick={() => onSave(tags)} className="text-xs text-accent hover:opacity-80">保存</button>
      </div>
    </div>
  );
}

function MoveMenu({ groups, currentGid, onMove }: { groups: Watchlist[]; currentGid: number | null; onMove: (target: number) => void }) {
  const [open, setOpen] = useState(false);
  const others = groups.filter((g) => g.id !== currentGid);
  if (others.length === 0) return null;
  return (
    <span className="relative inline-block">
      <button onClick={() => setOpen((o) => !o)} className="text-ink-faint hover:text-accent text-xs" title="移动到其他分组">移动▾</button>
      {open && (
        <span className="absolute right-0 z-20 mt-1 w-36 rounded-lg border border-line bg-panel shadow-xl py-1 flex flex-col text-left">
          {others.map((g) => (
            <button key={g.id} onClick={() => { setOpen(false); onMove(g.id); }} className="text-xs text-ink-dim hover:bg-panel-2 hover:text-ink px-3 py-1.5 text-left truncate">→ {g.name}</button>
          ))}
        </span>
      )}
    </span>
  );
}
