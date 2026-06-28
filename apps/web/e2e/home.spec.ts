import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("首页加载且无报错", async ({ page }) => {
  const w = watch(page);
  await page.goto("/");
  // IconRail (left nav) is always present — anchor on a stable nav label.
  await expect(page.getByText("自选", { exact: true }).first()).toBeVisible();
  // Don't waitForLoadState("networkidle") — the app polls /health + indices on a timer,
  // so the network is never idle. Settle briefly so initial XHRs (and any failure) surface.
  await page.waitForTimeout(2000);
  expectClean(w);
});
