import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("推荐页:分类加载 + 列表渲染(不触发生成)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/recommendations");

  await expect(page.getByRole("heading", { name: "AI 推荐" })).toBeVisible();
  // Category chips load from the API.
  await expect(page.getByRole("button", { name: "成长", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "AI 半导体", exact: true })).toBeVisible();

  // Default category (ai) either shows recommendation cards or the empty prompt — never broken.
  const card = page.locator("text=查看研究 →").first();
  const empty = page.getByText("还没有", { exact: false });
  await expect(card.or(empty).first()).toBeVisible({ timeout: 15_000 });

  await page.waitForTimeout(1000);
  expectClean(w);
});
