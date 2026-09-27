import { fetchPublic } from "./http";

/** Hosted NHL API origin. Absent until nhl-api is live; builds still bake an HTTPS origin. */
export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function localSlateDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export type HealthStatus = {
  status: string;
  service?: string;
  detail?: string;
};

/**
 * GET /health — expected NHL HTTP surface once the hosted API exists.
 * Until then, callers must treat network/404 failures as "API not hosted yet".
 */
export async function fetchHealth(): Promise<HealthStatus> {
  const r = await fetchPublic(`${API_URL}/health`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return (await r.json()) as HealthStatus;
}

/**
 * GET /slate/{date} — placeholder client for the future hosted slate payload.
 * TODO: wire once nhl-oracle hosted API serves slate timing / pool context.
 */
export async function fetchSlate(date: string): Promise<unknown | null> {
  const r = await fetchPublic(`${API_URL}/slate/${encodeURIComponent(date)}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

/**
 * GET /lineup/{date} — placeholder client for the future frozen five-card lineup.
 * TODO: wire once freeze artifacts are published by the hosted lifecycle.
 */
export async function fetchLineup(date: string): Promise<unknown | null> {
  const r = await fetchPublic(`${API_URL}/lineup/${encodeURIComponent(date)}`);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
