import { expect, test, type Page } from "@playwright/test";

// Phase 4a: the phone layout, on every device in the panel (these run on all five projects).
//   - after a search the header is collapsed, so the list gets the screen
//   - controls are real touch targets (44 px) on a coarse pointer
//   - the Add filter sheet applies pending edits with "Show results"

async function searchRecipe(page: Page) {
  const searchWait = page.waitForResponse(
    (r) => r.url().includes("/api/discovery/search") && !r.url().includes("/pins"),
    { timeout: 90_000 },
  );
  await page.goto("/discovery", { waitUntil: "domcontentloaded" });
  await page.getByTestId("discovery-start-recipe-vacant_mf_transit").click();
  await searchWait;
  await expect(page.getByTestId("discovery-result-row").first()).toBeVisible({ timeout: 30_000 });
}

test("a search leaves a collapsed header and room for the list", async ({ page }) => {
  await searchRecipe(page);
  const toggle = page.getByTestId("discovery-header-toggle");
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");

  const m = await page.evaluate(() => {
    const vh = window.innerHeight;
    const header = document.querySelector('[data-testid="discovery-header"]')!.getBoundingClientRect();
    const rows = [...document.querySelectorAll('[data-testid="discovery-result-row"]')];
    const visible = rows.filter((r) => {
      const b = r.getBoundingClientRect();
      return b.top >= 0 && b.bottom <= vh;
    });
    return { vh, headerH: Math.round(header.height), headerBottom: Math.round(header.bottom), fullyVisibleRows: visible.length };
  });
  // The header was 381 to 415 px (45% to 62% of a phone) and left one row on an iPhone SE.
  expect(m.headerBottom, `header bottom ${m.headerBottom}px of ${m.vh}px`).toBeLessThan(m.vh * 0.4);
  expect(m.fullyVisibleRows, `${m.fullyVisibleRows} result rows fully visible`).toBeGreaterThanOrEqual(3);
});

test("controls are 44 px touch targets on a coarse pointer", async ({ page }) => {
  await searchRecipe(page);
  const coarse = await page.evaluate(() => window.matchMedia("(pointer: coarse)").matches);
  test.skip(!coarse, "this device profile reports a fine pointer");

  const sized = async (loc: ReturnType<Page["getByTestId"]>, name: string) => {
    const b = await loc.boundingBox();
    expect(b, name).not.toBeNull();
    expect(b!.height, `${name} height`).toBeGreaterThanOrEqual(43.5);
  };
  await sized(page.getByTestId("discovery-new-search"), "New search");
  await sized(page.getByTestId("discovery-header-toggle"), "header summary button");
  await sized(page.getByRole("button", { name: "List", exact: true }), "List tab");
  await sized(page.getByRole("button", { name: "Map", exact: true }), "Map tab");

  await page.getByTestId("discovery-header-toggle").click();
  await sized(page.getByRole("button", { name: "Search", exact: true }), "Search");
  await sized(page.getByRole("textbox", { name: "Describe what you're looking for" }), "describe box");
  await sized(page.locator('[data-testid="discovery-header"] select'), "sort select");

  // Pills and icons keep their look and grow an invisible hit area to 44 px: 17 px above and below
  // the centre of the chip's x and of the Add filter pill must still land on that control (a
  // little past that is the neighbouring control's own target, which is as it should be).
  const hits = await page.evaluate(() => {
    const out: Record<string, boolean> = {};
    const hitTest = (el: Element | null, dy: number) => {
      if (!el) return false;
      const b = el.getBoundingClientRect();
      const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2 + dy);
      return hit === el || (hit !== null && el.contains(hit));
    };
    const x = document.querySelector('[data-testid="discovery-chips"] button[aria-label^="Remove"]');
    const add = document.querySelector('[data-testid="discovery-add-filter"]');
    out["chip x up"] = hitTest(x, -17);
    out["chip x down"] = hitTest(x, 17);
    out["add filter up"] = hitTest(add, -17);
    out["add filter down"] = hitTest(add, 17);
    return out;
  });
  for (const [name, ok] of Object.entries(hits)) expect(ok, name).toBe(true);
});

test("the Add filter sheet applies pending edits with Show results", async ({ page }) => {
  await searchRecipe(page);
  let searches = 0;
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/api/discovery/search") && !r.url().includes("/pins")) searches += 1;
  });

  await page.getByTestId("discovery-header-toggle").click();
  await page.getByTestId("discovery-add-filter").click();
  const sheet = page.getByTestId("discovery-filter-popover");
  await expect(sheet).toBeVisible();
  const box = await sheet.boundingBox();
  const vp = page.viewportSize()!;
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(vp.width + 1); // a full-width bottom sheet, no overflow
  expect(Math.round(box!.y + box!.height)).toBeGreaterThanOrEqual(vp.height - 1);

  await sheet.getByRole("button", { name: /^TIF district/ }).click(); // a flag: adds as Yes
  const action = page.getByTestId("discovery-sheet-footer-action");
  await expect(action).toHaveText(/Show results \(1\)/);
  expect(searches, "nothing is requested until the user asks").toBe(0);
  const abox = await action.boundingBox();
  expect(abox!.height).toBeGreaterThanOrEqual(43.5);

  await action.click();
  await expect(sheet).toBeHidden();
  await expect.poll(() => searches, { timeout: 30_000 }).toBe(1);
  // the new result lands: the header folds away again
  await expect(page.getByTestId("discovery-header-toggle")).toHaveAttribute("aria-expanded", "false", { timeout: 60_000 });
  await expect(page.getByTestId("discovery-update-results")).toHaveCount(0);
});
