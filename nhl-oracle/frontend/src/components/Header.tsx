import { Link } from "react-router-dom";
import { ThemeToggle } from "./ThemeToggle";

interface Props {
  theme: "light" | "dark";
  onThemeToggle: () => void;
  slateDateDisplay: string | null;
}

export function Header({ theme, onThemeToggle, slateDateDisplay }: Props) {
  return (
    <header className="header" aria-label="Site header">
      <Link to="/" className="header__lockup">
        <span className="header__mark" aria-hidden="true">
          H
        </span>
        <span className="header__wordmark">
          NHL <em>Oracle</em>
        </span>
      </Link>
      <div className="header__meta" aria-label="Slate date">
        <span>Today&rsquo;s Slate</span>
        <span className="header__meta-strong">{slateDateDisplay ?? "—"}</span>
      </div>
      <div className="header__right">
        <nav className="header__nav" aria-label="Site navigation">
          <Link to="/system" className="header__nav-link">
            System
          </Link>
        </nav>
        <ThemeToggle theme={theme} onToggle={onThemeToggle} />
      </div>
    </header>
  );
}
