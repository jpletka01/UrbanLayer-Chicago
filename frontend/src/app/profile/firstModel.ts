// The Profile's first screen (decision Item 82), from `/api/scorecard/first` while the full response loads.
// Pure, with an injected `t`. The one sentence uses the same arithmetic as the Build tab's "Allowed vs built"
// (the district's FAR × the lot area, rounded the same way), so the floor area doesn't change when the full
// response replaces this screen. The four tiles hold their places and say what each is waiting for.
import type { ScorecardFirst } from "../../lib/api";
import type { TFunc } from "../../lib/scorecardVerdict";
import { fmtFar } from "../../lib/answerSentence";
import { fmtInt, heightFeet, type Tile } from "./profileModel";
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** The first screen's one sentence: the district and what it allows on this lot. */
export function firstSentence(first: ScorecardFirst, t: TFunc, lng = "en"): string {
  if (first.zoning_unchecked) return t("profile.first.zoningUnchecked");
  const zone = first.zoning?.zone_class;
  if (!zone) return t("profile.first.noZone");
  const far = num(first.zone_definition?.far);
  const height = heightFeet(first.zone_definition?.max_height ?? null);
  const land = first.lot?.land_sqft ?? null;
  const h = height != null ? fmtInt(height, lng) : null;
  if (far != null && far > 0 && land && land > 0) {
    const vars = { zone, floor: fmtInt(far * land, lng), lot: fmtInt(land, lng) };
    return h ? t("profile.first.zonedLotHeight", { ...vars, height: h }) : t("profile.first.zonedLot", vars);
  }
  if (far != null && far > 0) {
    const vars = { zone, far: fmtFar(far) }; // as the answer sentence that replaces this one writes it
    return h ? t("profile.first.zonedFarHeight", { ...vars, height: h }) : t("profile.first.zonedFar", vars);
  }
  return t("profile.first.zoned", { zone });
}

/** The four Overview tiles in their final order, each saying what it waits for. */
export function checkingTiles(t: TFunc): Tile[] {
  const tile = (key: Tile["key"], tabOf: Tile["tabOf"]): Tile => ({
    key, tabOf, label: t(`profile.tiles.${key}`), figure: "", note: t(`profile.first.checking.${key}`), state: null, tab: null, checking: true,
  });
  return [tile("units", "build"), tile("tax", "money"), tile("walk", "neighborhood"), tile("lastSale", "history")];
}
