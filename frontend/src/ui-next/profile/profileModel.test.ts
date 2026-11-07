import { describe, expect, it } from "vitest";
import i18n from "../../lib/i18n";
import { computeVerdict } from "../../lib/scorecardVerdict";
import { profileFixture } from "../test/fixtures";
import { allowedVsBuilt, heightFeet, isMarketSale, overviewTiles, pendingRezonings, ruleChips, stageOf } from "./profileModel";

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
    // Real values from the Clerk snapshot (2026-11-07).
    expect(stageOf({ status: "3-Council Introduction", sub_status: "Council Introduction" })).toBe("introduced");
    expect(stageOf({ status: "4-In Committee", sub_status: "Referred" })).toBe("committee");
    expect(stageOf({ status: "5-Council Consideration", sub_status: "Recommended to Pass" })).toBe("council");
    expect(stageOf({ status: "90-Final", sub_status: "Passed" })).toBe("inEffect");
    expect(stageOf({ status: "90-Final", sub_status: "Failed to Pass" })).toBeNull();
    expect(stageOf({ status: "Referred", sub_status: "In Committee on Zoning" })).toBeNull();
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

describe("overview tiles: one per tab", () => {
  it("gives Build units allowed, Money property tax, Neighborhood walk score, History last market sale", () => {
    const data = profileFixture();
    const tiles = overviewTiles(data, computeVerdict(data, tp), t);
    expect(tiles.map((x) => [x.tabOf, x.key, x.figure])).toEqual([
      ["build", "units", "≤ 11"], ["money", "tax", "$64,000"], ["neighborhood", "walk", "99"], ["history", "lastSale", "$1,200,000"],
    ]);
    expect(tiles.some((x) => (x.key as string) === "zoning")).toBe(false);
  });

  it("never shows a $1 transfer, a quit claim or an unknown deed as the sale price", () => {
    expect(isMarketSale({ price: 1, deed_type: "Warranty" })).toBe(false);
    expect(isMarketSale({ price: 400000, deed_type: "Quit claim" })).toBe(false);
    expect(isMarketSale({ price: 400000, deed_type: null })).toBe(false);
    expect(isMarketSale({ price: 395000, deed_type: "Trustee" })).toBe(true);
    const data = profileFixture({ context: { property: { sales_history: [
      { date: "2022-05-01T00:00:00.000", price: 1, deed_type: "Quit claim" },
      { date: "2019-06-24T00:00:00.000", price: 1200000, deed_type: "Warranty" },
    ] } } } as never);
    const sale = overviewTiles(data, computeVerdict(data, tp), t)[3];
    expect(sale.figure).toBe("$1,200,000");
    expect(sale.warning).toBe("A 2022 transfer isn't counted as a sale");
    const onlyTransfers = profileFixture({ context: { property: { sales_history: [{ date: "2022-05-01T00:00:00.000", price: 1, deed_type: "Quit claim" }] } } } as never);
    const tile = overviewTiles(onlyTransfers, computeVerdict(onlyTransfers, tp), t)[3];
    expect(tile.figure).toBe("—");
    expect(tile.note).toBe("1 transfer on record, not a market sale");
  });

  it("says exempt in words and keeps the walk score's slot when it couldn't be read", () => {
    const exempt = profileFixture({ context: { property: { tax_exempt: true, estimated_annual_tax: null } } } as never);
    expect(overviewTiles(exempt, computeVerdict(exempt, tp), t)[1].figure).toBe("Exempt");
    const noWalk = profileFixture({ context: { neighborhood: null } } as never);
    const walk = overviewTiles(noWalk, computeVerdict(noWalk, tp), t)[2];
    expect(walk.figure).toBe("—");
    expect(walk.state?.kind).toBe("not_checked");
  });
});
