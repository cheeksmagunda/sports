import { BrowserRouter, Route, Routes } from "react-router-dom";
import { HealthPage } from "./pages/HealthPage";
import { HomePage } from "./pages/HomePage";
import { SlatePage } from "./pages/SlatePage";

export function App() {
  return (
    <BrowserRouter>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/slate/:date" element={<SlatePage />} />
        <Route path="/health" element={<HealthPage />} />
      </Routes>
    </BrowserRouter>
  );
}
