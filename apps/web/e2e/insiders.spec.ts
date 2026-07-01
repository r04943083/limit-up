import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("研究页 股东 Tab:内部人交易 + SEC 申报(美股)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/research/NVDA");

  await page.getByRole("button", { name: "股东", exact: true }).click();

  // The EDGAR panels render for US symbols (data warmed; may still show 加载中 briefly).
  await expect(page.getByRole("heading", { name: "内部人交易" })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "SEC 申报" })).toBeVisible();

  // The 10-K red-line diff panel is present (button-triggered — do NOT click, parsing two
  // 10-Ks is slow; assert the entry + section buttons render).
  await expect(page.getByRole("heading", { name: "10-K 红线对比" })).toBeVisible();
  await expect(page.getByRole("button", { name: "风险因素" })).toBeVisible();

  // Let the cached SEC data resolve; assert no console errors / no 5xx.
  await page.waitForTimeout(2000);
  expectClean(w);
});
