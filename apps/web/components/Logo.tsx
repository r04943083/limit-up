// LU brand mark: the letters "LU" stroked in a teal→cyan gradient on a dark rounded
// tile (gallery2 #2). The brand color is intentionally independent of the in-app
// "red=up / green=down" data palette. Keep app/icon.svg in sync with this markup.
export default function Logo({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none"
      className={className} aria-label="LU" role="img">
      <defs>
        <linearGradient id="luTeal" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2DD4BF" />
          <stop offset="1" stopColor="#22D3EE" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="#11161D" />
      {/* L */}
      <path d="M9 8 V21 H14" stroke="url(#luTeal)" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" />
      {/* U */}
      <path d="M17 8 V16 a4.3 4.3 0 0 0 8.6 0 V8" stroke="url(#luTeal)" strokeWidth="3"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
