import { test, expect } from "@playwright/test";
import { watch, expectClean } from "./_helpers";

test("对话页:加载 + 建议 + 输入框(不触发 LLM)", async ({ page }) => {
  const w = watch(page);
  await page.goto("/chat");

  await expect(page.getByRole("heading", { name: "AI 对话" })).toBeVisible();
  // Either prior history renders, or the empty-state suggestions show — never broken.
  const suggestion = page.getByText("现在的多空逻辑", { exact: false });
  const bubble = page.locator("div.rounded-2xl").first();
  await expect(suggestion.or(bubble).first()).toBeVisible({ timeout: 10_000 });
  // The composer is present (do NOT send — that triggers a slow/billed claude -p call).
  await expect(page.getByPlaceholder(/问 LU 任何投研问题/)).toBeVisible();

  await page.waitForTimeout(800);
  expectClean(w);
});
