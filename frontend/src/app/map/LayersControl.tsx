// The map's Layers control (owner's map reviews, Item 128), the way Google Maps does it: a square in the corner that
// previews the OTHER map (a satellite photo while the standard map shows, our map while the photo shows) and switches to
// it on a click; hovering it (a tap on a touch screen) opens a row beside it with the layers: Transit, Zoning districts,
// Saved lots. No close button: the row folds when the pointer leaves or the map is touched. The data credits sit behind
// a small info icon at the row's end (hover or click), so the row is only as wide as its tiles (owner's review
// 2026-11-16). A layer with nothing to draw at this zoom, or nothing saved, says so under its name (Item 136: a click
// that changed nothing on the map read as broken).
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Bookmark, ImageOff, Info } from "lucide-react";
import { STROKE } from "../icons";
import { CTA_COLORS, PALETTES, ZONING_COLORS, type Theme } from "./mapStyle";

export type Basemap = "standard" | "satellite";

export type LayerToggle = "transit" | "zoning" | "saved";

export interface LayersState {
  basemap: Basemap;
  transit: boolean;
  zoning: boolean;
  saved: boolean;
}

/** A fixed corner of Wicker Park in Cook County's 2025 photos, as the Satellite preview (asked from the County's image
    server like the map's own photo tiles; CSP allows it). */
export const SATELLITE_PREVIEW = "https://gis.cookcountyil.gov/imagery/rest/services/CookOrtho2025/ImageServer/exportImage"
  + "?bbox=-9760365,5147133,-9760065,5147433&bboxSR=3857&imageSR=3857&size=128,128&format=jpg&f=image";

/** Our map in miniature: land, a street grid as gaps, a park, water and a few lot colors in the theme's own palette. */
function MapPreview({ theme }: { theme: Theme }) {
  const p = PALETTES[theme];
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden>
      <rect width="64" height="64" fill={p.land} />
      <rect x="44" y="0" width="20" height="64" fill={p.water} />
      <rect x="4" y="36" width="16" height="12" fill={p.park} />
      {[[4, 4, "#A9D2CE"], [24, 4, "#72B0AB"], [4, 20, "#DCEDEB"], [24, 20, "#4A867E"], [24, 36, "#A9D2CE"]].map(([x, y, c]) => (
        <rect key={`${x}-${y}`} x={x as number} y={y as number} width="16" height="12" fill={c as string} opacity="0.85" />
      ))}
      {[0, 16, 32, 48].map((y) => <rect key={`h${y}`} x="0" y={y} width="44" height="4" fill={p.minor} />)}
      {[0, 20, 40].map((x) => <rect key={`v${x}`} x={x} y="0" width="4" height="64" fill={p.minor} />)}
      <rect x="20" y="0" width="4" height="64" fill={p.major} />
    </svg>
  );
}

function TransitPreview() {
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden>
      <rect width="64" height="64" fill="#EEF0F3" />
      <path d="M0 22 H64" stroke="#FFFFFF" strokeWidth="9" />
      <path d="M0 22 H64" stroke={CTA_COLORS.BR} strokeWidth="5" />
      <path d="M0 40 H64" stroke="#FFFFFF" strokeWidth="9" />
      <path d="M0 40 H64" stroke={CTA_COLORS.RD} strokeWidth="5" />
      <path d="M38 0 V64" stroke="#FFFFFF" strokeWidth="9" />
      <path d="M38 0 V64" stroke="#005DAA" strokeWidth="5" />
      <rect x="24" y="24" width="16" height="16" rx="4" fill="#FFFFFF" stroke="#1C1C1C" strokeWidth="1.5" />
      <text x="32" y="36.5" textAnchor="middle" fontSize="11" fontWeight="700" fill="#1C1C1C" fontFamily="sans-serif">M</text>
    </svg>
  );
}

function ZoningPreview() {
  const c = [ZONING_COLORS.residential[1], ZONING_COLORS.business[1], ZONING_COLORS.manufacturing[0], ZONING_COLORS.downtown[1]];
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full" aria-hidden>
      <rect x="0" y="0" width="34" height="30" fill={c[0]} />
      <rect x="34" y="0" width="30" height="30" fill={c[1]} />
      <rect x="0" y="30" width="22" height="34" fill={c[2]} />
      <rect x="22" y="30" width="42" height="34" fill={c[3]} />
      <path d="M34 0 V30 M0 30 H64 M22 30 V64" stroke="#FFFFFF" strokeWidth="1.5" />
    </svg>
  );
}

/** The Satellite preview, or a plain tile with a crossed-out picture when Cook County's image server doesn't answer. */
function SatellitePreview({ lazy = false }: { lazy?: boolean }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span className="grid h-full w-full place-items-center bg-nx-block nx-muted" data-testid="satellite-preview-failed">
        <ImageOff aria-hidden className="h-6 w-6" strokeWidth={STROKE} />
      </span>
    );
  }
  return <img src={SATELLITE_PREVIEW} alt="" className="h-full w-full object-cover" loading={lazy ? "lazy" : undefined} onError={() => setFailed(true)} />;
}

export function LayersControl({ value, onChange, theme, className, foldSignal = 0, hints, stacked = false }: {
  value: LayersState;
  onChange: (next: LayersState) => void;
  theme: Theme;
  className?: string;
  /** Changes when the map is touched: the open row folds. */
  foldSignal?: number;
  /** A short note under a layer's name when turning it on would show nothing right now ("Zoom in to see"). */
  hints?: Partial<Record<LayerToggle, string>>;
  /** The row opens under the corner square, not beside it: on a phone, beside it ran ~25 px off a 375 px screen. */
  stacked?: boolean;
}) {
  const { t } = useTranslation("next");
  const [open, setOpen] = useState(false);
  const [credits, setCredits] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const touch = typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(hover: none)").matches;
  useEffect(() => { setOpen(false); }, [foldSignal]);
  useEffect(() => { if (!open) setCredits(false); }, [open]);
  useEffect(() => {
    if (!open) return;
    const down = (e: PointerEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", down);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("pointerdown", down); document.removeEventListener("keydown", key); };
  }, [open]);

  const other: Basemap = value.basemap === "standard" ? "satellite" : "standard";
  const tileBox = "relative h-14 w-14 overflow-hidden rounded-lg";
  const label = "text-[11px] font-medium leading-tight";
  const toggle = (k: LayerToggle, preview: ReactNode) => {
    const on = value[k];
    const hint = hints?.[k];
    return (
      <button key={k} type="button" aria-pressed={on} data-testid={`layers-${k}`} onClick={() => onChange({ ...value, [k]: !on })}
        className="flex w-16 flex-col items-center gap-1 rounded-xl p-1 hover:bg-nx-ink/5 touch-target">
        <span className={`${tileBox} ring-2 ${on ? "ring-nx-ink" : "ring-transparent"}`}>{preview}</span>
        <span className={`${label} ${on ? "" : "nx-muted"}`}>{t(`map.layers.${k}`)}</span>
        {hint && <span className="text-center text-[10px] leading-tight nx-muted" data-testid={`layers-${k}-hint`}>{hint}</span>}
      </button>
    );
  };
  return (
    <div ref={box} className={`pointer-events-auto flex gap-2 ${stacked ? "flex-col items-start" : "items-end"} ${className ?? ""}`} data-testid="layers-control"
      onMouseEnter={touch ? undefined : () => setOpen(true)} onMouseLeave={touch ? undefined : () => setOpen(false)}>
      {/* The corner square: the other map's preview; a click switches to it (a touch screen's first tap opens the row). */}
      <button type="button" data-testid="layers-button" aria-expanded={open}
        aria-label={t("map.layers.switchTo", { map: t(`map.layers.${other}`) })}
        onClick={() => (touch && !open ? setOpen(true) : onChange({ ...value, basemap: other }))}
        className="relative h-16 w-16 overflow-hidden rounded-xl border-2 border-white shadow-[0_4px_16px_rgb(0_0_0/0.25)] touch-target">
        {other === "satellite" ? <SatellitePreview lazy /> : <MapPreview theme={theme} />}
        <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent pb-0.5 pt-3 text-center text-[11px] font-semibold text-white">
          {t(`map.layers.${other}`)}
        </span>
      </button>
      {open && (
        <div role="group" aria-label={t("map.layers.title")}
          className="relative rounded-2xl bg-nx-page p-2 shadow-[0_8px_32px_rgb(0_0_0/0.18)]" data-testid="layers-row">
          <div className="flex gap-1">
            {touch && (
              <button type="button" onClick={() => onChange({ ...value, basemap: other })} data-testid={`layers-${other}`}
                className="flex w-16 flex-col items-center gap-1 rounded-xl p-1 hover:bg-nx-ink/5 touch-target">
                <span className={tileBox}>
                  {other === "satellite" ? <SatellitePreview /> : <MapPreview theme={theme} />}
                </span>
                <span className={label}>{t(`map.layers.${other}`)}</span>
              </button>
            )}
            {toggle("transit", <TransitPreview />)}
            {toggle("zoning", <ZoningPreview />)}
            {toggle("saved", (
              <span className="grid h-full w-full place-items-center bg-nx-block">
                <Bookmark aria-hidden className="h-6 w-6 text-[#7C5CC4]" fill="#B9A6E8" strokeWidth={STROKE} />
              </span>
            ))}
            <button type="button" data-testid="layers-credits" aria-expanded={credits} aria-label={t("map.layers.creditsLabel")}
              onClick={() => setCredits((c) => !c)}
              onMouseEnter={touch ? undefined : () => setCredits(true)} onMouseLeave={touch ? undefined : () => setCredits(false)}
              className="grid h-7 w-7 shrink-0 self-start place-items-center rounded-full nx-muted hover:bg-nx-ink/5 hover:text-nx-ink touch-target">
              <Info aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
            </button>
          </div>
          {credits && (
            <p role="note" data-testid="layers-credits-text"
              className="absolute bottom-full right-0 mb-2 w-64 rounded-xl bg-nx-page p-2 text-[11px] leading-snug shadow-[0_8px_32px_rgb(0_0_0/0.18)] nx-muted">
              {value.basemap === "satellite" ? t("map.layers.creditsSatellite") : t("map.layers.credits")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
