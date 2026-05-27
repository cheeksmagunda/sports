// Tiny inline-SVG icon set. Keeps the frontend free of iconify-icon to
// avoid the web-component dep — only a handful of glyphs are needed.

import type { CSSProperties } from "react";

type IconName =
  | "bolt"
  | "warn"
  | "moon"
  | "sun";

interface Props {
  name: IconName;
  size?: number;
  className?: string;
  style?: CSSProperties;
  ariaLabel?: string;
}

const PATHS: Record<IconName, string> = {
  // Phosphor-ish lightning glyph
  bolt: "M13 3 4 14h6l-1 7 9-11h-6l1-7z",
  // Filled circle with exclamation
  warn: "M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 15.5a1.25 1.25 0 1 1 1.25-1.25A1.24 1.24 0 0 1 12 17.5zm1-4.5h-2V7h2z",
  moon: "M20 14.5A8.5 8.5 0 1 1 9.5 4 7 7 0 0 0 20 14.5z",
  sun: "M12 7a5 5 0 1 0 5 5 5 5 0 0 0-5-5zm0-5a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V3a1 1 0 0 0-1-1zm0 17a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0v-2a1 1 0 0 0-1-1zM5.64 4.22a1 1 0 1 0-1.41 1.41l1.41 1.42a1 1 0 0 0 1.42-1.42zM18.36 19.78a1 1 0 0 0 1.41-1.41l-1.41-1.42a1 1 0 1 0-1.42 1.42zM3 13H1a1 1 0 0 0 0-2h2a1 1 0 0 0 0 2zm20-2h-2a1 1 0 0 0 0 2h2a1 1 0 0 0 0-2zM5.64 19.78a1 1 0 0 0 1.42-1.42l-1.42-1.41a1 1 0 0 0-1.41 1.41zM18.36 4.22l-1.42 1.41a1 1 0 1 0 1.42 1.42l1.41-1.42a1 1 0 0 0-1.41-1.41z",
};

export function Icon({ name, size = 16, className, style, ariaLabel }: Props) {
  const path = PATHS[name];
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="currentColor"
      className={className}
      style={style}
      role={ariaLabel ? "img" : undefined}
      aria-label={ariaLabel}
      aria-hidden={ariaLabel ? undefined : "true"}
    >
      <path d={path} />
    </svg>
  );
}
