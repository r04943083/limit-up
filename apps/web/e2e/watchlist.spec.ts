import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("自选页:分组 / 选股 / 右栏公司名 / 个股 Tab", async ({ page }) => {
  const w = watch(page);
  await page.goto("/watchlist");

  // Group tab strip renders (the default "Target" group).
  await expect(page.getByRole("button", { name: "Target", exact: true })).toBeVisible();

  // Pick a stock → the right panel must show the COMPANY NAME (regression: it once
  // collapsed to just the symbol via flex+truncate).
  await page.locator('button:has-text("NVIDIA")').first().click();
  await expect(page.getByRole("heading", { name: /NVIDIA Corporation/ })).toBeVisible();

  // ▾ dropdown lists every group (Futu-style "expand all"). Scope to the dropdown menu
  // so "ARKK" doesn't also match the same-named tab in the strip.
  await page.locator('button[title="展开全部分组"]').click();
  const menu = page.locator("div.z-40.w-44");
  await expect(menu).toBeVisible();
  await menu.getByText("ARKK").click(); // select + close menu
  await expect(menu).toBeHidden();

  // StockPage tabs switch without crashing.
  for (const t of ["财报", "分红", "股东", "概况", "行情"]) {
    await page.getByRole("button", { name: t, exact: true }).click();
    await page.waitForTimeout(300);
  }

  await page.waitForTimeout(1500);
  expectClean(w);
});
