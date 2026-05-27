import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/main.css";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("missing #root");
createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// Pre-hydration shell is owned by index.html; tear it down after first
// paint so it doesn't sit on top of the React tree forever.
const shell = document.getElementById("pre-hydration-shell");
if (shell) {
  requestAnimationFrame(() => {
    shell.style.transition = "opacity 240ms ease";
    shell.style.opacity = "0";
    setTimeout(() => shell.remove(), 300);
  });
}
