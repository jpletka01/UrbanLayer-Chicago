// @vitest-environment jsdom
// "What best describes you?" after a sign-in: asked once, an answer or a skip silences it for good.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axeViolations } from "../test/axe";

let auth = { isAuthenticated: true };
vi.mock("../../contexts/AuthContext", () => ({ useAuthContext: () => auth }));
const track = vi.fn();
vi.mock("../../lib/tracking", () => ({ track: (...a: unknown[]) => track(...a) }));

import { SegmentQuestion } from "./SegmentQuestion";

beforeEach(() => {
  auth = { isAuthenticated: true };
  localStorage.clear();
  sessionStorage.clear();
  sessionStorage.setItem("ul_segment_due", "1");
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("SegmentQuestion", () => {
  it("asks once after a sign-in: seven answers, each a tile with its own icon", async () => {
    render(<SegmentQuestion />);
    const dialog = await screen.findByTestId("segment-question");
    expect(within(dialog).getByRole("heading", { name: "What best describes you?" })).toBeTruthy();
    const tiles = within(dialog).getAllByRole("button").filter((b) => b.dataset.testid?.startsWith("segment-"));
    expect(tiles.map((b) => b.textContent)).toEqual(
      ["Developer", "Architect", "Attorney", "Broker / Appraiser", "Investor", "Homeowner", "Just curious"]);
    for (const b of tiles) expect(b.querySelector("svg")).toBeTruthy();
    expect(await axeViolations(dialog)).toEqual([]);
  });

  it("an answer is stored and tracked, and the question goes away for good", async () => {
    render(<SegmentQuestion />);
    fireEvent.click(await screen.findByTestId("segment-architect"));
    expect(screen.queryByTestId("segment-question")).toBeNull();
    expect(localStorage.getItem("ul_segment")).toBe("architect");
    expect(sessionStorage.getItem("ul_segment_due")).toBeNull();
    expect(track).toHaveBeenCalledWith("segment_selected", { segment: "architect" });
  });

  it("Skip for now settles it as dismissed", async () => {
    render(<SegmentQuestion />);
    fireEvent.click(await screen.findByRole("button", { name: "Skip for now" }));
    expect(screen.queryByTestId("segment-question")).toBeNull();
    expect(localStorage.getItem("ul_segment")).toBe("dismissed");
  });

  it("stays quiet when signed out, not due, or already answered", () => {
    auth = { isAuthenticated: false };
    const { unmount } = render(<SegmentQuestion />);
    expect(screen.queryByTestId("segment-question")).toBeNull();
    unmount();
    auth = { isAuthenticated: true };
    localStorage.setItem("ul_segment", "investor");
    render(<SegmentQuestion />);
    expect(screen.queryByTestId("segment-question")).toBeNull();
  });
});
