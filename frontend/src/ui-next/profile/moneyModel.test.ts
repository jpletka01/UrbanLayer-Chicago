// The Money tab's rules (decision Item 99): the Assessor flag reads only this lot's own recent market sale, rent
// is read for a unit size only when the records give one, and late incentive programs say "checking".
import { describe, expect, it } from "vitest";
import i18n from "../../lib/i18n";
import { profileFixture } from "../test/fixtures";
import {
  assessorBelowSale, compsModel, incentiveChips, moneySentence, rentModel, taxModel, unitSize, valueHistory,
} from "./moneyModel";

const t = (key: string, opts?: Record<string, unknown>) => i18n.t(key, { ns: "next", ...opts }) as string;
const NOW = new Date("2026-11-09T12:00:00Z");

describe("the Assessor flag", () => {
  const withSale = (price: number, date: string, arms_length: boolean | null = true) =>
    profileFixture({ context: { property: { implied_market_value: 1_000_000, sales_history: [{ date, price, deed_type: "Warranty", arms_length }] } } } as never);

  it("fires when the Assessor's value is well below this lot's recent market sale", () => {
    expect(assessorBelowSale(withSale(2_000_000, "2024-05-01T00:00:00.000"), NOW)).toEqual({ pctBelow: 50, saleYear: "2024", salePrice: 2_000_000 });
  });
  it("stays quiet near the sale, for an old sale, and for a transfer that isn't a market sale", () => {
    expect(assessorBelowSale(withSale(1_500_000, "2024-05-01T00:00:00.000"), NOW)).toBeNull(); // 67%: above the 60% line
    expect(assessorBelowSale(withSale(3_000_000, "2015-05-01T00:00:00.000"), NOW)).toBeNull();
    expect(assessorBelowSale(withSale(3_000_000, "2024-05-01T00:00:00.000", false), NOW)).toBeNull();
    expect(assessorBelowSale(withSale(3_000_000, "2024-05-01T00:00:00.000", null), NOW)).toBeNull();
  });
});

describe("taxes", () => {
  it("reads the bill and its typical class rate from the backend", () => {
    const data = profileFixture({ provenance: { "property.tax_class_norm": { label: "x", value: 0.0525, confidence: "standard" } } } as never);
    const m = taxModel(data);
    expect(m.kind).toBe("bill");
    expect(m.tax).toBe(64000);
    expect(m.typicalRate).toBe(0.0525);
  });
  it("says exempt and nominal in words, never as a figure", () => {
    expect(taxModel(profileFixture({ context: { property: { tax_exempt: true } } } as never)).kind).toBe("exempt");
    expect(taxModel(profileFixture({ context: { property: { nominal_assessment: true } } } as never)).kind).toBe("nominal");
  });
});

describe("value over time", () => {
  it("turns assessed values into the Assessor's value by the class's level, oldest first", () => {
    const data = profileFixture({ context: { property: { assessment_level: 0.1, assessment_history: [
      { year: 2024, land: 10, building: 40, total: 50 }, { year: 2022, land: 10, building: 30, total: 40 },
    ] } } } as never);
    const h = valueHistory(data);
    expect(h.basis).toBe("market");
    expect(h.years.map((y) => [y.year, y.total])).toEqual([[2022, 400], [2024, 500]]);
  });
});

describe("nearby sales", () => {
  it("prints the search as its rule and keeps a withheld median out of the sentence", async () => {
    await i18n.changeLanguage("en");
    const data = profileFixture({
      comparables: { comp_basis: "Class 2xx sales within 0.55 mi, last 5 yr (n=1)", comp_radius_mi: 0.55, comp_window_years: 5, comp_widened: true, sales_volume: 1,
        sales: [{ pin: "1", sale_date: "2021-12-01T00:00:00.000", sale_price: 395000 }] },
      provenance: { "property.comps.median_price": { label: "x", confidence: "withheld" } },
    } as never);
    const c = compsModel(data)!;
    expect(c.rule).toEqual({ classGroup: "2", radiusMi: 0.55, years: 5, n: 1, widened: true });
    expect(c.medianWithheld).toBe(true);
    expect(moneySentence(data, t, "en")).toBe("About $64,000 a year in property tax, on an Assessor's value of $1,000,000.");
  });
});

describe("rent", () => {
  it("reads a unit size from bedrooms and units", () => {
    expect(unitSize(4, 2)).toBe("2_bedrooms");
    expect(unitSize(9, 3)).toBe("3_bedrooms");
    expect(unitSize(1, 2)).toBeNull(); // fewer bedrooms than units: the records don't say
    expect(unitSize(null, 2)).toBeNull();
  });
  it("marks this building's size only for a residential class", () => {
    const rent = { bedrooms: [{ bedrooms: "2_bedrooms", scope: "tract", estimate: 2100 }], unchecked: [] };
    const res = profileFixture({ context: { property: { bldg_class: "211", bedrooms: 4, units: 2 }, neighborhood: { rent } } } as never);
    const com = profileFixture({ context: { property: { bldg_class: "592", bedrooms: 4, units: 2 }, neighborhood: { rent } } } as never);
    expect(rentModel(res)!.thisSize).toBe("2_bedrooms");
    expect(rentModel(com)!.thisSize).toBeNull();
  });
});

describe("incentives", () => {
  it("says checking for the tract programs until the incentives part lands, and not checked for a failed source", () => {
    const data = profileFixture({ context: { incentives: { in_tif_district: true, tif_name: "Milwaukee/Ashland", unchecked: ["ez"] } } } as never);
    const pending = incentiveChips(data, true);
    expect(pending[0]).toMatchObject({ key: "tif", answer: "yes" });
    expect(pending.find((c) => c.key === "qct")!.answer).toBe("checking");
    expect(pending.find((c) => c.key === "ez")!.answer).toBe("notChecked");
    expect(incentiveChips(data, false).find((c) => c.key === "qct")!.answer).toBe("no");
  });
});

describe("numbers in Spanish (Item 82)", () => {
  it("formats as Mexico's es-MX (comma thousands), never Spain's es", async () => {
    const { fmtInt } = await import("./profileModel");
    expect(fmtInt(11250, "es")).toBe("11,250");
    expect(fmtInt(11250, "en")).toBe("11,250");
  });
});

describe("chart scale", () => {
  it("rounds the top up to 1, 2, 2.5 or 5 times a power of ten", async () => {
    const { niceCeil } = await import("./moneyModel");
    expect(niceCeil(619_000)).toBe(1_000_000);
    expect(niceCeil(3_480_000)).toBe(5_000_000);
    expect(niceCeil(1_592_480)).toBe(2_000_000);
    expect(niceCeil(240_000)).toBe(250_000);
  });
});
