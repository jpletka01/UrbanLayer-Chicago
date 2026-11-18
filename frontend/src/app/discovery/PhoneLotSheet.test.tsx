// On a phone a tapped lot opens in Discovery's own bottom sheet (decision Item 129 §1, PR 2), not in the floating card:
// the address with ×, the figures, Open profile, Street View and Google Maps at 44 px; dragging the handle down or ×
// closes it and the sheet goes back to what it was. The map is a stand-in that records its props (jsdom has no WebGL).
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { REG } from "../../discovery/_fixtures";
import type { Registry } from "../../discovery/types";
import type { DiscoveryOutlineLookup } from "../../lib/api";
import { axeViolations } from "../test/axe";
import type { Picked } from "./ExploreMap";
import DiscoveryNextPage from "./DiscoveryNextPage";

const mocks = vi.hoisted(() => ({ loadRegistry: vi.fn() }));
vi.mock("../../discovery/searchClient", () => ({
  runSearch: vi.fn(), runPins: () => Promise.resolve(null), previewText: vi.fn(), exportCsv: vi.fn(), fetchParcelRow: vi.fn(),
}));
vi.mock("../../discovery/registryClient", () => ({ loadRegistry: mocks.loadRegistry }));
vi.mock("../../lib/tracking", () => ({ track: vi.fn() }));
vi.mock("../../contexts/AuthContext", () => ({
  useAuthContext: () => ({ user: null, isAuthenticated: false, authRequired: true, loading: false, signIn: vi.fn(), signOut: vi.fn() }),
}));
vi.mock("maplibre-gl", () => ({ setWorkerUrl: () => {} }));
vi.mock("maplibre-gl/dist/maplibre-gl-worker.mjs?url", () => ({ default: "" }));
const mapProps = vi.hoisted(() => ({ last: null as null | Record<string, unknown> }));
vi.mock("./ExploreMap", async (orig) => ({
  ...(await orig<typeof import("./ExploreMap")>()),
  ExploreMap: (props: Record<string, unknown>) => {
    mapProps.last = props;
    return <div data-testid="explore-map" />;
  },
}));
vi.mock("../../lib/useIsPhone", () => ({ useIsPhone: () => true }));
vi.mock("./discoveryData", async (orig) => ({
  ...(await orig<typeof import("./discoveryData")>()),
  useDistribution: () => null,
}));
vi.mock("../frame/AppFrame", () => ({ AppFrame: ({ children, bar }: { children: React.ReactNode; bar?: React.ReactNode }) => <div className="ui-next">{bar}{children}</div> }));

const registry: Registry = { ...REG, populatedFields: ["land_use", "tif"], recipeCounts: { vacant_mf: 12 } };

const found: DiscoveryOutlineLookup = {
  status: "found",
  row: { pin: "14313250010000", lat: 41.91, lon: -87.677, address: "1601 N MILWAUKEE AVE", zone_class: "B3-2", lot_sqft: 3125,
    room_sqft: 2000 } as never,
};
const lot = (lookup: DiscoveryOutlineLookup | null): Picked =>
  ({ pin10: "1431325001", at: [180, 500], size: [360, 700], ll: [-87.677, 41.91], roads: [], lookup });

async function page() {
  mocks.loadRegistry.mockResolvedValue(registry);
  const view = render(<MemoryRouter initialEntries={["/discovery"]}><DiscoveryNextPage /></MemoryRouter>);
  await screen.findByTestId("phone-sheet");
  return view;
}

function pick(p: Picked | null) {
  const set = mapProps.last?.onPickedChange as (p: Picked | null) => void;
  act(() => set(p));
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("Discovery on a phone: the tapped lot in the sheet", () => {
  it("hands the map the lot to hold and asks for no floating card", async () => {
    await page();
    expect(mapProps.last?.inlineCard).toBe(false);
    expect(mapProps.last?.picked).toBeNull();
    expect(mapProps.last?.bottomInset).toBe(0);
  });

  it("opens the lot in the sheet in place of the peek, with the address, ×, figures and 44 px buttons", async () => {
    const { container } = await page();
    const sheet = screen.getByTestId("phone-sheet");
    expect(sheet.getAttribute("data-state")).toBe("peek");
    pick(lot(found));
    expect(sheet.getAttribute("data-state")).toBe("lot");
    expect(sheet.getAttribute("aria-label")).toBe("Lot");
    expect(screen.getByTestId("lot-sheet-title").textContent).toBe("1601 N Milwaukee Ave");
    expect(screen.queryByTestId("search-view")).toBeNull(); // the "Search these lots" peek gives way
    const body = screen.getByTestId("lot-sheet-body");
    expect(body.textContent).toContain("B3-2");
    expect(body.textContent).toContain("3,125");
    expect(body.textContent).toContain("2,000");
    for (const id of ["lot-card-open", "lot-card-street-view", "lot-card-google-maps"]) {
      expect(screen.getByTestId(id).className).toContain("h-11");
    }
    expect(screen.queryByTestId("lot-card")).toBeNull();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("shows the lookup's state in the head while the row loads", async () => {
    await page();
    pick(lot(null));
    expect(screen.getByTestId("lot-sheet-title").textContent).toContain("Loading");
    expect(screen.queryByTestId("lot-sheet-body")).toBeNull();
  });

  it("× closes it and the sheet goes back to what it was", async () => {
    await page();
    const sheet = screen.getByTestId("phone-sheet");
    fireEvent.click(screen.getByRole("button", { name: "Show more of the list" }));
    expect(sheet.getAttribute("data-state")).toBe("half");
    pick(lot(found));
    expect(sheet.getAttribute("data-state")).toBe("lot");
    fireEvent.click(screen.getByTestId("lot-sheet-close"));
    expect(mapProps.last?.picked).toBeNull();
    expect(sheet.getAttribute("data-state")).toBe("half");
  });

  it("dragging the handle down 30 px closes it; a smaller drag or a drag up doesn't", async () => {
    await page();
    pick(lot(found));
    const sheet = screen.getByTestId("phone-sheet");
    const grip = screen.getByTestId("lot-sheet-handle").parentElement!;
    fireEvent.pointerDown(grip, { clientY: 400 });
    fireEvent.pointerUp(grip, { clientY: 420 });
    expect(sheet.getAttribute("data-state")).toBe("lot");
    fireEvent.pointerDown(grip, { clientY: 400 });
    fireEvent.pointerUp(grip, { clientY: 340 });
    expect(sheet.getAttribute("data-state")).toBe("lot");
    fireEvent.pointerDown(grip, { clientY: 400 });
    fireEvent.pointerUp(grip, { clientY: 440 });
    expect(sheet.getAttribute("data-state")).toBe("peek");
    expect(mapProps.last?.picked).toBeNull();
  });

  it("tells the map how much of it the sheet covers while a lot is open", async () => {
    await page();
    const sheet = screen.getByTestId("phone-sheet");
    sheet.getBoundingClientRect = () => ({ height: 260 } as DOMRect);
    pick(lot(found));
    expect(mapProps.last?.bottomInset).toBe(260);
    fireEvent.click(screen.getByTestId("lot-sheet-close"));
    expect(mapProps.last?.bottomInset).toBe(0);
  });
});
