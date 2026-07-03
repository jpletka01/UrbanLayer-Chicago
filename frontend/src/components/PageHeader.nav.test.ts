import { describe, expect, it } from "vitest";
import { navItemsFor } from "./PageHeader";
import enPages from "../locales/en/pages.json";
import esPages from "../locales/es/pages.json";
import enCommon from "../locales/en/common.json";
import esCommon from "../locales/es/common.json";

describe("PageHeader nav — Discovery linked only when its index is live", () => {
  it("omits Discovery while dormant (coverage none)", () => {
    const keys = navItemsFor(false).map((n) => n.key);
    expect(keys).not.toContain("nav.discovery");
  });

  it("inserts Discovery after Scorecard once live", () => {
    const keys = navItemsFor(true).map((n) => n.key);
    expect(keys).toContain("nav.discovery");
    expect(keys.indexOf("nav.discovery")).toBe(keys.indexOf("nav.scorecard") + 1);
    // Explore was retired — it should no longer appear in nav at all.
    expect(keys).not.toContain("nav.explore");
  });
});

// Nav chrome is horizontal and width-constrained; every string that renders in
// the bar must fit in every locale (Spanish ran ~35% wider and pushed actions
// off-screen, 2026-07-03). Words belong in menus; anything here stays short.
const NAV_CHROME_BUDGET = 20;

describe("nav chrome strings fit the width budget in every locale", () => {
  const navKeys = navItemsFor(true).map((n) => n.key.replace(/^nav\./, ""));
  const cases: [string, string][] = [];
  for (const [locale, pages] of [["en", enPages], ["es", esPages]] as const) {
    for (const key of navKeys) {
      cases.push([`${locale} pages:nav.${key}`, (pages.nav as Record<string, string>)[key]]);
    }
  }
  for (const [locale, common] of [["en", enCommon], ["es", esCommon]] as const) {
    for (const key of ["newChat", "signInToSaveShort"] as const) {
      cases.push([`${locale} common:${key}`, (common as Record<string, string>)[key]]);
    }
  }

  it.each(cases)("%s stays under %i chars".replace("%i", String(NAV_CHROME_BUDGET)), (label, value) => {
    expect(value, `${label} is missing`).toBeTruthy();
    expect(value.length, `${label} ("${value}") exceeds the ${NAV_CHROME_BUDGET}-char nav budget`).toBeLessThanOrEqual(NAV_CHROME_BUDGET);
  });
});
