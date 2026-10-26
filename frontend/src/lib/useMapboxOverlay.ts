import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import type { LayerPickInfo, TooltipContent } from "./mapTooltip";
import {
  reviseMapStyleOrder,
  type MapStyleLayerLike,
  type MapStyleOrderRevision,
} from "./mapLayerOrder";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;

interface UseMapboxOverlayOptions {
  center: [number, number];
  zoom: number;
  getTooltip?: (info: LayerPickInfo) => TooltipContent | null;
  onClick?: (info: LayerPickInfo) => void;
  interactive?: boolean;
  /** Extra pick tolerance in px around pointer events (touch needs ~14; mouse none). */
  pickingRadius?: number;
  /** Mapbox style URL; defaults to dark-v11 (the chat map). Read once at init —
      runtime style swaps go through mapRef.current.setStyle(). */
  style?: string;
  /** Disable scroll-zoom until the map is clicked (page-scroll trap guard for
      inline page maps; the chat/Discovery maps keep default behavior). */
  clickToActivate?: boolean;
  /** Deck shares Mapbox's WebGL canvas by default. Discovery opts out because
      a map initialized under display:none can leave the shared drawing buffer
      pinned to Mapbox's 400×300 fallback after the pane is revealed. */
  interleaved?: boolean;
}

/**
 * Shared Mapbox GL + deck.gl overlay lifecycle for both map views.
 *
 * Creates the map once, attaches a deck.gl MapboxOverlay, and tears both down
 * on unmount. Tooltip/click callbacks are read through a ref so they can change
 * without re-initializing the map. Guards against double-init (React StrictMode
 * mounts effects twice in dev) and swallows the benign webglcontextlost event
 * so the context restores instead of logging an error.
 */
export function useMapboxOverlay(opts: UseMapboxOverlayOptions) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [contextRestored, setContextRestored] = useState(0);
  const [styleOrder, setStyleOrder] = useState<MapStyleOrderRevision>({
    roadInsertionId: null,
    revision: 0,
  });

  // Keep the latest callbacks without retriggering init. Updated in an effect
  // (not during render) so the tooltip/click handlers always see fresh props.
  const optsRef = useRef(opts);
  useEffect(() => {
    optsRef.current = opts;
  });

  useEffect(() => {
    if (!containerRef.current || !MAPBOX_TOKEN || mapRef.current) return;
    mapboxgl.accessToken = MAPBOX_TOKEN;

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: optsRef.current.style ?? "mapbox://styles/mapbox/dark-v11",
      center: optsRef.current.center,
      zoom: optsRef.current.zoom,
      attributionControl: false,
      interactive: optsRef.current.interactive ?? true,
      preserveDrawingBuffer: true,
    });

    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "bottom-right");

    if (optsRef.current.clickToActivate) {
      map.scrollZoom.disable();
      map.on("click", () => map.scrollZoom.enable());
      map.on("mouseout", () => map.scrollZoom.disable());
    }

    // A lost WebGL context can otherwise log as an uncaught error; preventing
    // the default lets the browser restore it (common during dev remounts).
    map.on("webglcontextlost", (e) => {
      (e as unknown as { preventDefault?: () => void }).preventDefault?.();
    });

    map.on("webglcontextrestored", () => {
      map.setStyle(map.getStyle());
      setContextRestored((c) => c + 1);
    });

    const overlay = new MapboxOverlay({
      interleaved: optsRef.current.interleaved ?? true,
      pickingRadius: optsRef.current.pickingRadius,
      getTooltip: (info: LayerPickInfo) => optsRef.current.getTooltip?.(info) ?? null,
      onClick: (info: LayerPickInfo) => optsRef.current.onClick?.(info),
    });
    map.addControl(overlay);

    mapRef.current = map;
    overlayRef.current = overlay;
    const resolveStyleOrder = () => {
      const layers = (map.getStyle()?.layers ?? []) as MapStyleLayerLike[];
      setStyleOrder((previous) => reviseMapStyleOrder(previous, layers));
    };
    const onLoad = () => {
      setMapReady(true);
      resolveStyleOrder();
    };
    // `style.load` fires again after setStyle() (including light/dark swaps),
    // so deck layers that carry beforeId are rebuilt against the new style.
    map.on("style.load", resolveStyleOrder);
    map.on("load", onLoad);

    return () => {
      map.off("style.load", resolveStyleOrder);
      map.off("load", onLoad);
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
      setMapReady(false);
    };
  }, []);

  return {
    containerRef,
    mapRef,
    overlayRef,
    mapReady,
    contextRestored,
    roadInsertionId: styleOrder.roadInsertionId,
    styleRevision: styleOrder.revision,
  };
}
