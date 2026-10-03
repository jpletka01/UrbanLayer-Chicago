import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ScorecardRegulatoryCard } from "./ScorecardRegulatoryCard";
import type { AduStatus, RegulatorySummary, TodBenefits } from "../../lib/types";

afterEach(cleanup);

const base = {
  overlays: [], in_planned_development: false, in_landmark_district: false, is_landmark_building: false,
  in_historic_district: false, on_national_register: false, in_lakefront_protection: false, on_pedestrian_street: false,
  in_special_district: false, in_pmd: false, in_tod_area: false, in_adu_area: false, in_aro_zone: false, in_ssa: false,
  flood_zone: null, flood_zone_subtype: null, in_special_flood_hazard: false, brownfield_sites: [],
} as unknown as RegulatorySummary;

const zone10 = {
  layer_type: "adu_area", name: "ADU-Allowed RS Area — Zone 10", ordinance: null, description: "ADU Eligible Areas",
  detail: "Limitations: Annual Limits, Owner Occupancy Limits (§17-7-0573, §17-7-0574).", link: null,
};
const aduWithLimits: AduStatus = {
  status: "allowed_with_limits", zone: "ADU-Allowed RS Area — Zone 10", limits: zone10.detail,
  note: "Coach houses and conversion units are permitted by right in this RS district because the parcel is in the ADU-Allowed RS Area — Zone 10 (§17-7-0570). Limitations: Annual Limits, Owner Occupancy Limits (§17-7-0573, §17-7-0574).",
};

describe("ScorecardRegulatoryCard — overlays named, with what they require (F7)", () => {
  it("RS parcel in an ADU zone: names Zone 10 and states its annual-limit and owner-occupancy limits (kit P6)", () => {
    render(<ScorecardRegulatoryCard data={{ ...base, in_adu_area: true, overlays: [zone10] }} adu={aduWithLimits} />);
    expect(screen.getAllByText(/Zone 10/).length).toBeGreaterThan(0);
    const notes = screen.getByTestId("overlay-notes");
    expect(notes.textContent).toContain("Annual Limits, Owner Occupancy Limits");
    expect(notes.textContent).toContain("§17-7-0570");
  });

  it("non-RS parcel: the ADU layer artifact is replaced by 'permitted by right' (kit P7)", () => {
    const adu: AduStatus = { status: "allowed_by_right", zone: null, limits: null, note: "Coach houses and conversion units are permitted by right in this district (§17-2-0207)." };
    render(<ScorecardRegulatoryCard data={{ ...base, in_adu_area: true, overlays: [zone10] }} adu={adu} />);
    expect(screen.queryByText(/Zone 10/)).toBeNull();
    expect(screen.getAllByText(/permitted by right/).length).toBeGreaterThan(0);
  });

  it("older payloads without adu keep the flag row (no behavior change)", () => {
    render(<ScorecardRegulatoryCard data={{ ...base, in_adu_area: true }} />);
    expect(screen.getAllByText(/ADU/i).length).toBeGreaterThan(0);
  });

  it("names the 606 special district and links its code section", () => {
    const sd = {
      layer_type: "special_district", name: "Predominance of the Block (606) District", ordinance: null, description: "Special Districts",
      detail: "Applies to RS-3 and RT-3.5 parcels only (§17-7-0591).", link: "https://codelibrary.amlegal.com/x",
    };
    render(<ScorecardRegulatoryCard data={{ ...base, in_special_district: true, overlays: [sd] }} />);
    expect(screen.getAllByText(/Predominance of the Block \(606\) District/).length).toBeGreaterThan(0);
    const link = screen.getByTestId("overlay-notes").querySelector("a");
    expect(link?.getAttribute("href")).toBe("https://codelibrary.amlegal.com/x");
  });

  it("links the Planned Development ordinance PDF and says the standards live there (kit P4)", () => {
    const pd = {
      layer_type: "planned_development", name: "Planned Development 835", ordinance: "13559", description: "Planned Developments",
      detail: "Height, floor area and use standards come from the PD ordinance's plan of development and bulk table, not from Title 17's base-district tables.",
      link: "https://gisapps.chicago.gov/gisimages/zoning_pds/PD835.pdf",
    };
    const { container } = render(<ScorecardRegulatoryCard data={{ ...base, in_planned_development: true, overlays: [pd] }} />);
    expect(screen.getAllByText(/Planned Development 835/).length).toBeGreaterThan(0);
    expect(container.textContent).toContain("bulk table");
    expect(container.querySelector('a[href$="PD835.pdf"]')).not.toBeNull();
  });

  it("a landmark states the Commission's written-approval requirement, not 'design review' (kit P5)", () => {
    const lm = {
      layer_type: "landmark_building", name: "Noel State Bank", ordinance: null, description: "Individual Landmark Buildings",
      detail: "Individual Chicago Landmark: a permit to alter, demolish or add to it needs the Commission on Chicago Landmarks' written approval (§2-120-740).",
      link: null,
    };
    const { container } = render(<ScorecardRegulatoryCard data={{ ...base, is_landmark_building: true, overlays: [lm] }} />);
    expect(container.textContent).toContain("written approval");
    expect(container.textContent).toContain("§2-120-740");
    expect(container.textContent?.toLowerCase()).not.toContain("design review");
  });
});


describe("ScorecardRegulatoryCard — what transit-served status changes (kit P5)", () => {
  const tod = { layer_type: "tod_cta", name: "Transit-Oriented Development (CTA)", ordinance: null, description: "Transit-Oriented Development (CTA)", detail: null, link: null };
  const benefits: TodBenefits = {
    parking_relief: true, parking_max_reduction_pct: 100, density_bonus_eligible: false, entitlement_required: false,
    note: "Transit-served: minimum parking can be reduced by up to 100% (§17-10-0102-B). No density, FAR or height bonus at B3-2.",
  };

  it("states the parking amount and the absent density bonus on the transit row", () => {
    render(<ScorecardRegulatoryCard data={{ ...base, in_tod_area: true, overlays: [tod] }} tod={benefits} />);
    const notes = screen.getByTestId("overlay-notes").textContent ?? "";
    expect(notes).toContain("up to 100%");
    expect(notes).toContain("No density, FAR or height bonus at B3-2");
  });

  it("says it once even when both a CTA and a Metra overlay are present", () => {
    const metra = { ...tod, layer_type: "tod_metra", name: "Transit-Oriented Development (Metra)" };
    render(<ScorecardRegulatoryCard data={{ ...base, in_tod_area: true, overlays: [tod, metra] }} tod={benefits} />);
    expect((screen.getByTestId("overlay-notes").textContent ?? "").split("up to 100%").length - 1).toBe(1);
  });

  it("older payloads without tod_benefits render as before", () => {
    render(<ScorecardRegulatoryCard data={{ ...base, in_tod_area: true, overlays: [tod] }} />);
    expect(screen.getAllByText(/Transit/i).length).toBeGreaterThan(0);
  });
});
