"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import ApiStatus from "./ApiStatus";

export default function Topbar() {
  const router = useRouter();
  const [q, setQ] = useState("");
  return (
    <header className="h-14 shrink-0 border-b border-line flex items-center justify-between px-5">
      <div className="flex items-center gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && q.trim()) {
              router.push(`/research/${encodeURIComponent(q.trim().toUpperCase())}`);
              setQ("");
            }
          }}
          placeholder="Search ticker  ·  e.g. NVDA, 0700.HK"
          className="w-72 bg-panel border border-line rounded-lg px-3 py-1.5 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent/60"
        />
      </div>
      <ApiStatus />
    </header>
  );
}
