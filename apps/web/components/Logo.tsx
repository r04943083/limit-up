// LU brand mark: the letters "LU" + a red upward triangle (涨停 / limit-up = red up
// in the CN/Futu convention). Reused as the IconRail logo and the browser favicon (app/icon.svg).
export default function Logo({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-label="LU 涨停" role="img">
      <rect width="32" height="32" rx="7" fill="#11161D" />
      <text x="4" y="24" fontFamily="Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"
        fontSize="16" fontWeight="800" fill="#E6EDF3">LU</text>
      <path d="M25.5 4 L30 11.5 L21 11.5 Z" fill="#F6465D" />
    </svg>
  );
}
