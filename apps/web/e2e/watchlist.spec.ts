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

test("自选页:列排序 + 可定制副指标列 + 分时", async ({ page }) => {
  const w = watch(page);
  await page.goto("/watchlist");

  // Sortable column headers (Futu-style).
  await expect(page.getByRole("button", { name: /名称\/代码/ })).toBeVisible();
  await page.getByRole("button", { name: /名称\/代码/ }).click(); // sort by name
  await expect(page.getByRole("button", { name: /最新·涨跌/ })).toBeVisible();

  // Customizable secondary metric: open the selector and switch to 换手率.
  const metricBtn = page.locator('button[title="选择副指标 / 排序"]');
  await metricBtn.click();
  const metricMenu = page.locator("div.z-40.w-28");
  await expect(metricMenu).toBeVisible();
  await metricMenu.getByText("换手率", { exact: true }).click();
  await expect(metricMenu).toBeHidden();

  // 分时 view on a stock's 行情 (live; degrades gracefully — must not 5xx the page).
  await page.locator('button:has-text("NVIDIA")').first().click();
  await page.getByRole("button", { name: "分时", exact: true }).click();
  await page.waitForTimeout(1200);

  expectClean(w);
});
