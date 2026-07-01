import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("选股页:筛选条件 + 灌入面板 + 运行结果", async ({ page }) => {
  const w = watch(page);
  await page.goto("/screener");

  // Meta loads → filter fields + seed indices visible.
  await expect(page.getByRole("heading", { name: "筛选条件" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("市盈率TTM", { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "沪深300", exact: true })).toBeVisible();

  // Preset strategies: one click applies filters + auto-runs.
  await expect(page.getByRole("heading", { name: "预设策略" })).toBeVisible();
  await page.getByRole("button", { name: /低估值/ }).click();
  await expect(page.getByRole("heading", { name: "筛选结果" })).toBeVisible({ timeout: 15_000 });

  // Financials backfill control is present (we don't trigger the heavy fill in e2e).
  await expect(page.getByRole("button", { name: "补全财报三表", exact: true })).toBeVisible();

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

test("选股页:AI 预设浮出可移除的行业筛选芯片(不再是隐藏粘性筛选)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/screener");

  await expect(page.getByRole("heading", { name: "预设策略" })).toBeVisible({ timeout: 10_000 });
  // The AI / 科技成长 preset is the only one that sets a sector filter (Technology).
  // (Preset buttons render label + hint, so match on a substring.)
  await page.getByRole("button", { name: /AI \/ 科技成长/ }).click();

  // That sector filter must now be VISIBLE as a removable chip (was hidden + sticky before).
  const chip = page.getByRole("button", { name: /Technology ✕/ });
  await expect(chip).toBeVisible({ timeout: 15_000 });

  // Clicking the chip clears the constraint.
  await chip.click();
  await expect(chip).toHaveCount(0);

  await page.waitForTimeout(300);
  expectClean(w);
});
