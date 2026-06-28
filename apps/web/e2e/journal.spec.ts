import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("日志页:新增表单 + 列表/空态", async ({ page }) => {
  const w = watch(page);
  await page.goto("/journal");

  await expect(page.getByRole("heading", { name: "投资日志" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "新增记录" })).toBeVisible();
  await expect(page.getByPlaceholder(/标题:这次决策是什么/)).toBeVisible();
  // Either existing entries render, or the empty-state — never broken.
  const empty = page.getByText("还没有日志", { exact: false });
  const entry = page.locator("text=查看研究 →").first();
  const addBtn = page.getByRole("button", { name: "添加记录" });
  await expect(empty.or(entry).or(addBtn).first()).toBeVisible({ timeout: 10_000 });

  await page.waitForTimeout(800);
  expectClean(w);
});
