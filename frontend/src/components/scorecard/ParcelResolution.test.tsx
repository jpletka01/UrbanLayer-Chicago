import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ParcelResolution } from "./ParcelResolution";
import type { ParcelResolutionRecord } from "../../lib/api";

afterEach(cleanup);

const base: ParcelResolutionRecord = {
  method: "address_points", point_basis: "address_point", input_address: "1601 N Milwaukee Ave", pin: "14313320180000",
  confidence: "authoritative", point: { lat: 41.9, lon: -87.7 }, centroid_gap_ft: 5, candidates: [],
  multiple_parcels: false, sources_disagree: false, identity_unconfirmed: false, unverified_reason: null, property_record_pin: null,
};

describe("ParcelResolution — how we matched this parcel (V3)", () => {
  it("names the record that matched and how far its point is from the parcel's center", () => {
    render(<ParcelResolution resolution={base} />);
    const el = screen.getByTestId("parcel-resolution");
    expect(el.textContent).toContain("Matched by Cook County Address Points");
    expect(el.textContent).toContain("5 ft from the parcel's center");
    expect(screen.queryByTestId("resolution-candidates")).toBeNull();
    expect(screen.queryByTestId("resolution-unconfirmed")).toBeNull();
  });

  it("an address that maps to three parcels lists them all and marks the one shown (kit P5)", () => {
    render(
      <ParcelResolution
        resolution={{
          ...base, multiple_parcels: true,
          candidates: [
            { pin: "14313320160000", sources: ["assessor_addresses"], used: false },
            { pin: "14313320170000", sources: ["assessor_addresses"], used: false },
            { pin: "14313320180000", sources: ["address_points", "assessor_addresses"], used: true },
          ],
        }}
      />,
    );
    const box = screen.getByTestId("resolution-candidates");
    expect(box.textContent).toContain("This address maps to 3 parcels");
    expect(screen.getAllByTestId("candidate")).toHaveLength(2);
    const used = screen.getByTestId("candidate-used");
    expect(used.textContent).toContain("14-31-332-018-0000");
    expect(used.textContent).toContain("the one shown");
    expect(used.textContent).toContain("Address Points, Assessor");
    expect(box.textContent).not.toContain("name different ones");
  });

  it("says so when the county's two address records name different parcels (kit P3)", () => {
    render(
      <ParcelResolution
        resolution={{
          ...base, multiple_parcels: true, sources_disagree: true,
          candidates: [
            { pin: "14171060250000", sources: ["address_points"], used: true },
            { pin: "14171060440000", sources: ["assessor_addresses"], used: false },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("resolution-candidates").textContent).toContain("name different ones");
  });

  it("an unconfirmed identity says why and names the parcel the figures may describe (kit P4)", () => {
    render(
      <ParcelResolution
        resolution={{ ...base, pin: "17101350390000", identity_unconfirmed: true, unverified_reason: "property_record_is_another_parcel", property_record_pin: "17101350382166" }}
      />,
    );
    const note = screen.getByTestId("resolution-unconfirmed");
    expect(note.textContent).toContain("Identity unconfirmed");
    expect(note.textContent).toContain("17-10-135-039-0000");
    expect(note.textContent).toContain("17-10-135-038-2166");
  });

  it("a geocode-only match is labelled approximate, not a match", () => {
    render(<ParcelResolution resolution={{ ...base, method: "geocode_nearest", confidence: "approximate", pin: null, centroid_gap_ft: null }} />);
    const el = screen.getByTestId("parcel-resolution");
    expect(el.textContent).toContain("the geocoded point only (nearest parcel, approximate)");
    expect(el.textContent).not.toContain("from the parcel's center");
  });

  it("a PIN the user gave is stated as such; older payloads render nothing", () => {
    render(<ParcelResolution resolution={{ ...base, method: "pin", point_basis: "parcel_centroid", centroid_gap_ft: 0 }} />);
    expect(screen.getByTestId("parcel-resolution").textContent).toContain("the PIN you gave");
    cleanup();
    const { container } = render(<ParcelResolution resolution={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("a condominium building says its units have their own PINs and caps the list (kit P4)", () => {
    const units = Array.from({ length: 50 }, (_, i) => ({ pin: `171013503${String(91001 + i).padStart(5, "0")}`.slice(0, 14), sources: ["assessor_addresses" as const], used: false }));
    render(
      <ParcelResolution
        resolution={{
          ...base, pin: "17101350390000", multiple_parcels: true, condo_units: 50, sources_disagree: false,
          candidates: [{ pin: "17101350390000", sources: ["address_points"], used: true }, ...units],
        }}
      />,
    );
    const box = screen.getByTestId("resolution-candidates");
    expect(box.textContent).toContain("This is a condominium building: 50 units each have their own PIN");
    expect(box.textContent).not.toContain("name different ones");
    expect(screen.getByTestId("candidate-used").textContent).toContain("17-10-135-039-0000"); // the matched one leads
    expect(screen.getAllByTestId("candidate")).toHaveLength(7); // 8 shown in all
    expect(box.textContent).toContain("and 43 more");
  });
});
