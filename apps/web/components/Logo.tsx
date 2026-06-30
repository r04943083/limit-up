// limit-up brand mark — "Breakout": an upward arrow punching through the 涨停板 (limit)
// cap line. It encodes the product name literally (price breaking its upper limit) without
// using the letters "LU". Indigo→cyan gradient is intentionally independent of the in-app
// "red=up / green=down" data palette. Keep app/icon.svg in sync with this markup.
export default function Logo({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none"
      className={className} aria-label="limit-up" role="img">
      <defs>
        <linearGradient id="luBreak" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#6366F1" />
          <stop offset="1" stopColor="#22D3EE" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="#0E1116" />
      {/* 涨停板 / 压力线 */}
      <line x1="7" y1="9" x2="25" y2="9" stroke="#2A3542" strokeWidth="2.4" strokeLinecap="round" />
      {/* 上破箭头 */}
      <path d="M16 25 V11 M16 11 L11 16 M16 11 L21 16" stroke="url(#luBreak)" strokeWidth="3.2"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
