import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { localSlateDate } from "../lib/api";

const APP_VERSION =
  (import.meta.env.VITE_APP_VERSION as string | undefined) ?? "v0.1.0-scaffold";

interface Props {
  children: ReactNode;
  eyebrow?: string;
}

export function Shell({ children, eyebrow }: Props) {
  const today = localSlateDate();

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand__mark" aria-hidden="true" />
          <span className="brand__name">NHL Oracle</span>
        </Link>
        <nav className="topbar__nav" aria-label="Primary">
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to={`/slate/${today}`}>Slate</NavLink>
          <NavLink to="/health">Health</NavLink>
        </nav>
        {eyebrow ? <span className="topbar__eyebrow">{eyebrow}</span> : null}
      </header>
      <main id="main-content" className="main">
        {children}
      </main>
      <footer className="footer">
        <span>Five-card ordered · observation only</span>
        <span className="footer__version">{APP_VERSION}</span>
      </footer>
    </div>
  );
}
