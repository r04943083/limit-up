// LU brand mark: the letters "LU" where the right stem of the "U" is rendered as a
// red rising stroke topped with a red triangle (red = up in the CN/Futu convention) —
// 上涨 / 涨停. Reused as the IconRail logo and the browser favicon (keep
// app/icon.svg in sync with this markup).
export default function Logo({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none"
      className={className} aria-label="LU 上涨" role="img">
      <rect width="32" height="32" rx="7" fill="#11161D" />
      {/* L */}
      <path d="M7 9 V22 H13" stroke="#E6EDF3" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" />
      {/* U — left stem + rounded bottom; right stem becomes the red riser below */}
      <path d="M16 9 V18 a4 4 0 0 0 8 0" stroke="#E6EDF3" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" />
      {/* right stem of U = red riser + triangle top = 上涨 */}
      <line x1="24" y1="18" x2="24" y2="11" stroke="#F6465D" strokeWidth="3" strokeLinecap="round" />
      <path d="M21 11 L24 6.5 L27 11 Z" fill="#F6465D" />
    </svg>
  );
}
