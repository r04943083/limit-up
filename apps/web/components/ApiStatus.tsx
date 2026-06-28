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
  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        className={`w-2 h-2 rounded-full ${ok ? "bg-up" : "bg-down"} ${ok ? "" : "animate-pulse"}`}
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
