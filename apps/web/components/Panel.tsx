import type { ReactNode } from "react";

export default function Panel({
  title,
  hint,
  children,
  className = "",
}: {
  title: string;
  hint?: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-line bg-panel ${className}`}>
      <div className="flex items-center justify-between px-4 h-11 border-b border-line">
        <h2 className="text-sm font-medium text-ink">{title}</h2>
        {hint && <span className="text-[11px] uppercase tracking-wide text-ink-faint">{hint}</span>}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}
