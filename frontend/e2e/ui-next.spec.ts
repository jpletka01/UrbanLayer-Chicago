import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * The new UI's local release gates (decision Items 75–76), beside the overflow audit:
 *   - Playwright axe (WCAG 2 A/AA, color contrast included) on every preview route, light and dark;
 *   - Spanish at 360 px: no horizontal overflow and the Spanish strings on screen;
 *   - a keyboard walkthrough: Tab reaches the side panel, the tools, the tabs; the Ask drawer opens and
 *     closes from the keyboard and focus returns to Ask.
 * Needs the dev stack (vite :5173 + backend :8001). No question is ever sent to the analyst.
 */

const ROUTES = [
  { id: "search", path: "/scorecard?ui=next" },
  { id: "profile", path: "/scorecard?address=1601%20N%20Milwaukee%20Ave&ui=next", ready: "answer-sentence" },
  { id: "discovery", path: "/discovery?ui=next" },
];

async function open(page: Page, path: string, ready?: string) {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  if (ready) await page.getByTestId(ready).waitFor({ timeout: 90_000 });
  else await page.locator(".ui-next").first().waitFor();
  await page.waitForTimeout(800);
}

async function axe(page: Page) {
  const result = await new AxeBuilder({ page })
    .include(".ui-next")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    // The map canvas and Mapbox's own controls are third-party.
    .exclude(".mapboxgl-map")
    .analyze();
  return result.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
}

for (const scheme of ["light", "dark"] as const) {
  for (const route of ROUTES) {
    test(`axe ${scheme}: ${route.id}`, async ({ page }, testInfo) => {
      test.skip(testInfo.project.name !== "Pixel 3", "axe runs once, on one device");
      await page.emulateMedia({ colorScheme: scheme });
      await open(page, route.path, route.ready);
      expect(await axe(page)).toEqual([]);
      if (route.id === "profile") {
        await page.getByRole("tab", { name: "Build" }).click();
        await page.waitForTimeout(300);
        expect(await axe(page)).toEqual([]);
      }
    });
  }
}

test("Spanish at 360 px: no overflow, Spanish on screen", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "Galaxy S24", "the 360 px device");
  await page.addInitScript(() => localStorage.setItem("urbanlayer-language", "es"));
  for (const route of ROUTES) {
    await open(page, route.path, route.ready);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${route.id} overflow`).toBeLessThanOrEqual(1);
    await expect(page.getByText("Vista previa", { exact: true })).toBeVisible();
    if (route.id === "profile") {
      await page.getByRole("tab", { name: "Construir" }).click();
      await page.waitForTimeout(300);
      const after = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(after, "Build tab overflow (es)").toBeLessThanOrEqual(1);
    }
  }
});

test("keyboard walkthrough of the preview Profile", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "Pixel 3", "once");
  await page.setViewportSize({ width: 1280, height: 800 });
  await open(page, ROUTES[1].path, ROUTES[1].ready);
  const ask = page.getByTestId("tool-ask-top");
  await ask.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("ask-drawer")).toBeVisible();
  await expect(page.getByLabel("Your question")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("ask-drawer")).toBeHidden();
  await expect(ask).toBeFocused();
  await page.getByRole("tab", { name: "Overview" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Build" })).toHaveAttribute("aria-selected", "true");
  // Tab from the top of a fresh load reaches the side panel's destinations before the page.
  await open(page, "/scorecard?ui=next");
  const seen: string[] = [];
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press("Tab");
    seen.push(await page.evaluate(() => document.activeElement?.getAttribute("aria-label") || document.activeElement?.textContent?.trim() || ""));
  }
  expect(seen.join(" | ")).toMatch(/Search.*Discovery.*Chat/);
});

// Progressive loading (decision Items 82, 89): the Overview part is held back so the first screen can be checked,
// then released; a late part is held so its waiting line can be checked. The map must survive every swap (same
// canvas), the figures must not jump, and the tools that read the whole Profile turn on once every part is in.
test("first screen, then the Overview, then the late parts: axe, no overflow, one map", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "Galaxy S24", "the 360 px device");
  let release: () => void = () => {};
  const held = new Promise<void>((r) => { release = r; });
  let releaseLate: () => void = () => {};
  const heldLate = new Promise<void>((r) => { releaseLate = r; });
  await page.route(/\/api\/profile\/overview\?/, async (route) => { await held; await route.continue(); });
  await page.route(/\/api\/profile\/part\/activity\?/, async (route) => { await heldLate; await route.continue(); });
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto(ROUTES[1].path, { waitUntil: "domcontentloaded" });
    await page.getByTestId("first-sentence").waitFor({ timeout: 60_000 });
    await page.waitForTimeout(500);
    expect(await axe(page), `axe ${scheme}`).toEqual([]);
  }
  await expect(page.getByTestId("still-checking")).toBeVisible();
  await expect(page.getByTestId("tool-ask-top")).toBeDisabled();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "first screen overflow").toBeLessThanOrEqual(1);
  const floor = (await page.getByTestId("first-sentence").textContent())?.match(/up to ([\d,]+) sq ft of floor area/)?.[1];
  await page.evaluate(() => { const c = document.querySelector<HTMLCanvasElement>('[data-testid="map-band"] canvas'); if (c) c.dataset.probe = "first"; });
  release();
  await page.getByTestId("answer-sentence").waitFor({ timeout: 90_000 });
  expect(await page.evaluate(() => document.querySelector<HTMLCanvasElement>('[data-testid="map-band"] canvas')?.dataset.probe)).toBe("first");
  // The Overview is in; the held part is named while it waits, and the whole-Profile tools wait with it.
  await expect(page.getByTestId("parts-waiting")).toContainText("crime, 311 and building violations");
  await expect(page.getByTestId("tool-ask-top")).toBeDisabled();
  expect(await axe(page), "axe with parts waiting").toEqual([]);
  releaseLate();
  await expect(page.getByTestId("tool-ask-top")).toBeEnabled({ timeout: 90_000 });
  await expect(page.getByTestId("parts-waiting")).toHaveCount(0);
  expect(await page.evaluate(() => document.querySelector<HTMLCanvasElement>('[data-testid="map-band"] canvas')?.dataset.probe)).toBe("first");
  const after = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(after, "complete profile overflow").toBeLessThanOrEqual(1);
  await page.getByRole("tab", { name: "Build" }).click();
  if (floor) await expect(page.getByText(`${floor} sq ft allowed`, { exact: false }).first()).toBeVisible();
});
