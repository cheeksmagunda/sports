import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchHealth, fetchLineup, fetchSlate } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("NHL API client stubs", () => {
  it("fetchHealth parses a healthy JSON payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", service: "nhl-api" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchHealth()).resolves.toEqual({ status: "ok", service: "nhl-api" });
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/health$/);
  });

  it("fetchSlate returns null on 404", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 404 })));
    await expect(fetchSlate("2026-09-27")).resolves.toBeNull();
  });

  it("fetchLineup returns null on 404", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 404 })));
    await expect(fetchLineup("2026-09-27")).resolves.toBeNull();
  });
});
