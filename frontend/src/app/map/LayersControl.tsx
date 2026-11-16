// The map's Layers button (owner's map review, Item 128), like Google Maps': a small square in the corner that opens a
// panel to pick the map (Standard, or Satellite: Cook County's 2025 aerial photos) and turn layers on or off (Transit,
// Zoning districts). The Cities: Skylines style stays the default; Satellite is opt-in.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Check, Layers, Map as MapIcon, Satellite, Shapes, TrainFront, X } from "lucide-react";
import { STROKE } from "../icons";

export type Basemap = "standard" | "satellite";

export interface LayersState {
  basemap: Basemap;
  transit: boolean;
  zoning: boolean;
}

export function LayersControl({ value, onChange, className, dropDown = false }: {
  value: LayersState;
  onChange: (next: LayersState) => void;
  className?: string;
  /** The panel opens below the button (a phone, where the button sits at the top); else above it. */
  dropDown?: boolean;
}) {
  const { t } = useTranslation("next");
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  // Close on a click outside or Escape.
  useEffect(() => {
    if (!open) return;
    const down = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", down);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", down); document.removeEventListener("keydown", key); };
  }, [open]);

  const tile = (on: boolean) =>
    `flex flex-col items-center gap-1 rounded-xl border-2 p-2 text-caption touch-target ${on ? "border-nx-ink" : "border-transparent hover:bg-nx-ink/5"}`;
  const PANEL = open ? (
    <div role="dialog" aria-label={t("map.layers.title")}
          className={`${dropDown ? "mt-2" : "mb-2"} w-[15rem] rounded-2xl bg-nx-page p-3 text-caption shadow-[0_8px_32px_rgb(0_0_0/0.18)]`}>
          <div className="mb-2 flex items-center justify-between">
            <p className="font-medium">{t("map.layers.title")}</p>
            <button type="button" onClick={() => setOpen(false)} aria-label={t("map.layers.close")}
              className="grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon">
              <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
            </button>
          </div>
          <p className="mb-1 nx-muted">{t("map.layers.map")}</p>
          <div className="mb-3 grid grid-cols-2 gap-2" role="radiogroup" aria-label={t("map.layers.map")}>
            {(["standard", "satellite"] as const).map((b) => (
              <button key={b} type="button" role="radio" aria-checked={value.basemap === b} data-testid={`layers-${b}`}
                onClick={() => onChange({ ...value, basemap: b })} className={tile(value.basemap === b)}>
                <span aria-hidden className={`grid h-12 w-full place-items-center rounded-lg ${b === "satellite" ? "bg-[#4B5B3A] text-white" : "bg-nx-block"}`}>
                  {b === "satellite" ? <Satellite className="h-5 w-5" strokeWidth={STROKE} /> : <MapIcon className="h-5 w-5" strokeWidth={STROKE} />}
                </span>
                {t(`map.layers.${b}`)}
              </button>
            ))}
          </div>
          <p className="mb-1 nx-muted">{t("map.layers.show")}</p>
          <div className="grid grid-cols-2 gap-2">
            {([["transit", TrainFront], ["zoning", Shapes]] as const).map(([k, Icon]) => {
              const on = value[k];
              return (
                <button key={k} type="button" aria-pressed={on} data-testid={`layers-${k}`}
                  onClick={() => onChange({ ...value, [k]: !on })} className={tile(on)}>
                  <span aria-hidden className="relative grid h-12 w-full place-items-center rounded-lg bg-nx-block">
                    <Icon className="h-5 w-5" strokeWidth={STROKE} />
                    {on && <Check className="absolute right-1 top-1 h-3.5 w-3.5" strokeWidth={STROKE} />}
                  </span>
                  {t(`map.layers.${k}`)}
                </button>
              );
            })}
          </div>
          {value.basemap === "satellite" && <p className="mt-2 nx-muted">{t("map.layers.satelliteNote")}</p>}
        </div>
  ) : null;
  return (
    <div ref={box} className={`pointer-events-auto ${className ?? ""}`} data-testid="layers-control">
      {dropDown ? null : PANEL}
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label={t("map.layers.title")}
        data-testid="layers-button"
        className="flex h-14 w-14 flex-col items-center justify-center gap-0.5 rounded-xl border-2 border-nx-page bg-nx-page text-[11px] font-medium shadow-[0_4px_16px_rgb(0_0_0/0.18)] touch-target">
        <Layers aria-hidden className="h-5 w-5" strokeWidth={STROKE} />
        {t("map.layers.button")}
      </button>
      {dropDown ? PANEL : null}
    </div>
  );
}
