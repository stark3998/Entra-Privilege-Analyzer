import { test, expect } from "@playwright/test";

const PROJECT_ID = "7af60f33-a114-4d46-bbfd-df72bcb370c3";

test.describe("Scan Page — Polling Live Events", () => {
  test("verify scan page loads and polling delivers events", async ({
    page,
  }) => {
    await page.goto(`/projects/${PROJECT_ID}/scan`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });

    const scansHeading = page.getByRole("heading", { name: "Scans" });

    // Handle auth — MSAL may show an in-app LoginGate or redirect to AAD
    const signInBtn = page.getByRole("button", {
      name: "Sign in with Microsoft",
    });
    const needsAuth =
      (await signInBtn.isVisible({ timeout: 5_000 }).catch(() => false)) ||
      page.url().includes("login.microsoftonline.com");

    if (needsAuth) {
      console.log(
        "Auth required — clicking Sign In. Complete login manually in the browser.",
      );
      if (await signInBtn.isVisible()) {
        await signInBtn.click();
      }
      // Wait for user to complete MSAL login and redirect back
      await page.waitForURL(`**/projects/${PROJECT_ID}/scan`, {
        timeout: 120_000,
      });
      await page.waitForTimeout(5000);
    }

    await expect(scansHeading).toBeVisible({ timeout: 15_000 });
    console.log("Scan page loaded.");

    await page.screenshot({
      path: "e2e/screenshots/scan-poll-initial.png",
      fullPage: true,
    });

    // Check if a scan is running (stuck or active)
    const scanInProgressBtn = page.getByRole("button", {
      name: "Scan in Progress...",
    });
    const isAlreadyRunning = await scanInProgressBtn
      .isVisible()
      .catch(() => false);

    if (!isAlreadyRunning) {
      // Select delegated mode + full scan, then trigger
      const myCredsBtn = page.getByRole("button", { name: "My Credentials" });
      if (await myCredsBtn.isVisible()) {
        await myCredsBtn.click();
      }
      const scanTypeSelect = page.locator("select");
      await scanTypeSelect.selectOption("full");

      const runBtn = page.getByRole("button", { name: "Run Scan" });
      await expect(runBtn).toBeEnabled({ timeout: 10_000 });
      await runBtn.click();
      console.log("Scan triggered.");
    } else {
      console.log("Scan already running — testing polling on existing scan.");
    }

    // The Live Activity section should appear
    const liveActivity = page.getByText("Live Activity");
    await expect(liveActivity).toBeVisible({ timeout: 20_000 });
    console.log("Live Activity section visible.");

    // The Polling badge should appear instead of Connected (SSE)
    const pollingBadge = page.getByText("Polling", { exact: true });
    await expect(pollingBadge).toBeVisible({ timeout: 20_000 });
    console.log("Polling badge visible.");

    // Wait for a few poll cycles (6s = 3 polls)
    await page.waitForTimeout(6000);

    // Check the debug panel shows polling stats
    const debugPanel = page.locator(".grid.grid-cols-2").first();
    const debugText = await debugPanel.textContent().catch(() => "");
    console.log("Debug panel:", debugText);

    // Verify polls happened
    expect(debugText).toContain("polls:");
    const pollMatch = debugText?.match(/polls:\s*(\d+)/);
    const pollCount = pollMatch ? parseInt(pollMatch[1], 10) : 0;
    console.log("Poll count:", pollCount);
    expect(pollCount).toBeGreaterThan(0);

    // Verify events were received
    const eventMatch = debugText?.match(/recv events:\s*(\d+)/);
    const eventCount = eventMatch ? parseInt(eventMatch[1], 10) : 0;
    console.log("Received events:", eventCount);
    expect(eventCount).toBeGreaterThan(0);

    // Count event cards in the Live Activity stream
    const eventCards = page.locator(
      ".rounded-lg.border.border-slate-800.bg-slate-900",
    );
    const cardCount = await eventCards.count();
    console.log("Event cards in UI:", cardCount);
    expect(cardCount).toBeGreaterThan(0);

    await page.screenshot({
      path: "e2e/screenshots/scan-poll-final.png",
      fullPage: true,
    });
    console.log("Test passed — polling is delivering events to the UI.");
  });
});
