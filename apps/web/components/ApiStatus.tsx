"use client";

import { useEffect, useState } from "react";
import { getHealth, type Health } from "@/lib/api";

export default function ApiStatus() {
  const [health, setHealth] = useState<Health | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    const tick = () =>
      getHealth()
        .then((h) => alive && (setHealth(h), setErr(false)))
        .catch(() => alive && setErr(true));
    tick();
    const id = setInterval(tick, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const ok = !!health && !err;
  // A connectivity light is NOT market data — green=online / red=offline is the
  // universal convention. (Don't reuse the app's red=up / green=down data palette
  // here, or a healthy API shows a red dot.)
  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        className={`w-2 h-2 rounded-full ${ok ? "bg-[#2EBD85]" : "bg-[#F6465D] animate-pulse"}`}
      />
      <span className="text-ink-dim">
        {ok ? (
          <>
            API <span className="text-ink-faint">·</span> {health!.llm_provider}{" "}
            <span className="text-ink-faint">·</span> {health!.markets.join("/")}
          </>
        ) : (
          "API 离线 — 请运行 `make api`"
        )}
      </span>
    </div>
  );
}
