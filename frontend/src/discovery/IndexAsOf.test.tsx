import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { formatAsOf } from "./coverage";
import { IndexAsOf } from "./IndexAsOf";
import { REG } from "./_fixtures";
import type { Registry } from "./types";

afterEach(cleanup);

const withCoverage = (coverage: Registry["coverage"]): Registry => ({ ...REG, coverage });
const areas = (n: number) => Array.from({ length: n }, (_, i) => i + 1);

describe("IndexAsOf", () => {
  it("says when the index was built and how wide it is (citywide)", () => {
    render(<IndexAsOf registry={withCoverage({ mode: "all", liveAreas: areas(77), asOf: "2026-10-01" })} />);
    expect(screen.getByTestId("discovery-index-as-of").textContent).toBe(
      "Index built Oct 1, 2026 · all 77 community areas",
    );
  });

  it("does not claim the whole city for a partial index", () => {
    render(<IndexAsOf registry={withCoverage({ mode: "partial", liveAreas: areas(6), asOf: "2026-07-07" })} />);
    expect(screen.getByTestId("discovery-index-as-of").textContent).toBe(
      "Index built Jul 7, 2026 · 6 community areas",
    );
  });

  it("shows nothing without an index or without a build date", () => {
    const { container, rerender } = render(<IndexAsOf registry={withCoverage({ mode: "none", liveAreas: [] })} />);
    expect(container.textContent).toBe("");
    rerender(<IndexAsOf registry={withCoverage({ mode: "all", liveAreas: areas(77) })} />);
    expect(container.textContent).toBe("");
    rerender(<IndexAsOf registry={withCoverage({ mode: "all", liveAreas: areas(77), asOf: "not-a-date" })} />);
    expect(container.textContent).toBe("");
  });
});

describe("formatAsOf", () => {
  it("is a calendar date, not a moment: the viewer's time zone cannot move it", () => {
    expect(formatAsOf("2026-10-01", "en")).toBe("Oct 1, 2026");
    expect(formatAsOf("2026-10-01T23:59:59", "en")).toBe("Oct 1, 2026");
  });
});
