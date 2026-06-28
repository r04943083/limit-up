import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("模拟交易页:概览卡 + 下单 + 持仓", async ({ page }) => {
  const w = watch(page);
  await page.goto("/paper");

  await expect(page.getByRole("heading", { name: "模拟交易" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "总资产" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "现金" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "下单" })).toBeVisible();
  // Holdings panel renders either rows or the empty-state.
  const holdings = page.getByRole("heading", { name: "持仓", exact: true });
  await expect(holdings).toBeVisible({ timeout: 10_000 });

  await page.waitForTimeout(800);
  expectClean(w);
});
