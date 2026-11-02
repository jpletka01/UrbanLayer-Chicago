// The Property Profile's page budget (redesign plan §4 principle 10, decision Item 51): the page's
// "owner". On four reference parcels, desktop and phone, the first screen (no scroll) may not exceed
// its word, amber and solid-orange counts; the default page may not exceed 4 desktop screens; no heading
// may appear twice; no figure may carry more than one confidence state.
//
// Ratchet: the word, solid-orange and page-height numbers in profile-budget.baseline.json may only go
// DOWN (amber is held to its cap only: it moves with live source states; decision Item 52). A run fails when any count is
// above its baseline, and the baseline itself may not exceed the hard caps below. `BUDGET_UPDATE=1`
// lowers baseline entries that improved and never raises one: raising a budget is a hand edit of the
// JSON, reviewed in its PR. Live data, so a source state can move a count (a "couldn't check" row);
// that is exactly the kind of growth the reviewer should see.
//
// Runs once (in the "Pixel 3" project; it opens its own desktop and phone contexts) as part of
// `npm run test:mobile`. CI does not run Playwright: this is part of the definition of done for any
// Profile PR, like the overflow audit.
import { expect, test, type Browser } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { firstScreenCounts, type Counts } from "./budgetMeasure";

const BASELINE = path.resolve("e2e/profile-budget.baseline.json");
const CAPS = {
  desktop: { words: 120, amber: 3, orange: 1, screens: 4 },
  phone: { words: 90, amber: 3, orange: 1, screens: 1000 },
} as const;
/** The opened "What you can build" section (decision Item 54): ~1,000 words before the tool tray. */
const BUILD_WORDS_CAP = 500;
/** Words a live source state can add to the first screen (decision Item 52). */
const WORD_STATE_SLACK = 8;
const PARCELS: Array<[string, string]> = [
  ["twoflat", "/scorecard?address=2541%20N%20Spaulding%20Ave"],
  ["milwaukee", "/scorecard?address=1601%20N%20Milwaukee%20Ave"],
  ["downtown", "/scorecard?address=233%20S%20Wacker%20Dr"],
  ["pin1", "/scorecard?pin=14-28-319-102-0000"],
];
const VIEWS = {
  desktop: { viewport: { width: 1440, height: 900 } },
  phone: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};

async function measure(browser: Browser, baseURL: string, url: string, view: keyof typeof VIEWS): Promise<Counts> {
  const ctx = await browser.newContext({ ...VIEWS[view], colorScheme: "light", reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(baseURL + url, { waitUntil: "load", timeout: 120_000 });
  await page.waitForFunction(
    () => !/Building the Property Profile|Looking up/.test(document.body.innerText) && !!document.querySelector("[data-testid=answer-panels]"),
    null, { timeout: 120_000 },
  );
  await page.waitForTimeout(2000);
  const counts = await page.evaluate(firstScreenCounts);
  await ctx.close();
  return counts;
}

async function buildSectionWords(browser: Browser, baseURL: string, url: string): Promise<number> {
  const ctx = await browser.newContext({ ...VIEWS.desktop, colorScheme: "light", reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(baseURL + url, { waitUntil: "load", timeout: 120_000 });
  await page.waitForSelector("[data-testid=answer-panels]", { timeout: 120_000 });
  await page.click("#module-build > button");
  // Measure only an opened section: a body that never rendered would read as 0 words and pass.
  await page.waitForSelector("#module-build-body", { timeout: 30_000 });
  for (let y = 0; y < 12_000; y += 600) {
    await page.evaluate((v) => window.scrollTo(0, v), y);
    await page.waitForTimeout(120);
  }
  await page.waitForTimeout(2000);
  const words = await page.evaluate(() => {
    const body = document.querySelector("#module-build-body");
    if (!body) return -1;
    let n = 0;
    const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    while ((node = walker.nextNode())) {
      const el = node.parentElement;
      if (!el || el.closest(".mapboxgl-map, .sr-only, [role=dialog], [aria-hidden=true]")) continue;
      const s = getComputedStyle(el);
      if (s.display === "none" || s.visibility === "hidden") continue;
      n += (node.textContent ?? "").split(/\s+/).filter((w) => /[\p{L}\p{N}$]/u.test(w)).length;
    }
    return n;
  });
  await ctx.close();
  if (words <= 0) throw new Error(`the opened Build section had no text to measure at ${url}`);
  return words;
}

test.describe("Property Profile page budget", () => {
  // Serial: each test rewrites the shared baseline file under BUDGET_UPDATE.
  test.describe.configure({ mode: "serial" });

  for (const [name, url] of PARCELS) {
    test(`budget: ${name}`, async ({ browser, baseURL }) => {
      test.skip(test.info().project.name !== "Pixel 3", "runs once, in its own desktop and phone contexts");
      const baseline: Record<string, Partial<Record<"words" | "orange" | "screens", number>>> =
        JSON.parse(fs.readFileSync(BASELINE, "utf8"));
      for (const view of Object.keys(VIEWS) as Array<keyof typeof VIEWS>) {
        const key = `${name}/${view}`;
        const got = await measure(browser, baseURL ?? "http://localhost:5173", url, view);
        const base = baseline[key];
        expect(base, `${key} has no baseline entry`).toBeDefined();
        console.log(`${key}: ${JSON.stringify(got)}`);
        expect(got.duplicateHeadings, `${key}: a heading appears twice`).toEqual([]);
        expect(got.multiStateFigures, `${key}: a figure carries two confidence states`).toEqual([]);
        // Amber follows live source and sample states (a source that is down today, a comp set that
        // is thin), so it is held to the hard cap only; the counts that grow by accretion ratchet.
        expect(got.amber, `${key}.amber: ${got.amber} is above the cap ${CAPS[view].amber}`).toBeLessThanOrEqual(CAPS[view].amber);
        for (const metric of ["words", "orange", "screens"] as const) {
          const cap = CAPS[view][metric];
          const b = base![metric];
          if (b == null) continue;
          expect(b, `${key}.${metric}: baseline ${b} is above the hard cap ${cap}`).toBeLessThanOrEqual(cap);
          // Words carry a small allowance for live state rows ("◌ Not checked: FEMA flood zone" is 4-6
          // words); a new card or caveat is tens. The hard cap above still binds without any allowance.
          const allowed = metric === "words" ? Math.min(b + WORD_STATE_SLACK, cap) : b;
          expect(got[metric], `${key}.${metric}: ${got[metric]} is above its baseline ${b}${metric === "words" ? ` (+${WORD_STATE_SLACK} for live state rows)` : ""}; the budget only ratchets down`).toBeLessThanOrEqual(allowed);
          if (process.env.BUDGET_UPDATE === "1" && got[metric] < b) base![metric] = got[metric];
        }
      }
      // The opened Build section: its printed words only (tool popovers, screen-reader text and maps excluded).
      {
        const key = `${name}/build`;
        const words = await buildSectionWords(browser, baseURL ?? "http://localhost:5173", url);
        const b = baseline[key]?.words;
        console.log(`${key}: ${JSON.stringify({ words })}`);
        expect(b, `${key} has no baseline entry`).toBeDefined();
        expect(b!, `${key}.words: baseline ${b} is above the hard cap ${BUILD_WORDS_CAP}`).toBeLessThanOrEqual(BUILD_WORDS_CAP);
        expect(words, `${key}.words: ${words} is above its baseline ${b} (+${WORD_STATE_SLACK} for live state rows); the budget only ratchets down`)
          .toBeLessThanOrEqual(Math.min(b! + WORD_STATE_SLACK, BUILD_WORDS_CAP));
        if (process.env.BUDGET_UPDATE === "1" && words < b!) baseline[key]!.words = words;
      }
      if (process.env.BUDGET_UPDATE === "1") fs.writeFileSync(BASELINE, JSON.stringify(baseline, null, 2) + "\n");
    });
  }
});
