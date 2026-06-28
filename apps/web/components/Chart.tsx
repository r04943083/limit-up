"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  type IChartApi,
  LineStyle,
} from "lightweight-charts";
import type { OhlcvBar, Technical } from "@/lib/api";

// CN/Futu convention: red = up, green = down.
const C = {
  bg: "#0B0E11",
  text: "#8B98A5",
  grid: "#1B232B",
  up: "#F6465D",
  down: "#2EBD85",
  volUp: "#3d1f24",
  volDown: "#16352a",
  sma20: "#21D0C3",
  sma50: "#E0A33E",
  sma200: "#9B7BE6",
  bb: "#3A4754",
  rsi: "#21D0C3",
  macd: "#21D0C3",
  macdSignal: "#E0A33E",
  kdjK: "#21D0C3",
  kdjD: "#E0A33E",
  kdjJ: "#E06AAA",
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

type Lower = "MACD" | "RSI" | "KDJ";

function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-0.5 rounded text-[11px] transition-colors ${
        on ? "bg-accent/15 text-accent" : "text-ink-dim hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

export default function Chart({ ohlcv, technical }: { ohlcv: OhlcvBar[]; technical: Technical }) {
  const priceRef = useRef<HTMLDivElement>(null);
  const lowerRef = useRef<HTMLDivElement>(null);
  const [showMA, setShowMA] = useState(true);
  const [showBoll, setShowBoll] = useState(false);
  const [lower, setLower] = useState<Lower>("MACD");

  useEffect(() => {
    if (!priceRef.current || !lowerRef.current) return;

    const common = {
      layout: { background: { type: ColorType.Solid, color: C.bg }, textColor: C.text, fontSize: 11 },
      grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
      rightPriceScale: { borderColor: C.grid },
      timeScale: { borderColor: C.grid },
      crosshair: { mode: 0 as const },
    };

    const price: IChartApi = createChart(priceRef.current, { ...common, height: 400 });
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
        color: b.close >= b.open ? C.volUp : C.volDown,
      })),
    );
    price.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

    const addLine = (vals: (number | null)[], color: string, width: 1 | 2 = 1) => {
      const s = price.addLineSeries({ color, lineWidth: width, priceLineVisible: false, lastValueVisible: false });
      s.setData(overlay(technical.dates, vals));
    };
    if (showMA) {
      addLine(technical.sma20, C.sma20);
      addLine(technical.sma50, C.sma50);
      addLine(technical.sma200, C.sma200);
    }
    if (showBoll) {
      addLine(technical.bb_upper, C.bb);
      addLine(technical.bb_lower, C.bb);
    }

    // Lower pane: MACD / RSI / KDJ
    const low: IChartApi = createChart(lowerRef.current, { ...common, height: 140 });
    if (lower === "RSI") {
      const rsiSeries = low.addLineSeries({ color: C.rsi, lineWidth: 1, priceLineVisible: false });
      rsiSeries.setData(overlay(technical.dates, technical.rsi14));
      for (const lvl of [70, 30]) {
        rsiSeries.createPriceLine({ price: lvl, color: C.grid, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "" });
      }
      rsiSeries.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
    } else if (lower === "KDJ") {
      const k = low.addLineSeries({ color: C.kdjK, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      k.setData(overlay(technical.dates, technical.kdj_k));
      const d = low.addLineSeries({ color: C.kdjD, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      d.setData(overlay(technical.dates, technical.kdj_d));
      const j = low.addLineSeries({ color: C.kdjJ, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      j.setData(overlay(technical.dates, technical.kdj_j));
    } else {
      const hist = low.addHistogramSeries({ priceFormat: { type: "price" } });
      hist.setData(
        overlay(technical.dates, technical.macd_hist).map((p) => ({
          time: p.time, value: p.value, color: p.value >= 0 ? C.up : C.down,
        })),
      );
      const macdLine = low.addLineSeries({ color: C.macd, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      macdLine.setData(overlay(technical.dates, technical.macd));
      const sigLine = low.addLineSeries({ color: C.macdSignal, lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      sigLine.setData(overlay(technical.dates, technical.macd_signal));
    }

    const sync = (src: IChartApi, dst: IChartApi) =>
      src.timeScale().subscribeVisibleLogicalRangeChange((r) => r && dst.timeScale().setVisibleLogicalRange(r));
    sync(price, low);
    sync(low, price);
    price.timeScale().fitContent();
    low.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (priceRef.current) price.applyOptions({ width: priceRef.current.clientWidth });
      if (lowerRef.current) low.applyOptions({ width: lowerRef.current.clientWidth });
    });
    ro.observe(priceRef.current);
    ro.observe(lowerRef.current);

    return () => {
      ro.disconnect();
      price.remove();
      low.remove();
    };
  }, [ohlcv, technical, showMA, showBoll, lower]);

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 px-1 pb-1 text-[11px]">
        <Toggle on={showMA} onClick={() => setShowMA((v) => !v)}>MA</Toggle>
        <Toggle on={showBoll} onClick={() => setShowBoll((v) => !v)}>BOLL</Toggle>
        <span className="w-px h-3 bg-line mx-1" />
        <Toggle on={lower === "MACD"} onClick={() => setLower("MACD")}>MACD</Toggle>
        <Toggle on={lower === "RSI"} onClick={() => setLower("RSI")}>RSI</Toggle>
        <Toggle on={lower === "KDJ"} onClick={() => setLower("KDJ")}>KDJ</Toggle>
        {lower === "KDJ" && (
          <span className="flex items-center gap-2 text-ink-faint">
            <span style={{ color: C.kdjK }}>K</span>
            <span style={{ color: C.kdjD }}>D</span>
            <span style={{ color: C.kdjJ }}>J</span>
          </span>
        )}
        {showMA && (
          <span className="ml-auto flex items-center gap-3 text-ink-faint">
            <span className="text-accent">MA20</span>
            <span style={{ color: C.sma50 }}>MA50</span>
            <span style={{ color: C.sma200 }}>MA200</span>
          </span>
        )}
      </div>
      <div ref={priceRef} className="w-full" />
      <div ref={lowerRef} className="w-full" />
    </div>
  );
}
