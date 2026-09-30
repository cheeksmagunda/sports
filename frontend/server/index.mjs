// Static host + same-origin read-only API proxy for the Sports Oracle frontend.
// Upstreams come from NFL_API_URL / NBA_API_URL / NHL_API_URL at runtime.
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve } from "node:path";
import { resolveUpstream } from "./routes.mjs";

const DIST = resolve(process.env.DIST_DIR ?? "dist");
const PORT = Number(process.env.PORT ?? 8080);
const UPSTREAM_TIMEOUT_MS = 10_000;

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".json": "application/json",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
};

const SECURITY = {
  "Content-Security-Policy":
    "default-src 'self'; base-uri 'self'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; img-src 'self' data:; object-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'",
  "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
};

function send(res, status, body, headers = {}) {
  res.writeHead(status, { ...SECURITY, ...headers });
  res.end(body);
}

function sendJson(res, status, payload) {
  send(res, status, JSON.stringify(payload), {
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
  });
}

async function proxy(req, res) {
  const target = resolveUpstream(req.method, req.url, process.env);
  if (!target.url) return sendJson(res, target.status, { error: target.error });
  try {
    const upstream = await fetch(target.url, {
      method: req.method,
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    const body = req.method === "HEAD" ? "" : Buffer.from(await upstream.arrayBuffer());
    send(res, upstream.status, body, {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    });
  } catch {
    sendJson(res, 502, { error: "upstream_unreachable" });
  }
}

function serveStatic(req, res) {
  if (req.method !== "GET" && req.method !== "HEAD") {
    return sendJson(res, 405, { error: "method_not_allowed" });
  }
  const pathname = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const candidate = join(DIST, normalize(pathname));
  const inDist = candidate === DIST || candidate.startsWith(DIST + "/");
  let file = candidate;
  const isAsset = pathname.startsWith("/assets/");
  if (!inDist || !existsSync(file) || !statSync(file).isFile()) {
    if (isAsset) return sendJson(res, 404, { error: "not_found" });
    file = join(DIST, "index.html"); // SPA fallback for /nfl, /nba, /nhl
  }
  res.writeHead(200, {
    ...SECURITY,
    "Content-Type": TYPES[extname(file)] ?? "application/octet-stream",
    "Cache-Control": isAsset ? "public, max-age=31536000, immutable" : "no-cache",
  });
  if (req.method === "HEAD") return res.end();
  createReadStream(file).pipe(res);
}

createServer((req, res) => {
  try {
    if (req.url === "/healthz") return sendJson(res, 200, { status: "ok" });
    if (req.url?.startsWith("/api/")) return void proxy(req, res);
    return serveStatic(req, res);
  } catch {
    return sendJson(res, 400, { error: "bad_request" });
  }
}).listen(PORT, "0.0.0.0", () => console.log(`sports-oracle-frontend listening on ${PORT}`));
