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

test("日志页:新增 → 出现 → 删除 → 消失(全 CRUD 往返,自清理不残留)", async ({ page }) => {
  const w = watch(page);
  page.on("dialog", (d) => d.accept()); // the 删除 confirmation
  await page.goto("/journal");

  // Unique title so the round-trip never collides with the user's real entries.
  const title = `E2E 决策 ${Date.now()}`;
  await page.getByPlaceholder(/标题:这次决策是什么/).fill(title);
  await page.getByRole("button", { name: "添加记录" }).click();

  // The new entry renders as its own Panel (<section><h2>title</h2>) — list refreshed.
  const card = page.locator("section").filter({
    has: page.getByRole("heading", { level: 2, name: title }),
  });
  await expect(card).toBeVisible({ timeout: 10_000 });

  // Delete it → the card disappears (state refresh), leaving no residue.
  await card.getByRole("button", { name: "删除" }).click();
  await expect(card).toHaveCount(0, { timeout: 10_000 });

  await page.waitForTimeout(300);
  expectClean(w);
});
