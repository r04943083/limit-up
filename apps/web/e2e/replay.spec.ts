import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("复盘页:载入 K 线 + 播放控件 + 猜涨跌", async ({ page }) => {
  const w = watch(page);
  await page.goto("/replay");

  await expect(page.getByRole("heading", { name: "复盘 Replay" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "行情回放" })).toBeVisible();
  // OHLCV loads (default NVDA) and candles render — wait for the candle <rect>s.
  await expect(page.locator("svg rect").first()).toBeVisible({ timeout: 15_000 });

  // Stepping forward one bar works (deterministic, no network on step).
  await page.getByRole("button", { name: "⏭ 下一根" }).click();
  await expect(page.getByRole("heading", { name: "猜涨跌" })).toBeVisible();

  await page.waitForTimeout(800);
  expectClean(w);
});
