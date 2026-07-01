import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("组合页:概览 / 分布 / 相关性 / 点评入口", async ({ page }) => {
  const w = watch(page);
  await page.goto("/portfolio");

  await expect(page.getByRole("heading", { name: "组合", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "新增 / 导入持仓" })).toBeVisible();

  // With holdings present, the analytics panels render; otherwise the empty-state shows.
  const sector = page.getByRole("heading", { name: "行业分布" });
  const empty = page.getByText("还没有持仓", { exact: false });
  await expect(sector.or(empty).first()).toBeVisible({ timeout: 15_000 });

  // When holdings exist, each row exposes 编辑 / 删除 actions (do NOT click 删除 — it mutates
  // the user's portfolio; we only assert the controls render).
  if (await sector.isVisible().catch(() => false)) {
    await expect(page.getByRole("columnheader", { name: "操作" })).toBeVisible();
    await expect(page.getByRole("button", { name: "编辑" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "删除" }).first()).toBeVisible();
    // The deterministic performance tear-sheet panel renders alongside the analytics.
    await expect(page.getByRole("heading", { name: "绩效 tear-sheet" })).toBeVisible();
  }

  // AI review entry exists (do NOT click — it triggers a slow/billed claude -p call).
  await expect(page.getByRole("heading", { name: "AI 组合点评" })).toBeVisible();

  await page.waitForTimeout(1000);
  expectClean(w);
});
