import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { REG } from "./_fixtures";
import { useDiscoverySearch } from "./useDiscoverySearch";
import type { PinsResponse, SearchResponse } from "./types";

const mocks = vi.hoisted(() => ({
  runSearch: vi.fn(),
  runPins: vi.fn(),
  previewText: vi.fn(),
  exportCsv: vi.fn(),
  track: vi.fn(),
}));

vi.mock("./searchClient", () => ({
  runSearch: mocks.runSearch,
  runPins: mocks.runPins,
  previewText: mocks.previewText,
  exportCsv: mocks.exportCsv,
}));
vi.mock("../lib/tracking", () => ({ track: mocks.track }));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function row(pin: string) {
  return {
    pin, lat: 41.9, lon: -87.7, address: `${pin} address`, community_area: 24,
    land_use: "commercial", class: null, lot_sqft: null, bldg_sqft: null,
    year_built: null, units: null, assessed_value: null, price_per_sf: null,
    last_sale_price: null, last_sale_date: null, improvement_ratio: null,
    value_percentile: null, upside_score: null, is_teardown_candidate: false, sortValue: pin,
  };
}

// A response whose cqs carries the user filters that were sent, like the real backend.
function response(dataVersion: string, pin: string, filters: SearchResponse["cqs"]["filters"] = {}, total = 1): SearchResponse {
  return {
    dataVersion,
    cqs: { filters, sort: REG.defaultSort, scope: { mode: "all" }, meta: {} },
    result: { rows: [row(pin)], total, nextOffset: null },
    diagnostics: {
      resultCount: total, broad: false, appliedFilters: Object.keys(filters).length,
      conflicts: [], droppedInvalid: [], excludedUnknown: {}, mostRestrictive: [],
    },
  };
}

function pins(dataVersion: string, pin: string, total = 1): PinsResponse {
  return {
    dataVersion, total, truncated: false,
    points: [{ pin, lat: 41.9, lon: -87.7, upside: null, landUse: "commercial" }],
  };
}

// What the backend returns for a search that asked for `includePins`: the map's points from
// the same evaluation, inside the one response.
function combined(dataVersion: string, pin: string, filters: SearchResponse["cqs"]["filters"] = {}, total = 1): SearchResponse {
  return { ...response(dataVersion, pin, filters, total), pins: pins(dataVersion, pin, total) };
}

const TIF = { kind: "flag", value: true } as const;
const LAND = { kind: "enum", values: ["multi_family"] } as const;
const withFilters = (...ids: Array<[string, typeof TIF | typeof LAND]>) =>
  Object.fromEntries(ids.map(([id, predicate]) => [id, { predicate, source: "user" as const }]));

function setup() {
  return renderHook(() => useDiscoverySearch(REG));
}

async function firstSearch(hook: ReturnType<typeof setup>, filters = withFilters(["tif", TIF], ["land_use", LAND])) {
  mocks.runSearch.mockResolvedValueOnce(combined("v1", "first", filters));
  act(() => {
    hook.result.current.editPanel("tif", TIF);
    hook.result.current.editPanel("land_use", LAND);
  });
  act(() => hook.result.current.apply());
  await waitFor(() => expect(hook.result.current.loading).toBe(false));
  mocks.runSearch.mockClear();
  mocks.runPins.mockClear();
}

beforeEach(() => {
  mocks.runSearch.mockReset();
  mocks.runPins.mockReset();
  mocks.exportCsv.mockReset();
  mocks.track.mockReset();
  mocks.previewText.mockReset().mockResolvedValue({ understood: [{ filterId: "tif", predicate: { kind: "flag", value: true } }], residual: [], droppedInvalid: [] });
});

afterEach(cleanup);

describe("useDiscoverySearch: draft and apply", () => {
  it("requests nothing for draft edits, then exactly one request (list + map) per apply", async () => {
    const hook = setup();
    await firstSearch(hook);

    act(() => {
      hook.result.current.removeFilter("tif");
      hook.result.current.removeFilter("land_use");
      hook.result.current.editPanel("lot_size", { kind: "range", min: 3000 });
      hook.result.current.setText("");
      hook.result.current.clearAll();
      hook.result.current.restoreFilter("tif");
    });
    expect(mocks.runSearch).not.toHaveBeenCalled();
    expect(mocks.runPins).not.toHaveBeenCalled();
    expect(hook.result.current.pendingCount).toBeGreaterThan(0);

    mocks.runSearch.mockResolvedValueOnce(combined("v1", "second", withFilters(["tif", TIF])));
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.loading).toBe(false));
    expect(mocks.runSearch).toHaveBeenCalledTimes(1);
    expect(mocks.runSearch.mock.calls[0][0].includePins).toBe(true);
    expect(mocks.runPins).not.toHaveBeenCalled(); // the points came back in the same response
    expect(hook.result.current.rows[0].pin).toBe("second");
    expect(hook.result.current.map.points[0].pin).toBe("second");
  });

  it("sends the draft as it is at apply time", async () => {
    const hook = setup();
    await firstSearch(hook);
    act(() => hook.result.current.removeFilter("tif"));
    mocks.runSearch.mockResolvedValueOnce(response("v1", "x", withFilters(["land_use", LAND])));
    mocks.runPins.mockResolvedValueOnce(pins("v1", "x"));
    act(() => hook.result.current.apply());
    const sent = mocks.runSearch.mock.calls[0][0];
    expect(Object.keys(sent.panelState)).toEqual(["land_use"]);
    await waitFor(() => expect(hook.result.current.loading).toBe(false));
  });

  it("does nothing for an apply that matches the search already in flight", async () => {
    const hook = setup();
    const search = deferred<SearchResponse | null>();
    mocks.runSearch.mockImplementation(() => search.promise);
    mocks.runPins.mockResolvedValue(null);
    act(() => hook.result.current.editPanel("tif", TIF));
    act(() => hook.result.current.apply());
    act(() => hook.result.current.apply());
    act(() => hook.result.current.apply());
    expect(mocks.runSearch).toHaveBeenCalledTimes(1);
    expect(hook.result.current.draftIsInFlight).toBe(true);
    await act(async () => search.resolve(null));
  });

  it("aborts the superseded request and ignores its late response", async () => {
    const hook = setup();
    await firstSearch(hook);
    const slowSearch = deferred<SearchResponse | null>();
    mocks.runSearch.mockImplementationOnce(() => slowSearch.promise);
    act(() => hook.result.current.removeFilter("tif"));
    act(() => hook.result.current.apply());
    const firstSignal = mocks.runSearch.mock.calls[0][2] as AbortSignal;
    expect(firstSignal.aborted).toBe(false);

    mocks.runSearch.mockResolvedValueOnce(combined("v2", "newer", withFilters()));
    act(() => hook.result.current.removeFilter("land_use"));
    act(() => hook.result.current.apply());
    expect(firstSignal.aborted).toBe(true);
    await waitFor(() => expect(hook.result.current.rows[0]?.pin).toBe("newer"));

    // the aborted request resolves late: it must not overwrite the newer commit
    await act(async () => {
      slowSearch.resolve(combined("v1", "stale", withFilters(["land_use", LAND])));
    });
    expect(hook.result.current.rows[0].pin).toBe("newer");
    expect(hook.result.current.map.points[0].pin).toBe("newer");
    expect(hook.result.current.applied?.dataVersion).toBe("v2");
  });

  it("never sends a search without the default sort, so the response still reconciles the draft", async () => {
    // A search issued before the default-sort effect had run went out with sort null; the effect then
    // changed the draft, the response no longer matched it, and its filters showed as removed chips
    // (the 2026-10-31 Discovery test flake).
    const hook = setup();
    act(() => hook.result.current.setSort(null));
    mocks.runSearch.mockResolvedValueOnce(combined("v1", "first", withFilters(["tif", TIF])));
    act(() => hook.result.current.editPanel("tif", TIF));
    act(() => hook.result.current.apply());
    expect(mocks.runSearch.mock.calls[0][0].sort).toEqual(REG.defaultSort);
    await waitFor(() => expect(hook.result.current.loading).toBe(false));
    expect(hook.result.current.chips.map((c) => [c.id, c.state])).toEqual([["tif", "applied"]]);
  });

  it("keeps the previous results, count and dots while a refresh runs", async () => {
    const hook = setup();
    await firstSearch(hook);
    const nextSearch = deferred<SearchResponse | null>();
    const nextPins = deferred<PinsResponse | null>();
    mocks.runSearch.mockImplementationOnce(() => nextSearch.promise);
    mocks.runPins.mockImplementationOnce(() => nextPins.promise);
    act(() => hook.result.current.removeFilter("tif"));
    act(() => hook.result.current.apply());

    expect(hook.result.current.loading).toBe(true);
    expect(hook.result.current.refreshing).toBe(true);
    expect(hook.result.current.applied?.dataVersion).toBe("v1");
    expect(hook.result.current.rows.map((r) => r.pin)).toEqual(["first"]);
    expect(hook.result.current.map.status).toBe("ready");
    expect(hook.result.current.map.points).toHaveLength(1);
    // chips stay available and editable mid-refresh
    expect(hook.result.current.chips.map((c) => c.id)).toEqual(["land_use", "tif"]);
    act(() => hook.result.current.restoreFilter("tif"));
    expect(hook.result.current.chips.find((c) => c.id === "tif")?.state).toBe("applied");

    await act(async () => {
      nextSearch.resolve(response("v1", "second", withFilters(["land_use", LAND])));
      nextPins.resolve(pins("v1", "second"));
    });
    expect(hook.result.current.rows[0].pin).toBe("second");
  });

  it("keeps the previous results and flags a failed refresh; the retry sends the draft again", async () => {
    const hook = setup();
    await firstSearch(hook);
    mocks.runSearch.mockResolvedValueOnce(null);
    mocks.runPins.mockResolvedValueOnce(pins("v1", "x"));
    act(() => hook.result.current.removeFilter("tif"));
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.refreshFailed).toBe(true));
    expect(hook.result.current.unavailable).toBe(false);
    expect(hook.result.current.rows.map((r) => r.pin)).toEqual(["first"]);
    expect(hook.result.current.applied?.dataVersion).toBe("v1");
    expect(hook.result.current.map.points).toHaveLength(1);
    expect(hook.result.current.pendingCount).toBe(1);

    mocks.runSearch.mockResolvedValueOnce(response("v1", "retried", withFilters(["land_use", LAND])));
    mocks.runPins.mockResolvedValueOnce(pins("v1", "retried"));
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.rows[0].pin).toBe("retried"));
    expect(hook.result.current.refreshFailed).toBe(false);
  });

  it("treats a failure with nothing on screen as unavailable", async () => {
    const hook = setup();
    mocks.runSearch.mockResolvedValue(null);
    mocks.runPins.mockResolvedValue(null);
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.unavailable).toBe(true));
    expect(hook.result.current.refreshFailed).toBe(false);
    expect(hook.result.current.map.status).toBe("unavailable");
  });
});

describe("useDiscoverySearch: INV-4 and Item 30", () => {
  it("never describes an unevaluated draft: applied (summary/count source) only changes on a response", async () => {
    const hook = setup();
    await firstSearch(hook);
    const evaluated = hook.result.current.applied;
    act(() => {
      hook.result.current.clearAll();
      hook.result.current.setText("something new");
      hook.result.current.setSort({ key: "lot_size", dir: "desc" });
    });
    expect(hook.result.current.applied).toBe(evaluated);
    expect(Object.keys(hook.result.current.applied!.cqs.filters).sort()).toEqual(["land_use", "tif"]);
    expect(hook.result.current.applied!.result.total).toBe(1);
    expect(hook.result.current.rows.map((r) => r.pin)).toEqual(["first"]);
    // the draft differs, and says so through the pending count and struck-through chips
    expect(hook.result.current.pendingCount).toBeGreaterThan(0);
    expect(hook.result.current.chips.every((c) => c.state === "removed")).toBe(true);
  });

  it("Clear all is a draft edit: chips show the removal, the evaluated query is untouched until applied", async () => {
    const hook = setup();
    await firstSearch(hook);
    act(() => hook.result.current.clearAll());
    expect(mocks.runSearch).not.toHaveBeenCalled();
    expect(hook.result.current.draft.panelState).toEqual({});
    expect(hook.result.current.pendingCount).toBe(2);

    mocks.runSearch.mockResolvedValueOnce(response("v1", "all", withFilters(), 99));
    mocks.runPins.mockResolvedValueOnce(pins("v1", "all", 99));
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.applied?.result.total).toBe(99));
    expect(hook.result.current.pendingCount).toBe(0);
    expect(hook.result.current.chips).toEqual([]);
  });

  it("keeps the new list but marks the map unavailable when the pins disagree with it", async () => {
    const hook = setup();
    await firstSearch(hook);
    mocks.runSearch.mockResolvedValueOnce(response("v2", "second", withFilters()));
    mocks.runPins.mockResolvedValueOnce(pins("OTHER", "wrong"));
    act(() => hook.result.current.clearAll());
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.rows[0].pin).toBe("second"));
    expect(hook.result.current.map.status).toBe("unavailable");
    expect(hook.result.current.map.points).toEqual([]);
  });

  it("rejects pins whose total or cardinality disagree", async () => {
    const hook = setup();
    mocks.runSearch.mockResolvedValueOnce(response("v1", "one", {}, 3));
    mocks.runPins.mockResolvedValueOnce(pins("v1", "one", 2));
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.loading).toBe(false));
    expect(hook.result.current.map.status).toBe("unavailable");
  });

  it("reconciles the strip to the evaluated cqs when no edits were made in flight", async () => {
    const hook = setup();
    mocks.runSearch.mockResolvedValueOnce(response("v1", "one", withFilters(["tif", TIF])));
    mocks.runPins.mockResolvedValueOnce(pins("v1", "one"));
    act(() => hook.result.current.editPanel("tif", TIF));
    act(() => hook.result.current.editPanel("land_use", LAND)); // the server drops this one
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.loading).toBe(false));
    expect(Object.keys(hook.result.current.draft.panelState)).toEqual(["tif"]);
    expect(hook.result.current.pendingCount).toBe(0);
  });

  it("does not overwrite edits made while the search was running", async () => {
    const hook = setup();
    const search = deferred<SearchResponse | null>();
    mocks.runSearch.mockImplementationOnce(() => search.promise);
    mocks.runPins.mockResolvedValueOnce(pins("v1", "one"));
    act(() => hook.result.current.editPanel("tif", TIF));
    act(() => hook.result.current.apply());
    act(() => hook.result.current.editPanel("land_use", LAND));
    await act(async () => search.resolve(response("v1", "one", withFilters(["tif", TIF]))));
    expect(Object.keys(hook.result.current.draft.panelState).sort()).toEqual(["land_use", "tif"]);
    expect(hook.result.current.pendingCount).toBe(1);
  });
});

describe("useDiscoverySearch: load more, export, analytics", () => {
  it("loads further pages from the committed search, not from a draft", async () => {
    const hook = setup();
    mocks.runSearch.mockResolvedValueOnce({
      ...response("v1", "p0", withFilters(["tif", TIF]), 2),
      result: { rows: [row("p0")], total: 2, nextOffset: 1 },
    });
    mocks.runPins.mockResolvedValueOnce({ ...pins("v1", "p0", 2), points: [pins("v1", "p0").points[0], pins("v1", "p1").points[0]] });
    act(() => hook.result.current.editPanel("tif", TIF));
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.nextOffset).toBe(1));

    act(() => hook.result.current.clearAll()); // an unapplied edit
    mocks.runSearch.mockResolvedValueOnce({
      ...response("v1", "p1", withFilters(["tif", TIF]), 2),
      result: { rows: [row("p1")], total: 2, nextOffset: null },
    });
    await act(async () => { await hook.result.current.loadMore(); });
    const sent = mocks.runSearch.mock.calls.at(-1)![0];
    expect(Object.keys(sent.panelState)).toEqual(["tif"]);
    expect(sent.offset).toBe(1);
    expect(hook.result.current.rows.map((r) => r.pin)).toEqual(["p0", "p1"]);
  });

  it("exports the search on screen", async () => {
    const hook = setup();
    await firstSearch(hook);
    act(() => hook.result.current.clearAll());
    act(() => hook.result.current.exportApplied());
    const exported = mocks.exportCsv.mock.calls[0][0];
    expect(Object.keys(exported.panelState).sort()).toEqual(["land_use", "tif"]);
  });

  it("adds ms (click to results painted) to the discovery_search event", async () => {
    const hook = setup();
    mocks.runSearch.mockResolvedValueOnce(response("v1", "one", {}, 7));
    mocks.runPins.mockResolvedValueOnce(pins("v1", "one", 7));
    act(() => hook.result.current.apply());
    await waitFor(() => expect(mocks.track).toHaveBeenCalled());
    const [name, props] = mocks.track.mock.calls[0];
    expect(name).toBe("discovery_search");
    expect(props).toMatchObject({ topic_id: null, has_text: false, total: 7, gated: null });
    expect(typeof props.ms).toBe("number");
    expect(props.ms).toBeGreaterThanOrEqual(0);
  });
});

describe("useDiscoverySearch: the map's points ride the search response (includePins)", () => {
  async function applyOnce(hook: ReturnType<typeof setup>, resp: SearchResponse) {
    mocks.runSearch.mockResolvedValueOnce(resp);
    act(() => hook.result.current.editPanel("tif", TIF));
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.loading).toBe(false));
  }

  it("still withholds the map when the embedded points belong to another data version", async () => {
    const hook = setup();
    await applyOnce(hook, { ...response("v1", "one"), pins: pins("v0", "one") });
    expect(hook.result.current.rows[0].pin).toBe("one"); // the list stays canonical
    expect(hook.result.current.map.status).toBe("unavailable");
    expect(hook.result.current.map.points).toEqual([]);
  });

  it("withholds the map when the embedded total or cardinality disagrees with the list", async () => {
    const wrongTotal = setup();
    await applyOnce(wrongTotal, { ...response("v1", "one", {}, 5), pins: pins("v1", "one", 4) });
    expect(wrongTotal.result.current.map.status).toBe("unavailable");
    cleanup();

    const wrongCount = setup();
    await applyOnce(wrongCount, {
      ...response("v1", "one", {}, 2),
      pins: { ...pins("v1", "one", 2), points: pins("v1", "one", 1).points },
    });
    expect(wrongCount.result.current.map.status).toBe("unavailable");
  });

  it("shows the embedded points as the map when they agree with the list", async () => {
    const hook = setup();
    await applyOnce(hook, combined("v1", "one"));
    expect(hook.result.current.map).toMatchObject({ status: "ready", total: 1, truncated: false });
    expect(hook.result.current.map.points[0].pin).toBe("one");
  });

  it("falls back to the separate pins request when the backend sends no points (older backend)", async () => {
    const hook = setup();
    mocks.runPins.mockResolvedValueOnce(pins("v1", "one"));
    await applyOnce(hook, response("v1", "one")); // no `pins` field
    expect(mocks.runPins).toHaveBeenCalledTimes(1);
    expect(mocks.runPins.mock.calls[0][0].includePins).toBeUndefined();
    expect(hook.result.current.map.status).toBe("ready");
    expect(hook.result.current.map.points[0].pin).toBe("one");
  });

  it("a failed fallback pins request leaves the list and makes only the map unavailable", async () => {
    const hook = setup();
    mocks.runPins.mockRejectedValueOnce(new Error("pins down"));
    await applyOnce(hook, response("v1", "one"));
    expect(hook.result.current.rows[0].pin).toBe("one");
    expect(hook.result.current.map.status).toBe("unavailable");
    expect(hook.result.current.unavailable).toBe(false);
  });

  it("does not make a second request when the response already carries the points", async () => {
    const hook = setup();
    await applyOnce(hook, combined("v1", "one"));
    expect(mocks.runPins).not.toHaveBeenCalled();
  });

  it("load more asks for the next window only, never for the points again", async () => {
    const hook = setup();
    const first = combined("v1", "one", {}, 120);
    first.result.nextOffset = 50;
    await applyOnce(hook, first);
    mocks.runSearch.mockResolvedValueOnce(response("v1", "two", {}, 120));
    await act(async () => { await hook.result.current.loadMore(); });
    const call = mocks.runSearch.mock.calls[1][0];
    expect(call.offset).toBe(50);
    expect(call.includePins).toBeUndefined();
  });
});


describe("useDiscoverySearch: the text gate (ask the compiler before searching)", () => {
  const NOTHING = { understood: [], residual: ["teardown", "logan"], droppedInvalid: [] };

  it("does not search a phrase the compiler understood none of, and keeps the previous results", async () => {
    const hook = setup();
    await firstSearch(hook);
    mocks.previewText.mockResolvedValueOnce(NOTHING);
    act(() => {
      hook.result.current.clearAll();
      hook.result.current.setText("teardown in logan square");
    });
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.textNotice).not.toBeNull());
    expect(hook.result.current.textNotice).toEqual({ text: "teardown in logan square", words: ["teardown", "logan"] });
    expect(mocks.runSearch).not.toHaveBeenCalled();
    expect(hook.result.current.rows[0].pin).toBe("first"); // nothing was replaced
    expect(hook.result.current.applied?.dataVersion).toBe("v1");
  });

  it("searches when the compiler understood something, sending the text as typed", async () => {
    const hook = setup();
    mocks.runSearch.mockResolvedValueOnce(combined("v1", "one"));
    act(() => hook.result.current.setText("tif"));
    act(() => hook.result.current.apply());
    // `loading` is false until the async text check hands over to the search, so wait for the
    // result itself, not for "not loading".
    await waitFor(() => expect(hook.result.current.appliedText).toBe("tif"));
    expect(mocks.previewText).toHaveBeenCalledWith("tif");
    expect(mocks.runSearch.mock.calls[0][0].text).toBe("tif");
    expect(hook.result.current.textNotice).toBeNull();
  });

  it("fails open: if the compiler cannot be asked (null or a throw), it searches anyway", async () => {
    for (const failure of [() => Promise.resolve(null), () => Promise.reject(new Error("down"))]) {
      cleanup();
      mocks.runSearch.mockReset();
      mocks.previewText.mockReset().mockImplementationOnce(failure);
      mocks.runSearch.mockResolvedValueOnce(combined("v1", "one"));
      const hook = setup();
      act(() => hook.result.current.setText("anything"));
      act(() => hook.result.current.apply());
      await waitFor(() => expect(mocks.runSearch).toHaveBeenCalledTimes(1));
      expect(hook.result.current.textNotice).toBeNull();
    }
  });

  it("does not ask when there are panel filters beside the text, or when the text is blank", async () => {
    const hook = setup();
    mocks.runSearch.mockResolvedValue(combined("v1", "one"));
    act(() => {
      hook.result.current.editPanel("tif", TIF);
      hook.result.current.setText("teardown in logan square");
    });
    act(() => hook.result.current.apply());
    expect(mocks.runSearch).toHaveBeenCalledTimes(1); // immediately: the filters carry the search
    expect(mocks.previewText).not.toHaveBeenCalled();
    await waitFor(() => expect(hook.result.current.loading).toBe(false));

    mocks.runSearch.mockClear();
    act(() => {
      hook.result.current.clearAll();
      hook.result.current.setText("   ");
    });
    act(() => hook.result.current.apply());
    expect(mocks.previewText).not.toHaveBeenCalled();
  });

  it("ignores a text check that a later edit or a recipe click superseded", async () => {
    const hook = setup();
    const slow = deferred<typeof NOTHING | null>();
    mocks.previewText.mockImplementationOnce(() => slow.promise);
    act(() => hook.result.current.setText("tif"));
    act(() => hook.result.current.apply());
    // the user clicks a recipe while the check is in flight: the recipe wins
    mocks.runSearch.mockResolvedValueOnce(combined("v1", "recipe"));
    act(() => hook.result.current.pickRecipe(REG.topics[0]));
    await waitFor(() => expect(mocks.runSearch).toHaveBeenCalledTimes(1));
    await act(async () => slow.resolve(null)); // the stale check now answers
    expect(mocks.runSearch).toHaveBeenCalledTimes(1); // and does not start a second search
    expect(hook.result.current.textNotice).toBeNull();
  });

  it("clears the notice when the text changes", async () => {
    const hook = setup();
    mocks.previewText.mockResolvedValueOnce(NOTHING);
    act(() => hook.result.current.setText("teardown"));
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.textNotice).not.toBeNull());
    act(() => hook.result.current.setText("teardown tif"));
    expect(hook.result.current.textNotice).toBeNull();
  });
});


describe("useDiscoverySearch: discard changes", () => {
  it("puts the draft back to the evaluated query (filters, text, sort) and requests nothing", async () => {
    const hook = setup();
    await firstSearch(hook); // applied: tif + land_use
    act(() => {
      hook.result.current.removeFilter("tif");
      hook.result.current.editPanel("lot_size", { kind: "range", min: 3000 });
      hook.result.current.setSort({ key: "lot_size", dir: "desc" });
    });
    expect(hook.result.current.pendingCount).toBeGreaterThan(0);
    act(() => hook.result.current.discardChanges());
    expect(hook.result.current.pendingCount).toBe(0);
    expect(Object.keys(hook.result.current.draft.panelState).sort()).toEqual(["land_use", "tif"]);
    expect(hook.result.current.draft.sort).toEqual(REG.defaultSort);
    expect(mocks.runSearch).not.toHaveBeenCalled();
    expect(hook.result.current.rows[0].pin).toBe("first"); // what is on screen never moved
  });

  it("does nothing before any search has been evaluated", () => {
    const hook = setup();
    act(() => hook.result.current.editPanel("tif", TIF));
    act(() => hook.result.current.discardChanges());
    expect(hook.result.current.draft.panelState.tif).toEqual(TIF); // nothing to go back to
  });

  it("clears a 'nothing understood' notice along with the edit it came from", async () => {
    const hook = setup();
    await firstSearch(hook);
    mocks.previewText.mockResolvedValueOnce({ understood: [], residual: ["x"], droppedInvalid: [] });
    act(() => {
      hook.result.current.clearAll();
      hook.result.current.setText("xyz");
    });
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.textNotice).not.toBeNull());
    act(() => hook.result.current.discardChanges());
    expect(hook.result.current.textNotice).toBeNull();
    expect(hook.result.current.draft.text).toBe("");
  });
});


describe("useDiscoverySearch: start over", () => {
  it("drops everything on screen, empties the draft, and goes back to nothing evaluated", async () => {
    const hook = setup();
    await firstSearch(hook);
    act(() => hook.result.current.setText("leftover"));
    act(() => hook.result.current.startOver());
    expect(hook.result.current.applied).toBeNull();
    expect(hook.result.current.rows).toEqual([]);
    expect(hook.result.current.map).toMatchObject({ points: [], status: "idle", total: 0 });
    expect(hook.result.current.draft).toMatchObject({ panelState: {}, text: "", topicId: null, sort: REG.defaultSort });
    expect(hook.result.current.chips).toEqual([]);
    expect(hook.result.current.pendingCount).toBe(0);
    expect(hook.result.current.loading).toBe(false);
    expect(mocks.runSearch).not.toHaveBeenCalled();
  });

  it("abandons a search in flight: its late response must not bring the old results back", async () => {
    const hook = setup();
    await firstSearch(hook);
    const slow = deferred<SearchResponse | null>();
    mocks.runSearch.mockImplementationOnce(() => slow.promise);
    act(() => hook.result.current.removeFilter("tif"));
    act(() => hook.result.current.apply());
    const signal = mocks.runSearch.mock.calls[0][2] as AbortSignal;
    act(() => hook.result.current.startOver());
    expect(signal.aborted).toBe(true);
    expect(hook.result.current.loading).toBe(false);
    await act(async () => slow.resolve(combined("v2", "late")));
    expect(hook.result.current.applied).toBeNull();
    expect(hook.result.current.rows).toEqual([]);
  });

  it("clears a failure state so the Start panel is not shown beside an error", async () => {
    const hook = setup();
    mocks.runSearch.mockResolvedValueOnce(null);
    act(() => hook.result.current.editPanel("tif", TIF));
    act(() => hook.result.current.apply());
    await waitFor(() => expect(hook.result.current.unavailable).toBe(true));
    act(() => hook.result.current.startOver());
    expect(hook.result.current.unavailable).toBe(false);
    expect(hook.result.current.refreshFailed).toBe(false);
  });
});
