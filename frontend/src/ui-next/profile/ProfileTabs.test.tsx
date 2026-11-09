// The new Profile's Overview, Build and Money tabs, rendered from a typed fixture with no network, with axe checks.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import i18n from "../../lib/i18n";
import { computeVerdict } from "../../lib/scorecardVerdict";
import { profileFixture } from "../test/fixtures";
import { axeViolations } from "../test/axe";
import { OverviewTab } from "./OverviewTab";
import { BuildTab } from "./BuildTab";
import { MoneyTab } from "./MoneyTab";

const tp = (key: string, opts?: Record<string, unknown>) => i18n.t(key, { ns: "pages", ...opts }) as string;

afterEach(async () => { cleanup(); await i18n.changeLanguage("en"); });

function renderOverview(onOpenTab = vi.fn()) {
  const data = profileFixture();
  const { container } = render(
    <div className="ui-next"><OverviewTab data={data} verdict={computeVerdict(data, tp)} identity="exact" onOpenTab={onOpenTab} /></div>,
  );
  return { container, onOpenTab };
}

describe("Overview", () => {
  it("leads with the answer sentence, then four tiles with icon, label and figure", async () => {
    const { container, onOpenTab } = renderOverview();
    expect(screen.getByTestId("answer-sentence").textContent).toMatch(/^B3-2 allows/);
    const tiles = within(screen.getByTestId("overview-tiles")).getAllByRole("listitem");
    expect(tiles).toHaveLength(4);
    expect(tiles.map((li) => li.getAttribute("data-tile"))).toEqual(["units", "tax", "walk", "lastSale"]);
    for (const li of tiles) expect(li.querySelector("svg")).not.toBeNull();
    fireEvent.click(within(tiles[0]).getByRole("button"));
    expect(onOpenTab).toHaveBeenCalledWith("build");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("renders in Spanish (usted) with no English left in the tiles", async () => {
    await i18n.changeLanguage("es");
    renderOverview();
    const text = screen.getByTestId("overview-tiles").textContent ?? "";
    expect(text).toContain("Unidades permitidas");
    expect(text).toContain("Impuesto predial");
    expect(text).not.toMatch(/Units allowed|Property tax/);
  });
});

describe("Build", () => {
  it("draws allowed vs built with the deciding limit, pending rezonings and rule chips", async () => {
    const data = profileFixture();
    const { container } = render(<div className="ui-next"><BuildTab data={data} verdict={computeVerdict(data, tp)} /></div>);
    const avb = screen.getByTestId("allowed-vs-built");
    expect(avb.querySelectorAll("[data-deciding]")).toHaveLength(1);
    expect(avb.querySelector("[data-deciding]")!.textContent).toContain("Floor area");
    expect(screen.getAllByRole("img", { name: /Floor area: 14,700 sq ft built of 24,750 sq ft allowed/ })).toHaveLength(1);
    expect(screen.getByText("Map amendment, 1650 N Damen").closest("a")!.getAttribute("target")).toBe("_blank");
    expect(screen.getByRole("list", { name: /Stage: Committee/ })).toBeTruthy();
    const landmark = container.querySelector('[data-rule="landmark"]')!;
    expect(landmark.getAttribute("data-answer")).toBe("yes");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("says when the Clerk couldn't be checked instead of saying none", () => {
    const data = profileFixture({ context: { upcoming_zoning: null } } as never);
    render(<div className="ui-next"><BuildTab data={data} verdict={computeVerdict(data, tp)} /></div>);
    expect(screen.getByText(/couldn't be checked today/)).toBeTruthy();
  });
});

describe("Money", () => {
  const ready = { money: "ready", incentives: "ready", neighborhood: "ready" } as const;
  const sales = [
    { pin: "1", sale_date: "2024-03-01T00:00:00.000", sale_price: 900000, zone_class: "B3-2", distance_mi: 0.12, price_per_buildable_sqft: 140, lat: 41.91, lon: -87.68 },
    { pin: "2", sale_date: "2023-06-01T00:00:00.000", sale_price: 700000, zone_class: "RS-3", distance_mi: 0.2, price_per_buildable_sqft: null, lat: 41.91, lon: -87.68 },
    { pin: "3", sale_date: "2022-01-01T00:00:00.000", sale_price: 1100000, zone_class: "B3-2", distance_mi: 0.24, price_per_buildable_sqft: 150, lat: 41.91, lon: -87.68 },
  ];
  const moneyData = () => profileFixture({
    comparables: { median_sale_price: 900000, sales_volume: 3, comp_basis: "Class 5xx sales within 0.25 mi, last 3 yr (n=3)", comp_radius_mi: 0.25, comp_window_years: 3, comp_widened: false, sales },
    context: { property: {
      tax_breakdown: [{ agency: "BOARD OF EDUCATION", rate: 3.6, amount: 34000 }, { agency: "CITY OF CHICAGO", rate: 1.6, amount: 15000 }, { agency: "COUNTY OF COOK", rate: 0.4, amount: 4000 }],
      assessment_history: [{ year: 2023, land: 80000, building: 160000, total: 240000 }, { year: 2024, land: 90000, building: 160000, total: 250000 }],
    } },
  } as never);

  it("leads with the sentence, then sales with their rule, taxes, rent and incentives", async () => {
    const { container } = render(<div className="ui-next"><MoneyTab data={moneyData()} late={ready} onRetry={vi.fn()} /></div>);
    expect(screen.getByTestId("money-sentence").textContent).toBe("About $64,000 a year in property tax, on an Assessor's value of $1,000,000; 3 nearby market sales, median $900,000.");
    expect(within(screen.getByTestId("sales-rule")).getByText("Within 0.25 mi")).toBeTruthy();
    expect(screen.getByTestId("price-strip")).toBeTruthy();
    expect(within(screen.getByTestId("sales-list")).getAllByRole("row")).toHaveLength(4);
    expect(screen.getByTestId("agency-bar").getAttribute("aria-label")).toContain("Board of Education");
    expect(screen.getByTestId("value-bars")).toBeTruthy();
    expect(screen.getByText("Couldn't check rent today")).toBeTruthy(); // the fixture has no rent: never "none"
    expect(await axeViolations(container)).toEqual([]);
  });

  it("shows each late block's own outline while it waits, and Retry in place when it ran out of time", () => {
    const onRetry = vi.fn();
    const { rerender } = render(<div className="ui-next"><MoneyTab data={moneyData()} late={{ ...ready, money: "loading", incentives: "loading" }} onRetry={onRetry} /></div>);
    expect(screen.getByText("Checking nearby sales…")).toBeTruthy();
    expect(screen.queryByTestId("sales-list")).toBeNull();
    expect(document.querySelector('[data-incentive="qct"]')!.getAttribute("data-answer")).toBe("checking");
    rerender(<div className="ui-next"><MoneyTab data={moneyData()} late={{ ...ready, money: "timedOut" }} onRetry={onRetry} /></div>);
    fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
    expect(onRetry).toHaveBeenCalledWith("money");
  });

  it("renders in Spanish (usted) with no English left in the blocks", async () => {
    await i18n.changeLanguage("es");
    render(<div className="ui-next"><MoneyTab data={moneyData()} late={ready} onRetry={vi.fn()} /></div>);
    const text = screen.getByTestId("money-tab").textContent ?? "";
    expect(text).toContain("Ventas de mercado cercanas");
    expect(text).toContain("Impuestos y valor");
    expect(text).not.toMatch(/Nearby market sales|Taxes and value|Rent nearby/);
  });
});
