import { describe, expect, it } from "vitest";
import { centralDate, picksOf } from "./api";
import { isSportId } from "./sports";

describe("picksOf", () => {
  it("returns [] for a missing lineup", () => {
    expect(picksOf(null)).toEqual([]);
    expect(picksOf({ lineup: null })).toEqual([]);
  });

  it("keeps only well-formed picks", () => {
    const payload = { lineup: { picks: [{ name: "A" }, { nope: 1 }] } } as never;
    expect(picksOf(payload)).toEqual([{ name: "A" }]);
  });
});

describe("centralDate", () => {
  it("formats as YYYY-MM-DD in Central time", () => {
    expect(centralDate(new Date("2026-09-29T02:00:00Z"))).toBe("2026-09-28");
  });
});

describe("isSportId", () => {
  it("accepts the three sports and rejects wnba", () => {
    expect(isSportId("nfl")).toBe(true);
    expect(isSportId("wnba")).toBe(false);
  });
});
