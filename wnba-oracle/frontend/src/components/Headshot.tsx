// Circular avatar. The WNBA project doesn't have a portrait CDN like
// MLB's midfield.mlbstatic.com, so this always renders initials inside a
// team-tinted disc. The team-color ring + glow come from the parent via
// --team-primary; size defaults to the original 100px card treatment but
// the Slip row passes 40 for its compact identity column.

import { useMemo } from "react";

interface Props {
  name: string;
  size?: number;
}

export function Headshot({ name, size = 100 }: Props) {
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
    <div
      className="headshot"
      style={{ ["--headshot-size" as string]: `${size}px` }}
    >
      <span className="headshot__fallback" aria-label={name}>
        {initials || "?"}
      </span>
    </div>
  );
}
