import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("AI 工作室:五个 Tab 切换渲染(不触发生成)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/studio");

  await expect(page.getByRole("heading", { name: "AI 工作室" })).toBeVisible();

  // Each tab switches and renders its own structure (do NOT click generate buttons).
  await page.getByRole("button", { name: "多空辩论" }).click();
  await expect(page.getByRole("heading", { name: "多空辩论" })).toBeVisible();

  await page.getByRole("button", { name: "多智能体" }).click();
  await expect(page.getByRole("heading", { name: "多智能体投研" })).toBeVisible();

  await page.getByRole("button", { name: "投资人格" }).click();
  // Persona cards load from the API.
  await expect(page.getByRole("heading", { name: /Buffett/ })).toBeVisible({ timeout: 10_000 });

  await page.getByRole("button", { name: "AI 教练" }).click();
  await expect(page.getByRole("heading", { name: "AI 投资教练" })).toBeVisible();

  await page.getByRole("button", { name: "投资 DNA" }).click();
  await expect(page.getByRole("heading", { name: "投资 DNA" })).toBeVisible();

  await page.waitForTimeout(800);
  expectClean(w);
});
