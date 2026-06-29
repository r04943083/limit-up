// LU brand mark: the letters "LU" drawn as strokes, where the right arm of the "U"
// resolves into a red UP-ARROW (red = up in the CN/Futu convention) — the U's right
// side rises into an arrowhead = 上涨 / breakout. Reused as the IconRail logo and the
// browser favicon (keep app/icon.svg in sync with this markup).
export default function Logo({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none"
      className={className} aria-label="LU 上涨" role="img">
      <rect width="32" height="32" rx="7" fill="#11161D" />
      {/* L */}
      <path d="M6 9 V22 H12" stroke="#E6EDF3" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" />
      {/* U — left stem + rounded bottom; the right arm becomes the up-arrow below */}
      <path d="M15 9 V18 a4 4 0 0 0 8 0" stroke="#E6EDF3" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" />
      {/* right arm of U = red up-arrow: shaft rising + arrowhead */}
      <path d="M23 18 V7 M19.5 10.5 L23 7 L26.5 10.5" stroke="#F6465D" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
