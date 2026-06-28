"use client";

import { useRef, useState } from "react";
import Topbar from "./Topbar";
import StatusBar from "./StatusBar";

/**
 * Right column = collapsible Topbar + scrollable main + StatusBar.
 *
 * Futu-style: the top bar slides away (and gives its row back to the content)
 * when you scroll the page down, and reappears when you scroll up. The "LU" mark
 * lives in the left IconRail, so it never moves. We listen with onScrollCapture so
 * any descendant scroll container (page body, watchlist pane) drives the toggle.
 */
export default function RightColumn({ children }: { children: React.ReactNode }) {
  const [hidden, setHidden] = useState(false);
  const last = useRef(0);

  const onScroll = (e: React.UIEvent<HTMLElement>) => {
    const el = e.target as HTMLElement;
    if (!el || typeof el.scrollTop !== "number") return;
    const y = el.scrollTop;
    if (Math.abs(y - last.current) < 8) return; // ignore jitter
    setHidden(y > last.current && y > 48); // hide when scrolling down past a bit
    last.current = y;
  };

  return (
    <div className="flex-1 flex flex-col min-w-0">
      <div className={`shrink-0 overflow-hidden transition-[height] duration-200 ease-out ${hidden ? "h-0" : "h-14"}`}>
        <Topbar />
      </div>
      <main onScrollCapture={onScroll} className="flex-1 min-h-0 overflow-hidden flex">{children}</main>
      <StatusBar />
    </div>
  );
}
