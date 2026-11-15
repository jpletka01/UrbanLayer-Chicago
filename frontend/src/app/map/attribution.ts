// The map's data credit ("City of Chicago, Cook County") as a folded "i" button from the start (owner's review,
// 2026-11-12: the open label took a lot of room on a phone). MapLibre's compact attribution opens on load and folds at
// the first drag; this folds it at load. A tap still opens it, so the sources stay credited.
export function foldAttribution(container: HTMLElement): void {
  container.querySelector(".maplibregl-ctrl-attrib.maplibregl-compact")?.classList.remove("maplibregl-compact-show");
}
