import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("发现页:美股异动 feed tabs + 榜单渲染(不触发 LLM)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/discover");

  await expect(page.getByRole("heading", { name: "发现 · 美股异动" })).toBeVisible();

  // Feed tabs load from /markets/us/feeds.
  await expect(page.getByRole("button", { name: "涨幅榜" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("button", { name: "跌幅榜" })).toBeVisible();
  await expect(page.getByRole("button", { name: "成交活跃" })).toBeVisible();

  // The board panel resolves to either a table (代码 header) or a friendly empty/error state
  // — never a crash. Switching feeds must not error.
  await page.getByRole("button", { name: "成交活跃" }).click();
  await page.waitForTimeout(1500);
  await page.getByRole("button", { name: "跌幅榜" }).click();
  await page.waitForTimeout(1500);

  expectClean(w);
});

test("发现页:从 IconRail 进入", async ({ page }) => {
  const w = watch(page);
  await page.goto("/");
  await page.getByRole("link", { name: "发现" }).click();
  await expect(page).toHaveURL(/\/discover/);
  await expect(page.getByRole("heading", { name: "发现 · 美股异动" })).toBeVisible();
  await page.waitForTimeout(500);
  expectClean(w);
});
