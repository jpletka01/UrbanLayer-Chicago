// Spanish overflowed the workspace nav in 2026-07 (PageHeader.nav.test.ts budgets that). The
// Discovery header and sheet are the other place a longer string breaks a 360 px layout, so the
// labels on its phone controls get the same kind of budget, per locale. Interpolation
// placeholders ({{count}}) are counted as written: a fair stand-in for a 1-3 digit number.
//
// If a string legitimately needs more room, widen the budget and check it at 360 px first
// (npm run test:mobile / e2e/discovery-phone.spec.ts), do not just raise the number.

import { describe, expect, it } from "vitest";
import en from "../locales/en/pages.json";
import es from "../locales/es/pages.json";

type Tree = { [key: string]: string | Tree };

function get(tree: Tree, path: string): string {
  let node: string | Tree = tree;
  for (const part of path.split(".")) node = (node as Tree)[part];
  if (typeof node !== "string") throw new Error(`no string at discovery.${path}`);
  return node;
}

// key (under `discovery.`) -> max characters, per locale.
const BUDGET: Record<string, number> = {
  search: 10,
  newSearch: 16,
  "header.noFilters": 14,
  "header.more": 16,
  "addFilter.button": 16,
  "addFilter.discard": 20,
  "addFilter.done": 8,
  "addFilter.showResults": 34,
  updateResults: 36,
  retry: 12,
  viewList: 6,
  viewMap: 6,
  mapKey: 20,
  mapShownOfTotal: 36,
  mapZoomToResults: 28,
  "start.resume": 12,
  "start.forget": 12,
};

describe.each([
  ["en", (en as unknown as { discovery: Tree }).discovery],
  ["es", (es as unknown as { discovery: Tree }).discovery],
])("Discovery phone control labels fit their budget (%s)", (_locale, discovery) => {
  it.each(Object.entries(BUDGET))("discovery.%s <= %i characters", (key, max) => {
    const text = get(discovery, key);
    expect(text.length, `"${text}" is ${text.length} characters`).toBeLessThanOrEqual(max);
  });

  it("no phone label is left in the other language's wording (Spanish never equals English by accident)", () => {
    if (_locale !== "es") return;
    const english = (en as unknown as { discovery: Tree }).discovery;
    // identical words are fine (a name, "OK"); a multi-word UI label that is identical is a missed translation
    for (const key of Object.keys(BUDGET)) {
      const a = get(english, key);
      const b = get(discovery, key);
      if (a === b) expect(a.split(/\s+/).length, `discovery.${key} is untranslated: "${a}"`).toBe(1);
    }
  });
});
