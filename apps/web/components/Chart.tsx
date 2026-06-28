"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  type IChartApi,
  LineStyle,
} from "lightweight-charts";
import type { OhlcvBar, Technical } from "@/lib/api";

const C = {
  bg: "#0B0E11",
  text: "#8B98A5",
  grid: "#1B232B",
  up: "#22C55E",
  down: "#EF4444",
  sma20: "#21D0C3",
  sma50: "#E0A33E",
  sma200: "#9B7BE6",
  bb: "#3A4754",
  rsi: "#21D0C3",
};

type LinePoint = { time: string; value: number };

function overlay(dates: string[], values: (number | null)[]): LinePoint[] {
  const out: LinePoint[] = [];
  for (let i = 0; i < dates.length; i++) {
    const v = values[i];
    if (v !== null && v !== undefined) out.push({ time: dates[i], value: v });
  }
  return out;
}

export default function Chart({ ohlcv, technical }: { ohlcv: OhlcvBar[]; technical: Technical }) {
  const priceRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!priceRef.current || !rsiRef.current) return;

    const common = {
      layout: { background: { type: ColorType.Solid, color: C.bg }, textColor: C.text, fontSize: 11 },
      grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
      rightPriceScale: { borderColor: C.grid },
      timeScale: { borderColor: C.grid },
      crosshair: { mode: 0 as const },
    };

    const price: IChartApi = createChart(priceRef.current, { ...common, height: 380 });
    const candle = price.addCandlestickSeries({
      upColor: C.up, downColor: C.down, borderVisible: false, wickUpColor: C.up, wickDownColor: C.down,
    });
    candle.setData(
      ohlcv.map((b) => ({ time: b.date, open: b.open, high: b.high, low: b.low, close: b.close })),
    );

    const vol = price.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" } });
    vol.setData(
      ohlcv.map((b) => ({
        time: b.date,
        value: b.volume ?? 0,
        color: b.close >= b.open ? "#1f3d2b" : "#3d1f22",
      })),
    );
    price.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    const addLine = (vals: (number | null)[], color: string, width: 1 | 2 = 1) => {
      const s = price.addLineSeries({ color, lineWidth: width, priceLineVisible: false, lastValueVisible: false });
      s.setData(overlay(technical.dates, vals));
    };
    addLine(technical.sma20, C.sma20);
    addLine(technical.sma50, C.sma50);
    addLine(technical.sma200, C.sma200);
    addLine(technical.bb_upper, C.bb);
    addLine(technical.bb_lower, C.bb);

    // RSI pane
    const rsi: IChartApi = createChart(rsiRef.current, { ...common, height: 120 });
    const rsiSeries = rsi.addLineSeries({ color: C.rsi, lineWidth: 1, priceLineVisible: false });
    rsiSeries.setData(overlay(technical.dates, technical.rsi14));
    for (const lvl of [70, 30]) {
      rsiSeries.createPriceLine({
        price: lvl, color: C.grid, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "",
      });
    }
    rsi.priceScale("right").applyOptions({ autoScale: false });
    rsiSeries.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });

    // Keep the two panes' time axes in sync.
    const sync = (src: IChartApi, dst: IChartApi) =>
      src.timeScale().subscribeVisibleLogicalRangeChange((r) => r && dst.timeScale().setVisibleLogicalRange(r));
    sync(price, rsi);
    sync(rsi, price);
    price.timeScale().fitContent();
    rsi.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (priceRef.current) price.applyOptions({ width: priceRef.current.clientWidth });
      if (rsiRef.current) rsi.applyOptions({ width: rsiRef.current.clientWidth });
    });
    ro.observe(priceRef.current);
    ro.observe(rsiRef.current);

    return () => {
      ro.disconnect();
      price.remove();
      rsi.remove();
    };
  }, [ohlcv, technical]);

  return (
    <div className="space-y-1">
      <div ref={priceRef} className="w-full" />
      <div className="flex items-center gap-3 px-1 text-[11px] text-ink-faint">
        <span className="text-accent">SMA20</span>
        <span style={{ color: C.sma50 }}>SMA50</span>
        <span style={{ color: C.sma200 }}>SMA200</span>
        <span style={{ color: C.bb }}>Bollinger</span>
        <span className="ml-auto">RSI(14)</span>
      </div>
      <div ref={rsiRef} className="w-full" />
    </div>
  );
}
