import { Page, expect } from "@playwright/test";

// Console-error / failed-request collectors. Attach at the very start of a test,
// read the arrays after the page settles. Known third-party / benign noise is
// filtered so a green run really means "no app errors".
const IGNORE_CONSOLE = [
  /favicon/i,
  /Download the React DevTools/i,
  /\[Fast Refresh\]/i,
  /ResizeObserver loop/i, // benign, fired by chart resize observers
];

export type Watcher = {
  consoleErrors: string[];
  badResponses: string[];
};

export function watch(page: Page): Watcher {
  const w: Watcher = { consoleErrors: [], badResponses: [] };
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    if (IGNORE_CONSOLE.some((re) => re.test(text))) return;
    w.consoleErrors.push(text);
  });
  page.on("response", (res) => {
    const url = res.url();
    if (url.includes("/api/") && res.status() >= 500) {
      w.badResponses.push(`${res.status()} ${url}`);
    }
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (url.includes("/api/")) w.badResponses.push(`FAILED ${url} (${req.failure()?.errorText})`);
  });
  return w;
}

// Assert the page produced no app console errors and no 5xx/failed API calls.
export function expectClean(w: Watcher) {
  expect(w.consoleErrors, `console errors:\n${w.consoleErrors.join("\n")}`).toEqual([]);
  expect(w.badResponses, `failed API responses:\n${w.badResponses.join("\n")}`).toEqual([]);
}
