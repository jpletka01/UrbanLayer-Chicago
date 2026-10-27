import { expect, test, type Page } from "@playwright/test";

test.skip(
  ({ browserName, viewport }) => browserName !== "chromium" || viewport?.width !== 360,
  "Run the free/Pro Discovery map fixtures once in Chromium",
);

async function useTier(page: Page, tier: "free" | "admin") {
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

test("free fixture keeps a counted land-use key and row-focus map linkage", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await useTier(page, "free");
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

test("Pro fixture keeps upside interaction and survives a live system-theme swap", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await useTier(page, "admin");
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
