import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// When Stripe isn't configured, checkout 503s. Purchase UI must say "coming
// soon" instead of offering a button that silently does nothing, while
// access codes (which don't need Stripe) keep working.

const status = { reports: false, subscriptions: false };
vi.mock("../lib/api", () => ({
  fetchPaymentsStatus: vi.fn(async () => status),
  createReportCheckoutSession: vi.fn(),
  createCheckoutSession: vi.fn(),
  redeemVoucher: vi.fn(),
}));

import ReportPurchasePrompt from "./ReportPurchasePrompt";
import UpgradePrompt from "./UpgradePrompt";

const parcel = { pin: "14313320180000", address: "1601 N Milwaukee Ave", lat: 41.9, lon: -87.6 } as never;

describe("purchases unavailable", () => {
  afterEach(() => {
    cleanup();
    status.reports = false;
    status.subscriptions = false;
  });

  it("report modal shows coming soon, keeps the sample and access codes", async () => {
    render(<ReportPurchasePrompt parcel={parcel} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText(/report purchases are coming soon/i)).toBeTruthy());
    expect(screen.queryByRole("button", { name: /buy report/i })).toBeNull();
    expect(screen.getByRole("button", { name: /access code/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /sample report/i })).toBeTruthy();
  });

  it("report modal offers the purchase when payments are configured", async () => {
    status.reports = true;
    status.subscriptions = true;
    render(<ReportPurchasePrompt parcel={parcel} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByRole("button", { name: /buy report/i })).toBeTruthy());
  });

  it("upgrade prompt shows coming soon when subscriptions are off", async () => {
    render(<UpgradePrompt onClose={() => {}} />);
    await waitFor(() => expect(screen.getByText(/pro subscriptions are coming soon/i)).toBeTruthy());
  });
});
