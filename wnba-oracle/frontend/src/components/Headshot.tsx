// Circular avatar. The WNBA project doesn't have a portrait CDN like
// MLB's midfield.mlbstatic.com, so this always renders initials inside a
// team-tinted disc. The team-color ring + glow come from the parent .card
// via --team-primary.

import { useMemo } from "react";

interface Props {
  name: string;
}

export function Headshot({ name }: Props) {
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

  return (
    <div className="headshot">
      <span className="headshot__fallback" aria-label={name}>
        {initials || "?"}
      </span>
    </div>
  );
}
