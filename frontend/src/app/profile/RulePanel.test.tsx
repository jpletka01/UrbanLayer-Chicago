// A Build rule's page in the right panel (decision Item 99): the City's own code-pinned sentence for each record,
// the record and its source, who decides, and Ask last; a failed check never reads as "doesn't apply".
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import i18n from "../../lib/i18n";
import { computeVerdict } from "../../lib/scorecardVerdict";
import { profileFixture } from "../test/fixtures";
import { axeViolations } from "../test/axe";
import { AskContext } from "../ask/askContext";
import { RulePanel } from "./RulePanel";
import { BuildTab } from "./BuildTab";

const tp = (key: string, opts?: Record<string, unknown>) => i18n.t(key, { ns: "pages", ...opts }) as string;
afterEach(async () => { cleanup(); await i18n.changeLanguage("en"); });

const DETAIL = "Chicago Landmark district: permits to alter or demolish a building need the Commission on Chicago Landmarks' written approval (§2-120-740).";
const data = () => profileFixture({ context: {
  regulatory: { overlays: [
    { layer_type: "historic_district", name: "Milwaukee Avenue District", description: "Historic Districts", ordinance: null, detail: DETAIL, link: "https://example.org/landmark" },
    { layer_type: "tod_cta", name: "Transit-Oriented Development (CTA)", description: "Transit-Oriented Development (CTA)", ordinance: null },
  ] },
  tod_benefits: { parking_relief: true, parking_max_reduction_pct: 100, density_bonus_eligible: false, entitlement_required: false, note: "Transit-served: minimum parking can be reduced by up to 100% (17-10-0102-B)." },
} } as never);

const renderRule = (rule: "landmark" | "tod" | "flood", answer: "yes" | "no" | "notChecked", open = vi.fn()) => render(
  <div className="ui-next">
    <AskContext.Provider value={{ ready: true, address: "1601 N Milwaukee Ave", open }}>
      <RulePanel data={data()} rule={rule} answer={answer} blocks={rule === "landmark"} onClose={vi.fn()} instant />
    </AskContext.Provider>
  </div>,
);

describe("the rule panel", () => {
  it("leads with the City's own sentence, lists the record with its source, and says it changes the build answer", async () => {
    const { container } = renderRule("landmark", "yes");
    const panel = screen.getByTestId("rule-panel");
    expect(panel.textContent).toContain("Changes what can be built");
    expect(screen.getByTestId("rule-means").textContent).toContain("Commission on Chicago Landmarks' written approval");
    expect(within(screen.getByTestId("rule-records")).getByText("Milwaukee Avenue District")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Read the source/ }).getAttribute("target")).toBe("_blank");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("uses the backend's own note for transit-served lots, and Ask writes a question about this lot", () => {
    const open = vi.fn();
    renderRule("tod", "yes", open);
    expect(screen.getByTestId("rule-means").textContent).toContain("reduced by up to 100%");
    fireEvent.click(screen.getByTestId("rule-ask"));
    expect(open).toHaveBeenCalledWith("What does Transit-oriented area mean for a project at 1601 N Milwaukee Ave?");
  });

  it("never reads a failed check as 'doesn't apply'", () => {
    renderRule("flood", "notChecked");
    expect(screen.getByTestId("rule-means").textContent).toMatch(/couldn't check/);
    expect(screen.queryByText("Doesn't apply")).toBeNull();
  });

  it("reads in Spanish (usted)", async () => {
    await i18n.changeLanguage("es");
    renderRule("landmark", "no");
    expect(screen.getByTestId("rule-means").textContent).toMatch(/^Este terreno no es un Monumento de Chicago/);
  });
});

describe("Build's rule chips", () => {
  it("open the rule's page, and the TIF chip the TIF's page", () => {
    const openRule = vi.fn();
    const openProgram = vi.fn();
    const d = data();
    render(
      <div className="ui-next">
        <AskContext.Provider value={{ ready: true, address: "1601 N Milwaukee Ave", open: vi.fn(), openRule, openProgram }}>
          <BuildTab data={d} verdict={computeVerdict(d, tp)} />
        </AskContext.Provider>
      </div>,
    );
    fireEvent.click(within(document.querySelector('[data-rule="landmark"]') as HTMLElement).getByRole("button"));
    expect(openRule).toHaveBeenCalledWith("landmark");
    fireEvent.click(within(document.querySelector('[data-rule="tif"]') as HTMLElement).getByRole("button"));
    expect(openProgram).toHaveBeenCalledWith("tif");
  });
});
