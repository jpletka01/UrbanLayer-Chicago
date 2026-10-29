import { expect, test, type Page } from "@playwright/test";

test.skip(
  ({ browserName, viewport }) => browserName !== "chromium" || viewport?.width !== 360,
  "Run the free/Pro Discovery map fixtures once in Chromium",
);

async function useTier(page: Page, baseURL: string | undefined, tier: "free" | "admin") {
  // The mocked /api/auth/me below can't issue the double-submit cookie a real
  // one would. Dev backends skip the CSRF check; production enforces it, so
  // without this every Discovery POST 403s and the map reads "unavailable".
  await page.context().addCookies([
    { name: "csrf_token", value: "e2e-fixture", url: baseURL ?? "http://localhost:5173" },
  ]);
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        auth_required: true,
        user: {
          id: `fixture-${tier}`,
          email: `${tier}@example.com`,
          name: tier === "free" ? "Free fixture" : "Pro fixture",
          picture_url: null,
          tier,
        },
      }),
    });
  });
}

async function openDiscovery(page: Page, expectDesktopKey = true) {
  const searchWait = page.waitForResponse(
    (response) => response.url().includes("/api/discovery/search"),
    { timeout: 90_000 },
  );
  await page.goto("/discovery", { waitUntil: "domcontentloaded" });
  await searchWait;
  if (expectDesktopKey) await expect(page.getByTestId("discovery-map-legend")).toBeVisible();
}

test("free fixture keeps a counted land-use key and row-focus map linkage", async ({ page, baseURL }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await useTier(page, baseURL, "free");
  await openDiscovery(page, false);

  await page.getByRole("button", { name: "Map", exact: true }).click();
  const keyButton = page.getByTestId("discovery-map-key-button");
  await expect(keyButton).toBeVisible();
  await keyButton.click();

  const key = page.getByTestId("discovery-map-legend");
  await expect(key).toBeVisible();
  await expect(key).toContainText("Property use");
  const keyBox = await key.boundingBox();
  expect(keyBox).not.toBeNull();
  expect(keyBox!.x).toBeGreaterThanOrEqual(0);
  expect(keyBox!.x + keyBox!.width).toBeLessThanOrEqual(391);
  await page.screenshot({ path: testInfo.outputPath("discovery-free-phone-key.png") });

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.getByText("Export (Pro)")).toBeVisible();
  const firstRow = page.getByTestId("discovery-result-row").first();
  await firstRow.focus();
  await expect(firstRow).toBeFocused();
  await page.screenshot({ path: testInfo.outputPath("discovery-free-row-focus.png") });
});

test("Pro fixture keeps upside interaction and survives a live system-theme swap", async ({ page, baseURL }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await useTier(page, baseURL, "admin");
  await page.emulateMedia({ colorScheme: "dark" });
  await page.addInitScript(() => localStorage.setItem("urbanlayer-theme", "system"));
  await openDiscovery(page);

  const key = page.getByTestId("discovery-map-legend");
  await expect(key).toContainText("Redevelopment upside");
  const firstRow = page.getByTestId("discovery-result-row").first();
  await firstRow.hover();
  await expect(firstRow.locator("span.bg-accent")).toBeVisible();

  const lightStyle = page.waitForResponse(
    (response) => response.url().includes("mapbox/light-v11"),
    { timeout: 30_000 },
  );
  await page.emulateMedia({ colorScheme: "light" });
  await lightStyle;
  await expect(page.getByTestId("discovery-map-pane").locator("canvas.mapboxgl-canvas")).toBeVisible();
  await expect(key).toContainText("Redevelopment upside");
  await page.screenshot({ path: testInfo.outputPath("discovery-pro-light-theme.png") });
});

test("Pro fixture dims and disarms the previous dots during a refresh, and respects a moved camera", async ({ page, baseURL }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await useTier(page, baseURL, "admin");
  let delayMs = 0;
  await page.route("**/api/discovery/search**", async (route) => {
    if (delayMs) await new Promise((resolve) => setTimeout(resolve, delayMs));
    await route.continue();
  });
  await openDiscovery(page);
  const body = page.getByTestId("discovery-results-body");
  await expect(body).toHaveAttribute("data-stale", "false");
  const key = page.getByTestId("discovery-map-legend");
  await expect(key).toContainText("Redevelopment upside");
  await page.waitForTimeout(1500);

  // The user takes the camera.
  const mapBox = (await page.getByTestId("discovery-map-container").boundingBox())!;
  await page.mouse.move(mapBox.x + mapBox.width / 2, mapBox.y + mapBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(mapBox.x + mapBox.width / 2 + 120, mapBox.y + mapBox.height / 2 + 60, { steps: 8 });
  await page.mouse.up();

  await page.getByTestId("discovery-chips").getByRole("button", { name: /^Remove / }).first().click();
  delayMs = 3000;
  await page.getByTestId("discovery-update-results").first().click();

  // Previous dots stay (key still counted from the previous model) but are flagged stale.
  await expect(page.getByTestId("discovery-map-stale")).toHaveText("Previous results, updating");
  await expect(key).toContainText("Redevelopment upside");
  await expect(page.getByTestId("discovery-map-pane").locator("canvas.mapboxgl-canvas")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("discovery-pro-stale-map.png") });

  // New dots arrive; the moved camera is left alone and a button offers the fit.
  await expect(body).toHaveAttribute("data-stale", "false", { timeout: 60_000 });
  await expect(page.getByTestId("discovery-map-stale")).toHaveCount(0);
  await expect(page.getByTestId("discovery-map-zoom")).toBeVisible();
  await page.getByTestId("discovery-map-zoom").click();
  await expect(page.getByTestId("discovery-map-zoom")).toHaveCount(0);
  delayMs = 0;
});
