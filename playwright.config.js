import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/frontend",
  fullyParallel: true,
  workers: 2,
  reporter: "list",
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR || "test-results",
  use: { baseURL: "http://127.0.0.1:18763", browserName: "chromium", timezoneId: "America/Los_Angeles" },
  webServer: {
    command: "node tests/frontend/server.js",
    url: "http://127.0.0.1:18763",
    reuseExistingServer: false,
  },
});
