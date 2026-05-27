import { jsx as _jsx } from "react/jsx-runtime";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
const rootEl = document.getElementById("root");
if (!rootEl)
    throw new Error("missing #root");
createRoot(rootEl).render(_jsx(StrictMode, { children: _jsx(App, {}) }));
