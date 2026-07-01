import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("AI 工作室:五个 Tab 切换渲染(不触发生成)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/studio");

  await expect(page.getByRole("heading", { name: "AI 工作室" })).toBeVisible();

  // Each tab switches and renders its own structure (do NOT click generate buttons).
  await page.getByRole("button", { name: "多空辩论" }).click();
  await expect(page.getByRole("heading", { name: "多空辩论" })).toBeVisible();
  // Persona seating: a 多头席位 + 空头席位 selector each seat a master (default 通用).
  await expect(page.locator("select").filter({ hasText: "多头席位:通用" })).toBeVisible({ timeout: 10_000 });
  await expect(page.locator("select").filter({ hasText: "空头席位:通用" })).toBeVisible();

  await page.getByRole("button", { name: "多智能体" }).click();
  await expect(page.getByRole("heading", { name: "多智能体投研" })).toBeVisible();

  await page.getByRole("button", { name: "投资人格" }).click();
  // Persona cards load from the API — the roster was expanded to 14 masters.
  await expect(page.getByRole("heading", { name: /Buffett/ })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("heading", { name: /Munger/ })).toBeVisible();  // new master
  // 人格会诊 entry point is present (do NOT click — it bills an LLM run).
  await expect(page.getByRole("button", { name: /全员会诊/ })).toBeVisible();

  await page.getByRole("button", { name: "AI 教练" }).click();
  await expect(page.getByRole("heading", { name: "AI 投资教练" })).toBeVisible();

  await page.getByRole("button", { name: "投资 DNA" }).click();
  await expect(page.getByRole("heading", { name: "投资 DNA" })).toBeVisible();
  // The decision-reflection memory panel renders in the DNA tab (empty state OK).
  await expect(page.getByRole("heading", { name: "决策复盘记忆" })).toBeVisible();

  await page.waitForTimeout(800);
  expectClean(w);
});

test("研究页「解读」:大师会诊入口在个股终端可见(不触发生成)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/research/NVDA");

  // Right-panel 解读 sub-tab hosts the LU AI brain + the 大师会诊 (persona council) block.
  await page.getByRole("button", { name: "解读", exact: true }).click();
  await expect(page.getByText("大师会诊", { exact: true })).toBeVisible({ timeout: 10_000 });
  // Entry point present; do NOT click (bills an LLM run). Either "全员会诊" (empty) or
  // "重新会诊" (cached) shows depending on whether a council was generated before.
  await expect(page.getByRole("button", { name: /全员会诊|重新会诊/ })).toBeVisible();

  await page.waitForTimeout(500);
  expectClean(w);
});
