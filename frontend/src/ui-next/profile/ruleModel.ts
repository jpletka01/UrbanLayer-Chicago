// A Build rule's page in the right panel (decision Item 99, the owner's review: Build's rule chips should open a page
// like Money's incentive chips). What the rule means for THIS lot, from the Profile: the City's overlay records
// (each with the backend's code-pinned `detail` sentence and source link), FEMA's zone, the transit-served and ADU
// notes the backend computes, and affordable-housing projects in the area. Pure; words in the `next` catalog.
import type { ScorecardResponse } from "../../lib/api";
import type { OverlayDistrict } from "../../lib/types";
import type { RuleAnswer, RuleChip } from "./profileModel";

export type RuleKey = Exclude<RuleChip["key"], "tif">;

/** The overlay layers behind each chip (backend `retrieval/regulatory` layer types). */
export const RULE_LAYERS: Record<RuleKey, string[]> = {
  landmark: ["landmark_district", "landmark_building"],
  historic: ["historic_district", "national_register"],
  pd: ["planned_development"],
  flood: [],
  lakefront: ["lakefront_protection"],
  tod: ["tod_cta", "tod_metra"],
  adu: ["adu_area"],
  aro: ["aro_zone"],
};

export interface RuleDetail {
  key: RuleKey;
  answer: RuleAnswer;
  /** The rule changes what the build answer says (verdict friction). */
  blocks: boolean;
  /** The City's records that put this lot under the rule. */
  records: OverlayDistrict[];
  /** The backend's own sentence for this lot, when it computes one (transit-served, ADU). */
  backendNote: string | null;
  flood: { zone: string; subtype: string | null; special: boolean | null } | null;
  /** Affordable projects in the community area (ARO). */
  aroNearby: { projects: number; units: number } | null;
}

export function ruleDetail(data: ScorecardResponse, rule: Pick<RuleChip, "key" | "answer" | "blocks"> & { key: RuleKey }): RuleDetail {
  const ctx = data.context;
  const reg = ctx?.regulatory ?? null;
  const layers = RULE_LAYERS[rule.key];
  // The City's Historic Districts layer also holds Chicago Landmark districts (LANDMARK=Y); the backend marks those
  // with its "Chicago Landmark district: …" sentence (overlay_facts.py), the only sign of the flag in the response.
  const isLandmarkDistrict = (o: OverlayDistrict) => o.layer_type === "historic_district" && /^Chicago Landmark district/.test(o.detail ?? "");
  const records = (reg?.overlays ?? []).filter((o) => layers.includes(o.layer_type) || (rule.key === "landmark" && isLandmarkDistrict(o)));
  let backendNote: string | null = null;
  if (rule.key === "tod") backendNote = ctx?.tod_benefits?.note ?? null;
  if (rule.key === "adu") backendNote = ctx?.adu?.note ?? null;
  const flood = rule.key === "flood" && reg?.flood_zone
    ? { zone: reg.flood_zone, subtype: reg.flood_zone_subtype ?? null, special: reg.in_special_flood_hazard ?? null }
    : null;
  const aro = rule.key === "aro" ? reg?.aro_housing ?? null : null;
  return {
    key: rule.key,
    answer: rule.answer,
    blocks: rule.blocks,
    records,
    backendNote,
    flood,
    aroNearby: aro && aro.total_projects ? { projects: aro.total_projects, units: aro.total_units } : null,
  };
}
