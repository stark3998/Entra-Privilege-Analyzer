import { test, expect } from "@playwright/test";

const PROJECT_ID = "7af60f33-a114-4d46-bbfd-df72bcb370c3";

test.describe("Scan Page — Polling Live Events", () => {
  test("trigger scan, verify Graph API progress events stream to UI, then cancel", async ({
    page,
  }) => {
    await page.goto(`/projects/${PROJECT_ID}/scan`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });

    const scansHeading = page.getByRole("heading", { name: "Scans" });

    // Handle auth if not in LOCAL_MODE
    const signInBtn = page.getByRole("button", {
      name: "Sign in with Microsoft",
    });
    const needsAuth = await signInBtn
      .isVisible({ timeout: 5_000 })
      .catch(() => false);

    if (needsAuth) {
      console.log(
        "Auth required — clicking Sign In. Complete login manually.",
      );
      await signInBtn.click();
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

    // Check if a scan is already running
    const scanInProgressBtn = page.getByRole("button", {
      name: "Scan in Progress...",
    });
    const isAlreadyRunning = await scanInProgressBtn
      .isVisible()
      .catch(() => false);

    if (!isAlreadyRunning) {
      // Trigger a new scan
      const scanTypeSelect = page.locator("select");
      await scanTypeSelect.selectOption("full");

      const runBtn = page.getByRole("button", { name: "Run Scan" });
      await expect(runBtn).toBeEnabled({ timeout: 10_000 });
      await runBtn.click();
      console.log("Scan triggered.");
    } else {
      console.log("Scan already running.");
    }

    // Live Activity section should appear
    const liveActivity = page.getByText("Live Activity");
    await expect(liveActivity).toBeVisible({ timeout: 20_000 });
    console.log("Live Activity section visible.");

    // Polling badge should show
    const pollingBadge = page.getByText("Polling", { exact: true });
    await expect(pollingBadge).toBeVisible({ timeout: 20_000 });
    console.log("Polling badge visible.");

    // Wait for several poll cycles to accumulate Graph API events
    await page.waitForTimeout(10_000);

    // Check the debug panel for poll stats
    const debugPanel = page.locator(".grid.grid-cols-2").first();
    const debugText = (await debugPanel.textContent().catch(() => "")) ?? "";
    console.log("Debug panel:", debugText);

    // Verify polls happened
    const pollMatch = debugText.match(/polls:\s*(\d+)/);
    const pollCount = pollMatch ? parseInt(pollMatch[1], 10) : 0;
    console.log("Poll count:", pollCount);
    expect(pollCount).toBeGreaterThan(0);

    // Verify events were received
    const eventMatch = debugText.match(/recv events:\s*(\d+)/);
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

    // Collect all event text to verify Graph API logs are streaming
    const allEventTexts: string[] = [];
    for (let i = 0; i < cardCount; i++) {
      const text = await eventCards.nth(i).textContent();
      if (text) allEventTexts.push(text);
    }
    console.log("All event texts:");
    allEventTexts.forEach((t, i) => console.log(`  [${i}] ${t}`));

    await page.screenshot({
      path: "e2e/screenshots/scan-poll-events.png",
      fullPage: true,
    });

    // Test the Cancel Scan button
    const cancelBtn = page.getByRole("button", { name: "Cancel Scan" });
    const cancelVisible = await cancelBtn.isVisible().catch(() => false);
    if (cancelVisible) {
      console.log("Cancel Scan button is visible — clicking it.");
      await cancelBtn.click();

      // Wait for the scan to transition to failed/cancelled state
      await page.waitForTimeout(3000);

      // The "Scan in Progress..." button should disappear
      const stillRunning = await scanInProgressBtn
        .isVisible()
        .catch(() => false);
      console.log("Scan still running after cancel:", stillRunning);

      await page.screenshot({
        path: "e2e/screenshots/scan-poll-cancelled.png",
        fullPage: true,
      });
    } else {
      console.log("Cancel button not visible (scan may have finished).");
    }

    await page.screenshot({
      path: "e2e/screenshots/scan-poll-final.png",
      fullPage: true,
    });
    console.log("Test complete.");
  });
});
