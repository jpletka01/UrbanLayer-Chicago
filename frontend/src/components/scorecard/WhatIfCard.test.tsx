import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import i18n from "i18next";

vi.mock("../../lib/api", () => ({ fetchWhatIf: vi.fn() }));

import { fetchWhatIf, type WhatIfFigures } from "../../lib/api";
import { WhatIfCard } from "./WhatIfCard";

const fig = (over: Partial<WhatIfFigures>): WhatIfFigures => ({
  zone_class: "RS-3", name: "Residential Single-Unit", code_section: "§17-2-0102", far: 0.9, max_floor_area_sqft: 2812,
  max_height: "30 ft", min_lot_area_per_unit: 2500, units_by_lot_area: 1, units_arithmetic: null, ...over,
});

beforeEach(() => {
  vi.mocked(fetchWhatIf).mockReset();
  vi.mocked(fetchWhatIf).mockImplementation(async (_current, district) => district
    ? { suggestions: ["RT-3.5", "RT-4"], districts: ["RS-3", "RT-3.5", "RT-4", "B3-2"], lot_sqft: 3125,
        current: fig({}), target: fig({ zone_class: "RT-4", far: 1.2, max_floor_area_sqft: 3750, max_height: "38 ft", units_by_lot_area: 3, code_section: "§17-2-0103" }) }
    : { suggestions: ["RT-3.5", "RT-4"], districts: ["RS-3", "RT-3.5", "RT-4", "B3-2"] });
});
afterEach(async () => {
  cleanup();
  await i18n.changeLanguage("en");
});

describe("WhatIfCard", () => {
  it("offers the next districts and compares one with today's", async () => {
    render(<WhatIfCard currentDistrict="RS-3" lotSqft={3125} in606={false} />);
    fireEvent.click(await screen.findByRole("button", { name: "RT-4" }));
    const table = await screen.findByTestId("what-if-table");
    expect(table.textContent).toContain("Today: RS-3");
    expect(table.textContent).toContain("If RT-4");
    expect(table.textContent).toContain("3,750 sq ft");
    expect(fetchWhatIf).toHaveBeenLastCalledWith("RS-3", "RT-4", 3125, false);
    expect(screen.getByTestId("what-if").textContent).toContain("City Council approval");
    expect(screen.getByTestId("what-if").textContent).not.toMatch(/you can build/i);
  });

  it("any district is a select of every other district", async () => {
    render(<WhatIfCard currentDistrict="RS-3" lotSqft={3125} />);
    const select = (await screen.findByTestId("what-if-any")) as HTMLSelectElement;
    expect([...select.options].map((o) => o.value)).toEqual(["", "RT-3.5", "RT-4", "B3-2"]);
    fireEvent.change(select, { target: { value: "B3-2" } });
    expect(fetchWhatIf).toHaveBeenLastCalledWith("RS-3", "B3-2", 3125, undefined);
  });

  it("a failed comparison says so", async () => {
    render(<WhatIfCard currentDistrict="RS-3" lotSqft={3125} />);
    const btn = await screen.findByRole("button", { name: "RT-3.5" });
    vi.mocked(fetchWhatIf).mockResolvedValueOnce(null);
    fireEvent.click(btn);
    expect((await screen.findByRole("status")).textContent).toContain("Couldn't load");
  });

  it("renders in Spanish", async () => {
    await i18n.changeLanguage("es");
    render(<WhatIfCard currentDistrict="RS-3" lotSqft={3125} />);
    expect(await screen.findByText("¿Y si se cambiara la zonificación?")).toBeTruthy();
  });
});
