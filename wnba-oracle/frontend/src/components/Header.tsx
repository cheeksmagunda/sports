// Sticky page header. WNBA wordmark + slate date + frozen-at + theme
// toggle. On narrow viewports the middle meta column hides.

import { ThemeToggle } from "./ThemeToggle";

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
      <div className="header__lockup">
        <span className="header__mark" aria-hidden="true">W</span>
        <span className="header__wordmark">
          WNBA <em>Oracle</em>
        </span>
      </div>
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
        <ThemeToggle theme={theme} onToggle={onThemeToggle} />
      </div>
    </header>
  );
}
