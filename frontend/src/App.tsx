import { BrowserRouter, Navigate, NavLink, Route, Routes } from "react-router-dom";
import { SportPage } from "./pages/SportPage";
import { SPORTS } from "./lib/sports";

export function App() {
  return (
    <BrowserRouter>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <header className="topbar">
        <span className="brand">Sports Oracle</span>
        <nav className="tabs" aria-label="Sport">
          {SPORTS.map((sport) => (
            <NavLink key={sport.id} to={`/${sport.id}`} className="tab">
              {sport.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main id="main-content" className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/nfl" replace />} />
          <Route path="/:sport" element={<SportPage />} />
          <Route path="*" element={<Navigate to="/nfl" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
