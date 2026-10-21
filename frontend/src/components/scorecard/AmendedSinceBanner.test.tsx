import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { AmendedSinceBanner, NotCodifiedNotice } from "./AmendedSinceBanner";
import { AmendmentList, amendmentStatus } from "./AmendmentList";
import { lawrence, noEffect, tod } from "./amendments.fixtures";

afterEach(cleanup);

describe("amendmentStatus — what the page says about each amendment", () => {
  it("applied → reflected; pending or never reviewed → not yet reviewed; reviewed with no effect → not reflected", () => {
    expect(amendmentStatus(tod)).toBe("applied");
    expect(amendmentStatus(lawrence)).toBe("pending");
    expect(amendmentStatus(noEffect)).toBe("none");
    expect(amendmentStatus({ review_status: "reviewed", product_effect: null })).toBe("pending");
  });
});

describe("AmendmentList", () => {
  it("lists date · linked record · summary (the title until reviewed) · status", () => {
    render(<AmendmentList amendments={[lawrence, tod]} />);
    const row = screen.getByTestId("amendment-O2026-0026042");
    expect(row.textContent).toContain("Sep 23, 2026");
    expect(row.textContent).toContain("Amendment of Title 17 regarding pedestrian streets");
    expect(screen.getByTestId("amendment-status-O2026-0026042").textContent).toContain("Not yet reviewed");
    expect(row.querySelector("a")?.getAttribute("href")).toContain("matterId=ped");
    expect(screen.getByTestId("amendment-SO2026-0025391").textContent).toContain("Adds §17-3-0600");
    expect(screen.getByTestId("amendment-status-SO2026-0025391").textContent).toContain("Reflected on this page");
  });

  it("shows a record without a Clerk link as plain text", () => {
    render(<AmendmentList amendments={[noEffect]} />);
    expect(screen.getByTestId("amendment-O2026-0000001").querySelector("a")).toBeNull();
    expect(screen.getByTestId("amendment-status-O2026-0000001").textContent).toContain("not reflected on this page");
  });
});

describe("AmendedSinceBanner — the text predates a change", () => {
  it("renders nothing for a section no amendment touches", () => {
    const { container } = render(<AmendedSinceBanner amendments={[]} />);
    expect(container.textContent).toBe("");
  });

  it("names the amendment, its date and link, and says the text below does not include it", () => {
    render(<AmendedSinceBanner amendments={[lawrence]} />);
    const box = screen.getByTestId("amended-since");
    expect(box.textContent).toContain("amended after this text was published");
    expect(box.textContent).toContain("O2026-0026042");
    expect(box.textContent).toContain("Sep 23, 2026");
    expect(box.textContent).toContain("The text below does not include that change.");
    expect(box.querySelector("a")?.getAttribute("href")).toContain("matterId=ped");
  });

  it("pluralizes the caveat for several amendments", () => {
    render(<AmendedSinceBanner amendments={[lawrence, tod]} />);
    expect(screen.getByTestId("amended-since").textContent).toContain("does not include those changes");
  });
});

describe("NotCodifiedNotice — a section an amendment added (17-3-0600)", () => {
  it("says the section isn't in the published text and links the ordinance", () => {
    render(<NotCodifiedNotice notice={{ not_in_published_code: true, section_id: "17-3-0600", message: "x", added_by: [tod] }} />);
    const box = screen.getByTestId("not-codified");
    expect(box.textContent).toContain("17-3-0600 isn't in the published Municipal Code text yet");
    expect(box.textContent).toContain("SO2026-0025391");
    expect(box.textContent).toContain("Oct 14, 2026");
    expect(box.querySelector("a")?.getAttribute("href")).toContain("matterId=tod");
  });
});
