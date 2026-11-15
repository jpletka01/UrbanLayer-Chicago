// The new Profile's loading in parts (decision Item 89): the Overview first, the late parts only after it has
// painted, the highest version kept whatever order the parts land in, per-part Retry, an expired lookup asks the
// Overview again, a new lookup aborts the old one, and the status line names what waits and what ran out of time
// (English and Mexican Spanish, no axe violations).
import { useEffect } from "react";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import i18n from "../../lib/i18n";
import type { ProfileLatePart, ProfilePartResponse } from "../../lib/api";
import { profileFixture } from "../test/fixtures";
import { axeViolations } from "../test/axe";
import { PartsStatus } from "./PartsStatus";

const api = vi.hoisted(() => ({
  fetchScorecardFirst: vi.fn(),
  fetchProfileOverview: vi.fn(),
  fetchProfilePart: vi.fn(),
}));
vi.mock("../../lib/api", async (orig) => ({ ...(await orig<typeof import("../../lib/api")>()), ...api }));

const { useProfileParts } = await import("./useProfileParts");

const KEY = JSON.stringify({ address: "1601 N Milwaukee Ave" });
const PENDING: ProfileLatePart[] = ["history", "money", "activity"];

function resp(part: ProfilePartResponse["part"], version: number, over: Partial<ProfilePartResponse> = {}): ProfilePartResponse {
  return {
    part, lookup: `tok${version}`, record: "rec1", version, parts_in: ["overview"], parts_pending: [],
    timed_out: [], timed_out_by_part: {}, profile: { ...profileFixture(), address: `v${version}` }, ...over,
  };
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

let latest: ReturnType<typeof useProfileParts> | null = null;
function Harness({ k, onComplete }: { k: string | null; onComplete?: (d: unknown) => void }) {
  const parts = useProfileParts(k, { onComplete });
  useEffect(() => { latest = parts; });
  return null;
}

beforeEach(() => {
  api.fetchScorecardFirst.mockResolvedValue(null);
  api.fetchProfileOverview.mockReset();
  api.fetchProfilePart.mockReset();
});
afterEach(async () => { cleanup(); latest = null; await i18n.changeLanguage("en"); });

describe("useProfileParts", () => {
  it("draws the Overview, then asks the late parts after it painted, and keeps the highest version", async () => {
    const parts: Record<string, ReturnType<typeof deferred<ProfilePartResponse>>> = {};
    api.fetchProfileOverview.mockResolvedValue(resp("overview", 1, { parts_pending: PENDING }));
    api.fetchProfilePart.mockImplementation((name: string) => { parts[name] = deferred(); return parts[name].promise; });
    const onComplete = vi.fn();
    render(<Harness k={KEY} onComplete={onComplete} />);
    await waitFor(() => expect(latest!.status).toBe("overview"));
    expect(latest!.data!.address).toBe("v1");
    expect(latest!.parts).toEqual({ history: "waiting", money: "waiting", activity: "waiting" });
    await waitFor(() => expect(api.fetchProfilePart).toHaveBeenCalledTimes(3));
    expect(api.fetchProfilePart.mock.calls.map((c) => c[1])).toEqual(["tok1", "tok1", "tok1"]);
    // they land out of order: version 4 first, then 2 (older: its Profile is not shown), then 3
    await act(async () => parts.activity.resolve(resp("activity", 4, { timed_out: ["crime"] })));
    expect(latest!.data!.address).toBe("v4");
    await act(async () => parts.history.resolve(resp("history", 2)));
    expect(latest!.data!.address).toBe("v4");
    expect(latest!.status).toBe("overview");
    expect(onComplete).not.toHaveBeenCalled();
    await act(async () => parts.money.resolve(resp("money", 3)));
    expect(latest!.status).toBe("complete");
    expect(latest!.data!.address).toBe("v4");
    expect(latest!.timedOut).toEqual({ activity: ["crime"], history: [], money: [] });
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete.mock.calls[0][0]).toMatchObject({ address: "v4" });
  });

  it("retries one part with the parts it already has, and asks the Overview again when the lookup expired", async () => {
    api.fetchProfileOverview.mockResolvedValueOnce(resp("overview", 1, { parts_pending: ["history", "money"] }));
    api.fetchProfilePart
      .mockResolvedValueOnce(resp("history", 2))
      .mockResolvedValueOnce("failed");
    render(<Harness k={KEY} />);
    await waitFor(() => expect(latest!.status).toBe("complete"));
    expect(latest!.parts).toEqual({ history: "done", money: "failed" });
    api.fetchProfilePart.mockResolvedValueOnce(resp("money", 3));
    await act(async () => latest!.retryPart("money"));
    await waitFor(() => expect(latest!.parts.money).toBe("done"));
    expect(api.fetchProfilePart.mock.calls.at(-1)!.slice(0, 3)).toEqual(["money", "tok2", ["history"]]);
    expect(latest!.data!.address).toBe("v3");

    // an expired lookup: one fresh Overview, keeping the first screen
    api.fetchProfilePart.mockResolvedValueOnce("expired");
    api.fetchProfileOverview.mockResolvedValueOnce(resp("overview", 1, { record: "rec2", parts_pending: [] }));
    await act(async () => latest!.retryPart("history"));
    await waitFor(() => expect(api.fetchProfileOverview).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(latest!.status).toBe("complete"));
  });

  it("aborts the old lookup's requests when a new one starts, and says not found", async () => {
    const signals: AbortSignal[] = [];
    api.fetchProfileOverview.mockImplementation((_q: unknown, signal: AbortSignal) => { signals.push(signal); return new Promise(() => {}); });
    const { rerender } = render(<Harness k={KEY} />);
    await waitFor(() => expect(signals).toHaveLength(1));
    api.fetchProfileOverview.mockImplementation((_q: unknown, signal: AbortSignal) => { signals.push(signal); return Promise.resolve("notFound"); });
    rerender(<Harness k={JSON.stringify({ address: "nowhere" })} />);
    await waitFor(() => expect(latest!.status).toBe("notFound"));
    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);
  });
});

describe("PartsStatus", () => {
  it("names what is still on its way, what ran out of time and what failed, each with Retry", async () => {
    const onRetry = vi.fn();
    render(
      <PartsStatus
        parts={{ history: "waiting", money: "failed", activity: "done", neighborhood: "done" }}
        timedOut={{ activity: ["crime", "address_311"], neighborhood: [] }}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByTestId("parts-waiting").textContent).toBe("Still checking: City permits and violations, building records, City lists and appeals");
    expect(screen.getByTestId("parts-timed-out").textContent).toContain("Couldn't check in time: crime and 311 requests.");
    expect(screen.getByTestId("parts-failed").textContent).toContain("Couldn't load: nearby sales.");
    screen.getAllByRole("button", { name: "Retry" })[0].click();
    expect(onRetry).toHaveBeenCalledWith(["activity"]);
    expect(await axeViolations(document.body)).toEqual([]);
  });

  it("reads in Mexican Spanish and says nothing once everything is in", async () => {
    await i18n.changeLanguage("es");
    const { rerender } = render(<PartsStatus parts={{ history: "waiting", activity: "done" }} timedOut={{ activity: ["crime"] }} onRetry={() => {}} />);
    expect(screen.getByTestId("parts-waiting").textContent).toBe("Seguimos revisando: permisos e infracciones de la Ciudad, registros del edificio, listas de la Ciudad y apelaciones");
    expect(screen.getByTestId("parts-timed-out").textContent).toContain("No se pudo revisar a tiempo: delitos.");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeTruthy();
    rerender(<PartsStatus parts={{ history: "done", activity: "done" }} timedOut={{ activity: [] }} onRetry={() => {}} />);
    expect(screen.queryByTestId("parts-status")).toBeNull();
  });
});
