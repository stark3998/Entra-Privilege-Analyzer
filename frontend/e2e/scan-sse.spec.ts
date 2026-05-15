import { test, expect } from "@playwright/test";

const PROJECT_ID = "7af60f33-a114-4d46-bbfd-df72bcb370c3";

test.describe("Scan Page — SSE Log Streaming", () => {
  test("trigger scan and verify live activity receives SSE events", async ({
    page,
  }) => {
    // The deployed app uses MSAL auth — we need to handle the login flow.
    // Navigate to the scan page; MSAL may redirect to login.
    await page.goto(`/projects/${PROJECT_ID}/scan`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });

    // If we're redirected to a login page, pause so the tester can log in manually
    const currentUrl = page.url();
    const scansHeading = page.getByRole("heading", { name: "Scans" });

    if (
      currentUrl.includes("login.microsoftonline.com") ||
      currentUrl.includes("LoginGate")
    ) {
      console.log(
        "Auth required — please log in manually in the browser window.",
      );
      console.log("Current URL:", currentUrl);

      // Wait for navigation back to the scan page after manual login
      await page.waitForURL(`**/projects/${PROJECT_ID}/scan`, {
        timeout: 120_000,
      });

      await page.waitForTimeout(5000);
    }

    // Now we should be on the Scan page
    await expect(scansHeading).toBeVisible({ timeout: 15_000 });
    console.log("Scan page loaded successfully.");

    // Take a screenshot of the initial state
    await page.screenshot({
      path: "e2e/screenshots/scan-page-initial.png",
      fullPage: true,
    });

    // Check if a scan is already running
    const scanInProgressBtn = page.getByRole("button", {
      name: "Scan in Progress...",
    });
    const isAlreadyRunning = await scanInProgressBtn.isVisible().catch(() => false);

    if (isAlreadyRunning) {
      console.log("A scan is already running — skipping trigger, testing SSE stream directly.");
    } else {
      // Select "My Credentials" (delegated mode)
      const myCredsBtn = page.getByRole("button", {
        name: "My Credentials",
      });
      if (await myCredsBtn.isVisible()) {
        await myCredsBtn.click();
      }

      // Select full scan
      const scanTypeSelect = page.locator("select");
      await scanTypeSelect.selectOption("full");

      // Click Run Scan
      const runBtn = page.getByRole("button", { name: "Run Scan" });
      await expect(runBtn).toBeEnabled({ timeout: 10_000 });
      await runBtn.click();
      console.log("Scan triggered.");
    }

    // Wait for the "Live Activity" section to appear
    const liveActivity = page.getByText("Live Activity");
    await expect(liveActivity).toBeVisible({ timeout: 20_000 });
    console.log("Live Activity section visible.");

    // Wait for the "Connected" badge
    const connectedBadge = page.getByText("Connected");
    await expect(connectedBadge).toBeVisible({ timeout: 20_000 });
    console.log("SSE Connected badge visible.");

    // --- Capture SSE debug state over time ---

    // Wait up to 30s, polling every 2s, to give SSE time to connect
    for (let i = 0; i < 15; i++) {
      await page.waitForTimeout(2000);
      const debug = await page.evaluate(() => window.__scanStreamDebug);
      console.log(
        `[${i * 2}s] debug:`,
        JSON.stringify(debug, null, 2),
      );
      if (debug?.chunkCount && debug.chunkCount > 0) {
        console.log("SSE chunks detected!");
        break;
      }
    }

    // Capture the UI debug panel text
    const debugPanelText = await page
      .locator(".grid.grid-cols-2")
      .first()
      .textContent()
      .catch(() => "debug panel not found");
    console.log("UI debug panel:", debugPanelText);

    // Count event cards
    const eventCards = page.locator(
      ".rounded-lg.border.border-slate-800.bg-slate-900",
    );
    const eventCount = await eventCards.count();
    console.log("Event cards in UI:", eventCount);

    // Final debug state
    const finalDebug = await page.evaluate(() => window.__scanStreamDebug);
    console.log(
      "Final SSE debug state:",
      JSON.stringify(finalDebug, null, 2),
    );

    // Take screenshot
    await page.screenshot({
      path: "e2e/screenshots/scan-sse-final.png",
      fullPage: true,
    });
    console.log("Screenshot saved.");

    // --- Assertions ---
    // These will tell us whether SSE is working on the deployed version
    expect(finalDebug).toBeTruthy();
    expect(finalDebug!.responseStatus).toBe(200);
    expect(finalDebug!.chunkCount).toBeGreaterThan(0);
    expect(finalDebug!.parsedEventCount).toBeGreaterThan(0);
  });
});
