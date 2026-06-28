// LU brand mark: three ascending bars (涨停 / limit-up), climax in brand teal.
// Reused as the IconRail logo and (as app/icon.svg) the browser favicon.
export default function Logo({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-label="LU" role="img">
      <rect width="32" height="32" rx="7" fill="#11161D" />
      <rect x="6.5" y="19" width="4" height="6.5" rx="1.3" fill="#F6465D" opacity="0.55" />
      <rect x="14" y="14" width="4" height="11.5" rx="1.3" fill="#F6465D" opacity="0.8" />
      <rect x="21.5" y="7" width="4" height="18.5" rx="1.3" fill="#21D0C3" />
    </svg>
  );
}
