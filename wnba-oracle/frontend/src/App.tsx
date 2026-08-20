import { BrowserRouter, Route, Routes } from "react-router-dom";
import { FreezesPage } from "./pages/FreezesPage";
import { HistoryPage } from "./pages/HistoryPage";
import { PickerPage } from "./pages/PickerPage";
import { PlayerPage } from "./pages/PlayerPage";
import { SlatePage } from "./pages/SlatePage";
import { SystemPage } from "./pages/SystemPage";

export function App() {
  return (
    <BrowserRouter>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <Routes>
        <Route path="/" element={<PickerPage />} />
        <Route path="/player/:date/:playerId" element={<PlayerPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/slate/:date" element={<SlatePage />} />
        <Route path="/freezes/:date" element={<FreezesPage />} />
        <Route path="/system" element={<SystemPage />} />
      </Routes>
    </BrowserRouter>
  );
}
