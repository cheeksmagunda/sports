// Circular avatar. Renders the ESPN CDN photo when an athlete id has
// resolved (Phase 3's playerMatch), falling back to team-tinted initials
// on a missing id or a failed/404 image load -- an <img> tag needs no
// CORS, and the fallback keeps the row intact either way. The team-color
// ring + glow come from the parent via --team-primary; size defaults to
// the original 100px card treatment but the Slip row passes 40 for its
// compact identity column.

import { useMemo, useState } from "react";

interface Props {
  name: string;
  size?: number;
  espnAthleteId?: string | null;
}

export function Headshot({ name, size = 100, espnAthleteId = null }: Props) {
  const initials = useMemo(
    () =>
      name
        .split(/\s+/)
        .map((p) => p[0] ?? "")
        .slice(0, 2)
        .join("")
        .toUpperCase(),
    [name],
  );

  // Tracks which id most recently failed, not a plain boolean, so a
  // later re-resolution to a *different* id (or a retry after the row's
  // data refreshes) gets a fresh attempt instead of staying stuck on the
  // fallback forever.
  const [failedId, setFailedId] = useState<string | null>(null);
  const showImg = Boolean(espnAthleteId) && espnAthleteId !== failedId;

  return (
    <div
      className="headshot"
      style={{ ["--headshot-size" as string]: `${size}px` }}
    >
      {showImg && espnAthleteId ? (
        <img
          className="headshot__img"
          src={`https://a.espncdn.com/i/headshots/wnba/players/full/${espnAthleteId}.png`}
          alt={name}
          loading="lazy"
          decoding="async"
          onError={() => setFailedId(espnAthleteId)}
        />
      ) : (
        <span className="headshot__fallback" aria-label={name}>
          {initials || "?"}
        </span>
      )}
    </div>
  );
}
