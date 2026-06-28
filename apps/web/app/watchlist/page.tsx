"use client";

import { useEffect, useState } from "react";
import WatchlistPane from "@/components/WatchlistPane";
import StockPage from "@/components/StockPage";
import { getWatchlists, getWatchlistQuotes } from "@/lib/api";

// 自选 = the Futu-style terminal. The left pane is the watchlist; clicking a row
// swaps the center symbol in place (no navigation). Management lives behind the
// pane's 「管理」 button (groups / tags / 汇入汇出).
export default function WatchlistPage() {
  const [sel, setSel] = useState<string | null>(null);

  // Pick a sensible default symbol: first item of the first group.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const gs = await getWatchlists();
        const first = gs[0];
        if (!first) return;
        const rows = await getWatchlistQuotes(first.id);
        if (!cancelled && rows.length) setSel(rows[0].symbol);
      } catch { /* empty watchlist — Terminal shows an empty prompt */ }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <>
      <WatchlistPane activeSymbol={sel ?? undefined} onSelect={setSel} />
      <StockPage symbol={sel} />
    </>
  );
}
