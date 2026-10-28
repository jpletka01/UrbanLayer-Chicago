import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { UpcomingZoningFiling, UpcomingZoningSummary } from "../../lib/types";
import { UpcomingZoningCard } from "./UpcomingZoningCard";

afterEach(cleanup);

const filing = (record: string, match_kind: UpcomingZoningFiling["match_kind"]): UpcomingZoningFiling => ({
  record_number: record,
  title: `Zoning Reclassification Map No. 1-A at ${record === "O-SUBJECT" ? "10" : "100"} N State St`,
  status: "4-In Committee",
  sub_status: "Referred",
  introduced_at: "2026-10-21T15:00:00+00:00",
  latest_action_at: "2026-10-22T05:00:00+00:00",
  url: `https://clerk.example/${record}`,
  segment: record === "O-SUBJECT" ? "10 N STATE ST" : "100 N STATE ST",
  match_kind,
  distance_mi: match_kind === "nearby" ? 0.123 : null,
});

const base = (over: Partial<UpcomingZoningSummary> = {}): UpcomingZoningSummary => ({
  status: "ready",
  placement_status: "complete",
  checked_at: "2026-10-27T18:00:00+00:00",
  radius_mi: 0.5,
  subject_filings: [],
  nearby_filings: [],
  placed_count: 0,
  unplaced_count: 0,
  placement_coverage: 1,
  record_provenance: {
    source_id: "chi.clerk.legislation", as_of: "2026-10-27", method: "Clerk record", confidence: "standard",
  },
  placement_provenance: {
    source_id: "cook.address_points", as_of: "2026-10-27", method: "Range placement", confidence: "standard",
  },
  ...over,
});

describe("UpcomingZoningCard", () => {
  it("renders a healthy checked zero separately from unavailable", () => {
    const { rerender } = render(<UpcomingZoningCard data={base()} />);
    expect(screen.getByText(/No placeable current zoning filings found/)).toBeTruthy();
    expect(screen.getByText(/Applicant filings are proposals, not approvals/)).toBeTruthy();

    rerender(<UpcomingZoningCard data={base({ status: "unavailable", placement_status: "partial" })} />);
    expect(screen.getByText(/couldn't be checked right now/)).toBeTruthy();
    expect(screen.queryByText(/No placeable current zoning filings found/)).toBeNull();
  });

  it("keeps stale and partial warnings explicit", () => {
    render(<UpcomingZoningCard data={base({ status: "stale", placement_status: "partial", unplaced_count: 3 })} />);
    expect(screen.getByText(/latest refresh did not complete/)).toBeTruthy();
    expect(screen.getByText(/3 current filing\(s\) could not be placed/)).toBeTruthy();
  });

  it("cannot swap exact-subject and nearby language and links to the official record", () => {
    render(<UpcomingZoningCard data={base({
      subject_filings: [filing("O-SUBJECT", "subject_pin")],
      nearby_filings: [filing("O-NEARBY", "nearby")],
    })} />);
    expect(screen.getByText("Lists this property")).toBeTruthy();
    expect(screen.getByText("subject match")).toBeTruthy();
    expect(screen.getByText("Nearby within 0.5 mi")).toBeTruthy();
    expect(screen.getByText("0.12 mi away")).toBeTruthy();
    expect(screen.getByRole("link", { name: "O-SUBJECT" }).getAttribute("href")).toBe("https://clerk.example/O-SUBJECT");
  });
});
