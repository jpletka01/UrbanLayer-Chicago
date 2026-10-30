import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { Provenance } from "../../lib/api";
import { ConfidenceCaption, ConfidenceValue, MethodCaption, SourceTooltip } from "./Confidence";

afterEach(cleanup);

function entry(over: Partial<Provenance>): Provenance {
  return {
    label: "Figure", kind: "derived", source: null, record_id: null, url: null, section: null,
    as_of: null, effective_date: null, query_date: "2026-10-21", note: null,
    tier: "our_calculation", as_of_basis: "queried", method_key: "calculation", method: "Our calculation",
    confidence: "standard", confidence_reasons: [], ...over,
  };
}
const comps = (n: number, over: Partial<Provenance> = {}) => entry({
  scope: "radius", period: "last 3 years", method_params: { radius_mi: 0.28, window_years: 3 },
  coverage: { n, unit: "sales", sample: "comps" }, ...over,
});

describe("ConfidenceCaption", () => {
  it("renders nothing for a quiet record", () => {
    const { container } = render(<ConfidenceCaption entry={entry({ tier: "official_record", method_key: "recorded" })} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing without an entry", () => {
    const { container } = render(<ConfidenceCaption entry={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the standard caption as real text", () => {
    render(<ConfidenceCaption entry={comps(12)} />);
    const el = screen.getByTestId("confidence-caption");
    expect(el.textContent).toBe("12 sales · 0.28 mi · 3 yr");
    expect(el.getAttribute("data-state")).toBe("standard");
  });

  it("leads a low figure with 'Low confidence' in the warning color", () => {
    render(<ConfidenceCaption entry={comps(4, { confidence: "low", confidence_reasons: ["small_sample"] })} />);
    const el = screen.getByTestId("confidence-caption");
    expect(el.textContent).toBe("Low confidence · 4 sales · 0.28 mi · 3 yr");
    expect(screen.getByText("Low confidence").className).toContain("text-state-warning");
  });

  it("renders a withheld figure as its reason alone", () => {
    render(<ConfidenceCaption entry={comps(2, { confidence: "withheld", confidence_reasons: ["small_sample"] })} />);
    const el = screen.getByTestId("confidence-caption");
    expect(el.textContent).toBe("Not shown: only 2 sales (needs 3).");
    expect(el.getAttribute("data-state")).toBe("withheld");
  });

  it("marks an AI reading with a neutral badge, no hue", () => {
    render(<ConfidenceCaption entry={entry({
      tier: "ai_extracted", method_key: "ai_read_code", method: "Read by AI",
      confidence: "low", confidence_reasons: ["ai_unverified"],
    })} />);
    const badge = screen.getByText("AI");
    expect(badge.className).toContain("font-mono");
    expect(badge.className).not.toMatch(/state-|accent|highlight/);
    expect(screen.getByTestId("confidence-caption").textContent).toBe("AIRead by AI from the code · not verified");
  });

  it("uses the micro scale in tiles and a prefix to name a figure", () => {
    render(<ConfidenceCaption entry={comps(12)} size="micro" prefix="Price per ft²" />);
    const el = screen.getByTestId("confidence-caption");
    expect(el.className).toContain("text-micro");
    expect(el.textContent).toBe("Price per ft²: 12 sales · 0.28 mi · 3 yr");
  });

  it("can omit a part the caller shows beside the value", () => {
    render(<ConfidenceCaption entry={entry({
      tier: "official_estimate", method_key: "government_model", period: "2024", as_of_basis: "tax_year",
    })} omit={["period"]} />);
    expect(screen.getByTestId("confidence-caption").textContent).toBe("Government model");
  });
});

describe("unavailable (WS6: the source couldn't be checked today)", () => {
  it("says so even for a figure that would otherwise be quiet", () => {
    render(<ConfidenceCaption entry={undefined} unavailable />);
    const el = screen.getByTestId("confidence-caption");
    expect(el.textContent).toBe("Couldn't be checked today");
    expect(el.getAttribute("data-state")).toBe("unavailable");
  });

  it("dashes the value", () => {
    render(<ConfidenceValue entry={entry({})} unavailable>$310,000</ConfidenceValue>);
    expect(screen.queryByText("$310,000")).toBeNull();
    expect(screen.getByText("—").getAttribute("data-state")).toBe("unavailable");
  });
});

describe("ConfidenceValue", () => {
  it("shows a standard value as is", () => {
    render(<ConfidenceValue entry={entry({})}>$310,000</ConfidenceValue>);
    expect(screen.getByText("$310,000")).toBeTruthy();
  });

  it("quiets a low value without fading the text below contrast", () => {
    render(<ConfidenceValue entry={entry({ confidence: "low" })}>$310,000</ConfidenceValue>);
    const el = screen.getByText("$310,000");
    expect(el.className).toContain("text-text-secondary");
    expect(el.className).not.toMatch(/opacity/);
  });

  it("replaces a withheld value with a dash", () => {
    render(<ConfidenceValue entry={entry({ confidence: "withheld" })}>$310,000</ConfidenceValue>);
    expect(screen.queryByText("$310,000")).toBeNull();
    expect(screen.getByText("—")).toBeTruthy();
  });
});

describe("SourceTooltip", () => {
  it("adds the Source block to the label's own definition", () => {
    render(
      <SourceTooltip label="Stories" description="Number of floors." entry={entry({
        tier: "official_record", method_key: "recorded", method: "Read as recorded by the publisher",
        as_of: "2015-08-15", as_of_basis: "source_updated", age_days: 4085, source_id: "chi.building_footprints",
      })}>Stories</SourceTooltip>,
    );
    fireEvent.mouseEnter(screen.getByText("Stories"));
    expect(screen.getByText("Number of floors.")).toBeTruthy();
    expect(screen.getByText("Published by: Official record")).toBeTruthy();
    expect(screen.getByText("Source: City footprint survey")).toBeTruthy();
  });

  it("is a plain label when there is neither a definition nor an entry", () => {
    render(<SourceTooltip label="Stories" entry={undefined}>Stories</SourceTooltip>);
    fireEvent.mouseEnter(screen.getByText("Stories"));
    expect(screen.queryByText("Source")).toBeNull();
  });
});

describe("MethodCaption", () => {
  it("states the method in words", () => {
    render(<MethodCaption method="keyword_grouping" />);
    expect(screen.getByText("Grouped by keyword (our grouping)")).toBeTruthy();
  });
});
