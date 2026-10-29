import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StartPanel } from "./StartPanel";
import { REG } from "./_fixtures";
import type { Registry } from "./types";

afterEach(cleanup);

const all77 = Array.from({ length: 77 }, (_, i) => i + 1);

function registry(over: Partial<Registry> = {}): Registry {
  return {
    ...REG,
    coverage: { mode: "all", liveAreas: all77, asOf: "2026-10-01" },
    populatedFields: ["land_use", "tif", "lot_size"],
    recipeCounts: { vacant_mf: 1234 },
    ...over,
  };
}

function setup(
  reg: Registry,
  resumable: Parameters<typeof StartPanel>[0]["resumable"] = null,
  extra: Partial<Parameters<typeof StartPanel>[0]> = {},
) {
  const onChoose = vi.fn();
  const onForgetResume = vi.fn();
  const onTextChange = vi.fn();
  const onSubmitText = vi.fn();
  render(
    <StartPanel
      registry={reg} resumable={resumable} onChoose={onChoose} onForgetResume={onForgetResume}
      text="" onTextChange={onTextChange} onSubmitText={onSubmitText} {...extra}
    />,
  );
  return { onChoose, onForgetResume, onTextChange, onSubmitText };
}

describe("StartPanel", () => {
  it("owns the page title now that there is no rail, then asks what the user is looking for", () => {
    setup(registry());
    expect(screen.getByRole("heading", { level: 1, name: "Property Discovery" })).toBeTruthy();
    expect(screen.getByRole("heading", { level: 2, name: "What are you looking for?" })).toBeTruthy();
    expect(screen.getByTestId("discovery-index-as-of").textContent).toBe("Index built Oct 1, 2026 · all 77 community areas");
  });

  it("shows no result of any kind (no count of rows, no list)", () => {
    setup(registry());
    expect(screen.queryByTestId("discovery-result-row")).toBeNull();
  });

  it("a recipe card carries its honest badge and the filters it will apply, read from its presets", () => {
    const { onChoose } = setup(registry());
    const card = screen.getByTestId("discovery-start-recipe-vacant_mf");
    expect(within(card).getByText("● Live · 1,234")).toBeTruthy();
    // from the presets themselves: it cannot say more or less than it filters
    expect(screen.getByTestId("discovery-start-filters-vacant_mf").textContent).toBe("Filters: Property use: Multifamily · TIF district");
    fireEvent.click(card);
    expect(onChoose).toHaveBeenCalledWith({ kind: "recipe", topic: REG.topics[0] });
  });

  it("badges 'No matches yet' and 'Needs data' instead of presenting them as live", () => {
    const { unmount } = render(
      <StartPanel registry={registry({ recipeCounts: { vacant_mf: 0 } })} resumable={null} onChoose={vi.fn()} onForgetResume={vi.fn()} text="" onTextChange={vi.fn()} onSubmitText={vi.fn()} />,
    );
    expect(screen.getByText("No matches yet")).toBeTruthy();
    unmount();
    render(
      <StartPanel registry={registry({ populatedFields: ["land_use"] })} resumable={null} onChoose={vi.fn()} onForgetResume={vi.fn()} text="" onTextChange={vi.fn()} onSubmitText={vi.fn()} />,
    );
    expect(screen.getByText("Needs data")).toBeTruthy();
  });

  it("lists neighborhoods, filters them as you type, and a pick names exactly one area", () => {
    const { onChoose } = setup(registry());
    const list = screen.getByTestId("discovery-start-areas");
    expect(within(list).getAllByRole("button")).toHaveLength(77);
    fireEvent.change(screen.getByRole("textbox", { name: "Search neighborhoods" }), { target: { value: "logan" } });
    const buttons = within(list).getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["Logan Square"]);
    fireEvent.click(buttons[0]);
    expect(onChoose).toHaveBeenCalledWith({ kind: "neighborhood", areaId: 22 });
  });

  it("says so when no neighborhood matches", () => {
    setup(registry());
    fireEvent.change(screen.getByRole("textbox", { name: "Search neighborhoods" }), { target: { value: "zzzz" } });
    expect(screen.getByText("No neighborhood matches that.")).toBeTruthy();
  });

  it("offers only the indexed areas when coverage is partial", () => {
    setup(registry({ coverage: { mode: "partial", liveAreas: [22, 24], asOf: "2026-07-07" } }));
    const names = within(screen.getByTestId("discovery-start-areas")).getAllByRole("button").map((b) => b.textContent);
    expect(names).toEqual(["Logan Square", "West Town"]);
    expect(screen.getByTestId("discovery-index-as-of").textContent).toBe("Index built Jul 7, 2026 · 2 community areas");
  });

  it("'all parcels' is a quiet, explicit choice that says what it does", () => {
    const { onChoose } = setup(registry());
    fireEvent.click(screen.getByTestId("discovery-start-all"));
    expect(onChoose).toHaveBeenCalledWith({ kind: "all" });
    expect(screen.getByText(/No filters: the whole index/)).toBeTruthy();
  });

  it("offers the last search only when there is one, and Resume/Forget do what they say", () => {
    const first = setup(registry());
    expect(screen.queryByTestId("discovery-start-resume")).toBeNull();
    expect(first.onChoose).not.toHaveBeenCalled();
    cleanup();

    const saved = { inputs: { panelState: {}, text: "", sort: null, topicId: null }, sentence: "All parcels, sorted by pin (ascending).", savedAt: 1 };
    const { onChoose, onForgetResume } = setup(registry(), saved);
    const block = screen.getByTestId("discovery-start-resume");
    expect(within(block).getByText("All parcels, sorted by pin (ascending).")).toBeTruthy();
    fireEvent.click(within(block).getByRole("button", { name: "Resume" }));
    expect(onChoose).toHaveBeenCalledWith({ kind: "resume" });
    fireEvent.click(within(block).getByRole("button", { name: "Forget it" }));
    expect(onForgetResume).toHaveBeenCalledTimes(1);
  });

  it("has a describe box that edits the draft text and submits on Enter or Search", () => {
    const { onTextChange, onSubmitText } = setup(registry(), null, { text: "tif" });
    const box = screen.getByRole("textbox", { name: "Describe what you're looking for" }) as HTMLInputElement;
    expect(box.value).toBe("tif");
    fireEvent.change(box, { target: { value: "tif near" } });
    expect(onTextChange).toHaveBeenCalledWith("tif near");
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSubmitText).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(onSubmitText).toHaveBeenCalledTimes(2);
  });

  it("shows what the text compiler made of the phrase under the box", () => {
    setup(registry(), null, { textFeedback: <p data-testid="fb">I couldn't turn it into filters.</p> });
    expect(screen.getByTestId("fb")).toBeTruthy();
  });

  it("keeps the partial-coverage notice (the rail used to carry it)", () => {
    setup(registry({ coverage: { mode: "partial", liveAreas: [22], asOf: "2026-07-07" } }));
    expect(screen.getByRole("status")).toBeTruthy();
  });
});
