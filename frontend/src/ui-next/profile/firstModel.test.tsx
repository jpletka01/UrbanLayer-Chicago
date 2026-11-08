// The Profile's first screen (decision Item 82): its sentence agrees with the full Profile's figures, the four
// tiles hold their final places, failures say so, and it reads in Spanish (usted) with no axe violations.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import i18n from "../../lib/i18n";
import type { ScorecardFirst } from "../../lib/api";
import { computeVerdict } from "../../lib/scorecardVerdict";
import { profileFixture } from "../test/fixtures";
import { axeViolations } from "../test/axe";
import { checkingTiles, firstSentence } from "./firstModel";
import { allowedVsBuilt, overviewTiles } from "./profileModel";
import { FirstOverview, ProfileSkeleton } from "./ProfileNextPage";

const t = (key: string, opts?: Record<string, unknown>) => i18n.t(key, { ns: "next", ...opts }) as string;
const tp = (key: string, opts?: Record<string, unknown>) => i18n.t(key, { ns: "pages", ...opts }) as string;

/** The first answer for the same parcel as `profileFixture` (1601 N Milwaukee, B3-2, 11,250 sq ft). */
function firstFixture(over: Partial<ScorecardFirst> = {}): ScorecardFirst {
  const full = profileFixture();
  return {
    address: full.address,
    resolved_pin: full.resolved_pin,
    resolved_confidence: "authoritative",
    resolved_lat: full.resolved_lat,
    resolved_lon: full.resolved_lon,
    zoning: { zone_class: "B3-2" },
    zoning_unchecked: false,
    zone_definition: full.zone_definition ?? null,
    lot: { pin14: full.resolved_pin!, land_sqft: full.context.property!.land_sqft!, land_sqft_source: "assessor", parcel_geometry: null, shared_outline_with: 0 },
    lot_unchecked: false,
    ...over,
  };
}

afterEach(async () => { cleanup(); await i18n.changeLanguage("en"); });

describe("firstSentence", () => {
  it("states the same allowed floor area as the full Profile's Build tab", () => {
    const full = profileFixture();
    const floor = allowedVsBuilt(full, computeVerdict(full, tp), t).find((r) => r.key === "floorArea")!;
    const sentence = firstSentence(firstFixture(), t);
    expect(sentence).toBe("Zoned B3-2: up to 24,750 sq ft of floor area on this 11,250 sq ft lot, up to 50 ft tall.");
    expect(sentence).toContain(floor.allowedText);
  });

  it("falls back to the ratio without a lot area (approximate match, or the lot couldn't be read)", () => {
    expect(firstSentence(firstFixture({ lot: null }), t)).toBe("Zoned B3-2: a floor-area ratio of 2.2, up to 50 ft tall.");
    expect(firstSentence(firstFixture({ lot: null, lot_unchecked: true }), t)).toMatch(/floor-area ratio of 2\.2/);
  });

  it("says a failed zoning lookup is unchecked, and an empty one is no district", () => {
    expect(firstSentence(firstFixture({ zoning: null, zoning_unchecked: true, zone_definition: null }), t))
      .toBe("The zoning district couldn't be checked yet.");
    expect(firstSentence(firstFixture({ zoning: null, zone_definition: null }), t))
      .toBe("The City's zoning map shows no district at this point.");
  });

  it("names a district with no ratio without inventing one", () => {
    const zdef = { ...profileFixture().zone_definition!, zone_class: "PD 1234", far: null, max_height: null };
    expect(firstSentence(firstFixture({ zoning: { zone_class: "PD 1234" }, zone_definition: zdef }), t)).toBe("Zoned PD 1234.");
  });
});

describe("checkingTiles", () => {
  it("holds the four tiles in the full Overview's order and labels", () => {
    const full = profileFixture();
    const final = overviewTiles(full, computeVerdict(full, tp), t);
    const waiting = checkingTiles(t);
    expect(waiting.map((x) => [x.key, x.label, x.tabOf])).toEqual(final.map((x) => [x.key, x.label, x.tabOf]));
    expect(waiting.every((x) => x.checking && x.note)).toBe(true);
  });
});

describe("FirstOverview", () => {
  it("shows the sentence, four waiting tiles and the still-checking line, accessibly", async () => {
    const { container } = render(<div className="ui-next"><FirstOverview first={firstFixture()} identity="exact" restFailed={false} onRetry={vi.fn()} /></div>);
    expect(screen.getByTestId("first-sentence").textContent).toMatch(/^Zoned B3-2/);
    const tiles = within(screen.getByTestId("overview-tiles")).getAllByRole("listitem");
    expect(tiles).toHaveLength(4);
    expect(tiles[0].textContent).toContain("Checking County building records");
    expect(screen.getByTestId("still-checking").textContent).toContain("Still checking");
    expect(screen.queryByText(/\d+ s\b/)).toBeNull(); // no seconds counter
    expect(await axeViolations(container)).toEqual([]);
  });

  it("keeps the first screen with Retry when the rest fails", () => {
    const onRetry = vi.fn();
    render(<div className="ui-next"><FirstOverview first={firstFixture()} identity="exact" restFailed onRetry={onRetry} /></div>);
    expect(screen.queryByTestId("still-checking")).toBeNull();
    fireEvent.click(within(screen.getByTestId("first-rest-failed")).getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("reads in Spanish (usted) with the approximate label", async () => {
    await i18n.changeLanguage("es");
    render(<div className="ui-next"><FirstOverview first={firstFixture({ resolved_confidence: "approximate", lot: null })} identity="approximate" restFailed={false} onRetry={vi.fn()} /></div>);
    // The ratio as the full answer sentence writes it (2.2, the term "coeficiente de edificabilidad (FAR)").
    expect(screen.getByTestId("first-sentence").textContent).toBe("Zonificación B3-2: un coeficiente de edificabilidad (FAR) de 2.2, con hasta 50 pies de altura.");
    expect(screen.getByText("Coincidencia aproximada")).toBeTruthy();
    expect(screen.getByTestId("still-checking").textContent).toMatch(/^Seguimos revisando/);
    expect(screen.getByTestId("overview-tiles").textContent).not.toMatch(/Checking/);
  });
});

describe("ProfileSkeleton (before the first screen, Item 89)", () => {
  it("draws the Profile's outline: the address, the four tiles in place, a status line, no time estimate", async () => {
    render(<ProfileSkeleton address="3500 S Halsted St" />);
    expect(screen.getByTestId("skeleton-tiles").querySelectorAll("li")).toHaveLength(4);
    expect(screen.getByRole("status").textContent).toContain("3500 S Halsted St");
    expect(screen.getByTestId("profile-loading").textContent).not.toMatch(/second/i);
    expect(await axeViolations(document.body)).toEqual([]);
  });

  it("reads in Spanish", async () => {
    await i18n.changeLanguage("es");
    render(<ProfileSkeleton address="3500 S Halsted St" />);
    expect(screen.getByRole("status").textContent).toContain("3500 S Halsted St");
    expect(screen.getByRole("status").textContent).not.toBe(i18n.t("profile.loading.at", { ns: "next", lng: "en", address: "3500 S Halsted St" }));
  });
});
