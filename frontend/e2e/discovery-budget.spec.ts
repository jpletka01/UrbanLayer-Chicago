// Discovery's page budget (decision Item 57), modelled on the Profile's (profile-budget.spec.ts, Item 51):
// the first screen of the Start panel and of a recipe's results, desktop and phone, may not exceed its word,
// amber and solid-orange counts, and no heading may appear twice. The dot preview may not exceed its words.
//
// Ratchet: words and solid orange in discovery-budget.baseline.json may only go DOWN; amber is held to its
// cap. `BUDGET_UPDATE=1` lowers entries that improved and never raises one: raising a budget is a hand edit
// of the JSON with its reason in the PR and a decision Item.
//
// Runs once (in the "Pixel 3" project; it opens its own desktop and phone contexts) as part of
// `npm run test:mobile`. Needs the dev stack with a Discovery index; CI does not run it.
import { expect, test, type Browser, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { firstScreenCounts, type Counts } from "./budgetMeasure";

const BASELINE = path.resolve("e2e/discovery-budget.baseline.json");
const CAPS = {
  "start/desktop": { words: 260, amber: 3, orange: 1 },
  "start/phone": { words: 200, amber: 3, orange: 1 },
  "results/desktop": { words: 220, amber: 3, orange: 1 },
  "results/phone": { words: 160, amber: 3, orange: 1 },
  "preview/desktop": { words: 40, amber: 1, orange: 1 },
} as const;
type Key = keyof typeof CAPS;
/** Words a live state can add (a "Needs data" badge, an approximate-address label). */
const WORD_STATE_SLACK = 8;
const VIEWS = {
  desktop: { viewport: { width: 1440, height: 900 } },
  phone: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};

async function open(browser: Browser, baseURL: string, view: keyof typeof VIEWS): Promise<Page> {
  const ctx = await browser.newContext({ ...VIEWS[view], colorScheme: "light", reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(baseURL + "/discovery", { waitUntil: "load", timeout: 120_000 });
  await page.getByTestId("discovery-start-panel").waitFor({ timeout: 60_000 });
  await page.waitForTimeout(800);
  return page;
}

/** Run the first live recipe (its badge reads "Live · N") and wait for its rows. */
async function runRecipe(page: Page): Promise<void> {
  const live = page.locator('[data-testid^="discovery-start-recipe-"]', { hasText: /Live/ }).first();
  await live.click();
  await page.getByTestId("discovery-result-row").first().waitFor({ timeout: 60_000 });
  await page.waitForTimeout(1200);
}

/** The dot preview's printed words: move the pointer across the map until a dot answers with a preview. */
async function previewWords(page: Page): Promise<number> {
  await page.getByTestId("discovery-map-container").waitFor();
  // Real pointer moves across the map until a dot answers (the camera fits the results, so dots are in view).
  const box = (await page.getByTestId("discovery-map-container").boundingBox())!;
  const step = 12;
  sweep: for (let y = box.y + step; y < box.y + box.height - step; y += step) {
    for (let x = box.x + step; x < box.x + box.width - step; x += step) {
      await page.mouse.move(x, y);
      if (await page.getByTestId("dot-preview").count()) break sweep;
    }
  }
  const preview = page.getByTestId("dot-preview");
  if (!(await preview.count())) throw new Error("no dot answered with a preview");
  await page.waitForTimeout(600); // the one-row read, when the row is not in the list
  return preview.evaluate((el) => {
    let n = 0;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    while ((node = walker.nextNode())) {
      if ((node.parentElement as Element | null)?.closest(".sr-only, [aria-hidden=true]")) continue;
      n += (node.textContent ?? "").split(/\s+/).filter((w) => /[\p{L}\p{N}$]/u.test(w)).length;
    }
    return n;
  });
}

function check(key: Key, got: Partial<Counts>, baseline: Record<string, Partial<Record<"words" | "orange", number>>>) {
  const base = baseline[key];
  expect(base, `${key} has no baseline entry`).toBeDefined();
  console.log(`${key}: ${JSON.stringify(got)}`);
  if (got.duplicateHeadings) expect(got.duplicateHeadings, `${key}: a heading appears twice`).toEqual([]);
  if (got.amber != null) expect(got.amber, `${key}.amber above the cap`).toBeLessThanOrEqual(CAPS[key].amber);
  for (const metric of ["words", "orange"] as const) {
    const b = base![metric];
    const v = got[metric];
    if (b == null || v == null) continue;
    const cap = CAPS[key][metric];
    expect(b, `${key}.${metric}: baseline ${b} is above the hard cap ${cap}`).toBeLessThanOrEqual(cap);
    const allowed = metric === "words" ? Math.min(b + WORD_STATE_SLACK, cap) : b;
    expect(v, `${key}.${metric}: ${v} is above its baseline ${b}; the budget only ratchets down`).toBeLessThanOrEqual(allowed);
    if (process.env.BUDGET_UPDATE === "1" && v < b) base![metric] = v;
  }
}

test.describe("Discovery page budget", () => {
  test.describe.configure({ mode: "serial" });

  test("budget: start, results and the dot preview", async ({ browser, baseURL }) => {
    test.skip(test.info().project.name !== "Pixel 3", "runs once, in its own desktop and phone contexts");
    const baseline = JSON.parse(fs.readFileSync(BASELINE, "utf8"));
    const base = baseURL ?? "http://localhost:5173";
    for (const view of Object.keys(VIEWS) as Array<keyof typeof VIEWS>) {
      const page = await open(browser, base, view);
      check(`start/${view}` as Key, await page.evaluate(firstScreenCounts), baseline);
      await runRecipe(page);
      check(`results/${view}` as Key, await page.evaluate(firstScreenCounts), baseline);
      if (view === "desktop") check("preview/desktop", { words: await previewWords(page) }, baseline);
      await page.context().close();
    }
    if (process.env.BUDGET_UPDATE === "1") fs.writeFileSync(BASELINE, JSON.stringify(baseline, null, 2) + "\n");
  });
});
