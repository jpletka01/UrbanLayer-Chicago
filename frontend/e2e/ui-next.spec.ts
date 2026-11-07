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
