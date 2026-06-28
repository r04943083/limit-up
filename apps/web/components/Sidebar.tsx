const NAV: { label: string; key: string; soon?: boolean }[] = [
  { label: "Dashboard", key: "dashboard" },
  { label: "Watchlist", key: "watchlist", soon: true },
  { label: "Research", key: "research", soon: true },
  { label: "Recommendations", key: "recommendations", soon: true },
  { label: "Portfolio", key: "portfolio", soon: true },
  { label: "Paper Trading", key: "paper", soon: true },
  { label: "Journal", key: "journal", soon: true },
  { label: "AI Coach", key: "coach", soon: true },
];

export default function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r border-line bg-panel/40 flex flex-col">
      <div className="h-14 flex items-center gap-2 px-4 border-b border-line">
        <span className="grid place-items-center w-7 h-7 rounded-lg bg-accent/15 text-accent font-bold">
          LU
        </span>
        <span className="font-semibold tracking-tight">limit-up</span>
      </div>
      <nav className="flex-1 p-2 space-y-0.5">
        {NAV.map((n, i) => (
          <button
            key={n.key}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center justify-between transition-colors ${
              i === 0 ? "bg-panel-2 text-ink" : "text-ink-dim hover:bg-panel-2/60 hover:text-ink"
            }`}
          >
            <span>{n.label}</span>
            {n.soon && (
              <span className="text-[10px] uppercase tracking-wide text-ink-faint">soon</span>
            )}
          </button>
        ))}
      </nav>
      <div className="p-3 text-[11px] text-ink-faint border-t border-line">
        Not financial advice. AI output is opinion.
      </div>
    </aside>
  );
}
