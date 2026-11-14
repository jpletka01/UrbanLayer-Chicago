import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DataHealthSection } from "./DataHealthSection";
import { sortSources } from "../../lib/dataHealth";
import type { DataHealth, DataHealthSource, SourceState } from "../../lib/api";

vi.mock("../../lib/api", async (orig) => {
  const mod = await orig<typeof import("../../lib/api")>();
  return { ...mod, fetchDataHealth: vi.fn(), fetchDataHealthHistory: vi.fn() };
});
import { fetchDataHealth, fetchDataHealthHistory } from "../../lib/api";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function src(id: string, state: SourceState, over: Partial<DataHealthSource> = {}): DataHealthSource {
  return {
    id, name: `Source ${id}`, publisher: "City of Chicago", link: null, tier: "official_record", kind: "socrata",
    severity: "standard", owner_modules: ["backend/retrieval/x.py"], surfaces: ["profile"], state, reason: "",
    as_of: "2026-10-01", basis: "content", age_days: 21, warn_days: 60, alarm_days: 120, frozen: null,
    contract: null, ack: null, state_since: "2026-10-01T05:37:00+00:00", checked_at: "2026-10-22T05:37:00+00:00",
    probe_error: false, latency_ms: 10, requests: 1, note: "", ...over,
  };
}

const health = (over: Partial<DataHealth["checker"]> = {}, sources: DataHealthSource[] = []): DataHealth => ({
  checker: {
    state: "ok", last_run: "2026-10-22T05:39:00+00:00", age_h: 3.4, late_after_h: 36,
    next_run: "2026-10-23T05:37:00+00:00", last_error: null, runs: [], ...over,
  },
  counts: sources.reduce<DataHealth["counts"]>((c, s) => ({ ...c, [s.state]: (c[s.state] ?? 0) + 1 }), {}),
  sources,
});

describe("sortSources", () => {
  it("orders alarm, error, warn, unknown, acked, ok, with critical first inside a state", () => {
    const rows = [
      src("z.ok", "ok"), src("y.acked", "acked"), src("x.unknown", "unknown"), src("w.warn", "warn"),
      src("v.error", "error"), src("u.alarm", "alarm"), src("a.alarm", "alarm"),
      src("c.alarm", "alarm", { severity: "critical" }), src("f.frozen", "frozen_ok"),
    ];
    expect(sortSources(rows).map((r) => r.id)).toEqual([
      "c.alarm", "a.alarm", "u.alarm", "v.error", "w.warn", "x.unknown", "y.acked", "z.ok", "f.frozen",
    ]);
  });
});

describe("DataHealthSection — contract column (WS6 M4)", () => {
  it("says what each source's daily contract checks, and lists it on hover", async () => {
    vi.mocked(fetchDataHealth).mockResolvedValue(health({}, [
      src("chi.zoning.districts", "ok", {
        contract: { layer_name: "Zoning Boundaries", required_fields: ["ZONE_CLASS", "ORDINANCE_NUM"], count_band: [14131, 15618], values: ["ZONE_CLASS"] },
      }),
      src("chi.crime", "ok", { contract: null }),
    ]));
    render(<DataHealthSection />);
    await waitFor(() => expect(screen.getByTestId("dh-table")).toBeTruthy());
    const cell = screen.getByText("2 fields · 1 value set · count band · layer name");
    expect(cell.getAttribute("title")).toContain("Fields read: ZONE_CLASS, ORDINANCE_NUM");
    expect(cell.getAttribute("title")).toContain("Value sets: ZONE_CLASS");
    expect(cell.getAttribute("title")).toContain("Count band: 14131–15618");
  });
});

describe("DataHealthSection — admin 'Data health' panel", () => {
  it("lists the worst source first, with its state and counts", async () => {
    vi.mocked(fetchDataHealth).mockResolvedValue(
      health({}, [src("a.ok", "ok"), src("drill.synthetic", "alarm", { severity: "critical", reason: "400 days old" })]),
    );
    render(<DataHealthSection />);
    await waitFor(() => expect(screen.getByTestId("data-health")).toBeTruthy());
    const rows = screen.getByTestId("dh-table").querySelectorAll("tbody tr");
    expect(rows[0].textContent).toContain("drill.synthetic");
    expect(screen.getByTestId("dh-state-drill.synthetic").textContent).toBe("alarm");
    expect(screen.getByTestId("dh-count-alarm").textContent).toBe("1 alarm");
    expect(screen.getByTestId("dh-count-ok").textContent).toBe("1 ok");
    expect(screen.queryByTestId("dh-late")).toBeNull();
    expect(screen.getByTestId("dh-last-run").textContent).toContain("3.4 h ago");
  });

  it("shows the stale-run banner when the checker is late", async () => {
    vi.mocked(fetchDataHealth).mockResolvedValue(
      health({ state: "late", age_h: 41.2, last_error: "database is locked" }, [src("a.ok", "ok")]),
    );
    render(<DataHealthSection />);
    const banner = await screen.findByTestId("dh-late");
    expect(banner.textContent).toContain("over 36 hours");
    expect(banner.textContent).toContain("database is locked");
  });

  it("says so when the store was never written", async () => {
    vi.mocked(fetchDataHealth).mockResolvedValue(health({ state: "late", last_run: null, age_h: null }));
    render(<DataHealthSection />);
    expect((await screen.findByTestId("dh-late")).textContent).toContain("never finished");
  });

  it("shows an ack's reason, owner and expiry", async () => {
    vi.mocked(fetchDataHealth).mockResolvedValue(
      health({}, [src("code.municipal_text", "acked", {
        ack: { reason: "American Legal lags 120 days", until: "2026-12-15", owner: "jack" },
      })]),
    );
    render(<DataHealthSection />);
    const cell = await screen.findByTestId("dh-ack-code.municipal_text");
    expect(cell.textContent).toContain("Dec 15, 2026");
    expect(cell.textContent).toContain("American Legal lags 120 days");
    expect(cell.textContent).toContain("jack");
    expect(screen.getByTestId("dh-state-code.municipal_text").textContent).toBe("acked");
  });

  it("opens a row to its reason and 90-day strip", async () => {
    vi.mocked(fetchDataHealth).mockResolvedValue(health({}, [src("a.warn", "warn", { reason: "newest data is 70 days old" })]));
    vi.mocked(fetchDataHealthHistory).mockResolvedValue({
      source: "a.warn",
      history: [
        { checked_at: "2026-10-20T05:37:00+00:00", state: "ok", reason: "", as_of: null, age_days: 60 },
        { checked_at: "2026-10-21T05:37:00+00:00", state: "warn", reason: "old", as_of: null, age_days: 70 },
      ],
    });
    render(<DataHealthSection />);
    fireEvent.click(await screen.findByTestId("dh-row-a.warn"));
    expect(screen.getByTestId("dh-detail-a.warn").textContent).toContain("newest data is 70 days old");
    const strip = await screen.findByTestId("dh-history");
    expect(strip.querySelectorAll("span[title]").length).toBe(2);
    expect(fetchDataHealthHistory).toHaveBeenCalledWith("a.warn");
    fireEvent.click(screen.getByTestId("dh-row-a.warn"));
    expect(screen.queryByTestId("dh-detail-a.warn")).toBeNull();
  });

  it("degrades to a message when the endpoint fails", async () => {
    vi.mocked(fetchDataHealth).mockResolvedValue(null);
    render(<DataHealthSection />);
    expect((await screen.findByText(/isn't available/)).textContent).toContain("Data health");
  });
});
