import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("选股页:筛选条件 + 灌入面板 + 运行结果", async ({ page }) => {
  const w = watch(page);
  await page.goto("/screener");

  // Meta loads → filter fields + seed indices visible.
  await expect(page.getByRole("heading", { name: "筛选条件" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("市盈率TTM", { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "沪深300", exact: true })).toBeVisible();

  // Filter US + run over the existing cached snapshots → results table appears.
  await page.getByRole("button", { name: "美股", exact: true }).click();
  await page.getByRole("button", { name: "运行筛选", exact: true }).click();
  await expect(page.getByRole("heading", { name: "筛选结果" })).toBeVisible({ timeout: 15_000 });

  // A result row click navigates to research.
  const firstRow = page.locator("tbody tr").first();
  await expect(firstRow).toBeVisible();
  await firstRow.click();
  await expect(page).toHaveURL(/\/research\//);

  await page.waitForTimeout(500);
  expectClean(w);
});
