import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("策略页:参数 + 运行回测(确定性,非 LLM)+ 统计渲染", async ({ page }) => {
  const w = watch(page);
  await page.goto("/strategy");

  await expect(page.getByRole("heading", { name: "策略构建器" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "策略参数" })).toBeVisible();

  // Backtest is pure compute (fast, not billed) — safe to actually run in E2E.
  await page.getByRole("button", { name: "运行回测" }).click();
  await expect(page.getByRole("heading", { name: "回测统计" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("heading", { name: "净值曲线" })).toBeVisible();
  // The equity curve SVG path renders.
  await expect(page.locator("svg path[stroke='#21D0C3']").first()).toBeVisible();

  await page.waitForTimeout(800);
  expectClean(w);
});
