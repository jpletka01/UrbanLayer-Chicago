import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AddFilterMenu, type FilterPopoverView } from "./AddFilterMenu";
import { REG } from "./_fixtures";
import type { Predicate, Registry } from "./types";

afterEach(cleanup);

const REGISTRY: Registry = {
  ...REG,
  filters: [
    { id: "land_use", category: "property_use", kind: "enum", field: "land_use_class", unknownPolicy: "exclude", enumValues: ["residential", "multi_family"], tier: "essential" },
    { id: "lot_size", category: "property_use", kind: "range", field: "land_sqft", unknownPolicy: "exclude", unit: "sqft", tier: "essential" },
    { id: "tif", category: "incentives", kind: "flag", field: "in_tif_district", unknownPolicy: "exclude", tier: "more" },
    { id: "upside_score", category: "zoning_dev", kind: "range", field: "upside_score", unknownPolicy: "exclude", tier: "more", label: "Redevelopment upside" },
    { id: "floodplain", category: "condition_risk", kind: "flag", field: "in_special_flood_hazard", unknownPolicy: "exclude", tier: "more" },
    { id: "adu_eligible", category: "zoning_dev", kind: "flag", field: "in_adu_area", unknownPolicy: "exclude", tier: "more" },
  ],
  populatedFields: ["land_use", "lot_size", "tif", "upside_score"],
};

function setup(view: Exclude<FilterPopoverView, null>, values: Record<string, Predicate> = {}, pendingCount = 0) {
  const onChange = vi.fn();
  const onView = vi.fn();
  const onClose = vi.fn();
  const onApply = vi.fn();
  const utils = render(
    <div>
      <button type="button" data-filter-popover-anchor="" data-testid="anchor">anchor</button>
      <span data-testid="outside">outside</span>
      <AddFilterMenu registry={REGISTRY} view={view} values={values} onChange={onChange} onView={onView} onClose={onClose} pendingCount={pendingCount} onApply={onApply} />
    </div>,
  );
  return { onChange, onView, onClose, onApply, ...utils };
}

const dialog = () => screen.getByTestId("discovery-filter-popover");

describe("AddFilterMenu: the menu view", () => {
  it("lists live filters under Essentials and More filters, in that order", () => {
    setup({ kind: "menu" });
    const headings = within(dialog()).getAllByRole("heading").map((h) => h.textContent);
    expect(headings).toEqual(["Essentials", "More filters"]);
    expect(within(dialog()).getByRole("button", { name: "Property use" })).toBeTruthy();
    expect(within(dialog()).getByRole("button", { name: /^TIF district/ })).toBeTruthy();
  });

  it("keeps filters with no data in a collapsed 'Coming soon' row, and says why they do nothing", () => {
    setup({ kind: "menu" });
    const soon = within(dialog()).getByRole("button", { name: /Coming soon \(2\)/ });
    expect(soon.getAttribute("aria-expanded")).toBe("false");
    expect(within(dialog()).queryByText("Floodplain")).toBeNull();
    fireEvent.click(soon);
    expect(within(dialog()).getByText("Floodplain")).toBeTruthy();
    expect(within(dialog()).getByText("ADU-eligible")).toBeTruthy();
    expect(within(dialog()).getByText("No data for these in the index yet.")).toBeTruthy();
    // listed, not offered: no control to add them
    expect(within(dialog()).queryByRole("button", { name: "Floodplain" })).toBeNull();
  });

  it("searches by name and says when nothing matches", () => {
    setup({ kind: "menu" });
    fireEvent.change(screen.getByRole("searchbox", { name: "Search filters" }), { target: { value: "lot" } });
    expect(within(dialog()).getByRole("button", { name: "Lot size" })).toBeTruthy();
    expect(within(dialog()).queryByRole("button", { name: "Property use" })).toBeNull();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search filters" }), { target: { value: "zzzz" } });
    expect(within(dialog()).getByText("No filter matches that.")).toBeTruthy();
  });

  it("marks a filter already in the search", () => {
    setup({ kind: "menu" }, { tif: { kind: "flag", value: true } });
    expect(within(within(dialog()).getByRole("button", { name: /^TIF district/ })).getByText("In your search")).toBeTruthy();
  });

  it("tags the upside score as a heuristic", () => {
    setup({ kind: "menu" });
    expect(within(within(dialog()).getByRole("button", { name: /Redevelopment upside/ })).getByText("heuristic")).toBeTruthy();
  });

  it("choosing a flag adds it as Yes and opens its editor; other kinds just open the editor", () => {
    const flag = setup({ kind: "menu" });
    fireEvent.click(within(dialog()).getByRole("button", { name: /^TIF district/ }));
    expect(flag.onChange).toHaveBeenCalledWith("tif", { kind: "flag", value: true });
    expect(flag.onView).toHaveBeenCalledWith({ kind: "edit", id: "tif" });
    cleanup();

    const range = setup({ kind: "menu" });
    fireEvent.click(within(dialog()).getByRole("button", { name: "Lot size" }));
    expect(range.onChange).not.toHaveBeenCalled(); // nothing to add until the user gives it a value
    expect(range.onView).toHaveBeenCalledWith({ kind: "edit", id: "lot_size" });
  });
});

describe("AddFilterMenu: the editor view", () => {
  it("reuses the filter's own control and writes the draft through onChange", () => {
    const { onChange } = setup({ kind: "edit", id: "land_use" });
    fireEvent.click(within(dialog()).getByRole("button", { name: "Multifamily" }));
    expect(onChange).toHaveBeenCalledWith("land_use", { kind: "enum", values: ["multi_family"] });
  });

  it("shows the current value and resets just this filter", () => {
    const { onChange } = setup({ kind: "edit", id: "lot_size" }, { lot_size: { kind: "range", min: 3000 } });
    expect((screen.getByRole("spinbutton", { name: /Minimum Lot size/i }) as HTMLInputElement).value).toBe("3000");
    fireEvent.click(within(dialog()).getByRole("button", { name: "Reset this filter" }));
    expect(onChange).toHaveBeenCalledWith("lot_size", null);
  });

  it("Reset is disabled when the filter has no value", () => {
    setup({ kind: "edit", id: "lot_size" });
    expect((within(dialog()).getByRole("button", { name: "Reset this filter" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("Done closes, and 'All filters' goes back to the menu", () => {
    const { onClose, onView } = setup({ kind: "edit", id: "tif" }, { tif: { kind: "flag", value: true } });
    // two Done buttons in the DOM: the inline one (desktop) and the sheet footer (phones, via CSS)
    fireEvent.click(within(dialog()).getAllByRole("button", { name: "Done" })[0]);
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(within(dialog()).getByRole("button", { name: /All filters/ }));
    expect(onView).toHaveBeenCalledWith({ kind: "menu" });
  });

  it("says the upside score is a rough heuristic, not an appraisal", () => {
    setup({ kind: "edit", id: "upside_score" });
    expect(within(dialog()).getAllByText(/not an appraisal/).length).toBeGreaterThan(0);
  });
});

describe("AddFilterMenu: closing", () => {
  it("closes on Escape", () => {
    const { onClose } = setup({ kind: "menu" });
    fireEvent.keyDown(dialog(), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on a click outside, but not on its own anchor (which toggles it itself)", () => {
    const { onClose } = setup({ kind: "menu" });
    fireEvent.mouseDown(screen.getByTestId("anchor"));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.mouseDown(within(dialog()).getByRole("searchbox"));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("puts focus in the search box on open and returns it to the opener on close", () => {
    const opener = document.createElement("button");
    document.body.appendChild(opener);
    opener.focus();
    const { unmount } = setup({ kind: "menu" });
    expect(document.activeElement).toBe(screen.getByRole("searchbox"));
    unmount();
    expect(document.activeElement).toBe(opener);
    opener.remove();
  });
});

describe("AddFilterMenu: the phone sheet's footer action", () => {
  const footer = () => screen.getByTestId("discovery-sheet-footer-action");

  it("with nothing pending it is just Done: it closes and applies nothing", () => {
    const { onClose, onApply } = setup({ kind: "menu" }, {}, 0);
    expect(footer().textContent).toBe("Done");
    fireEvent.click(footer());
    expect(onApply).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("with edits pending it says how many, applies them, and closes", () => {
    const { onClose, onApply } = setup({ kind: "menu" }, {}, 2);
    expect(footer().textContent).toBe("Show results (2)");
    fireEvent.click(footer());
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("is there in the editor view too, and is a phones-only element (md:hidden)", () => {
    setup({ kind: "edit", id: "tif" }, { tif: { kind: "flag", value: true } }, 1);
    expect(footer().textContent).toBe("Show results (1)");
    expect(footer().parentElement!.className).toContain("md:hidden");
  });
});
