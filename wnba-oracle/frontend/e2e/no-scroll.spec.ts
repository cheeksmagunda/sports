import { test, expect } from "@playwright/test";

const BASE_URL = "http://localhost:5173";
const DESKTOP_VIEWPORT = { width: 1280, height: 800 };
const PHONE_VIEWPORT = { width: 390, height: 844 };

// Slate lifecycle states (Phase 6 full matrix)
const DEMO_STATES = ["prefreeze", "frozen", "live", "final", "paused", "noslate", "error", "refrozen"] as const;

test.describe("No-scroll gate", () => {
  test.describe("desktop (1280x800)", () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize(DESKTOP_VIEWPORT);
    });

    DEMO_STATES.forEach((state) => {
      test(`/picker with demo=${state} does not scroll`, async ({ page }) => {
        await page.goto(`${BASE_URL}/?demo=${state}`);
        await page.waitForLoadState("networkidle");

        const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
        const clientHeight = await page.evaluate(() => window.innerHeight);

        expect(scrollHeight).toBeLessThanOrEqual(clientHeight + 1); // +1 for rounding
      });
    });

    test("/picker with a frozen lineup renders visible player rows", async ({ page }) => {
      await page.goto(`${BASE_URL}/?demo=frozen`);
      await page.waitForLoadState("networkidle");

      const row = page.locator(".slip-row").first();
      await expect(row).toBeVisible();
      expect((await row.boundingBox())?.height ?? 0).toBeGreaterThan(40);
    });

    test("/history does not scroll", async ({ page }) => {
      await page.goto(`${BASE_URL}/history`);
      await page.waitForLoadState("networkidle");

      const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
      const clientHeight = await page.evaluate(() => window.innerHeight);

      expect(scrollHeight).toBeLessThanOrEqual(clientHeight + 1);
    });

    test("/system does not scroll", async ({ page }) => {
      await page.goto(`${BASE_URL}/system`);
      await page.waitForLoadState("networkidle");

      const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
      const clientHeight = await page.evaluate(() => window.innerHeight);

      expect(scrollHeight).toBeLessThanOrEqual(clientHeight + 1);
    });
  });

  test.describe("phone (390x844)", () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize(PHONE_VIEWPORT);
    });

    DEMO_STATES.forEach((state) => {
      test(`/picker with demo=${state} does not scroll`, async ({ page }) => {
        await page.goto(`${BASE_URL}/?demo=${state}`);
        await page.waitForLoadState("networkidle");

        const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
        const clientHeight = await page.evaluate(() => window.innerHeight);

        expect(scrollHeight).toBeLessThanOrEqual(clientHeight + 1);
      });
    });

    test("/picker with a frozen lineup renders visible player rows", async ({ page }) => {
      await page.goto(`${BASE_URL}/?demo=frozen`);
      await page.waitForLoadState("networkidle");

      const row = page.locator(".slip-row").first();
      await expect(row).toBeVisible();
      expect((await row.boundingBox())?.height ?? 0).toBeGreaterThan(40);
    });

    test("/history does not scroll", async ({ page }) => {
      await page.goto(`${BASE_URL}/history`);
      await page.waitForLoadState("networkidle");

      const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
      const clientHeight = await page.evaluate(() => window.innerHeight);

      expect(scrollHeight).toBeLessThanOrEqual(clientHeight + 1);
    });

    test("/system does not scroll", async ({ page }) => {
      await page.goto(`${BASE_URL}/system`);
      await page.waitForLoadState("networkidle");

      const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
      const clientHeight = await page.evaluate(() => window.innerHeight);

      expect(scrollHeight).toBeLessThanOrEqual(clientHeight + 1);
    });
  });
});
