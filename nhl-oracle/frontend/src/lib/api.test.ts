import { describe, expect, it } from "vitest";
import { API_URL, localSlateDate } from "./api";

describe("api helpers", () => {
  it("exposes a default API origin", () => {
    expect(API_URL.length).toBeGreaterThan(0);
  });

  it("formats local slate date as YYYY-MM-DD", () => {
    expect(localSlateDate()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
