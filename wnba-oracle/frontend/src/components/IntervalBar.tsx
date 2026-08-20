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
  // Slip row minutes column: shrinks the bar and drops the on-bar text
  // labels (no room for them at 120px wide) -- the full P10/P50/P90
  // values stay available via ariaLabel.
  compact?: boolean;
  // Live/final: minutes actually played, drawn as a filled portion
  // behind the predicted band -- "is this working" at a glance.
  actual?: number | null;
  actualColor?: string;
}

export function IntervalBar({
  p10,
  p50,
  p90,
  min,
  max,
  unit = "",
  ariaLabel,
  compact = false,
  actual = null,
  actualColor,
}: Props) {
  const span = Math.max(max - min, 1);
  const clamp = (v: number) => Math.max(0, Math.min(1, (v - min) / span)) * 100;
  const left = clamp(p10);
  const right = clamp(p90);
  const width = Math.max(2, right - left);
  const median = clamp(p50);
  const actualPct = typeof actual === "number" ? clamp(actual) : null;

  const label =
    ariaLabel ??
    `Quantile interval. P10 ${p10.toFixed(1)}${unit}, median ${p50.toFixed(1)}${unit}, P90 ${p90.toFixed(1)}${unit}.`;

  return (
    <div
      className={compact ? "interval-bar interval-bar--compact" : "interval-bar"}
      role="img"
      aria-label={label}
    >
      {actualPct !== null ? (
        <div
          className="interval-bar__actual"
          style={{
            width: `${actualPct}%`,
            ...(actualColor ? { background: actualColor } : {}),
          }}
        />
      ) : null}
      <div
        className="interval-bar__band"
        style={{ left: `${left}%`, width: `${width}%` }}
      />
      <div className="interval-bar__median" style={{ left: `${median}%` }} />
      {compact ? null : (
        <div className="interval-bar__labels" aria-hidden="true">
          <span>P10 {p10.toFixed(0)}{unit}</span>
          <span>P50 {p50.toFixed(0)}{unit}</span>
          <span>P90 {p90.toFixed(0)}{unit}</span>
        </div>
      )}
    </div>
  );
}
