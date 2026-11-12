// The preview switch (decision Items 75–76): query cleanup, Back/Forward, shared links, storage failure,
// the kill switch, the Preview badge's exit, noindex, and analytics tagging.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { UiVersionProvider } from "./UiVersionProvider";
import { useUiVersion } from "./uiVersionContext";
import { PreviewBadge } from "./PreviewBadge";
import { useNoindex } from "./useNoindex";
import { navEntries, isReady } from "./readiness";
import { UI_FLAG_KEY, previewEnabled, resolveUiVersion, withoutUiParam } from "./uiVersion";

const navRef: { current: ReturnType<typeof useNavigate> | null } = { current: null };
function Probe() {
  const { version } = useUiVersion();
  const loc = useLocation();
  const navigate = useNavigate();
  useEffect(() => { navRef.current = navigate; });
  return <div data-testid="probe" data-version={version} data-search={loc.search} />;
}
function Noindex() {
  const { version } = useUiVersion();
  useNoindex(version === "next");
  return null;
}

function mount(url: string, enabled = true) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <UiVersionProvider enabled={enabled}>
        <Routes><Route path="*" element={<><Probe /><PreviewBadge /><Noindex /></>} /></Routes>
      </UiVersionProvider>
    </MemoryRouter>,
  );
}
const probe = () => screen.getByTestId("probe");

beforeEach(() => { localStorage.clear(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("resolving the version", () => {
  it("kill switch, then URL, then stored flag, then old", () => {
    expect(resolveUiVersion({ search: "?ui=next", stored: null, enabled: false })).toBe("old");
    expect(resolveUiVersion({ search: "?ui=old", stored: "next", enabled: true })).toBe("old");
    expect(resolveUiVersion({ search: "", stored: "next", enabled: true })).toBe("next");
    expect(resolveUiVersion({ search: "?ui=banana", stored: null, enabled: true })).toBe("old");
    expect(previewEnabled({ VITE_UI_PREVIEW: "off" })).toBe(false);
    expect(previewEnabled({})).toBe(true);
    expect(withoutUiParam("?pin=1&ui=next")).toBe("?pin=1");
    expect(withoutUiParam("?ui=next")).toBe("");
  });
});

describe("UiVersionProvider", () => {
  it("turns the preview on from ?ui=next, remembers it, and removes the parameter (replace)", async () => {
    mount("/scorecard?pin=14313250010000&ui=next");
    expect(probe().dataset.version).toBe("next");
    expect(probe().dataset.search).toBe("?pin=14313250010000");
    expect(localStorage.getItem(UI_FLAG_KEY)).toBe("next");
    // Back has nowhere to go: the cleanup replaced the entry instead of pushing one.
    act(() => navRef.current!(-1));
    expect(probe().dataset.search).toBe("?pin=14313250010000");
  });

  it("keeps the version across in-app navigation and Back/Forward without the parameter", () => {
    mount("/scorecard?ui=next");
    act(() => navRef.current!("/discovery"));
    expect(probe().dataset.version).toBe("next");
    act(() => navRef.current!(-1));
    expect(probe().dataset.version).toBe("next");
    act(() => navRef.current!(1));
    expect(probe().dataset.version).toBe("next");
    expect(probe().dataset.search).toBe("");
  });

  it("a shared link without the parameter opens today's UI for someone who never opted in", () => {
    mount("/scorecard?pin=14313250010000");
    expect(probe().dataset.version).toBe("old");
    expect(screen.queryByTestId("preview-badge")).toBeNull();
  });

  it("a pasted ?ui=old (or the badge's exit) turns it off and forgets the flag", () => {
    localStorage.setItem(UI_FLAG_KEY, "next");
    mount("/discovery");
    expect(probe().dataset.version).toBe("next");
    fireEvent.click(screen.getByRole("button", { name: "Exit preview" }));
    expect(probe().dataset.version).toBe("old");
    expect(localStorage.getItem(UI_FLAG_KEY)).toBeNull();
    act(() => navRef.current!("/scorecard?ui=next"));
    expect(probe().dataset.version).toBe("next");
    act(() => navRef.current!("/scorecard?ui=old"));
    expect(probe().dataset.version).toBe("old");
  });

  it("survives storage that throws: the choice holds for this session", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    mount("/scorecard?ui=next");
    expect(probe().dataset.version).toBe("next");
    act(() => navRef.current!("/discovery"));
    expect(probe().dataset.version).toBe("next");
  });

  it("with the kill switch off ignores the URL and the stored flag", () => {
    localStorage.setItem(UI_FLAG_KEY, "next");
    mount("/scorecard?ui=next", false);
    expect(probe().dataset.version).toBe("old");
    expect(screen.queryByTestId("preview-badge")).toBeNull();
  });

  it("marks preview pages noindex and removes the tag on exit", () => {
    mount("/scorecard?ui=next");
    expect(document.head.querySelector('meta[name="robots"][content="noindex"]')).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Exit preview" }));
    expect(document.head.querySelector('meta[name="robots"]')).toBeNull();
  });
});

describe("analytics tagging", () => {
  it("adds ui_version only while the preview is on", async () => {
    const real = await import("../lib/tracking");
    const beacon = vi.fn(() => true);
    Object.defineProperty(navigator, "sendBeacon", { value: beacon, configurable: true });
    real.setUiVersion("next");
    real.track("page_view", { page_name: "next_profile" });
    real.setUiVersion("old");
    real.track("page_view");
    real.flush();
    const blob = (beacon.mock.calls[0] as unknown as [string, Blob])[1];
    const text = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.readAsText(blob);
    });
    const body = JSON.parse(text);
    expect(body.events.map((e: { event_data: unknown }) => e.event_data)).toEqual([
      { page_name: "next_profile", ui_version: "next" },
      null,
    ]);
  });
});

describe("readiness registry", () => {
  it("drives the side panel: Saved stays hidden until its route exists", () => {
    expect(navEntries().map((e) => e.id)).toEqual(["home", "profile", "discovery", "chat"]);
    expect(isReady("saved")).toBe(false);
    expect(isReady("profile")).toBe(true);
    expect(isReady("chat")).toBe(true);
  });
});
