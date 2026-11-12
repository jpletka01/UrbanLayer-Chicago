import { describe, expect, it } from "vitest";
import { foldAttribution } from "./attribution";

describe("the map's data credit", () => {
  it("starts folded to its button, and leaves a non-compact credit alone", () => {
    const root = document.createElement("div");
    root.innerHTML = `<div class="maplibregl-ctrl-attrib maplibregl-compact maplibregl-compact-show"></div>`;
    foldAttribution(root);
    expect(root.firstElementChild!.classList.contains("maplibregl-compact-show")).toBe(false);
    expect(root.firstElementChild!.classList.contains("maplibregl-compact")).toBe(true);
  });
});
