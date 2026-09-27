import { BrowserRouter, Route, Routes } from "react-router-dom";
import { HomePage } from "./pages/HomePage";
import { SystemPage } from "./pages/SystemPage";

export function App() {
  return (
    <BrowserRouter>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/system" element={<SystemPage />} />
      </Routes>
    </BrowserRouter>
  );
}
