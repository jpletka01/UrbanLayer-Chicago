import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("../../lib/api", () => ({ fetchReport: vi.fn() }));

import { fetchReport, type ReportPurchase } from "../../lib/api";
import { PurchaseRow } from "./PurchaseRow";

const purchase = (over: Partial<ReportPurchase> = {}): ReportPurchase => ({
  id: 7, address: "1601 N Milwaukee Ave", pin: "14313320180000", lat: 41.91, lon: -87.68, amount_cents: 2500,
  created_at: 1_760_000_000_000, completed_at: 1_760_000_100_000, original: null, ...over,
});
const original = { rendered_at: Date.UTC(2026, 9, 2, 17), available: true };

beforeEach(() => {
  vi.mocked(fetchReport).mockReset();
  vi.mocked(fetchReport).mockResolvedValue(new Blob(["%PDF"]));
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("PurchaseRow — the original and an updated copy (WS6 M8)", () => {
  it("before any report was rendered there is one download, and it asks for no particular copy", async () => {
    const onDownloaded = vi.fn();
    render(<PurchaseRow purchase={purchase()} onDownloaded={onDownloaded} />);
    expect(screen.queryByTestId("download-original")).toBeNull();
    expect(screen.queryByTestId("original-note")).toBeNull();
    fireEvent.click(screen.getByTestId("download-updated"));
    await waitFor(() => expect(fetchReport).toHaveBeenCalledTimes(1));
    expect(vi.mocked(fetchReport).mock.calls[0][1]).toBeUndefined();
    await waitFor(() => expect(onDownloaded).toHaveBeenCalled()); // that download just became the original
  });

  it("once there is an original: both buttons, the original dated, and the explanation", () => {
    render(<PurchaseRow purchase={purchase({ original })} />);
    expect(screen.getByTestId("download-original").textContent).toContain("Original · Oct 2, 2026");
    expect(screen.getByTestId("download-updated").textContent).toBe("Updated copy");
    expect(screen.getByTestId("original-note").textContent).toContain("kept exactly as sold");
  });

  it("each button asks for its own copy, and only the first download refreshes the list", async () => {
    const onDownloaded = vi.fn();
    render(<PurchaseRow purchase={purchase({ original })} onDownloaded={onDownloaded} />);
    fireEvent.click(screen.getByTestId("download-original"));
    await waitFor(() => expect(fetchReport).toHaveBeenCalledTimes(1));
    expect(vi.mocked(fetchReport).mock.calls[0][1]).toBe("original");
    await waitFor(() => expect(screen.getByTestId("download-updated").hasAttribute("disabled")).toBe(false)); // the first finished
    fireEvent.click(screen.getByTestId("download-updated"));
    await waitFor(() => expect(fetchReport).toHaveBeenCalledTimes(2));
    expect(vi.mocked(fetchReport).mock.calls[1][1]).toBe("updated");
    expect(onDownloaded).not.toHaveBeenCalled();
  });

  it("an original that has gone missing is said so, and an updated copy is still offered", () => {
    render(<PurchaseRow purchase={purchase({ original: { ...original, available: false } })} />);
    expect(screen.queryByTestId("download-original")).toBeNull();
    expect(screen.getByTestId("original-note").textContent).toContain("couldn't be found");
    expect(screen.getByTestId("download-updated")).toBeTruthy();
  });

  it("a failed download says so and does not refresh", async () => {
    vi.mocked(fetchReport).mockResolvedValue(null);
    const onDownloaded = vi.fn();
    render(<PurchaseRow purchase={purchase()} onDownloaded={onDownloaded} />);
    fireEvent.click(screen.getByTestId("download-updated"));
    await waitFor(() => expect(screen.getByText(/Download failed/)).toBeTruthy());
    expect(onDownloaded).not.toHaveBeenCalled();
  });
});
