import { defineConfig, devices } from "@playwright/test";

// E2E against the locally-running PROD instance. Start the app first:
//   scripts/start-web.sh         (serves web :3000 + api :8000)
// then:  cd apps/web && npm run e2e
// We deliberately do NOT use a Playwright webServer — the suite runs against the
// real build the user is looking at, not a throwaway dev server.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 2,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome", // use the system /usr/bin/google-chrome
        viewport: { width: 1440, height: 900 },
        launchOptions: { args: ["--no-sandbox", "--disable-gpu"] },
      },
    },
  ],
});
