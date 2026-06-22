import { describe, expect, it } from "vitest";
import { formatHMS, msUntil } from "./scheduling";

describe("msUntil", () => {
  it("returns ms remaining to a future tip-relative target", () => {
    const now = Date.parse("2026-06-22T22:00:00Z");
    // 22:20 freeze target (23:00 first tip - 40min) -> 20 minutes out.
    expect(msUntil("2026-06-22T22:20:00+00:00", now)).toBe(20 * 60 * 1000);
  });

  it("goes negative once the freeze target has passed", () => {
    const now = Date.parse("2026-06-22T22:30:00Z");
    expect(msUntil("2026-06-22T22:20:00+00:00", now)).toBe(-10 * 60 * 1000);
  });

  it("returns null when the target is unknown or unparseable", () => {
    expect(msUntil(null, Date.now())).toBeNull();
    expect(msUntil("not-a-date", Date.now())).toBeNull();
  });
});

describe("formatHMS", () => {
  it("clamps non-positive durations to zero", () => {
    expect(formatHMS(0)).toBe("00:00:00");
    expect(formatHMS(-5000)).toBe("00:00:00");
  });

  it("formats hours, minutes, seconds", () => {
    expect(formatHMS((3 * 3600 + 4 * 60 + 5) * 1000)).toBe("03:04:05");
  });
});
