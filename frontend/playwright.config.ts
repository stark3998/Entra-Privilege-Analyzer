import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  retries: 0,
  use: {
    baseURL:
      "https://ca-entraperm-frontend-prod.mangobay-72292494.eastus.azurecontainerapps.io",
    headless: false,
    viewport: { width: 1440, height: 900 },
    actionTimeout: 15_000,
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
});
