"use client";

import { useParams } from "next/navigation";
import WatchlistPane from "@/components/WatchlistPane";
import DeepResearch from "@/components/DeepResearch";

export default function ResearchPage() {
  const params = useParams<{ symbol: string }>();
  const sym = decodeURIComponent(params.symbol).toUpperCase();

  return (
    <>
      <WatchlistPane activeSymbol={sym} />
      <DeepResearch symbol={sym} />
    </>
  );
}
