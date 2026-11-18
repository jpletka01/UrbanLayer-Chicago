// The review queue for suggested corrections (decision Item 129 §4, PR 4): a report's card, Accept with what to apply
// (prefilled from the report), Reject and Duplicate, and the export panel. The admin API is mocked.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { AdminCorrection } from "../../lib/api";
import { CorrectionsSection, defaultApply, reportWords } from "./CorrectionsSection";

vi.mock("../../lib/api", async (orig) => {
  const mod = await orig<typeof import("../../lib/api")>();
  return { ...mod, fetchAdminCorrections: vi.fn(), reviewAdminCorrection: vi.fn(), exportAdminCorrections: vi.fn() };
});
vi.mock("../discovery/discoveryData", async (orig) => ({ ...(await orig<typeof import("../discovery/discoveryData")>()), fetchLotContext: () => Promise.resolve(null) }));
import { exportAdminCorrections, fetchAdminCorrections, reviewAdminCorrection } from "../../lib/api";

afterEach(() => { cleanup(); vi.clearAllMocks(); });

function report(over: Partial<AdminCorrection> = {}): AdminCorrection {
  return {
    id: 7, pin10: "1431332018", kinds: ["stories"], stories: 3, area_dir: null, note: "Three floors, not two.",
    shown: { bldg_sqft: 22486, bldg_sqft_source: "footprint", room_sqft: 3806, structure: "built", condo: null, data_version: "v1" },
    now: { address: "1601 N MILWAUKEE AVE", lat: 41.91, lon: -87.68, zone_class: "B3-2", bldg_sqft: 22486, bldg_sqft_source: "footprint",
      room_sqft: 3806, structure: "built", condo: null, data_version: "v1" },
    changed: false, signed_in: false, past: { accepted: 1, rejected: 0 }, muted: false, others_open: [9], status: "new",
    created_at: Date.UTC(2026, 10, 17), reviewed_at: null, review_note: null, applied: null, ...over,
  };
}

describe("the report's words and Accept's default", () => {
  it("words each kind by what the card showed", () => {
    expect(reportWords(report({ kinds: ["stories", "area", "gone", "condo", "other"], area_dir: "high" })))
      .toEqual(["Stories: 3", "Floor area too high", "No building now", "It's a condo", "Other"]);
    expect(reportWords(report({ kinds: ["gone", "condo"], shown: { structure: "empty", condo: true } })))
      .toEqual(["There's a building", "Not a condo"]);
  });

  it("prefills the reporter's stories, no building for 'gone', a typed count for floor area, nothing for a condo", () => {
    expect(defaultApply(report())).toEqual({ apply: "stories", stories: "3" });
    expect(defaultApply(report({ kinds: ["gone"], stories: null }))).toEqual({ apply: "empty", stories: "" });
    expect(defaultApply(report({ kinds: ["area"], stories: null }))).toEqual({ apply: "stories", stories: "" });
    expect(defaultApply(report({ kinds: ["condo"], stories: null }))).toEqual({ apply: "none", stories: "" });
  });
});

describe("the queue", () => {
  it("shows a report's card and accepts it with the prefilled stories", async () => {
    vi.mocked(fetchAdminCorrections).mockResolvedValue({ reports: [report({ changed: true, now: { ...report().now!, bldg_sqft: 30000 } })], total: 1 });
    vi.mocked(reviewAdminCorrection).mockResolvedValue();
    render(<CorrectionsSection />);
    const card = await screen.findByTestId("correction-report");
    expect(card.textContent).toContain("1601 N Milwaukee Ave");
    expect(card.textContent).toContain("22,486 sq ft built (footprint × stories estimate)");
    expect(within(card).getByTestId("correction-changed").textContent).toContain("30,000 sq ft");
    expect(card.textContent).toContain("Stories: 3");
    expect(card.textContent).toContain("“Three floors, not two.”");
    expect(card.textContent).toContain("Signed out");
    expect(card.textContent).toContain("1 accepted · 0 rejected before");
    expect(card.textContent).toContain("#9");
    const sv = within(card).getByRole("link", { name: /Street View/ });
    expect(sv.getAttribute("target")).toBe("_blank");
    fireEvent.click(within(card).getByRole("button", { name: "Accept" }));
    expect((within(card).getByLabelText("Stories to apply") as HTMLInputElement).value).toBe("3");
    fireEvent.change(within(card).getByLabelText("Reason"), { target: { value: "3 floors on Street View" } });
    fireEvent.click(within(card).getByTestId("correction-review-save"));
    await waitFor(() => expect(reviewAdminCorrection).toHaveBeenCalledWith(7, { action: "accept", reason: "3 floors on Street View", apply: "stories", stories: 3 }));
    await waitFor(() => expect(fetchAdminCorrections).toHaveBeenCalledTimes(2)); // reloads the queue
  });

  it("Accept waits for a story count when floor area was reported; Duplicate prefills the other open report", async () => {
    vi.mocked(fetchAdminCorrections).mockResolvedValue({ reports: [report({ kinds: ["area"], stories: null, area_dir: "low" })], total: 1 });
    vi.mocked(reviewAdminCorrection).mockResolvedValue();
    render(<CorrectionsSection />);
    const card = await screen.findByTestId("correction-report");
    fireEvent.click(within(card).getByRole("button", { name: "Accept" }));
    expect((within(card).getByTestId("correction-review-save") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(card).getByLabelText("Stories to apply"), { target: { value: "4" } });
    expect((within(card).getByTestId("correction-review-save") as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(within(card).getByRole("button", { name: "Cancel" }));
    fireEvent.click(within(card).getByRole("button", { name: "Duplicate" }));
    expect((within(card).getByLabelText("Reason") as HTMLInputElement).value).toBe("Duplicate of #9");
    fireEvent.click(within(card).getByTestId("correction-review-save"));
    await waitFor(() => expect(reviewAdminCorrection).toHaveBeenCalledWith(7, { action: "duplicate", reason: "Duplicate of #9" }));
  });

  it("shows a review error and keeps the form", async () => {
    vi.mocked(fetchAdminCorrections).mockResolvedValue({ reports: [report()], total: 1 });
    vi.mocked(reviewAdminCorrection).mockRejectedValue(new Error("already rejected"));
    render(<CorrectionsSection />);
    const card = await screen.findByTestId("correction-report");
    fireEvent.click(within(card).getByRole("button", { name: "Reject" }));
    fireEvent.click(within(card).getByTestId("correction-review-save"));
    expect((await within(card).findByRole("alert")).textContent).toBe("already rejected");
    expect(within(card).getByTestId("correction-review")).toBeTruthy();
  });

  it("switches tabs and shows a reviewed report's verdict", async () => {
    vi.mocked(fetchAdminCorrections).mockResolvedValue({ reports: [], total: 0 });
    render(<CorrectionsSection />);
    expect(await screen.findByText("No open reports.")).toBeTruthy();
    vi.mocked(fetchAdminCorrections).mockResolvedValue({
      reports: [report({ status: "accepted", reviewed_at: Date.UTC(2026, 10, 18), applied: { stories: 3 }, review_note: "3 floors" })], total: 1,
    });
    fireEvent.click(screen.getByRole("tab", { name: /Accepted/ }));
    const card = await screen.findByTestId("correction-report");
    expect(fetchAdminCorrections).toHaveBeenLastCalledWith("accepted");
    expect(card.textContent).toContain("applies 3 stories");
    expect(within(card).queryByRole("button", { name: "Accept" })).toBeNull();
  });

  it("exports the file and its diff", async () => {
    vi.mocked(fetchAdminCorrections).mockResolvedValue({ reports: [], total: 0 });
    vi.mocked(exportAdminCorrections).mockResolvedValue({ content: "{}\n", diff: "--- a/x\n+++ b/x\n+  \"1431332018\": {", entries: 1, new_reports: 1 });
    render(<CorrectionsSection />);
    fireEvent.click(await screen.findByTestId("corrections-export"));
    const panel = await screen.findByTestId("corrections-export-panel");
    expect(panel.textContent).toContain("1 lot in the file, 1 newly accepted report");
    expect(screen.getByTestId("corrections-diff").textContent).toContain('"1431332018"');
  });
});
