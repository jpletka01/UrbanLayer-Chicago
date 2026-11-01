import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Button } from "./Button";
import { ConfidenceState } from "./ConfidenceState";
import { StatusLabel } from "./StatusLabel";
import { Toggletip } from "./Toggletip";
import { confidenceStateFor } from "../../lib/confidence";
import type { Provenance } from "../../lib/api";

afterEach(cleanup);

function entry(over: Partial<Provenance>): Provenance {
  return {
    label: "Figure", kind: "official_record", source: null, record_id: null, url: null, section: null, as_of: null,
    effective_date: null, query_date: "2026-11-01", note: null, tier: "official_record", as_of_basis: "queried",
    method_key: "recorded", method: "Recorded", confidence: "standard", confidence_reasons: [],
    ...over,
  };
}

describe("shape grammar: buttons and status labels differ in at least three properties", () => {
  it("separates radius, height, focusability and cursor", () => {
    render(
      <>
        <Button variant="primary">Ask the analyst</Button>
        <StatusLabel tone="warning">Landmark district</StatusLabel>
      </>,
    );
    const button = screen.getByRole("button", { name: "Ask the analyst" });
    const label = screen.getByText("Landmark district").closest("[data-status-label]") as HTMLElement;
    const differences = [
      button.className.includes("rounded-lg") && label.className.includes("rounded-[3px]"),
      /\bh-(9|10)\b/.test(button.className) && /\bh-5\b/.test(label.className),
      button.tabIndex === 0 && label.tabIndex === -1 && label.getAttribute("role") === null,
      button.className.includes("cursor-pointer") && label.className.includes("cursor-default"),
      /focus-visible:ring/.test(button.className) && !/focus-visible/.test(label.className),
    ].filter(Boolean).length;
    expect(differences).toBeGreaterThanOrEqual(3);
  });

  it("marks only the primary button as the solid action the page budget counts", () => {
    render(
      <>
        <Button variant="primary">One</Button>
        <Button variant="secondary">Two</Button>
        <Button variant="ghost">Three</Button>
      </>,
    );
    expect(document.querySelectorAll("[data-solid-action]")).toHaveLength(1);
  });

  it("gives every status tone a glyph, so color is never the only signal", () => {
    for (const tone of ["neutral", "info", "success", "warning", "danger"] as const) {
      const { container, unmount } = render(<StatusLabel tone={tone}>x</StatusLabel>);
      expect(container.querySelector("[aria-hidden]")?.textContent?.trim()).not.toBe("");
      unmount();
    }
  });
});

describe("ConfidenceState", () => {
  it("says Not checked and None found in different words with different glyphs", () => {
    render(
      <>
        <ConfidenceState kind="not_checked" />
        <ConfidenceState kind="none_found" />
      </>,
    );
    const a = document.querySelector('[data-confidence-state="not_checked"]')!;
    const b = document.querySelector('[data-confidence-state="none_found"]')!;
    expect(a.textContent).toContain("Not checked");
    expect(b.textContent).toContain("None found");
    expect(a.querySelector("[aria-hidden]")!.textContent).not.toBe(b.querySelector("[aria-hidden]")!.textContent);
  });

  it("renders the five states and the low estimate in amber", () => {
    const { container } = render(
      <>
        <ConfidenceState kind="estimate" />
        <ConfidenceState kind="estimate" low />
        <ConfidenceState kind="withheld" />
        <ConfidenceState kind="na" />
      </>,
    );
    expect(container.textContent).toContain("Estimate");
    expect(container.textContent).toContain("Low confidence");
    expect(container.textContent).toContain("Withheld");
    expect(container.textContent).toContain("N/A");
    const low = container.querySelector('[data-confidence-state="low"] [data-status-label]')!;
    expect(low.getAttribute("data-status-label")).toBe("warning");
    const plain = container.querySelector('[data-confidence-state="estimate"] [data-status-label]')!;
    expect(plain.getAttribute("data-status-label")).toBe("neutral");
  });

  it("opens its explanation on click and closes it with Escape, returning focus", () => {
    render(<ConfidenceState kind="estimate" explainLabel="Market value" explanation="Assessed value ÷ the class's 10% level." />);
    const trigger = screen.getByRole("button", { name: "Why: Market value" });
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(trigger);
    const tip = screen.getByRole("dialog", { name: "Why: Market value" });
    expect(tip.textContent).toContain("10% level");
    fireEvent.keyDown(tip, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("maps a provenance entry to a state without recomputing it", () => {
    expect(confidenceStateFor(entry({}))).toBeNull(); // a verified record carries no label
    expect(confidenceStateFor(entry({ confidence: "withheld" }))).toEqual({ kind: "withheld", low: false });
    expect(confidenceStateFor(entry({ confidence: "low", tier: "official_estimate" }))).toEqual({ kind: "estimate", low: true });
    expect(confidenceStateFor(entry({ tier: "our_calculation" }))).toEqual({ kind: "estimate", low: false });
    expect(confidenceStateFor(null)).toBeNull();
  });
});

describe("Toggletip", () => {
  it("uses one icon per meaning and keeps a visible year beside the date icon", () => {
    render(
      <>
        <Toggletip kind="info" label="Source">§17-3-0403</Toggletip>
        <Toggletip kind="date" label="Tax year" visible="2024">Bill year 2024, from the Clerk.</Toggletip>
      </>,
    );
    expect(screen.getByRole("button", { name: "Source" }).textContent).toBe("ⓘ");
    expect(screen.getByRole("button", { name: "Tax year" }).textContent).toBe("2024⏱");
  });

  it("closes on a click outside", () => {
    render(<div><span>outside</span><Toggletip label="Source">detail</Toggletip></div>);
    fireEvent.click(screen.getByRole("button", { name: "Source" }));
    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.pointerDown(screen.getByText("outside"));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
