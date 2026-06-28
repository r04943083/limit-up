// Tiny inline SVG sparkline for dense watchlist rows. Color follows net direction
// (CN/Futu convention: up = red, down = green).
export default function Sparkline({
  data,
  width = 56,
  height = 18,
}: {
  data: number[];
  width?: number;
  height?: number;
}) {
  if (!data || data.length < 2) {
    return <svg width={width} height={height} />;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const stepX = width / (data.length - 1);
  const pts = data
    .map((v, i) => `${(i * stepX).toFixed(1)},${(height - ((v - min) / span) * height).toFixed(1)}`)
    .join(" ");
  const up = data[data.length - 1] >= data[0];
  const color = up ? "#F6465D" : "#2EBD85";
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1} />
    </svg>
  );
}
