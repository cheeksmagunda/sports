// Countdown helpers. The freeze is tip-relative (job2 freezes at
// first_tip - freeze_lead_minutes, D93/D104), so the target comes from the
// API's /slate/{date} endpoint (freeze_target_utc); there is no hardcoded
// wall-clock slot here. These helpers are pure so they can be unit-tested.

export function msUntil(targetIso: string | null, nowMs: number): number | null {
  if (!targetIso) return null;
  const t = Date.parse(targetIso);
  if (Number.isNaN(t)) return null;
  return t - nowMs;
}

export function formatHMS(ms: number): string {
  if (ms <= 0) return "00:00:00";
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}
