// The History tab (decision Item 103), rendered from a typed fixture with no network, with axe checks.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import i18n from "../../lib/i18n";
import { profileFixture } from "../test/fixtures";
import { axeViolations } from "../test/axe";
import { HistoryTab } from "./HistoryTab";
import { RecordsPanel } from "./RecordsPanel";
import { DEFAULT_ON, historySource, laneMarks, violationEvents } from "./historyModel";
import { AskContext } from "../ask/askContext";
import type { ScorecardResponse } from "../../lib/api";

afterEach(async () => { cleanup(); await i18n.changeLanguage("en"); });
const t = i18n.getFixedT("en", "next");

const NEXT_UI = {
  permits_at_address: { years: 30, capped: false, projects: [
    { permit: "100623246", kind: "other", permit_type: "EASY PERMIT PROCESS", description: "REPAIR\\REPLACE DECKING ON REAR PORCH SAME AS EXISTING.", issued: "2015-11-10", cost: 6000, units_added: null, address: "2541 N Spaulding Ave", lat: null, lon: null, distance_mi: null, status: "COMPLETE" },
    { permit: "100384380", kind: "other", permit_type: "EASY PERMIT PROCESS", description: "GARAGE", issued: "2011-03-09", cost: 17000, units_added: null, address: "2541 N Spaulding Ave", lat: null, lon: null, distance_mi: null },
  ] },
  violations_at_address: { years: 30, capped: false, violations: [
    { date: "2019-05-01", code: "CN1", description: "REPAIR PORCH", status: "OPEN", status_date: null, inspection: "9" },
    { date: "2019-05-01", code: "CN2", description: "REPAIR STAIRS", status: "COMPLIED", status_date: "2019-08-01", inspection: "9" },
  ] },
  building_records: {
    facts: {
      year_built: [{ source: "assessor", value: 1992, as_of: null }, { source: "footprint", value: 1899, as_of: null }],
      stories: [{ source: "assessor", value: 2, as_of: null }, { source: "footprint", value: 2, as_of: null }],
      bldg_sqft: [{ source: "assessor", value: 2268, as_of: null }],
    },
    differ: ["year_built"], unanswered: [],
  },
};

function data(over: Record<string, unknown> = {}): ScorecardResponse {
  const base = profileFixture({} as never);
  return profileFixture({
    next_ui: NEXT_UI,
    context: {
      ...base.context,
      property: {
        ...base.context!.property!,
        pin14: "13264200270000", bldg_class: "211", year_built: 1992, year_built_source: "assessor", stories: 2, stories_source: "assessor",
        bldg_sqft: 2268, bldg_sqft_source: "assessor", units: 2, units_source: "assessor",
        sales_history: [
          { date: "2010-10-01T00:00:00.000", price: 395000, deed_type: "Trustee", arms_length: true },
          { date: "2017-11-13T00:00:00.000", price: 1, deed_type: "Quit Claim", arms_length: false },
        ],
        appeals: { records: [{ year: 2024, stage: "assessor", before_total: 71000, after_total: 61900, result: "change", reduction_pct: 12.8, appeal_type: "residential" }], nearby_window_years: [], nearby_appeal_count: 0, nearby_reduced_count: 0, nearby_median_reduction_pct: null },
        flags: { tax_sale_years: [2012], scavenger_sale_years: [], city_owned: false, city_owned_status: null, city_owned_sales_status: null, city_owned_application_url: null, scofflaw: false, scofflaw_case: null, str_prohibited: false, chrs_rating: "orange" },
      },
    },
    ...over,
  } as never);
}

describe("History", () => {
  it("leads with the sentence, then four tiles, the timeline and the building and record blocks", async () => {
    const { container } = render(<div className="ui-next"><HistoryTab data={data()} late="ready" timedOutHistory={[]} onRetry={vi.fn()} /></div>);
    expect(screen.getByTestId("history-sentence").textContent).toBe("Last sold in 2010 for $395,000. 2 City permits since 2011 and 1 building violation still open.");
    expect(within(screen.getByTestId("history-tiles")).getAllByRole("listitem")).toHaveLength(4);
    expect(screen.getByTestId("tile-built").textContent).toContain("1899–1992");
    expect(screen.getByTestId("tile-built").textContent).toContain("Cook County Assessor · City building footprints");
    expect(screen.getByTestId("tile-violations").textContent).toContain("1");
    // Appeals and the $1 transfer start hidden (owner: everything but the noise); a chip turns them on.
    const kinds = screen.getByTestId("history-kinds");
    expect(within(kinds).getByRole("button", { name: /Tax appeals/ }).getAttribute("aria-pressed")).toBe("false");
    expect(within(kinds).getByRole("button", { name: /Other transfers/ }).getAttribute("aria-pressed")).toBe("false");
    const events = () => within(screen.getByTestId("history-events")).getAllByRole("listitem").map((li) => li.getAttribute("data-kind"));
    expect(events()).toEqual(["violation", "permit", "permit", "sale"]);
    fireEvent.click(within(kinds).getByRole("button", { name: /Other transfers/ }));
    expect(events()).toContain("transfer");
    expect(screen.getByText("Not a market sale")).toBeTruthy(); // never shown as a sale price
    // An inspection expands its violations in place.
    fireEvent.click(screen.getByRole("button", { name: /Inspection: 2 violations/ }));
    expect(screen.getByTestId("violation-list").textContent).toContain("Repair stairs");
    expect(screen.getByTestId("history-record").textContent).toContain("Orange: 90-day demolition review");
    expect(screen.getByTestId("history-record").textContent).toContain("2012");
    for (const a of container.querySelectorAll("a[href]")) expect(a.getAttribute("target")).toBe("_blank");
    expect(await axeViolations(container)).toEqual([]);
  });

  it("opens a permit's page and the building records page from the right panel's handoff", () => {
    const openPermit = vi.fn(), openRecords = vi.fn();
    render(<AskContext.Provider value={{ ready: true, address: "2541 N Spaulding Ave", open: vi.fn(), openPermit, openRecords }}>
      <div className="ui-next"><HistoryTab data={data()} late="ready" timedOutHistory={[]} onRetry={vi.fn()} /></div>
    </AskContext.Provider>);
    fireEvent.click(screen.getByRole("button", { name: /Garage/ }));
    expect(openPermit.mock.calls[0][0].permit).toBe("100384380");
    fireEvent.click(screen.getAllByTestId("differ-year_built")[0]);
    expect(openRecords).toHaveBeenCalledWith("year_built");
  });

  it("keeps each source's place while history waits, and says Retry in place when one ran out of time", () => {
    const onRetry = vi.fn();
    const { rerender } = render(<div className="ui-next"><HistoryTab data={data({ next_ui: undefined })} late="loading" timedOutHistory={[]} onRetry={onRetry} /></div>);
    expect(screen.getByText("Checking City permits…")).toBeTruthy();
    expect(screen.getByText("Checking building records…")).toBeTruthy();
    expect(screen.getByTestId("history-events").textContent).toContain("Sold for $395,000"); // the Overview's sales show at once
    rerender(<div className="ui-next"><HistoryTab data={data({ next_ui: { ...NEXT_UI, permits_at_address: undefined } })} late="timedOut" timedOutHistory={["permits_at_address"]} onRetry={onRetry} /></div>);
    const retry = screen.getByText(/Couldn.t check in time: City permits/).closest("p")!;
    fireEvent.click(within(retry).getByRole("button"));
    expect(onRetry).toHaveBeenCalled();
    expect(screen.getByTestId("tile-violations").textContent).toContain("Of 2 on record"); // the other source still shows
  });

  it("reads in Mexican Spanish", async () => {
    await i18n.changeLanguage("es");
    render(<div className="ui-next"><HistoryTab data={data()} late="ready" timedOutHistory={[]} onRetry={vi.fn()} /></div>);
    expect(screen.getByTestId("history-sentence").textContent).toContain("Se vendió por última vez en 2010");
  });
});

describe("Building records page", () => {
  it("lists every source per fact, marks the difference and says why", async () => {
    const { container } = render(<div className="ui-next"><RecordsPanel data={data()} fact="year_built" onClose={vi.fn()} instant /></div>);
    const year = container.querySelector('[data-fact="year_built"]')!;
    expect(year.textContent).toContain("Records differ");
    expect(year.textContent).toContain("City building footprints");
    expect(screen.getByTestId("records-range-year_built").textContent).toBe("The sources span 1899–1992.");
    expect(screen.getByText("Why records differ")).toBeTruthy();
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("historyModel", () => {
  it("groups violations by inspection and counts lane marks per year", () => {
    const ev = violationEvents(NEXT_UI.violations_at_address.violations, t);
    expect(ev).toHaveLength(1);
    const marks = laneMarks([...ev, { id: "a", kind: "permit", date: "2019-01-01", title: "", pills: [] }, { id: "b", kind: "permit", date: "2019-06-01", title: "", pills: [] }], DEFAULT_ON);
    expect(marks.find((m) => m.kind === "permit")!.count).toBe(2);
  });

  it("names a source that wasn't asked, failed or timed out, never 'none'", () => {
    const d = data();
    expect(historySource(d, "ready", "permits_at_address", [])).toBe("ready");
    expect(historySource(d, "ready", "permits_at_address", ["permits_at_address"])).toBe("timedOut");
    expect(historySource(data({ next_ui: { failed: ["permits_at_address"] } }), "ready", "permits_at_address", [])).toBe("failed");
    expect(historySource(data({ next_ui: { permits_at_address: null } }), "ready", "permits_at_address", [])).toBe("none");
  });
});
