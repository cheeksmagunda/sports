// Time-to-next-freeze helper. cron-job2 first fires at 21:00 UTC (4 PM
// CDT / 5 PM EDT) — that is when today's lineup actually lands in the
// `frozen_lineups` table. cron-job1 (the data fetch) fires earlier at
// 13:00 UTC but produces nothing user-visible; pointing the countdown
// at 21:00 UTC matches what the operator is actually waiting for.

const FREEZE_HOUR_UTC = 21;

export function nextFreezeUTC(now: Date = new Date()): Date {
  const next = new Date(now);
  next.setUTCHours(FREEZE_HOUR_UTC, 0, 0, 0);
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
