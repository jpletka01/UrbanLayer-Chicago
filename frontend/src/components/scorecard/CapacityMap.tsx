// CapacityMap — the Profile's fourth module map: "How much of what's allowed is built" (WS8 Phase 1, decision
// Item 41). Each parcel within the radius is colored by built floor area ÷ (lot area × allowed FAR) only when the
// backend could compute it; every other parcel is drawn neutral and named in the key. The panel says how much of
// the view could be colored, and when that is too little it says why instead of drawing bins.
//
// Data: `/api/capacity-map` (backend/capacity_map.py), fetched once when the block scrolls near the viewport.
// Colors and counts come from `capacityMapModel` only.
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { GeoJsonLayer } from "@deck.gl/layers";
import { PathStyleExtension } from "@deck.gl/extensions";
import { useMapboxOverlay } from "../../lib/useMapboxOverlay";
import { useThemeContext } from "../../contexts/ThemeContext";
import { fetchCapacityMap } from "../../lib/api";
import { formatDay } from "../../lib/format";
import {
  buildCapacityMapModel,
  SUBJECT_LINE,
  type CapacityFeatureProps,
  type CapacityKeyRow,
  type CapacityMapModel,
  type CapacityMapResponse,
  type DrawnFeature,
} from "./capacityMapModel";

const DASH_EXTENSION = new PathStyleExtension({ dash: true });
const TIP_STYLE: Record<string, string> = {
  backgroundColor: "#333",
  color: "#eee",
  fontSize: "12px",
  borderRadius: "8px",
  padding: "6px 10px",
  fontFamily: "Inter, system-ui, sans-serif",
  maxWidth: "240px",
};

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]!
  ));
}

interface CapacityMapProps {
  pin?: string | null;
  lat: number;
  lon: number;
  /** Stable Property Profile identity (keys the canvas; the page also keys this component by it). */
  profileKey?: string | null;
  className?: string;
}

type Load = { status: "loading" } | { status: "ready"; data: CapacityMapResponse } | { status: "failed" };

export function CapacityMap({ pin, lat, lon, profileKey, className }: CapacityMapProps) {
  const { t, i18n } = useTranslation("pages");
  const { resolvedTheme } = useThemeContext();
  const theme = resolvedTheme === "light" ? "light" : "dark";
  const [inView, setInView] = useState(false);
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (inView) return;
    const el = sentinelRef.current;
    if (!el || typeof IntersectionObserver === "undefined") { setInView(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true); }, { rootMargin: "200px" });
    io.observe(el);
    return () => io.disconnect();
  }, [inView]);

  useEffect(() => {
    if (!inView) return;
    let cancelled = false;
    // A new parcel remounts this component (ScorecardPage keys it by profile), so the first state is "loading".
    fetchCapacityMap(pin, lat, lon).then((data) => {
      if (!cancelled) setLoad(data ? { status: "ready", data } : { status: "failed" });
    });
    return () => { cancelled = true; };
  }, [inView, pin, lat, lon]);

  const data = load.status === "ready" ? load.data : null;
  const model = useMemo(() => buildCapacityMapModel(data, theme), [data, theme]);
  const token = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;
  const pct = (x: number) => new Intl.NumberFormat(i18n.language === "es" ? "es-MX" : "en-US", { style: "percent", maximumFractionDigits: 0 }).format(x);
  const radius = data?.radius_mi ?? 0.1;

  return (
    <section ref={sentinelRef} className={`grid md:grid-cols-2 gap-x-10 gap-y-6 md:items-stretch ${className ?? ""}`} data-testid="capacity-map">
      <div className="flex flex-col gap-3">
        <h3 className="text-title text-text-primary">{t("scorecard.capacity.title")}</h3>
        <p className="text-caption text-text-secondary">{t("scorecard.capacity.method", { radius })}</p>
        <CoverageLine load={load} model={model} pct={pct} />
        {model.total > 0 && (
          <>
            <details className="md:hidden rounded-lg border border-dark-border px-3 py-2">
              <summary className="text-caption text-text-secondary cursor-pointer touch-target">{t("scorecard.capacity.keyToggle")}</summary>
              <CapacityKey model={model} />
            </details>
            <div className="hidden md:block"><CapacityKey model={model} /></div>
          </>
        )}
        {data && (
          <p className="text-micro text-text-muted" data-testid="capacity-sources">
            {t("scorecard.capacity.sources", {
              year: data.sources?.commercial_valuation?.year ?? "—",
              built: data.sources?.index?.built_at ? formatDay(data.sources.index.built_at) : "—",
            })}
          </p>
        )}
      </div>
      {token && model.total > 0 ? (
        <CapacityMapCanvas key={profileKey ?? `${lat}:${lon}`} model={model} lat={lat} lon={lon} theme={theme} />
      ) : (
        <div className="hidden md:block" />
      )}
    </section>
  );
}

function CoverageLine({ load, model, pct }: { load: Load; model: CapacityMapModel; pct: (x: number) => string }) {
  const { t } = useTranslation("pages");
  if (load.status === "loading") return <p className="text-body text-text-muted">{t("scorecard.capacity.loading")}</p>;
  if (load.status === "failed") {
    return <p role="status" className="text-body text-text-secondary">{t("scorecard.capacity.failed")}</p>;
  }
  const data = load.data;
  if (data.unchecked.length > 0 && model.total === 0) {
    const labels = data.unchecked.map((u) => t(`scorecard.capacity.unchecked.${u}`, { defaultValue: u })).join(", ");
    return <p role="status" className="text-body text-text-secondary" data-testid="capacity-unchecked">{t("scorecard.capacity.couldntCheck", { labels })}</p>;
  }
  if (model.total === 0) {
    return <p className="text-body text-text-secondary">{t("scorecard.capacity.empty")}</p>;
  }
  const counts = { colored: model.colored, total: model.total, share: pct(model.share) };
  return (
    <div className="space-y-1" data-testid="capacity-coverage">
      <p className="text-body text-text-primary">
        {model.binsDrawn
          ? t("scorecard.capacity.coverage", counts)
          : t("scorecard.capacity.coverageWithheld", { colorable: data.summary.colorable, total: model.total })}
      </p>
      <p className="text-caption text-text-secondary">{t(`scorecard.capacity.verdict.${model.verdict}`)}</p>
      {data.unchecked.length > 0 && (
        <p role="status" className="text-caption text-text-secondary">
          {t("scorecard.capacity.partlyUnchecked", {
            labels: data.unchecked.map((u) => t(`scorecard.capacity.unchecked.${u}`, { defaultValue: u })).join(", "),
          })}
        </p>
      )}
    </div>
  );
}

function KeyRow({ row, label }: { row: CapacityKeyRow; label: string }) {
  return (
    <li className="flex items-center gap-2 text-caption text-text-secondary leading-tight">
      <span
        className="w-3 h-3 rounded-[3px] shrink-0"
        style={{ background: row.swatchCSS, border: `1.5px solid ${row.outlineCSS ?? "transparent"}` }}
        aria-hidden
      />
      <span className="flex-1 min-w-0">{label}</span>
      <span className="font-mono tabular-nums text-text-muted">{row.count}</span>
    </li>
  );
}

function CapacityKey({ model }: { model: CapacityMapModel }) {
  const { t } = useTranslation("pages");
  return (
    <div className="space-y-3 pt-1" data-testid="capacity-key">
      {model.bins.length > 0 && (
        <div>
          <p className="text-micro uppercase tracking-wide text-text-muted mb-1">{t("scorecard.capacity.keyBuilt")}</p>
          <ul className="space-y-1">
            {model.bins.map((row) => <KeyRow key={row.key} row={row} label={t(`scorecard.capacity.bin.${row.key}`)} />)}
          </ul>
        </div>
      )}
      {model.uncolored.length > 0 && (
        <div>
          <p className="text-micro uppercase tracking-wide text-text-muted mb-1">{t("scorecard.capacity.keyNotColored")}</p>
          <ul className="space-y-1">
            {model.uncolored.map((row) => <KeyRow key={row.key} row={row} label={t(`scorecard.capacity.state.${row.key}`)} />)}
          </ul>
        </div>
      )}
      <p className="text-micro text-text-muted">{t("scorecard.capacity.keyNote")}</p>
    </div>
  );
}

type Painted = CapacityFeatureProps & { __paint: DrawnFeature };

/** The feature with its paint on its properties, so Deck's accessors and the tooltip read one object. */
function paintedFeature(d: DrawnFeature): GeoJSON.Feature {
  return { ...d.feature, properties: { ...d.feature.properties, __paint: d } };
}

function CapacityMapCanvas({ model, lat, lon, theme }: { model: CapacityMapModel; lat: number; lon: number; theme: "light" | "dark" }) {
  const { t } = useTranslation("pages");
  const style = theme === "light" ? "mapbox://styles/mapbox/light-v11" : "mapbox://styles/mapbox/dark-v11";
  const initialStyle = useMemo(() => style, []); // eslint-disable-line react-hooks/exhaustive-deps
  const { containerRef, mapRef, overlayRef, mapReady, contextRestored, styleRevision } = useMapboxOverlay({
    center: [lon, lat],
    zoom: 16.2,
    interactive: true,
    clickToActivate: true,
    style: initialStyle,
    pickingRadius: 14,
    getTooltip: (info) => {
      const f = (info as { object?: GeoJSON.Feature }).object;
      if (!f) return null;
      const p = f.properties as Painted;
      const d = p.__paint;
      const head = p.address ? esc(p.address) : esc(p.pin10);
      let body = esc(t(`scorecard.capacity.state.${p.state}`));
      if (d.bin && p.utilization != null && p.existing_far != null && p.allowed_far != null) {
        body = esc(t("scorecard.capacity.tip", {
          share: Math.round(p.utilization * 100), existing: p.existing_far.toFixed(2), allowed: p.allowed_far,
        }));
      }
      const zone = p.zone_class ? `<br/><span style="opacity:0.7">${esc(p.zone_class)}</span>` : "";
      const low = p.confidence === "low" ? `<br/><span style="opacity:0.6">${esc(t("scorecard.capacity.lowTip"))}</span>` : "";
      return { html: `<strong>${head}</strong><br/>${body}${zone}${low}`, style: TIP_STYLE };
    },
  });

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    map.setStyle(style);
  }, [style, mapReady, mapRef]);

  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay || !mapReady) return;
    const layers: unknown[] = [
      new GeoJsonLayer({
        id: "capacity-parcels",
        data: { type: "FeatureCollection", features: model.drawn.map(paintedFeature) } as GeoJSON.FeatureCollection,
        getFillColor: (f: GeoJSON.Feature) => (f.properties as Painted).__paint.fill,
        getLineColor: (f: GeoJSON.Feature) => (f.properties as Painted).__paint.line,
        getDashArray: (f: GeoJSON.Feature) => ((f.properties as Painted).__paint.dashed ? [4, 3] : [0, 0]),
        lineDashJustified: true,
        lineWidthMinPixels: 1,
        stroked: true,
        filled: true,
        pickable: true,
        extensions: [DASH_EXTENSION],
      }),
    ];
    if (model.subject) {
      layers.push(new GeoJsonLayer({
        id: "capacity-subject",
        data: [model.subject.feature],
        filled: false,
        stroked: true,
        getLineColor: SUBJECT_LINE,
        lineWidthMinPixels: 3,
        pickable: false,
      }));
    }
    overlay.setProps({ layers: layers as never });
  }, [model, mapReady, contextRestored, styleRevision, overlayRef]);

  return (
    <div className="relative w-full h-full min-h-[18rem] rounded-lg overflow-hidden border border-dark-border">
      <div ref={containerRef} className="absolute inset-0" />
    </div>
  );
}
