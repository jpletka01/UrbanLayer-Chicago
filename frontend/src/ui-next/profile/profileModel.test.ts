import { describe, expect, it } from "vitest";
import i18n from "../../lib/i18n";
import { computeVerdict } from "../../lib/scorecardVerdict";
import { profileFixture } from "../test/fixtures";
import { allowedVsBuilt, heightFeet, overviewTiles, pendingRezonings, ruleChips, stageOf } from "./profileModel";

const t = (key: string, opts?: Record<string, unknown>) => i18n.t(key, { ns: "next", ...opts }) as string;
const tp = (key: string, opts?: Record<string, unknown>) => i18n.t(key, { ns: "pages", ...opts }) as string;

describe("allowed vs built", () => {
  it("compares floor area and units and marks the most used-up limit as deciding", () => {
    const data = profileFixture();
    const rows = allowedVsBuilt(data, computeVerdict(data, tp), t);
    expect(rows.map((r) => r.key)).toEqual(["floorArea", "units", "height"]);
    const floor = rows[0];
    expect(floor.allowed).toBeCloseTo(2.2 * 11250);
    expect(floor.share).toBeCloseTo(14700 / 24750);
    expect(rows[1].share).toBeCloseTo(4 / 11);
    expect(rows.filter((r) => r.deciding).map((r) => r.key)).toEqual(["floorArea"]);
  });

  it("never compares stories against feet, and keeps a missing figure's slot", () => {
    const data = profileFixture({ context: { property: { units: null } } } as never);
    const rows = allowedVsBuilt(data, computeVerdict(data, tp), t);
    const height = rows.find((r) => r.key === "height")!;
    expect(height.share).toBeNull();
    expect(height.builtText).toBe("3 stories");
    const units = rows.find((r) => r.key === "units")!;
    expect(units.share).toBeNull();
    expect(units.builtText).toBe("not on record");
  });

  it("parses the table's height only when it is a plain number of feet", () => {
    expect(heightFeet("50 ft")).toBe(50);
    expect(heightFeet("65'")).toBe(65);
    expect(heightFeet("Varies by PD")).toBeNull();
  });
});

describe("pending rezonings", () => {
  it("reads a Clerk status into a stage only when the words say so", () => {
    expect(stageOf({ status: "Referred", sub_status: "In Committee on Zoning" })).toBe("committee");
    expect(stageOf({ status: "Passed", sub_status: "" })).toBe("inEffect");
    expect(stageOf({ status: "Something else", sub_status: "" })).toBeNull();
  });

  it("puts the lot's own filings first and keeps unavailable apart from none", () => {
    expect(pendingRezonings(profileFixture()).filings[0].onThisLot).toBe(false);
    expect(pendingRezonings(profileFixture({ context: { upcoming_zoning: null } } as never)).state).toBe("unavailable");
    expect(pendingRezonings(profileFixture({ context: { upcoming_zoning: { nearby_filings: [] } } } as never)).state).toBe("none");
  });
});

describe("rules", () => {
  it("lists what changes the build answer first and never turns a failed check into no", () => {
    const data = profileFixture();
    const chips = ruleChips(data, computeVerdict(data, tp));
    expect(chips[0]).toMatchObject({ key: "landmark", answer: "yes", blocks: true });
    const failed = profileFixture({ context: { regulatory: { flood_unchecked: true, unchecked_overlays: ["landmark_district"] } } } as never);
    const c2 = ruleChips(failed, computeVerdict(failed, tp));
    expect(c2.find((c) => c.key === "flood")!.answer).toBe("notChecked");
    expect(c2.find((c) => c.key === "landmark")!.answer).toBe("notChecked");
  });
});

describe("overview tiles (provisional set)", () => {
  it("gives units allowed, zoning, property tax and price per sq ft, in that order", () => {
    const data = profileFixture();
    const tiles = overviewTiles(data, computeVerdict(data, tp), t);
    expect(tiles.map((x) => [x.key, x.figure])).toEqual([
      ["units", "≤ 11"], ["zoning", "B3-2"], ["tax", "$64,000"], ["pricePerSqft", "$312"],
    ]);
    expect(tiles.every((x) => !x.warning || typeof x.warning === "string")).toBe(true);
  });

  it("says exempt and nominal in words, and withholds a price the backend withholds", () => {
    const exempt = profileFixture({ context: { property: { tax_exempt: true, estimated_annual_tax: null } } } as never);
    expect(overviewTiles(exempt, computeVerdict(exempt, tp), t)[2].figure).toBe("Exempt");
    const withheld = profileFixture({ provenance: { "property.comps.median_price": { label: "x", confidence: "withheld" } } } as never);
    const tile = overviewTiles(withheld, computeVerdict(withheld, tp), t)[3];
    expect(tile.figure).toBe("—");
    expect(tile.state?.kind).toBe("withheld");
  });
});
