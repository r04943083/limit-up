import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("代码输入:自动补全选择已下载标的(AI 工作室)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/studio");

  // The debate tab's symbol field is now an autocomplete over downloaded symbols.
  const box = page.getByPlaceholder(/代码或名称/).first();
  await expect(box).toBeVisible({ timeout: 10_000 });
  await box.fill("");
  await box.type("NV");

  // Dropdown of real hits → NVDA; picking it writes the canonical symbol back.
  const hit = page.getByRole("button", { name: /NVDA/ }).first();
  await expect(hit).toBeVisible({ timeout: 5000 });
  await hit.click();
  await expect(box).toHaveValue("NVDA");

  await page.waitForTimeout(300);
  expectClean(w);
});

test("状态栏:API 在线显示绿灯(非红)", async ({ page }) => {
  await page.goto("/watchlist");
  const dot = page.locator("footer span.rounded-full").first();
  // online = green (#2EBD85); the old bug showed the financial red token while healthy.
  await expect(dot).toHaveClass(/2EBD85/, { timeout: 10_000 });
});
