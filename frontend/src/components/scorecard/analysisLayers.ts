// Which layers the Build section's analysis map offers (decision Item 55), apart from the component so
// React Fast Refresh keeps working on AnalysisMap.tsx.
import { parcelMapHasContent, type ParcelMapLayers } from "../../lib/parcelMap";

export type AnalysisLayer = "zoning" | "overlays" | "capacity";

/** The layers this parcel can show, in the switch's order. Built vs allowed fetches its own data, so it is always offered. */
export function availableLayers(layers: ParcelMapLayers | null): AnalysisLayer[] {
  const out: AnalysisLayer[] = [];
  if (layers && parcelMapHasContent("zoning", layers)) out.push("zoning");
  if (layers && parcelMapHasContent("boundaries", layers)) out.push("overlays");
  out.push("capacity");
  return out;
}
