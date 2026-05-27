// Sun/moon switch. Sets data-theme on <html>; light-dark() resolves the
// rest.

import { Icon } from "./Icon";

interface Props {
  theme: "light" | "dark";
  onToggle: () => void;
}

export function ThemeToggle({ theme, onToggle }: Props) {
  const isDark = theme === "dark";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={onToggle}
      className="theme-toggle"
    >
      <span className="knob" aria-hidden="true">
        <Icon name={isDark ? "moon" : "sun"} size={14} />
      </span>
    </button>
  );
}
