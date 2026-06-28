import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("用量页:卡片 / 趋势 / 调用日志", async ({ page }) => {
  const w = watch(page);
  await page.goto("/usage");

  await expect(page.getByRole("heading", { name: "AI 用量" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "今日调用" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "累计成本" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "近 14 天 Tokens" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "最近调用" })).toBeVisible();

  await page.waitForTimeout(1500);
  expectClean(w);
});
