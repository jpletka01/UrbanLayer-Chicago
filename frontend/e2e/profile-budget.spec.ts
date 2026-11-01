// The Property Profile's page budget (redesign plan §4 principle 10, decision Item 51): the page's
// "owner". On four reference parcels, desktop and phone, the first screen (no scroll) may not exceed
// its word, amber and solid-orange counts; the default page may not exceed 4 desktop screens; no heading
// may appear twice; no figure may carry more than one confidence state.
//
// Ratchet: the numbers in profile-budget.baseline.json may only go DOWN. A run fails when any count is
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

const BASELINE = path.resolve("e2e/profile-budget.baseline.json");
const CAPS = {
  desktop: { words: 120, amber: 3, orange: 1, screens: 4 },
  phone: { words: 90, amber: 3, orange: 1, screens: 1000 },
} as const;
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

type Counts = { words: number; amber: number; orange: number; screens: number; duplicateHeadings: string[]; multiStateFigures: string[] };

async function measure(browser: Browser, baseURL: string, url: string, view: keyof typeof VIEWS): Promise<Counts> {
  const ctx = await browser.newContext({ ...VIEWS[view], colorScheme: "light", reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(baseURL + url, { waitUntil: "load", timeout: 120_000 });
  await page.waitForFunction(
    () => !/Building the Property Profile|Looking up/.test(document.body.innerText) && !!document.querySelector("[data-testid=answer-panels]"),
    null, { timeout: 120_000 },
  );
  await page.waitForTimeout(2000);
  const counts = await page.evaluate(() => {
    const H = window.innerHeight;
    const skip = (el: Element) => !!el.closest("header, nav, footer, .mapboxgl-map, canvas, [data-budget-skip]");
    const shown = (el: Element) => {
      const s = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return s.visibility !== "hidden" && s.display !== "none" && Number(s.opacity) > 0 && r.width > 0 && r.height > 0;
    };
    const inFold = (el: Element) => { const r = el.getBoundingClientRect(); return r.top < H && r.bottom > 0; };
    let words = 0;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n: Node | null;
    while ((n = walker.nextNode())) {
      const el = n.parentElement;
      if (!el || skip(el) || !shown(el) || !inFold(el) || el.closest("script, style, [aria-hidden=true]")) continue;
      const text = (n.textContent ?? "").replace(/\s+/g, " ").trim();
      if (text) words += text.split(" ").filter((w) => /[\p{L}\p{N}$]/u.test(w)).length;
    }
    const all = [...document.body.querySelectorAll("*")];
    const isAmber = (el: Element) => {
      const cls = typeof el.className === "string" ? el.className : "";
      return /(^|\s)(text|bg|border)-(state-warning|status-warning)/.test(cls) || el.getAttribute("data-status-label") === "warning" || el.getAttribute("data-state") === "low";
    };
    const amberEls = all.filter((el) => !skip(el) && shown(el) && inFold(el) && isAmber(el));
    const amber = amberEls.filter((el) => !amberEls.some((o) => o !== el && o.contains(el))).length;
    const orange = all.filter((el) => {
      if (skip(el) || !shown(el) || !inFold(el)) return false;
      const r = el.getBoundingClientRect();
      if (r.width < 24 || r.height < 16) return false;
      const bg = getComputedStyle(el).backgroundColor;
      return bg === "rgb(249, 164, 116)" || bg === "rgb(243, 154, 103)";
    }).length;
    const headings = [...document.querySelectorAll("main h1, main h2, main h3, main h4")].filter(shown)
      .map((h) => (h as HTMLElement).innerText.replace(/\s+/g, " ").trim()).filter(Boolean);
    const duplicateHeadings = [...new Set(headings.filter((h, i) => headings.indexOf(h) !== i))];
    const multiStateFigures = [...document.querySelectorAll("[data-figure]")]
      .filter((f) => f.querySelectorAll("[data-confidence-state]").length > 1)
      .map((f) => f.getAttribute("data-figure") ?? "?");
    const screens = Math.round((document.documentElement.scrollHeight / H) * 10) / 10;
    return { words, amber, orange, screens, duplicateHeadings, multiStateFigures };
  });
  await ctx.close();
  return counts;
}

test.describe("Property Profile page budget", () => {
  // Serial: each test rewrites the shared baseline file under BUDGET_UPDATE.
  test.describe.configure({ mode: "serial" });

  for (const [name, url] of PARCELS) {
    test(`budget: ${name}`, async ({ browser, baseURL }) => {
      test.skip(test.info().project.name !== "Pixel 3", "runs once, in its own desktop and phone contexts");
      const baseline: Record<string, Partial<Record<"words" | "amber" | "orange" | "screens", number>>> =
        JSON.parse(fs.readFileSync(BASELINE, "utf8"));
      for (const view of Object.keys(VIEWS) as Array<keyof typeof VIEWS>) {
        const key = `${name}/${view}`;
        const got = await measure(browser, baseURL ?? "http://localhost:5173", url, view);
        const base = baseline[key];
        expect(base, `${key} has no baseline entry`).toBeDefined();
        console.log(`${key}: ${JSON.stringify(got)}`);
        expect(got.duplicateHeadings, `${key}: a heading appears twice`).toEqual([]);
        expect(got.multiStateFigures, `${key}: a figure carries two confidence states`).toEqual([]);
        for (const metric of ["words", "amber", "orange", "screens"] as const) {
          const cap = CAPS[view][metric];
          const b = base![metric];
          if (b == null) continue;
          expect(b, `${key}.${metric}: baseline ${b} is above the hard cap ${cap}`).toBeLessThanOrEqual(cap);
          expect(got[metric], `${key}.${metric}: ${got[metric]} is above its baseline ${b} (the budget only ratchets down)`).toBeLessThanOrEqual(b);
          if (process.env.BUDGET_UPDATE === "1" && got[metric] < b) base![metric] = got[metric];
        }
      }
      if (process.env.BUDGET_UPDATE === "1") fs.writeFileSync(BASELINE, JSON.stringify(baseline, null, 2) + "\n");
    });
  }
});
