// Horizontal P10 / P50 / P90 band over a model-known domain. The picker
// only emits minutes quantiles per player (not score quantiles), so the
// caller passes the [min, max] envelope appropriate for the quantity being
// shown.

interface Props {
  p10: number;
  p50: number;
  p90: number;
  min: number;
  max: number;
  unit?: string;
  ariaLabel?: string;
}

export function IntervalBar({
  p10,
  p50,
  p90,
  min,
  max,
  unit = "",
  ariaLabel,
}: Props) {
  const span = Math.max(max - min, 1);
  const clamp = (v: number) => Math.max(0, Math.min(1, (v - min) / span)) * 100;
  const left = clamp(p10);
  const right = clamp(p90);
  const width = Math.max(2, right - left);
  const median = clamp(p50);

  const label =
    ariaLabel ??
    `Quantile interval. P10 ${p10.toFixed(1)}${unit}, median ${p50.toFixed(1)}${unit}, P90 ${p90.toFixed(1)}${unit}.`;

  return (
    <div className="interval-bar" role="img" aria-label={label}>
      <div
        className="interval-bar__band"
        style={{ left: `${left}%`, width: `${width}%` }}
      />
      <div className="interval-bar__median" style={{ left: `${median}%` }} />
      <div className="interval-bar__labels" aria-hidden="true">
        <span>P10 {p10.toFixed(0)}{unit}</span>
        <span>P50 {p50.toFixed(0)}{unit}</span>
        <span>P90 {p90.toFixed(0)}{unit}</span>
      </div>
    </div>
  );
}
