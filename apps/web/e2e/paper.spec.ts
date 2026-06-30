import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("模拟交易页:AI 竞技场(默认)+ 我的模拟盘", async ({ page }) => {
  const w = watch(page);
  await page.goto("/paper");

  await expect(page.getByRole("heading", { name: "模拟交易" })).toBeVisible();

  // Default tab = AI 竞技场: leaderboard + curve panel + run entry (do NOT click 运行一轮 — it bills LLM).
  await expect(page.getByRole("heading", { name: "AI 投资人排行榜" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("heading", { name: "收益曲线对比" })).toBeVisible();
  await expect(page.getByRole("button", { name: /运行一轮/ })).toBeVisible();

  // Leaderboard rows expand to reveal positions + the full operation ledger, and MULTIPLE
  // rows can be open at once (regression guard for the single-open → multi-open change).
  const rows = page.locator("tbody tr.cursor-pointer");
  if (await rows.count() >= 2) {
    await rows.nth(0).click();
    await expect(page.getByText("操盘次数").first()).toBeVisible();
    await rows.nth(1).click();
    // both stay open → "操盘次数" appears in two expanded blocks simultaneously
    await expect(page.getByText("操盘次数")).toHaveCount(2);
  }

  // Switch to the manual paper account.
  await page.getByRole("button", { name: "我的模拟盘", exact: true }).click();
  await expect(page.getByRole("heading", { name: "总资产" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "下单" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "持仓", exact: true })).toBeVisible();

  await page.waitForTimeout(800);
  expectClean(w);
});
