import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { RecipeShelf } from "./RecipeShelf";
import { expandTopic, panelFromCqs } from "./topicCompiler";
import { compilePanel } from "./uiCompiler";
import type { CQS, Registry, TopicDef } from "./types";

afterEach(cleanup);

const TOPIC: TopicDef = {
  id: "undervalued_mf",
  label: "Undervalued multifamily",
  description: "Bottom quartile of $/sqft.",
  presets: {
    land_use: { kind: "enum", values: ["multi_family"] },
    value_percentile: { kind: "range", max: 25 },
  },
  defaultSort: { key: "value_percentile", dir: "asc" },
};

function reg(over: Partial<Registry> = {}): Registry {
  return {
    version: "v1",
    filters: [
      { id: "land_use", category: "property_use", kind: "enum", field: "land_use_class", unknownPolicy: "exclude", enumValues: ["multi_family"], label: "Property use" },
      { id: "value_percentile", category: "financial", kind: "range", field: "value_percentile", unknownPolicy: "exclude", label: "Undervalued vs. neighborhood" },
    ],
    topics: [TOPIC],
    sortKeys: [{ key: "pin", field: "pin" }, { key: "value_percentile", field: "value_percentile" }],
    defaultSort: { key: "assessed_value", dir: "asc" },
    broadMinFilters: 2,
    coverage: { mode: "none", liveAreas: [] },
    populatedFields: [],
    ...over,
  };
}

describe("recipe → userFilters contract (FE expands; backend never re-expands)", () => {
  it("a recipe click compiles to userFilters equal to the topic presets", () => {
    const r = reg();
    // The page does setPanelState(expandTopic(id)); the wire userFilters = compilePanel(panel).
    const userFilters = compilePanel(expandTopic(TOPIC.id, r));
    expect(userFilters).toEqual(TOPIC.presets);
  });

  it("removing one preset chip rebuilds userFilters minus that id (no re-expand)", () => {
    // The evaluated CQS echoes the expanded presets as source 'user'.
    const cqs: CQS = {
      filters: {
        land_use: { predicate: TOPIC.presets.land_use, source: "user" },
        value_percentile: { predicate: TOPIC.presets.value_percentile, source: "user" },
      },
      sort: { key: "value_percentile", dir: "asc" },
      scope: { mode: "all" },
      meta: { topicId: TOPIC.id },
    };
    const panel = panelFromCqs(cqs);
    delete panel.value_percentile; // onRelax drops exactly this id
    expect(compilePanel(panel)).toEqual({ land_use: TOPIC.presets.land_use });
    // It did NOT re-expand the topic (value_percentile is gone, not re-added).
    expect(panel.value_percentile).toBeUndefined();
  });
});

describe("RecipeShelf badges (Needs data / No matches yet / Live · N)", () => {
  it("reads NEEDS-DATA when the recipe's fields aren't populated (pre-index)", () => {
    render(<RecipeShelf registry={reg({ populatedFields: [] })} onPick={() => {}} />);
    expect(screen.getByText("Needs data")).toBeTruthy();
    expect(screen.queryByText(/Live/)).toBeNull();
  });

  it("reads LIVE · N when fields are populated AND the recipe has results", () => {
    render(
      <RecipeShelf
        registry={reg({ populatedFields: ["land_use", "value_percentile"], recipeCounts: { undervalued_mf: 42 } })}
        onPick={() => {}}
      />,
    );
    expect(screen.getByText(/● Live · 42/)).toBeTruthy();
    expect(screen.queryByText("Needs data")).toBeNull();
  });

  it("reads NO MATCHES YET when fields are populated but the recipe's subset is empty", () => {
    // The LIVE-but-empty trap: value_percentile is populated (by condos), but no multifamily
    // has one, so undervalued_mf returns 0. It must NOT badge Live.
    render(
      <RecipeShelf
        registry={reg({ populatedFields: ["land_use", "value_percentile"], recipeCounts: { undervalued_mf: 0 } })}
        onPick={() => {}}
      />,
    );
    expect(screen.getByText("No matches yet")).toBeTruthy();
    expect(screen.queryByText(/Live/)).toBeNull();
  });

  it("fires onPick with the topic when clicked", () => {
    const onPick = vi.fn();
    render(<RecipeShelf registry={reg()} onPick={onPick} />);
    fireEvent.click(screen.getByText("Undervalued multifamily"));
    expect(onPick).toHaveBeenCalledWith(TOPIC);
  });

  it("shows coverage-aware copy for partial coverage (read from registry.coverage)", () => {
    render(<RecipeShelf registry={reg({ coverage: { mode: "partial", liveAreas: [24] } })} onPick={() => {}} />);
    expect(screen.getByText(/live in West Town/)).toBeTruthy();
  });
});
