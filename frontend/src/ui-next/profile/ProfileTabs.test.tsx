// The new Profile's Overview and Build tabs, rendered from a typed fixture with no network, with axe checks.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import i18n from "../../lib/i18n";
import { computeVerdict } from "../../lib/scorecardVerdict";
import { profileFixture } from "../test/fixtures";
import { axeViolations } from "../test/axe";
import { OverviewTab } from "./OverviewTab";
import { BuildTab } from "./BuildTab";

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
    expect(tiles.map((li) => li.getAttribute("data-tile"))).toEqual(["units", "zoning", "tax", "pricePerSqft"]);
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
