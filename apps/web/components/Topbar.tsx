import ApiStatus from "./ApiStatus";

export default function Topbar() {
  return (
    <header className="h-14 shrink-0 border-b border-line flex items-center justify-between px-5">
      <div className="flex items-center gap-3">
        <input
          placeholder="Search ticker  ·  ⌘K"
          className="w-72 bg-panel border border-line rounded-lg px-3 py-1.5 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent/60"
        />
      </div>
      <ApiStatus />
    </header>
  );
}
