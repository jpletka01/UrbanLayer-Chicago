// A program's page in the right panel (decision Item 99): what it means for this lot, read from the Profile, with
// Ask last. Rendered from a typed fixture shaped like 6300 S Cottage Grove Ave (inside the Woodlawn TIF).
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import i18n from "../../lib/i18n";
import { profileFixture } from "../test/fixtures";
import { axeViolations } from "../test/axe";
import { AskContext } from "../ask/askContext";
import { ProgramPanel } from "./ProgramPanel";
import { MoneyTab } from "./MoneyTab";
import { programDetail, tractLabel } from "./programModel";

afterEach(async () => { cleanup(); await i18n.changeLanguage("en"); });

const woodlawn = () => profileFixture({ context: { incentives: {
  in_tif_district: true, tif_name: "Woodlawn", tif_year_start: 1999, tif_end_year: 2035, tif_fund_balance: 30056685, tif_annual_expenditure: 7770693,
  tif_fund_history: [
    { year: "2023", revenue: 6075324, expenditure: 2300051, fund_balance: 26031743 },
    { year: "2025", revenue: 7339430, expenditure: 7770693, fund_balance: 30056685 },
    { year: "2024", revenue: 6368135, expenditure: 4125125, fund_balance: 28748919 },
  ],
  tif_financials: [
    { project_name: "Park Station", status: "Completed Project", public_funds: "5000000", private_funds: "40000000", report_year: "2025" },
    { project_name: "The Strand Hotel", status: "Completed Project", public_funds: "2000000", private_funds: "22849528", report_year: "2025" },
  ],
  in_nmtc: true, nmtc_tract: "17031420700", nmtc_poverty_rate: 41, nmtc_severe_distress: true,
  grant_programs: { total_projects: 18, total_funding: 1505124, by_program: { SBIF: 15, NOF: 3 }, recent_projects: [] },
  unchecked: [],
} } } as never);

const renderPanel = (program: "tif" | "nmtc" | "oz", answer: "yes" | "no" | "notChecked", open = vi.fn()) => render(
  <div className="ui-next">
    <AskContext.Provider value={{ ready: true, address: "6300 S Cottage Grove Ave", open }}>
      <ProgramPanel data={woodlawn()} program={program} answer={answer} onClose={vi.fn()} instant />
    </AskContext.Provider>
  </div>,
);

describe("the program panel", () => {
  it("says what a TIF means for this lot, with its years, fund, the projects it paid for and who decides", async () => {
    const { container } = renderPanel("tif", "yes");
    const panel = screen.getByTestId("program-panel");
    expect(within(panel).getByRole("heading", { level: 2 }).textContent).toBe("Woodlawn TIF district");
    expect(screen.getByTestId("program-means").textContent).toMatch(/^This lot is inside the Woodlawn TIF district/);
    expect(screen.getByTestId("tif-figures").textContent).toContain("1999–2035");
    expect(within(screen.getByTestId("tif-projects")).getAllByRole("listitem")[0].textContent).toContain("Park Station");
    expect(screen.getByTestId("area-grants").textContent).toContain("18 projects");
    expect(panel.textContent).toContain("City Council approves each agreement");
    expect(screen.getByRole("link", { name: /All TIF projects/ }).getAttribute("target")).toBe("_blank");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("puts Ask last and writes the question, never sends it", () => {
    const open = vi.fn();
    renderPanel("nmtc", "yes", open);
    expect(screen.getByText("41%")).toBeTruthy();
    fireEvent.click(screen.getByTestId("program-ask"));
    expect(open).toHaveBeenCalledWith("What would New Markets Tax Credit mean for a project at 6300 S Cottage Grove Ave?");
  });

  it("says the TIF's reports couldn't be checked in time, with Retry, instead of a blank fund", () => {
    const onRetry = vi.fn();
    render(<div className="ui-next"><ProgramPanel data={woodlawn()} program="tif" answer="yes" reports="timedOut" onRetry={onRetry} onClose={vi.fn()} instant /></div>);
    expect(screen.getByTestId("tif-reports-late").textContent).toContain("Couldn't check the district's annual reports in time");
    fireEvent.click(within(screen.getByTestId("tif-reports-late")).getByRole("button", { name: /Retry/ }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("never turns a failed check into 'not in one'", () => {
    renderPanel("oz", "notChecked");
    expect(screen.getByTestId("program-means").textContent).toMatch(/couldn't check/);
  });

  it("orders the fund by year and words a tract the way people write it", () => {
    expect(programDetail(woodlawn(), "tif", "yes", new Date("2026-11-09")).tif!.funds.map((f) => f.year)).toEqual([2023, 2024, 2025]);
    expect(programDetail(woodlawn(), "tif", "yes", new Date("2026-11-09")).tif!.yearsLeft).toBe(9);
    expect(tractLabel("17031420700")).toBe("4207");
    expect(tractLabel("17031220602")).toBe("2206.02");
  });

  it("reads in Spanish (usted)", async () => {
    await i18n.changeLanguage("es");
    renderPanel("tif", "yes");
    expect(screen.getByTestId("program-means").textContent).toMatch(/^Este terreno está dentro del distrito TIF Woodlawn/);
  });
});

describe("incentive chips", () => {
  it("open the program's page", () => {
    const openProgram = vi.fn();
    render(
      <div className="ui-next">
        <AskContext.Provider value={{ ready: true, address: "6300 S Cottage Grove Ave", open: vi.fn(), openProgram }}>
          <MoneyTab data={woodlawn()} late={{ money: "ready", incentives: "ready", neighborhood: "ready" }} onRetry={vi.fn()} />
        </AskContext.Provider>
      </div>,
    );
    fireEvent.click(within(document.querySelector('[data-incentive="tif"]') as HTMLElement).getByRole("button"));
    expect(openProgram).toHaveBeenCalledWith("tif");
  });
});
