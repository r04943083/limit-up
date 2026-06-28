import StatusBar from "./StatusBar";
import GlobalSearch from "./GlobalSearch";

/**
 * Right column = scrollable content + bottom StatusBar (Futu-style: no top bar).
 * Global symbol search lives in an overlay (⌘K / "/" / IconRail button), and
 * API status sits in the StatusBar — so the whole top row is gone and the
 * content area uses the full height.
 */
export default function RightColumn({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex-1 flex flex-col min-w-0">
      <main className="flex-1 min-h-0 overflow-hidden flex">{children}</main>
      <StatusBar />
      <GlobalSearch />
    </div>
  );
}
