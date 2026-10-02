// Pure routing for the same-origin API proxy. No I/O so it is unit-testable.

export const SPORTS = ["nfl", "nba", "nhl"];

// Read-only public surface the tabs use. Anything else is refused, so the
// proxy cannot be used to reach an upstream's admin or schema routes.
const ALLOWED = [
  /^\/health$/,
  /^\/readiness$/,
  /^\/history$/,
  /^\/lineup\/\d{4}-\d{2}-\d{2}$/,
  /^\/slate\/\d{4}-\d{2}-\d{2}$/,
];

export function upstreamEnv(sport) {
  return `${sport.toUpperCase()}_API_URL`;
}

/**
 * Map a request to an upstream URL.
 * Returns { url } on success or { status, error } when refused.
 */
export function resolveUpstream(method, requestUrl, env) {
  if (method !== "GET" && method !== "HEAD") {
    return { status: 405, error: "method_not_allowed" };
  }
  const parsed = new URL(requestUrl, "http://proxy.invalid");
  const match = /^\/api\/([a-z]+)(\/.*)$/.exec(parsed.pathname);
  if (!match || !SPORTS.includes(match[1])) {
    return { status: 404, error: "unknown_sport" };
  }
  const [, sport, rest] = match;
  if (!ALLOWED.some((re) => re.test(rest))) {
    return { status: 404, error: "route_not_allowed" };
  }
  const base = env[upstreamEnv(sport)];
  if (!base) return { status: 503, error: "upstream_not_configured" };
  let origin;
  try {
    origin = new URL(base);
  } catch {
    return { status: 503, error: "upstream_invalid" };
  }
  if (origin.protocol !== "https:" && origin.protocol !== "http:") {
    return { status: 503, error: "upstream_invalid" };
  }
  const limit = parsed.searchParams.get("limit");
  const query = rest === "/history" && /^\d{1,3}$/.test(limit ?? "") ? `?limit=${limit}` : "";
  return { url: `${origin.origin}${rest}${query}` };
}
