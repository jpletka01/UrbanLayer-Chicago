// The map's self-building key (map track M1): one row per layer that has something to show, its count on screen,
// and On / Off. Zoning explains its colors by family (business, residential, ...) for the families in view, darker
// meaning more intensive (owner's review, Item 95). Collapsed to one button on phones
// and on short maps (and by choice anywhere); the top-right corner is the key's (Item 79).
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, Layers } from "lucide-react";
import { ZONING_COLORS, ZONING_FAMILIES, type GroupId, type LayerMode } from "./mapStyle";
import { PIN_COLORS } from "./pins";
import type { LateState } from "./NextMap";

export interface GroupState {
  id: GroupId;
  mode: LayerMode;
  count?: number;
  /** For points: how many exist in all (the count is those on screen). */
  total?: number;
  late?: LateState;
}

const MODES: LayerMode[] = ["on", "off"];

function swatch(id: GroupId): string {
  return {
    zoning: "#CDB7F6", parcels: "transparent", sales: PIN_COLORS.sale, transit: PIN_COLORS.transit, streets: "#F6CF9E",
  }[id];
}

export function MapKey({ groups, families, onMode, onRetry, onShow, defaultOpen, maxHeight }: {
  /** The map's height less the key button: the open key scrolls inside it instead of running off the map. */
  maxHeight?: number;
  /** Open at first only on a map tall enough to hold it beside the lot (the Profile's band is not). */
  defaultOpen: boolean;
  groups: GroupState[];
  /** The zoning families on screen. */
  families: string[];
  onMode: (g: GroupId, m: LayerMode) => void;
  onRetry?: () => void;
  /** Fit the map to the lot and this group's points (when some are off screen). */
  onShow?: (g: GroupId) => void;
}) {
  const { t } = useTranslation("next");
  const [open, setOpen] = useState(defaultOpen);
  if (!groups.length) return null;
  return (
    <div className="absolute right-2 top-2 z-10 max-w-[calc(100%-1rem)] text-caption" data-testid="map-key">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="ml-auto flex items-center gap-1.5 rounded-lg bg-nx-page px-2.5 py-1.5 font-semibold shadow-[0_1px_2px_rgb(0_0_0/0.15)] touch-target"
      >
        <Layers aria-hidden className="h-3.5 w-3.5" strokeWidth={1.5} />
        {t("map.key")}
        <ChevronDown aria-hidden className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} strokeWidth={1.5} />
      </button>
      {open && (
        <ul className="mt-1.5 flex w-72 max-w-full flex-col gap-2 overflow-y-auto overscroll-contain rounded-xl bg-nx-page p-3 shadow-[0_1px_4px_rgb(0_0_0/0.15)]" style={maxHeight ? { maxHeight } : undefined}>
          {groups.map((g) => (
            <li key={g.id} className="flex flex-col gap-1" data-testid={`key-${g.id}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-1.5">
                  <span aria-hidden className="h-2.5 w-2.5 shrink-0 rounded-sm border border-nx-ink/30" style={{ background: swatch(g.id) }} />
                  <span className="truncate font-semibold">{t(`map.groups.${g.id}`)}</span>
                  {g.late === "loading" ? (
                    <span className="nx-muted">{t("map.loadingShort")}</span>
                  ) : g.late === "timedOut" || g.late === "failed" ? (
                    <span className="nx-muted">
                      {t("map.notChecked")}
                      {onRetry && <button type="button" onClick={onRetry} className="ml-1 underline underline-offset-2">{t("map.retry")}</button>}
                    </span>
                  ) : g.total != null && g.count != null && g.count < g.total ? (
                    // Some points are off screen (owner's review: the sales sat half a mile away, out of view).
                    <span className="nx-muted tabular-nums">
                      {t("map.inView", { count: g.count, total: g.total })}
                      {onShow && g.mode !== "off" && (
                        <button type="button" onClick={() => onShow(g.id)} className="ml-1 underline underline-offset-2" data-testid={`key-show-${g.id}`}>{t("map.show")}</button>
                      )}
                    </span>
                  ) : g.count != null && g.id !== "streets" ? (
                    <span className="nx-muted tabular-nums">{t(`map.count.${g.id}`, { count: g.count })}</span>
                  ) : null}
                </span>
                <span role="radiogroup" aria-label={t("map.modeLabel", { layer: t(`map.groups.${g.id}`) })} className="flex shrink-0 overflow-hidden rounded-md border border-nx-ink/15">
                  {MODES.map((m) => (
                    <button
                      key={m}
                      type="button"
                      role="radio"
                      aria-checked={g.mode === m}
                      onClick={() => onMode(g.id, m)}
                      className={`px-1.5 py-0.5 ${g.mode === m ? "bg-nx-ink text-nx-on-ink" : "hover:bg-nx-block"}`}
                    >
                      {t(`map.mode.${m}`)}
                    </button>
                  ))}
                </span>
              </div>
              {g.id === "zoning" && g.mode !== "off" && families.length > 0 && (
                <div className="flex flex-col gap-1 pl-4">
                  <ul className="flex flex-col gap-0.5" aria-label={t("map.familiesInView")} data-testid="key-families">
                    {ZONING_FAMILIES.filter((f) => families.includes(f)).map((f) => (
                      <li key={f} className="flex items-center gap-1.5">
                        {/* Two steps of the family's ramp: lighter and darker. */}
                        <span aria-hidden className="flex overflow-hidden rounded-sm">
                          <span className="h-2.5 w-2" style={{ background: ZONING_COLORS[f][0] }} />
                          <span className="h-2.5 w-2" style={{ background: ZONING_COLORS[f][2] }} />
                        </span>
                        {t(`map.families.${f}`)}
                      </li>
                    ))}
                  </ul>
                  <p className="nx-muted">{t("map.familiesNote")}</p>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
