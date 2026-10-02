import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: proxy /api/<sport>/* to a local server (node server/index.mjs) so the
// browser stays same-origin exactly as in production.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8080" } },
});
