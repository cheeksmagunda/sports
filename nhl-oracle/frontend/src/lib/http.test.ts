import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchPublic } from "./http";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("fetchPublic", () => {
  it("disables browser caching and supplies an abort signal", async () => {
    const response = new Response("{}", { status: 200 });
    const fetchMock = vi.fn().mockResolvedValue(response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchPublic("https://public.example/data")).resolves.toBe(response);

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(
      "https://public.example/data",
      expect.objectContaining({
        cache: "no-store",
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("turns an upstream stall into a bounded safe error", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn((_input: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted")), {
          once: true,
        });
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const assertion = expect(fetchPublic("https://public.example/data", 25)).rejects.toThrow(
      "Public data request timed out",
    );
    await vi.advanceTimersByTimeAsync(25);
    await assertion;
  });

  it("rejects invalid timeout configuration before network access", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchPublic("https://public.example/data", 0)).rejects.toThrow(RangeError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
