import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("涨停页:复盘 / 天梯 / 池 / 龙虎榜 结构渲染", async ({ page }) => {
  const w = watch(page);
  await page.goto("/limitup");

  await expect(page.getByRole("heading", { name: "涨停复盘" })).toBeVisible();
  // Panels always render their titles (data may be empty on non-trading days).
  await expect(page.getByRole("heading", { name: "AI 复盘解读" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "涨停板池" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "龙虎榜" })).toBeVisible();

  // Expect either the ladder (data) or the explicit empty-state — never a stuck spinner.
  // The .or().toBeVisible() waits for whichever resolves, so no networkidle needed.
  const ladder = page.getByRole("heading", { name: "连板天梯" });
  const empty = page.getByText("该日无涨停数据", { exact: false });
  await expect(ladder.or(empty).first()).toBeVisible({ timeout: 15_000 });

  await page.waitForTimeout(1000);
  expectClean(w);
});
