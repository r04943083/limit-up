import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("数据页:存量总览 + 各市场覆盖率", async ({ page }) => {
  const w = watch(page);
  await page.goto("/data");

  // Totals cards.
  await expect(page.getByRole("heading", { name: "股票总数" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("heading", { name: "K线总条数" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "数据库大小" })).toBeVisible();

  // Per-market panels (美股 / A股 / 港股) with coverage rows.
  await expect(page.getByRole("heading", { name: "美股" })).toBeVisible();
  await expect(page.getByText("日线行情", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("财报三表", { exact: true }).first()).toBeVisible();

  await page.waitForTimeout(500);
  expectClean(w);
});
