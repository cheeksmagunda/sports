// Sticky page header. WNBA wordmark (links home) + slate date + frozen-at
// + site nav + watchdog dot + theme toggle. On narrow viewports the
// middle meta column hides.

import { Link } from "react-router-dom";
import { ThemeToggle } from "./ThemeToggle";
import { WatchdogDot } from "./WatchdogDot";

interface Props {
  theme: "light" | "dark";
  onThemeToggle: () => void;
  slateDateDisplay: string | null;
  frozenAtDisplay: string | null;
}

export function Header({
  theme,
  onThemeToggle,
  slateDateDisplay,
  frozenAtDisplay,
}: Props) {
  return (
    <header className="header" aria-label="Site header">
      <Link to="/" className="header__lockup">
        <span className="header__mark" aria-hidden="true">W</span>
        <span className="header__wordmark">
          WNBA <em>Oracle</em>
        </span>
      </Link>
      <div className="header__meta" aria-label="Slate date">
        <span>Today&rsquo;s Slate</span>
        <span className="header__meta-strong">{slateDateDisplay ?? "—"}</span>
      </div>
      <div className="header__right">
        <div
          className="header__meta header__meta--end"
          aria-label="Frozen-at time"
        >
          <span>Frozen</span>
          <span className="header__meta-strong header__meta-strong--frozen">
            {frozenAtDisplay ?? "—"}
          </span>
        </div>
        <nav className="header__nav" aria-label="Site navigation">
          <Link to="/history" className="header__nav-link">
            History
          </Link>
          <Link to="/system" className="header__nav-link">
            System
          </Link>
        </nav>
        <WatchdogDot />
        <ThemeToggle theme={theme} onToggle={onThemeToggle} />
      </div>
    </header>
  );
}
