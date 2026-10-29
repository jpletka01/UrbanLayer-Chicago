import { expect, test } from "@playwright/test";

test.skip(
  ({ browserName, viewport }) => browserName !== "chromium" || viewport?.width !== 360,
  "Run the breakpoint matrix once in Chromium",
);

test("Discovery keeps usable panes across phone, tablet, and desktop widths", async ({ page }, testInfo) => {
  const cases = [
    { width: 390, minMapWidth: 389, threePane: false },
    { width: 768, minMapWidth: 400, threePane: false },
    { width: 1024, minMapWidth: 600, threePane: false },
    { width: 1440, minMapWidth: 400, threePane: true },
  ];

  for (const { width, minMapWidth, threePane } of cases) {
    await page.setViewportSize({ width, height: 900 });
    const searchWait = page.waitForResponse(
      (response) => response.url().includes("/search"),
      { timeout: 90_000 },
    ).catch(() => null);
    await page.goto("/discovery", { waitUntil: "domcontentloaded" });
    // The Start panel (nothing runs on arrival): pick the first recipe, one explicit search.
    await page.getByTestId("discovery-start-recipe-vacant_mf_transit").click();
    await searchWait;

    const toggle = page.getByRole("group", { name: "View" });
    const listPane = page.getByTestId("discovery-list-pane");
    const mapPane = page.getByTestId("discovery-map-pane");
    if (threePane) {
      await expect(toggle).toBeHidden();
      await expect(listPane).toBeVisible();
      await expect(mapPane).toBeVisible();
    } else {
      await expect(toggle).toBeVisible();
      await expect(listPane).toBeVisible();
      await expect(mapPane).toBeHidden();
      await page.getByRole("button", { name: "Map", exact: true }).click();
      await expect(listPane).toBeHidden();
    }
    await expect(mapPane).toBeVisible();
    const mapBox = await mapPane.boundingBox();
    expect(mapBox).not.toBeNull();
    expect(mapBox!.width).toBeGreaterThanOrEqual(minMapWidth);
    const keyButton = page.getByTestId("discovery-map-key-button");
    const keyPanel = page.getByTestId("discovery-map-legend");
    if (width < 768) {
      await expect(keyButton).toBeVisible();
      await expect(keyPanel).toBeHidden();
      await keyButton.click();
      await expect(keyPanel).toBeVisible();
    } else {
      await expect(keyButton).toBeHidden();
      await expect(keyPanel).toBeVisible();
    }
    await page.screenshot({ path: testInfo.outputPath(`discovery-${width}.png`) });
  }
});

// Phase 0 (draft + explicit apply): the strip, the Update results button and the dimmed
// previous results must fit every width, and a refresh must never blank the page.
test("Discovery keeps previous results on screen, dimmed, while an applied edit refreshes", async ({ page }, testInfo) => {
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    let delayMs = 0;
    let searchRequests = 0;
    await page.route("**/api/discovery/search**", async (route) => {
      searchRequests += 1;
      if (delayMs) await new Promise((resolve) => setTimeout(resolve, delayMs));
      await route.continue();
    });
    await page.goto("/discovery", { waitUntil: "domcontentloaded" });
    await page.getByTestId("discovery-start-recipe-vacant_mf_transit").click();
    const body = page.getByTestId("discovery-results-body");
    await expect(body).toHaveAttribute("data-stale", "false", { timeout: 90_000 });
    const rowsBefore = await page.getByTestId("discovery-result-row").count();
    expect(rowsBefore).toBeGreaterThan(0);
    await page.waitForTimeout(1500);

    // Draft edits only: nothing is requested.
    const requestsBefore = searchRequests;
    const chips = page.getByTestId("discovery-chips");
    await chips.getByRole("button", { name: /^Remove / }).first().click();
    await chips.getByRole("button", { name: /^Remove / }).first().click();
    await expect(page.getByTestId("discovery-update-results").first()).toContainText("(2)");
    await expect(page.getByTestId("discovery-result-row")).toHaveCount(rowsBefore);
    expect(searchRequests).toBe(requestsBefore);
    await page.screenshot({ path: testInfo.outputPath(`discovery-pending-${width}.png`) });

    // One press, one search; the old results stay, dimmed and inert.
    delayMs = 3000;
    await page.getByTestId("discovery-update-results").first().click();
    await expect(body).toHaveAttribute("data-stale", "true");
    await expect(body).toHaveAttribute("aria-busy", "true");
    await expect(body).toHaveAttribute("inert", "");
    expect(await page.getByTestId("discovery-result-row").count()).toBe(rowsBefore);
    await expect(page.getByTestId("discovery-chips")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await page.screenshot({ path: testInfo.outputPath(`discovery-refreshing-${width}.png`) });
    await expect(body).toHaveAttribute("data-stale", "false", { timeout: 60_000 });
    // One request when the backend returns the map's points with the list (includePins); two
    // against an older backend, where the page falls back to the separate pins request.
    expect([1, 2]).toContain(searchRequests - requestsBefore);
    delayMs = 0;
    await page.unroute("**/api/discovery/search**");
  }
});
