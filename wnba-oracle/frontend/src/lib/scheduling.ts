// Time-to-next-fire helper. Cron-job1 fires at 13:00 UTC daily.

const FIRE_HOUR_UTC = 13;

export function nextFireUTC(now: Date = new Date()): Date {
  const next = new Date(now);
  next.setUTCHours(FIRE_HOUR_UTC, 0, 0, 0);
  if (next.getTime() <= now.getTime()) {
    next.setUTCDate(next.getUTCDate() + 1);
  }
  return next;
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
