import { useState } from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { ParcelMapLayerState } from "../../lib/parcelMap";
import { ParcelMapControls, type ParcelMapControlSource } from "./ParcelMapControls";
import {
  buildBoundaryDeckLayers,
  buildSubjectParcelLayer,
  buildZoningDeckLayers,
  DEFAULT_PARCEL_MAP_LAYER_STATES,
} from "./parcelMapLayers";
import { buildBoundaryMapModel, buildZoningMapModel } from "./parcelMapModel";

const square = (size: number): GeoJSON.Polygon => ({
  type: "Polygon",
  coordinates: [[[0, 0], [size, 0], [size, size], [0, size], [0, 0]]],
});

afterEach(() => cleanup());

const zoningFixture: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [
    { type: "Feature", geometry: square(3), properties: { ZONE_CLASS: "B3-2", confidence: "standard" } },
    { type: "Feature", geometry: square(2), properties: { ZONE_CLASS: "B3-2", confidence: "low" } },
    { type: "Feature", geometry: square(1), properties: { ZONE_CLASS: "B3-3", confidence: "withheld" } },
  ],
};

type DeckLayer = {
  id: string;
  props: Record<string, unknown>;
};

function layer(layers: unknown[], id: string): DeckLayer {
  const found = layers.find((entry) => (entry as DeckLayer).id === id) as DeckLayer | undefined;
  expect(found, `missing Deck layer ${id}`).toBeDefined();
  return found!;
}

function ControlHarness({ initial = "on" }: { initial?: ParcelMapLayerState }) {
  const [state, setState] = useState(initial);
  const sources: ParcelMapControlSource[] = [{
    source: "zoning",
    label: "Zoning",
    availability: "available",
    state,
    visibleCount: 2,
    withheldCount: 1,
    rows: [{
      key: "B3-2",
      label: "B3-2",
      swatchCSS: "rgb(1,2,3)",
      count: 2,
      lowConfidenceCount: 1,
      countKind: "district",
    }],
  }];
  return <ParcelMapControls sources={sources} onChange={(_source, next) => setState(next)} />;
}

describe("ParcelMap layer controls", () => {
  it("uses radio semantics, supports arrow keys, and exposes a visible focus treatment", () => {
    render(<ControlHarness />);
    const group = screen.getByRole("radiogroup", { name: "Zoning visibility" });
    const on = within(group).getByRole("radio", { name: "On" });
    const dim = within(group).getByRole("radio", { name: "Dim" });

    expect(on.getAttribute("aria-checked")).toBe("true");
    on.focus();
    fireEvent.keyDown(on, { key: "ArrowRight" });
    expect(dim.getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(dim);
    expect(dim.className).toContain("focus-visible:ring-2");

    fireEvent.keyDown(dim, { key: "End" });
    expect(within(group).getByRole("radio", { name: "Off" }).getAttribute("aria-checked")).toBe("true");
  });

  it("uses a desktop card and a bounded mobile Layers popover without truncating long names", () => {
    const longName = "Milwaukee Avenue Special Character Overlay District with an intentionally long official boundary name";
    const sources: ParcelMapControlSource[] = [{
      source: "overlays",
      label: "Special-purpose boundaries",
      availability: "available",
      state: "on",
      visibleCount: 1,
      withheldCount: 0,
      rows: [{ key: "long", label: longName, swatchCSS: "#123456", count: 1, lowConfidenceCount: 0, countKind: "feature" }],
    }];
    render(<ParcelMapControls sources={sources} onChange={() => {}} />);

    const desktop = screen.getByTestId("parcel-map-controls-desktop");
    expect(desktop.className).toContain("right-2");
    expect(desktop.className).toContain("top-2");
    expect(desktop.className).toContain("hidden");
    expect(desktop.className).toContain("md:block");

    const button = screen.getByTestId("parcel-map-layers-button");
    expect(button.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(button);
    const mobile = screen.getByTestId("parcel-map-controls-mobile");
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(mobile.className).toContain("max-w-[18rem]");
    expect(mobile.className).toContain("top-11");
    const longLabel = within(mobile).getByText(longName);
    expect(longLabel.className).toContain("break-words");
    expect(longLabel.className).not.toContain("truncate");
  });

  it("links each map's Layers button to a unique popover", () => {
    render(
      <>
        <ControlHarness />
        <ControlHarness />
      </>,
    );
    const buttons = screen.getAllByTestId("parcel-map-layers-button");
    buttons.forEach((button) => fireEvent.click(button));
    const dialogs = screen.getAllByRole("dialog", { name: "Layers" });
    const controlledIds = buttons.map((button) => button.getAttribute("aria-controls"));

    expect(new Set(controlledIds).size).toBe(2);
    expect(dialogs.map((dialog) => dialog.id)).toEqual(controlledIds);
  });

  it("reports exact counts, withheld features, empty sources, and unavailable sources truthfully", () => {
    const sources: ParcelMapControlSource[] = [
      {
        source: "overlays", label: "Special-purpose boundaries", availability: "available", state: "on",
        visibleCount: 2, withheldCount: 1,
        rows: [{ key: "x", label: "Landmark District — Milwaukee Avenue", swatchCSS: "#123", count: 2, lowConfidenceCount: 0, countKind: "feature" }],
      },
      { source: "tif", label: "TIF districts", availability: "available", state: "on", visibleCount: 0, withheldCount: 0, rows: [] },
      { source: "ez", label: "Enterprise Zones", availability: "unavailable", state: "on", visibleCount: 0, withheldCount: 0, rows: [] },
    ];
    render(<ParcelMapControls sources={sources} onChange={() => {}} />);
    const desktop = screen.getByTestId("parcel-map-controls-desktop");

    expect(within(desktop).getByText("2 features")).toBeTruthy();
    expect(within(desktop).getByText("1 feature not shown")).toBeTruthy();
    expect(within(desktop).getByText("No features at this parcel.")).toBeTruthy();
    expect(within(desktop).getByText("Unavailable")).toBeTruthy();
    const disabled = within(within(desktop).getByTestId("parcel-map-source-ez"))
      .getAllByRole("radio");
    expect(disabled.every((radio) => (radio as HTMLButtonElement).disabled)).toBe(true);
  });
});

describe("ParcelMap confidence and layer presence", () => {
  it("keeps Dim pickable at 0.30 opacity, hides Off labels/layers, and excludes withheld zoning", () => {
    const model = buildZoningMapModel(zoningFixture, [
      { zone_class: "B3-2", position: [-87.677, 41.91] },
      { zone_class: "B3-3", position: [-87.675, 41.912] },
    ], "dark");
    const dim = buildZoningDeckLayers({
      model,
      state: "dim",
      mapTheme: "dark",
      mapZoom: 15.2,
      roadInsertionId: "road-primary",
    });

    expect(dim.map((entry) => (entry as DeckLayer).id)).toEqual(["zoning", "pm-zoning-outline", "pm-zone-labels"]);
    const fill = layer(dim, "zoning");
    const outline = layer(dim, "pm-zoning-outline");
    expect(fill.props.opacity).toBe(0.3);
    expect(fill.props.pickable).toBe(true);
    expect((fill.props.data as GeoJSON.FeatureCollection).features).toHaveLength(2);
    expect((fill.props.data as GeoJSON.FeatureCollection).features.every((feature) => feature.properties?.confidence !== "withheld")).toBe(true);

    const getFillColor = fill.props.getFillColor as (feature: GeoJSON.Feature) => number[];
    expect(getFillColor(model.featureCollection.features[0])[3]).toBe(78);
    expect(getFillColor(model.featureCollection.features[1])[3]).toBe(39);
    const getDashArray = outline.props.getDashArray as (feature: GeoJSON.Feature) => number[];
    expect(getDashArray(model.featureCollection.features[0])).toEqual([0, 0]);
    expect(getDashArray(model.featureCollection.features[1])).toEqual([4, 3]);

    expect(buildZoningDeckLayers({
      model, state: "off", mapTheme: "dark", mapZoom: 15.2, roadInsertionId: "road-primary",
    })).toEqual([]);
  });

  it("applies logical-source states to boundaries while withheld features never render or pick", () => {
    const model = buildBoundaryMapModel({
      overlays: {
        type: "FeatureCollection",
        features: [{ type: "Feature", geometry: square(1), properties: { overlay_type: "landmark_district", NAME: "Milwaukee", confidence: "low" } }],
      },
      tif: { type: "Feature", geometry: square(3), properties: { name: "Kinzie" } },
      ez: { type: "Feature", geometry: square(2), properties: { name: "Hidden EZ", confidence: "withheld" } },
    }, "dark");
    const layers = buildBoundaryDeckLayers({
      model,
      states: { ...DEFAULT_PARCEL_MAP_LAYER_STATES, overlays: "dim", tif: "off" },
    });

    expect(layers.map((entry) => (entry as DeckLayer).id)).toEqual(["overlay-districts-0"]);
    const overlay = layer(layers, "overlay-districts-0");
    expect(overlay.props.opacity).toBe(0.3);
    expect(overlay.props.pickable).toBe(true);
    expect(overlay.props.getDashArray).toEqual([4, 3]);
    expect((overlay.props.getFillColor as number[])[3]).toBe(3);
    expect(model.counts.ez).toEqual({ visible: 0, withheld: 1 });
  });

  it("keeps the subject parcel above thematic Off states and styles approximate identity as low confidence", () => {
    const subject = buildSubjectParcelLayer({
      parcelGeometry: square(1),
      lat: 41.91,
      lon: -87.677,
      satellite: false,
      variant: "zoning",
      confidence: "approximate",
    }) as DeckLayer;
    const thematic = buildZoningDeckLayers({
      model: buildZoningMapModel(zoningFixture, [], "dark"),
      state: "off",
      mapTheme: "dark",
      mapZoom: 15.2,
      roadInsertionId: null,
    });

    expect(thematic).toEqual([]);
    expect(subject.id).toBe("pm-parcel");
    expect(subject.props.pickable).toBe(false);
    expect(subject.props.getDashArray).toEqual([4, 3]);
    expect((subject.props.getFillColor as number[])[3]).toBe(13);
  });

  it("styles an approximate subject pin with half-alpha fill and a dashed outline", () => {
    const subject = buildSubjectParcelLayer({
      parcelGeometry: null,
      lat: 41.91,
      lon: -87.677,
      satellite: false,
      variant: "zoning",
      confidence: "approximate",
    }) as DeckLayer;
    const getIcon = subject.props.getIcon as () => { url: string };
    const icon = getIcon();
    const svg = decodeURIComponent(icon.url.split(",", 2)[1]);

    expect(subject.id).toBe("pm-pin");
    expect(subject.props.pickable).toBe(false);
    expect(svg).toContain('fill-opacity=".5"');
    expect(svg).toContain('stroke-dasharray="4 3"');
  });
});
