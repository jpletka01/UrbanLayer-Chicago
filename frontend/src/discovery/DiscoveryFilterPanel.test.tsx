import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { DiscoveryFilterPanel } from "./DiscoveryFilterPanel";
import type { FilterDef, Registry } from "./types";

afterEach(cleanup);

const FILTERS: FilterDef[] = [
  { id: "vacancy", category: "property_use", kind: "flag", field: "is_vacant", unknownPolicy: "exclude", label: "Vacant" },
  {
    id: "land_use", category: "property_use", kind: "enum", field: "land_use_class", unknownPolicy: "exclude",
    enumValues: ["vacant", "multi_family"], enumLabels: { vacant: "Vacant land", multi_family: "Multifamily" }, label: "Property use",
  },
  {
    id: "transit_proximity", category: "location", kind: "range", field: "cta_rail_distance_mi", unknownPolicy: "exclude",
    label: "Near transit", unit: "mi",
    range: { domain: [0, 3], step: 0.1, boundMode: "max", display: "mi", presets: [{ label: "½ mi", max: 0.5 }] },
  },
  {
    id: "year_built", category: "property_use", kind: "range", field: "year_built", unknownPolicy: "exclude",
    label: "Year built", range: { domain: [1850, 2025], step: 1, boundMode: "both", display: "year" },
  },
];

function reg(populated: string[]): Registry {
  return {
    version: "v1", filters: FILTERS, topics: [],
    sortKeys: [{ key: "pin", field: "pin" }], defaultSort: { key: "pin", dir: "asc" }, broadMinFilters: 2,
    coverage: { mode: "partial", liveAreas: [24] }, populatedFields: populated,
  };
}

describe("DiscoveryFilterPanel a11y", () => {
  function open(populated: string[]) {
    const registry = reg(populated);
    render(<DiscoveryFilterPanel registry={registry} state={{}} onChange={vi.fn()} />);
    // categories collapse by default — expand the two we assert on.
    fireExpand("Property & use");
    fireExpand("Location");
  }
  function fireExpand(label: string) {
    fireEvent.click(screen.getByRole("button", { name: new RegExp(label, "i") }));
  }

  it("flag pills expose aria-pressed", () => {
    open(["vacancy"]);
    const any = screen.getByRole("button", { name: "Any" });
    expect(any.getAttribute("aria-pressed")).toBe("true"); // nothing selected → Any pressed
    expect(screen.getByRole("button", { name: "Yes" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("enum pills expose aria-pressed and use enumLabels", () => {
    open(["land_use"]);
    const pill = screen.getByRole("button", { name: "Multifamily" });
    expect(pill.getAttribute("aria-pressed")).toBe("false");
  });

  it("preset-backed ranges render a radiogroup with aria-checked", () => {
    open(["transit_proximity"]);
    expect(screen.getByRole("radiogroup", { name: "Near transit" })).toBeTruthy();
    const half = screen.getByRole("radio", { name: "½ mi" });
    expect(half.getAttribute("aria-checked")).toBe("false");
    expect(screen.getByRole("radio", { name: "Any" }).getAttribute("aria-checked")).toBe("true");
  });

  it("min/max range inputs are individually labeled, with domain bounds", () => {
    open(["year_built"]);
    const min = screen.getByLabelText("minimum Year built") as HTMLInputElement;
    const max = screen.getByLabelText("maximum Year built") as HTMLInputElement;
    expect(min.min).toBe("1850");
    expect(max.max).toBe("2025");
  });

  it("unpopulated filters read 'coming', never a live control", () => {
    open([]); // nothing populated
    expect(screen.getAllByText(/Coming with the next data update/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });
});
