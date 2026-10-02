import { describe, expect, it } from "vitest";
import { resolveUpstream } from "./routes.mjs";

const env = { NFL_API_URL: "https://nfl.example.app", NHL_API_URL: "https://nhl.example.app/" };

describe("resolveUpstream", () => {
  it("maps an allowed route to the sport's upstream origin", () => {
    expect(resolveUpstream("GET", "/api/nfl/lineup/2026-09-29", env)).toEqual({
      url: "https://nfl.example.app/lineup/2026-09-29",
    });
  });

  it("drops any path prefix on the configured upstream", () => {
    expect(resolveUpstream("GET", "/api/nhl/health", env)).toEqual({
      url: "https://nhl.example.app/health",
    });
  });

  it("forwards a numeric history limit only", () => {
    expect(resolveUpstream("GET", "/api/nfl/history?limit=10", env)).toEqual({
      url: "https://nfl.example.app/history?limit=10",
    });
    expect(resolveUpstream("GET", "/api/nfl/history?limit=x;drop", env)).toEqual({
      url: "https://nfl.example.app/history",
    });
  });

  it("refuses non-read methods", () => {
    expect(resolveUpstream("POST", "/api/nfl/health", env)).toMatchObject({ status: 405 });
  });

  it("refuses routes outside the allow-list", () => {
    expect(resolveUpstream("GET", "/api/nfl/schemas/labels", env)).toMatchObject({ status: 404 });
    expect(resolveUpstream("GET", "/api/nfl/lineup/../admin", env)).toMatchObject({ status: 404 });
  });

  it("refuses unknown sports, including wnba", () => {
    expect(resolveUpstream("GET", "/api/wnba/health", env)).toMatchObject({ status: 404 });
  });

  it("reports an unconfigured or invalid upstream as 503", () => {
    expect(resolveUpstream("GET", "/api/nba/health", env)).toMatchObject({
      status: 503,
      error: "upstream_not_configured",
    });
    expect(resolveUpstream("GET", "/api/nba/health", { NBA_API_URL: "ftp://x" })).toMatchObject({
      status: 503,
      error: "upstream_invalid",
    });
  });
});
