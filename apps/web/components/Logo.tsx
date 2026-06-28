// LU brand mark: the letters "LU" drawn as strokes, where the right stem of the "U"
// is replaced by a red up-candlestick (body + wick) — red = up in the CN/Futu
// convention, the wick breaking through the top = 涨停 / breakout. Reused as the
// IconRail logo and the browser favicon (keep app/icon.svg in sync with this markup).
export default function Logo({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none"
      className={className} aria-label="LU 涨停" role="img">
      <rect width="32" height="32" rx="7" fill="#11161D" />
      {/* L */}
      <path d="M9 8 V23 H15" stroke="#E6EDF3" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" />
      {/* U — left stem + rounded bottom; the right arm is the candle below */}
      <path d="M18 8 V17 a4 4 0 0 0 8 0" stroke="#E6EDF3" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" />
      {/* right stem of U = red up-candle: wick then body */}
      <line x1="26" y1="4" x2="26" y2="20" stroke="#F6465D" strokeWidth="2" strokeLinecap="round" />
      <rect x="23.5" y="7" width="5" height="9" rx="1.5" fill="#F6465D" />
    </svg>
  );
}
