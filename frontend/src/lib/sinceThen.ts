// Words for "since then" (WS6 M9): what changed since an answer or a report was made. The backend decides what is
// a material change (`backend/data_health/diff.py`); this only says it, in the viewer's language.
import type { TFunction } from "i18next";
import { formatDay } from "./format";
import type { SinceThenChange, SinceThenResult } from "./types";

export interface ChangeLine {
  text: string;
  url?: string | null;
  /** Link label, when the change has a source record to open. */
  record?: string | null;
}

function layerName(layer: string, t: TFunction): string {
  return t(`sinceThen.layers.${layer}`, { defaultValue: layer.replace(/_/g, " ") });
}

function day(iso: string | null | undefined): string {
  return iso ? formatDay(iso) : "";
}

/** One change as a sentence. `t` is the `chat` namespace translator. */
export function describeChange(c: SinceThenChange, t: TFunction): ChangeLine {
  switch (c.kind) {
    case "district":
      return {
        text: t(c.record ? "sinceThen.district.withRecord" : "sinceThen.district.plain", {
          old: c.old, new: c.new, record: c.record, date: day(c.passed_on),
        }),
        url: c.url, record: c.record,
      };
    case "overlay":
      return {
        text: t(c.change === "added" && c.name ? "sinceThen.overlay.addedNamed" : `sinceThen.overlay.${c.change}`, {
          layer: layerName(c.layer, t), name: c.name,
        }),
      };
    case "standards":
      return {
        text: t("sinceThen.standards", {
          field: t(`sinceThen.fields.${c.field}`, { defaultValue: c.field }),
          zone: c.zone_class ?? "", old: c.old, new: c.new,
        }),
      };
    case "amendment":
      return {
        text: t(c.phase === "after_answer" ? "sinceThen.amendment.after" : "sinceThen.amendment.before", {
          record: c.record, date: day(c.passed_on), sections: c.sections.join(", "),
        }),
        url: c.url, record: c.record,
      };
    case "map_amendment":
      return { text: t("sinceThen.mapAmendment", { record: c.record, date: day(c.passed_on) }), url: c.url, record: c.record };
    case "designation":
      return { text: t("sinceThen.designation", { record: c.record, date: day(c.passed_on) }), url: c.url, record: c.record };
    case "text_refresh":
      return { text: t("sinceThen.textRefresh", { date: day(c.current_through), sections: c.sections.join(", ") }) };
    case "correction":
      return { text: c.summary };
  }
}

/** What a partial re-check could not read, as words ("the district, some map layers"). */
export function uncheckedWords(unchecked: string[], t: TFunction): string {
  const parts: string[] = [];
  if (unchecked.includes("everything")) return t("sinceThen.what.everything");
  if (unchecked.includes("district")) parts.push(t("sinceThen.what.district"));
  if (unchecked.some((u) => u.startsWith("overlay:"))) parts.push(t("sinceThen.what.overlays"));
  return parts.join(", ");
}

/** True when the result has something to say beyond the answer's date. */
export function hasSinceThenLine(r: SinceThenResult | undefined): boolean {
  return !!r && !["too_soon", "skipped", "no_parcel"].includes(r.status);
}
