import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type {
  PendingTextImpact,
  PendingTextReview,
  UpcomingZoningSummary,
} from "../../lib/types";
import { PendingTextImpactsCard } from "./PendingTextImpactsCard";

afterEach(cleanup);

const LONG_TITLE =
  "Amendment of Municipal Code Title 17 by modifying various sections regarding minimum lot area and adding new sections regarding a very long official title that must wrap rather than overflow the card on a 360 pixel wide phone";

const impact = (over: Partial<PendingTextImpact> = {}): PendingTextImpact => ({
  record_number: "O2026-0028842",
  lifecycle_id: "O2026-0028842",
  title: LONG_TITLE,
  status: "4-In Committee",
  sub_status: "Referred",
  introduced_at: "2026-09-23T15:00:00+00:00",
  latest_action_at: null,
  url: "https://clerk.example/matter/O2026-0028842",
  reviewed_on: "2026-10-28",
  reviewed_by: "claude (read in session)",
  basis: "ordinance",
  summary: "Would eliminate the minimum lot area per unit in RT and RM districts.",
  effects: [{
    id: "mla-rt-rm",
    sections: ["17-2-0301-A", "17-2-0303-A"],
    could_change: "the minimum lot area per dwelling unit for this district, which the proposal would eliminate",
    reach: "parcel",
    reach_note: null,
    affected: [{
      fact_id: "zoning.min_lot_area_per_unit",
      label: "Minimum lot area per dwelling unit for RT-4",
      current_value: "1,000 sq ft",
      section: "17-2-0303-A",
    }],
  }],
  ...over,
});

const review = (over: Partial<PendingTextReview> = {}): PendingTextReview => ({
  status: "complete",
  pending_count: 48,
  reviewed_count: 48,
  unreviewed: [],
  overdue: false,
  ...over,
});

const base = (over: Partial<UpcomingZoningSummary> = {}): UpcomingZoningSummary => ({
  status: "ready",
  placement_status: "complete",
  checked_at: "2026-10-28T04:18:05+00:00",
  radius_mi: 0.5,
  subject_filings: [],
  nearby_filings: [],
  placed_count: 0,
  unplaced_count: 0,
  placement_coverage: 1,
  record_provenance: { source_id: "chi.clerk.legislation", as_of: "2026-10-28", method: "Clerk", confidence: "standard" },
  placement_provenance: { source_id: "cook.address_points", as_of: "2026-10-28", method: "Range", confidence: "standard" },
  text_impacts: [],
  text_review: review(),
  ...over,
});

describe("PendingTextImpactsCard", () => {
  it("renders nothing when the response carries no review state (older backend)", () => {
    const { container } = render(<PendingTextImpactsCard data={base({ text_review: null })} />);
    expect(container.textContent).toBe("");
  });

  // The row is one line; its evidence sits behind the tool tray (decision Item 54). Tests open the tools
  // the way a user would and check the same guarantees as before.
  const open = (name: RegExp) => fireEvent.click(screen.getAllByRole("button", { name })[0]);

  it("keeps a proposal beside current law: 'could change' versus 'today, unchanged', with the official link", () => {
    render(<PendingTextImpactsCard data={base({ text_impacts: [impact()] })} />);
    // one human line: the rule it would change, today's value, and a visible "Proposed" label
    expect(screen.getByText("Minimum lot area per dwelling unit for RT-4")).toBeTruthy();
    expect(screen.getByText("Today: 1,000 sq ft")).toBeTruthy();
    expect(screen.getByText(/Proposed · Referred/)).toBeTruthy();
    // the disclaimer, the dates and the code sit behind tools, not on the page
    expect(screen.queryByText(/not adopted law/)).toBeNull();
    open(/^What this means: Pending zoning-code changes/);
    expect(screen.getByText(/not adopted law/)).toBeTruthy();
    open(/^What this means: Minimum lot area/);
    expect(screen.getByText("Proposed — could change")).toBeTruthy();
    expect(screen.getByText(/which the proposal would eliminate/)).toBeTruthy();
    expect(screen.getByText("Today · current law, unchanged")).toBeTruthy();
    expect(screen.getByText(/Minimum lot area per dwelling unit for RT-4: 1,000 sq ft/)).toBeTruthy();
    open(/^Code section: Minimum lot area/);
    expect(screen.getByText(/§17-2-0303-A/)).toBeTruthy();
    open(/^Dates: Minimum lot area/);
    expect(screen.getByText("We read the ordinance text")).toBeTruthy();
    expect(screen.getByText("Introduced at City Council")).toBeTruthy();
    const link = screen.getByRole("link", { name: /^Official record: Minimum lot area/ });
    expect(link.getAttribute("href")).toBe("https://clerk.example/matter/O2026-0028842");
    expect(link.getAttribute("title")).toContain("O2026-0028842");
    // never implies adoption
    expect(screen.queryByText(/approved|adopted by|takes effect|will change/i)).toBeNull();
  });

  it("never prints the Clerk number or the long official title as the row's headline", () => {
    render(<PendingTextImpactsCard data={base({ text_impacts: [impact()] })} />);
    expect(screen.queryByText("O2026-0028842")).toBeNull();
    expect(screen.queryByText(LONG_TITLE)).toBeNull();
    expect(screen.getByText("Minimum lot area per dwelling unit for RT-4").className).toContain("break-words");
  });

  it("says plainly when the reach cannot be tested rather than claiming it", () => {
    const untested = impact({
      effects: [{
        id: "adu-nw-boundary", sections: ["17-7-0572"], could_change: "where coach houses are allowed",
        reach: "untested", reach_note: "Whether the new boundary reaches this parcel needs map geometry.",
        affected: [{ fact_id: "zoning.adu", label: "Coach houses and conversion units", current_value: "not_allowed" }],
      }],
    });
    render(<PendingTextImpactsCard data={base({ text_impacts: [untested] })} />);
    expect(screen.getByText(/Can't be tested for this property/)).toBeTruthy(); // visible label
    open(/^What this means: Coach houses/);
    expect(screen.getByText(/needs map geometry/)).toBeTruthy();
  });

  it("shows a coverage-note fact as current law text, with no invented value", () => {
    const street = impact({
      record_number: "O2026-0026237", title: "Designation of W Lawrence Ave as a TOD street",
      effects: [{
        id: "tod-street-lawrence", sections: ["17-3-0602-F"], could_change: "whether this address is on a TOD street",
        reach: "parcel", reach_note: null,
        affected: [{ fact_id: "note.tod_street", label: "TOD street status", current_law: "Current law (17-3-0602-F) lists the TOD streets in force today; the proposal would add a segment." }],
      }],
    });
    render(<PendingTextImpactsCard data={base({ text_impacts: [street] })} />);
    expect(screen.queryByText(/^Today: /)).toBeNull(); // no value to show, none invented
    open(/^What this means: TOD street status/);
    expect(screen.getByText(/lists the TOD streets in force today/)).toBeTruthy();
  });

  it("a complete review with nothing relevant is the only 'none map to this property' state", () => {
    render(<PendingTextImpactsCard data={base()} />);
    const none = screen.getByTestId("pending-none");
    expect(none.textContent).toContain("None found");
    expect(none.textContent).toContain("48 reviewed; none applies here");
  });

  it("an empty docket reads as such, not as 'reviewed none'", () => {
    render(<PendingTextImpactsCard data={base({ text_review: review({ pending_count: 0, reviewed_count: 0 }) })} />);
    expect(screen.getByText(/No pending Title 17 text proposals are on the Clerk's docket/)).toBeTruthy();
    expect(screen.queryByText(/reviewed; none applies/)).toBeNull();
  });

  it("an incomplete review never says none and lists what is missing, still showing reviewed impacts", () => {
    render(<PendingTextImpactsCard data={base({
      text_impacts: [impact()],
      text_review: review({
        status: "incomplete", reviewed_count: 46,
        unreviewed: [
          { record_number: "O2026-0030001", title: "t", url: "https://clerk.example/new", reason: "unreviewed", waiting_days: 16 },
          { record_number: "SO2026-0028842", title: "t", url: "https://clerk.example/sub", reason: "outdated", waiting_days: 30 },
        ],
      }),
    })} />);
    expect(screen.getByText("2 proposals not yet reviewed")).toBeTruthy(); // visible amber label
    expect(screen.queryByTestId("pending-none")).toBeNull();
    fireEvent.click(screen.getAllByRole("button", { name: /^What this means: Pending zoning-code changes/ })[1]);
    expect(screen.getByText(/2 pending Title 17 proposals haven't been reviewed/)).toBeTruthy();
    expect(screen.getByText(/A newer version replaced the one we reviewed/)).toBeTruthy();
    expect(screen.getByText(/introduced 16 days ago/)).toBeTruthy();
    expect(screen.getByText("Minimum lot area per dwelling unit for RT-4")).toBeTruthy();
  });

  it("unavailable is its own state: no none, no list, no counts", () => {
    render(<PendingTextImpactsCard data={base({
      status: "unavailable", checked_at: null,
      text_review: review({ status: "unavailable", pending_count: 0, reviewed_count: 0 }),
    })} />);
    expect(document.querySelector('[data-confidence-state="not_checked"]')).not.toBeNull();
    expect(screen.queryByTestId("pending-none")).toBeNull();
    expect(screen.queryByText(/No pending Title 17/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /^Why: Pending zoning-code changes/ }));
    expect(screen.getByText(/couldn't be checked right now. This is not a finding of none/)).toBeTruthy();
  });

  it("stale keeps the reviewed list with the explicit last-good warning", () => {
    render(<PendingTextImpactsCard data={base({ status: "stale", text_impacts: [impact()] })} />);
    expect(screen.getByText("Last good check")).toBeTruthy();
    expect(screen.getByText("Minimum lot area per dwelling unit for RT-4")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: /^What this means: Pending zoning-code changes/ })[1]);
    expect(screen.getByText(/latest refresh did not complete/)).toBeTruthy();
  });

  it("bounds the list with the page's one disclosure idiom", () => {
    const many = ["A", "B", "C", "D"].map((x) => impact({ record_number: `O2026-000${x}`, url: `https://clerk.example/${x}` }));
    render(<PendingTextImpactsCard data={base({ text_impacts: many })} />);
    expect(document.querySelectorAll("[data-impact]").length).toBe(3);
    fireEvent.click(screen.getByRole("button", { name: /more/i }));
    expect(document.querySelectorAll("[data-impact]").length).toBe(4);
  });

  it("the free payload type carries no attachment or EDS field", () => {
    const keys = Object.keys(impact());
    expect(keys.some((k) => /attach|eds|pdf/i.test(k))).toBe(false);
  });
});
