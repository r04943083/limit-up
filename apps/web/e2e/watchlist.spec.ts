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

test("自选右侧:报价/分析/资讯/评论 四形态 (对齐富途)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/research/NVDA");

  // 报价 (fu2): dense quote table is the default right-panel form.
  await page.getByRole("button", { name: "报价", exact: true }).click();
  await expect(page.getByText("市盈率TTM", { exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("换手率", { exact: true })).toBeVisible();

  // 分析 (fu): 公司估值 PE/PB/PS band + 行业平均 + 分析师评级 + 卖空数据.
  await page.getByRole("button", { name: "分析", exact: true }).click();
  await expect(page.getByRole("heading", { name: "公司估值" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("行业平均", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("超过历史数据", { exact: true })).toBeVisible();
  // Switch the valuation metric (must not crash / 5xx).
  await page.getByRole("button", { name: "市净率 PB", exact: true }).click();
  await page.waitForTimeout(200);
  await page.getByRole("button", { name: "市销率 PS", exact: true }).click();
  await expect(page.getByRole("heading", { name: "分析师评级" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "卖空数据" })).toBeVisible();

  // 资讯 (fu3): news feed.
  await page.getByRole("button", { name: "资讯", exact: true }).click();
  await page.waitForTimeout(300);

  // 评论 (fu4): community placeholder (honest about the data gap).
  await page.getByRole("button", { name: "评论", exact: true }).click();
  await expect(page.getByText("社区评论", { exact: true })).toBeVisible();

  await page.waitForTimeout(500);
  expectClean(w);
});

test("全局搜索:代码/名称自动补全,只跳已下载标的", async ({ page }) => {
  const w = watch(page);
  await page.goto("/watchlist");

  await page.keyboard.press("/"); // open the overlay
  const overlay = page.locator("div.fixed.inset-0.z-50"); // scope to the search dialog
  const box = overlay.getByPlaceholder(/搜索代码/);
  await expect(box).toBeVisible();
  await box.fill("tes");

  // A dropdown of real matches appears; Tesla must be among them (scoped to the overlay
  // so it doesn't collide with the TSLA row in the watchlist behind it).
  const tslaHit = overlay.getByRole("button", { name: /TSLA/ });
  await expect(tslaHit).toBeVisible({ timeout: 5000 });
  await tslaHit.click();

  // Navigates to the resolved symbol — never a made-up /research/TES.
  await expect(page).toHaveURL(/\/research\/TSLA/);
  await page.waitForTimeout(800);
  expectClean(w);
});
