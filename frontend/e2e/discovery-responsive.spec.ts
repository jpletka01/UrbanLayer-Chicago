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
    await page.screenshot({ path: testInfo.outputPath(`discovery-${width}.png`) });
  }
});
