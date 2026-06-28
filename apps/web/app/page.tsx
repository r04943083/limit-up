import Panel from "@/components/Panel";

export default function DashboardPage() {
  return (
    <div className="space-y-5">
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Daily Briefing</h1>
          <p className="text-sm text-ink-dim">Your AI investment OS · US / HK / A-share</p>
        </div>
        <span className="text-xs text-ink-faint tnum">Phase 0 · scaffolding</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Panel title="Daily Briefing" hint="AI" className="lg:col-span-2">
          <p className="text-sm text-ink-dim">
            Each morning, LU will assemble market highlights, your holdings changes, watchlist
            updates, new recommendations and risk alerts here — written by the AI brain.
          </p>
        </Panel>
        <Panel title="Markets" hint="live">
          <ul className="text-sm space-y-2">
            {[
              ["US", "—"],
              ["HK", "—"],
              ["A-share", "—"],
            ].map(([m, v]) => (
              <li key={m} className="flex items-center justify-between">
                <span className="text-ink-dim">{m}</span>
                <span className="tnum text-ink-faint">{v}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Panel title="Watchlist" hint="soon" />
        <Panel title="Opportunity Feed" hint="soon" />
        <Panel title="Portfolio" hint="soon" />
      </div>
    </div>
  );
}
