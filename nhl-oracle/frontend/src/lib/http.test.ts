import { describe, expect, it } from "vitest";
import { fetchPublic } from "./http";

describe("fetchPublic", () => {
  it("rejects non-positive timeouts", async () => {
    await expect(fetchPublic("https://example.test", 0)).rejects.toBeInstanceOf(
      RangeError,
    );
  });
});
