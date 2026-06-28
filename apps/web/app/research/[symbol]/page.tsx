"use client";

import { useParams } from "next/navigation";
import WatchlistPane from "@/components/WatchlistPane";
import Terminal from "@/components/Terminal";

export default function ResearchPage() {
  const params = useParams<{ symbol: string }>();
  const sym = decodeURIComponent(params.symbol).toUpperCase();

  return (
    <>
      <WatchlistPane activeSymbol={sym} />
      <Terminal symbol={sym} />
    </>
  );
}
