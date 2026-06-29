"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, LineStyle, type IChartApi } from "lightweight-charts";
import type { IntradayPoint } from "@/lib/api";

/**
 * 分时图 — a single intraday price line vs the session's open (Futu-style). Red = up,
 * green = down (A-share convention), colored by where price sits relative to the baseline.
 */
export default function IntradayChart({ data, baseline }: { data: IntradayPoint[]; baseline?: number | null }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || data.length === 0) return;
    const base = baseline ?? data[0].price;
    const up = data[data.length - 1].price >= base;
    const color = up ? "#F6465D" : "#2EBD85";

    const chart: IChartApi = createChart(ref.current, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8B98A5" },
      grid: { vertLines: { color: "#1B2127" }, horzLines: { color: "#1B2127" } },
      rightPriceScale: { borderColor: "#22272E" },
      timeScale: { borderColor: "#22272E", timeVisible: true, secondsVisible: false },
      height: 420,
      autoSize: true,
      crosshair: { mode: 0 },
    });
    const series = chart.addAreaSeries({
      lineColor: color,
      topColor: up ? "rgba(246,70,93,0.22)" : "rgba(46,189,133,0.22)",
      bottomColor: "rgba(0,0,0,0)",
      lineWidth: 2,
      priceLineVisible: false,
    });
    // lightweight-charts wants unix-seconds for intraday points.
    series.setData(
      data.map((p) => ({ time: (Date.parse(p.t) / 1000) as never, value: p.price })),
    );
    if (base) {
      series.createPriceLine({
        price: base, color: "#8B98A5", lineWidth: 1, lineStyle: LineStyle.Dashed,
        axisLabelVisible: true, title: "昨收/开",
      });
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [data, baseline]);

  if (data.length === 0) {
    return <div className="h-[420px] grid place-items-center text-ink-faint text-sm">暂无分时数据(非交易时段或数据源未提供)。</div>;
  }
  return <div ref={ref} className="w-full" style={{ height: 420 }} />;
}
