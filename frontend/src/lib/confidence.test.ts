import { describe, expect, it } from "vitest";
import i18n from "./i18n";
import type { Provenance } from "./api";
import { captionParts, displayState, plainCaption, sourceBullets, wantsCaption } from "./confidence";

const t = i18n.getFixedT("en", "common");

// Entries shaped like the live payload for 1601 N Milwaukee Ave (2026-10-21).
function entry(over: Partial<Provenance>): Provenance {
  return {
    label: "Figure", kind: "official_record", source: null, record_id: null, url: null, section: null,
    as_of: null, effective_date: null, query_date: "2026-10-21", note: null,
    tier: "official_record", as_of_basis: "queried", method_key: "recorded",
    method: "Read as recorded by the publisher", confidence: "standard", confidence_reasons: [],
    ...over,
  };
}

const stories = entry({
  tier: "official_record", source_id: "chi.building_footprints", as_of: "2015-08-15", as_of_basis: "source_updated",
  age_days: 4085, scope: "parcel", confidence_reasons: ["old_source"], value: 2,
});
const tax = entry({
  kind: "derived", tier: "official_estimate", source_id: "cook.ptaxsim", as_of: "2024-12-31", as_of_basis: "tax_year",
  period: "2024", age_days: 659, method_key: "government_model", method: "A government agency's model", value: 82586.11,
});
const comps = (n: number, over: Partial<Provenance> = {}) => entry({
  kind: "derived", tier: "our_calculation", source_id: "cook.assessor.sales", as_of: "2026-08-12", as_of_basis: "period_end",
  period: "last 3 years", age_days: 70, scope: "radius", method_key: "calculation", method: "Our calculation",
  method_params: { radius_mi: 0.28, window_years: 3, widened: false },
  coverage: { n, unit: "sales", sample: "comps" }, ...over,
});
const acs = (over: Partial<Provenance>) => entry({
  kind: "derived", tier: "official_estimate", source_id: "census.reporter.acs", as_of: "2024-12-31", as_of_basis: "period_end",
  period: "2020–2024", age_days: 659, scope: "tract", geography: "Census Tract 8310, Cook, IL",
  method_key: "survey_estimate", method: "Census survey estimate", ...over,
});

describe("default-quiet rule (guide §4.1)", () => {
  it("prints nothing for an official record or published text in a standard state", () => {
    const record = entry({ as_of: "2026-10-20", as_of_basis: "period_end", age_days: 1 });
    const code = entry({ tier: "official_publication", method_key: "code_table", as_of: "2026-06-17", as_of_basis: "current_through", age_days: 126 });
    for (const e of [record, code]) {
      expect(wantsCaption(e)).toBe(false);
      expect(captionParts(e, t).visible).toBe(false);
    }
  });

  it("prints for tiers C–F, for low and withheld figures, and for a source older than 24 months", () => {
    expect(wantsCaption(tax)).toBe(true);
    expect(wantsCaption(comps(8))).toBe(true);
    expect(wantsCaption(entry({ tier: "ai_extracted" }))).toBe(true);
    expect(wantsCaption(entry({ tier: "non_government" }))).toBe(true);
    expect(wantsCaption(entry({ confidence: "low", confidence_reasons: ["high_cv"] }))).toBe(true);
    expect(wantsCaption(entry({ confidence: "withheld", confidence_reasons: ["small_sample"] }))).toBe(true);
    expect(wantsCaption(stories)).toBe(true);
  });

  it("is quiet when there is no entry at all", () => {
    expect(captionParts(undefined, t).visible).toBe(false);
    expect(displayState(undefined)).toBe("standard");
  });
});

describe("captionParts", () => {
  it("names a frozen source and its year: the 2015 footprint stories figure", () => {
    const c = captionParts(stories, t);
    expect(c.parts).toEqual(["City footprint survey", "2015"]);
    expect(c.lead).toBeNull();
  });

  it("states the tax year and a plain method, and lets a caller omit the year it already shows", () => {
    expect(captionParts(tax, t).parts).toEqual(["Government model", "2024"]);
    expect(captionParts(tax, t, { omit: ["period"] }).parts).toEqual(["Government model"]);
  });

  it("shows the comps basis from the search's own radius and window, not a fixed quarter mile", () => {
    expect(captionParts(comps(8), t).parts).toEqual(["8 sales", "0.28 mi · 3 yr"]);
    const widened = comps(6, { method_params: { radius_mi: 0.5, window_years: 5, widened: true } });
    expect(captionParts(widened, t).parts).toEqual(["6 sales", "0.5 mi · 5 yr (search widened)"]);
  });

  it("leads a low figure with the one amber phrase and shows a Census margin and area", () => {
    const vacancy = acs({
      confidence: "low", confidence_reasons: ["high_cv"], precision: { moe: 5.7, moe_level: 0.9, cv: 0.456 }, value: 7.6,
    });
    const c = captionParts(vacancy, t, { unit: "pct" });
    expect(c.state).toBe("low");
    expect(c.lead).toBe("Low confidence");
    expect(c.parts).toEqual(["Census survey estimate", "2020–2024", "±5.7 pts", "Census Tract 8310, Cook, IL"]);
  });

  it("prints a margin in dollars when asked", () => {
    const rent = acs({ precision: { moe: 220, moe_level: 0.9, cv: 0.055 } });
    expect(captionParts(rent, t, { unit: "usd" }).parts).toContain("±$220");
  });

  it("says a bracket median has no published margin", () => {
    const income = acs({
      source_id: "chi.acs_community_area", scope: "community_area", geography: "West Town", period: "2019–2023",
      tier: "our_calculation", method_key: "bracket_median", method: "Median interpolated from published brackets",
      confidence: "low", confidence_reasons: ["bracket_median"],
    });
    const c = captionParts(income, t);
    expect(c.lead).toBe("Low confidence");
    expect(c.parts).toEqual(["Estimated from income brackets", "2019–2023", "no margin of error published", "West Town"]);
  });

  it("reports the coverage a benchmark rests on, and drops scope when the caller already shows it", () => {
    const bench = entry({
      kind: "derived", tier: "our_calculation", source_id: "internal.discovery_index", as_of: "2026-10-01",
      as_of_basis: "source_updated", age_days: 20, scope: "community_area", geography: "Community area 24",
      method_key: "calculation", method: "Our calculation",
      coverage: { n: 14001, share: 0.4421, unit: "parcels", sample: "area_sample" },
    });
    expect(captionParts(bench, t, { omit: ["scope"] }).parts).toEqual(["14,001 parcels", "44% coverage"]);
  });

  it("names a private index as such", () => {
    const walk = entry({ tier: "non_government", source_id: "private.walkscore", method_key: "commercial_index", method: "A private company's index" });
    expect(captionParts(walk, t).parts).toEqual(["Walk Score® (private company)"]);
  });

  it("falls back to the method alone for a calculation with nothing else to say", () => {
    const farUsed = entry({ kind: "derived", tier: "our_calculation", method_key: "calculation", method: "Our calculation", as_of: "2026-10-15", as_of_basis: "source_updated", age_days: 6 });
    expect(captionParts(farUsed, t).parts).toEqual(["Our calculation"]);
  });

  it("marks an AI reading and says it is not verified, without calling it low confidence", () => {
    const setback = entry({
      tier: "ai_extracted", method_key: "ai_read_code", method: "Read by AI from Municipal Code text",
      confidence: "low", confidence_reasons: ["ai_unverified"],
    });
    const c = captionParts(setback, t);
    expect(c.ai).toBe(true);
    expect(c.lead).toBeNull();
    expect(c.parts).toEqual(["Read by AI from the code", "not verified"]);
  });
});

describe("withheld figures say why", () => {
  it("too few comparable sales, with the minimum", () => {
    const c = captionParts(comps(2, { confidence: "withheld", confidence_reasons: ["small_sample"] }), t);
    expect(c.visible).toBe(true);
    expect(c.withheld).toBe("Not shown: only 2 sales (needs 3).");
    expect(c.parts).toEqual([]);
  });

  it("too small an area sample uses the area minimum", () => {
    const e = entry({
      tier: "our_calculation", confidence: "withheld", confidence_reasons: ["small_sample"],
      coverage: { n: 12, unit: "parcels", sample: "area_sample" },
    });
    expect(captionParts(e, t).withheld).toBe("Not shown: only 12 parcels (needs 30).");
  });

  it("too little coverage", () => {
    const e = entry({
      tier: "our_calculation", confidence: "withheld", confidence_reasons: ["low_coverage"],
      coverage: { share: 0.05, unit: "units" },
    });
    expect(captionParts(e, t).withheld).toBe("Not shown: the data covers 5% here (needs 10%).");
  });

  it("an error as large as the estimate", () => {
    const e = acs({ confidence: "withheld", confidence_reasons: ["high_cv"], precision: { cv: 0.72 } });
    expect(captionParts(e, t).withheld).toBe("Not shown: the margin of error is 72% of the estimate.");
  });

  it("still gives a reason when the backend sends none", () => {
    expect(captionParts(entry({ confidence: "withheld" }), t).withheld).toBe("Not shown: too little data.");
  });
});

describe("sourceBullets (the tooltip's Source block)", () => {
  it("lists authority, date and age, source and method for a quiet record", () => {
    const b = sourceBullets(stories, t);
    expect(b).toContain("Published by: Official record");
    expect(b.some((x) => x.startsWith("As of: Aug 15, 2015") && x.includes("4085 days old") && x.includes("source last updated"))).toBe(true);
    expect(b).toContain("Source: City footprint survey");
    expect(b).toContain("Method: Recorded by the publisher");
  });

  it("adds margin, coverage and scope when they exist", () => {
    const b = sourceBullets(acs({ precision: { moe: 220, moe_level: 0.9, cv: 0.055 } }), t, { unit: "usd" });
    expect(b).toContain("Precision: ±$220 (90% margin of error)");
    expect(b).toContain("Covers: Census Tract 8310, Cook, IL");
  });

  it("says when the publisher gave no date", () => {
    const b = sourceBullets(entry({}), t);
    expect(b.some((x) => x.startsWith("No date from the publisher; checked Oct 21, 2026"))).toBe(true);
  });

  it("is empty without an entry", () => {
    expect(sourceBullets(undefined, t)).toEqual([]);
  });
});

describe("plainCaption (CSV)", () => {
  it("joins the words the page prints, and is empty when the page is quiet", () => {
    expect(plainCaption(stories, t)).toBe("City footprint survey · 2015");
    expect(plainCaption(entry({}), t)).toBe("");
  });

  it("carries the withheld reason", () => {
    expect(plainCaption(comps(2, { confidence: "withheld", confidence_reasons: ["small_sample"] }), t))
      .toBe("Not shown: only 2 sales (needs 3).");
  });
});
