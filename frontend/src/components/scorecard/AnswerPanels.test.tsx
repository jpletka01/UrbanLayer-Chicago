import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { AnswerPanels, MAX_AMBER, type PanelFigure, type PanelRow } from "./AnswerPanels";
import { ProfileHeader } from "./ProfileHeader";

afterEach(cleanup);

const noop = () => {};

describe("AnswerPanels — the truth rules on the first screen", () => {
  it("shows a withheld figure as — with its short reason, never silently", () => {
    const value: PanelFigure[] = [{
      key: "comps", label: "Comps median", value: "$2.0M",
      state: { kind: "withheld", low: false }, withheldReason: "Not shown: only 1 sale (needs 3).",
    }];
    render(<AnswerPanels build={[]} inTheWay={[]} value={value} onScrollTo={noop} />);
    const fig = document.querySelector('[data-figure="comps"]')!;
    expect(fig.textContent).toContain("—");
    expect(fig.textContent).not.toContain("$2.0M");
    expect(fig.querySelector("[data-withheld-reason]")!.textContent).toBe("Not shown: only 1 sale (needs 3).");
  });

  it("labels a low figure 'Low confidence' and an estimate 'Estimate'; a verified figure carries no label", () => {
    const build: PanelFigure[] = [
      { key: "far", label: "FAR", value: "1.31 of 2.2", state: { kind: "estimate", low: true } },
      { key: "units", label: "Units", value: "≤ 11", state: { kind: "estimate", low: false } },
      { key: "zoning", label: "District", value: "B3-2" },
    ];
    render(<AnswerPanels build={build} inTheWay={[]} value={[]} onScrollTo={noop} />);
    expect(document.querySelector('[data-figure="far"]')!.textContent).toContain("Low confidence");
    expect(document.querySelector('[data-figure="units"]')!.textContent).toContain("Estimate");
    expect(document.querySelector('[data-figure="zoning"] [data-confidence-state]')).toBeNull();
  });

  it("keeps Not checked and None found apart, and rations amber to three rows", () => {
    const rows: PanelRow[] = [
      { key: "a", tone: "warning", text: "Landmark district" },
      { key: "b", tone: "warning", text: "Historic district" },
      { key: "c", tone: "warning", text: "Planned Development" },
      { key: "d", tone: "warning", text: "Lakefront Protection" },
      { key: "flood", tone: "warning", state: "not_checked", text: "FEMA flood zone" },
    ];
    render(<AnswerPanels build={[]} inTheWay={rows} value={[]} onScrollTo={noop} />);
    const panel = screen.getByTestId("panel-in-the-way");
    expect(panel.querySelectorAll('[data-status-label="warning"]').length).toBe(MAX_AMBER);
    expect(panel.textContent).toContain("+2 more");

    cleanup();
    render(<AnswerPanels build={[]} inTheWay={[{ key: "n", tone: "neutral", state: "none_found", text: "No landmark, PD, flood or lakefront rules" }]} value={[]} onScrollTo={noop} />);
    const none = screen.getByTestId("panel-in-the-way");
    expect(none.querySelector('[data-confidence-state="none_found"]')).not.toBeNull();
    expect(none.textContent).toContain("None found");
    expect(none.textContent).not.toContain("Not checked");
  });

  it("shares the amber allowance with Low confidence labels and an approximate match", () => {
    // The $1 parcel on 2026-11-02: three blockers plus a low-confidence comps median made four amber items.
    const rows: PanelRow[] = [
      { key: "nominal", tone: "warning", text: "Nominal assessment" },
      { key: "pd", tone: "warning", text: "Planned Development" },
      { key: "lake", tone: "warning", text: "Lakefront Protection" },
    ];
    const value: PanelFigure[] = [{ key: "comps", label: "Comps median", value: "$2.0M", state: { kind: "estimate", low: true } }];
    render(<AnswerPanels build={[]} inTheWay={rows} value={value} onScrollTo={noop} />);
    const all = () => document.querySelectorAll('[data-status-label="warning"]').length;
    expect(all()).toBe(MAX_AMBER); // 2 rows + the Low confidence label
    expect(screen.getByTestId("panel-in-the-way").textContent).toContain("+1 more");
    expect(screen.getByTestId("panel-in-the-way").textContent).toContain("Nominal assessment"); // most decisive kept

    cleanup();
    render(<AnswerPanels build={[]} inTheWay={rows} value={value} onScrollTo={noop} amberElsewhere={1} />);
    expect(all()).toBe(MAX_AMBER - 1); // 1 row + the label; the header's approximate label is the third
    expect(screen.getByTestId("panel-in-the-way").textContent).toContain("+2 more");
  });

  it("puts a figure's explanation behind a click, not on the page", () => {
    const value: PanelFigure[] = [{ key: "tax", label: "Est. tax", value: "$83K/yr", detailKind: "date", detailVisible: "2024", detail: "Bill year 2024." }];
    render(<AnswerPanels build={[]} inTheWay={[]} value={value} onScrollTo={noop} />);
    expect(screen.queryByText("Bill year 2024.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Est. tax" }));
    expect(screen.getByRole("dialog").textContent).toBe("Bill year 2024.");
  });
});

describe("ProfileHeader", () => {
  it("shows the address alone; area, ward, PIN and the match sit behind Parcel details", () => {
    render(<ProfileHeader title="1601 N Milwaukee Ave" pin="14313320180000" identity="exact" areaName="West Town" ward={32} />);
    const header = screen.getByTestId("profile-header");
    expect(header.textContent).not.toContain("West Town");
    expect(header.textContent).not.toContain("14-31-332-018-0000");
    expect(screen.queryByTestId("identity-warning")).toBeNull(); // no check mark, no label for a verified match
    fireEvent.click(screen.getByTestId("parcel-details-toggle"));
    const details = screen.getByTestId("parcel-details");
    expect(details.textContent).toContain("West Town · Ward 32");
    expect(within(details).getByText("PIN 14-31-332-018-0000")).toBeTruthy();
    expect(within(details).getByRole("button", { name: "Copy PIN" })).toBeTruthy();
  });

  it("keeps an approximate match visible as one amber label", () => {
    render(<ProfileHeader title="2541 N Spaulding Ave" pin="13261290170000" identity="approximate" />);
    const warn = screen.getByTestId("identity-warning");
    expect(warn.querySelector('[data-status-label="warning"]')!.textContent).toContain("Approximate location");
  });
});
