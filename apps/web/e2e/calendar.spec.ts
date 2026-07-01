import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("财经日历:自选/持仓的财报 / 除息(窗口切换)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/calendar");

  await expect(page.getByRole("heading", { name: "财经日历" })).toBeVisible();
  await expect(page.getByRole("button", { name: "14天" })).toBeVisible();
  await expect(page.getByRole("button", { name: "60天" })).toBeVisible();

  // The panel resolves to a day-by-day agenda or a friendly empty state — never a crash.
  await page.getByRole("button", { name: "60天" }).click();
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "14天" }).click();
  await page.waitForTimeout(1200);

  expectClean(w);
});

test("财经日历:从 IconRail 进入", async ({ page }) => {
  const w = watch(page);
  await page.goto("/");
  await page.getByRole("link", { name: "日历" }).click();
  await expect(page).toHaveURL(/\/calendar/);
  await expect(page.getByRole("heading", { name: "财经日历" })).toBeVisible();
  await page.waitForTimeout(500);
  expectClean(w);
});
