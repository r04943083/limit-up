import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("研究页:全局搜索跳转 + 财报/DCF 渲染", async ({ page }) => {
  const w = watch(page);
  await page.goto("/");

  // "/" opens GlobalSearch → type a symbol → Enter navigates to /research/<SYMBOL>.
  await page.keyboard.press("/");
  await page.getByPlaceholder(/搜索代码/).fill("NVDA");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/research\/NVDA/);

  // 财报 tab → statements + DCF.
  await page.getByRole("button", { name: "财报", exact: true }).click();
  await expect(page.getByRole("heading", { name: "财务报表" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "DCF 估值" })).toBeVisible();

  // DCF must show a numeric intrinsic value (not the "—" placeholder).
  const intrinsic = page.locator("text=每股内在价值").locator("xpath=following-sibling::*[1]");
  await expect(intrinsic).toHaveText(/\d/, { timeout: 10_000 }); // a real number, not "—"

  // 年度 / 季度 toggle works.
  await page.getByRole("button", { name: "季度", exact: true }).click();
  await page.waitForTimeout(300);

  await page.waitForTimeout(1500);
  expectClean(w);
});

test("研究页:美股分时含盘前盘后开关(RTH/EXT)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/research/AAPL");

  // Switch the chart to 分时 (intraday). US equities expose an extended-hours toggle.
  await page.getByRole("button", { name: "分时", exact: true }).click();
  const extBtn = page.getByRole("button", { name: "盘前盘后" });
  await expect(extBtn).toBeVisible({ timeout: 10_000 });

  // Toggling extended hours off then on must not error or blank the chart.
  await extBtn.click();
  await page.waitForTimeout(400);
  await extBtn.click();
  await page.waitForTimeout(400);

  expectClean(w);
});
