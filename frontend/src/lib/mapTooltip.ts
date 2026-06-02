import type { TransitStation } from "./types";
import { formatDate } from "./format";
import { overlayLabel, incentiveLabel } from "./mapColors";

/** Minimal shape of a deck.gl picking info we read in tooltips/click handlers. */
export interface LayerPickInfo {
  object?: unknown;
  layer: { id: string } | null;
  x: number;
  y: number;
}

export interface TooltipContent {
  html: string;
  style: Record<string, string>;
}

const TOOLTIP_STYLE: Record<string, string> = {
  backgroundColor: "#333",
  color: "#eee",
  fontSize: "12px",
  borderRadius: "8px",
  padding: "8px 12px",
  fontFamily: "Inter, system-ui, sans-serif",
  maxWidth: "240px",
};

/**
 * Build the HTML tooltip for any map layer. Shared by the landing map and the
 * sidebar map — handles every layer id either renders (crime/311/permit point
 * layers, plus zoning and transit which only the sidebar map shows).
 */
export function buildLayerTooltip(info: LayerPickInfo): TooltipContent | null {
  if (!info.object) return null;
  const o = info.object as Record<string, unknown>;
  const lid = info.layer?.id ?? "";
  let html: string;

  if (lid === "crimes" || lid.startsWith("crime-")) {
    html = `<strong>${o.primary_type}</strong><br/>${formatDate(o.date as string)}`;
  } else if (lid === "requests-311" || lid.startsWith("dept-")) {
    html = `<strong>${o.sr_type}</strong><br/>${formatDate(o.created_date as string)}`;
  } else if (lid === "permits") {
    html = `<strong>${o.permit_type}</strong><br/>${formatDate(o.issue_date as string)}`;
  } else if (lid === "zoning") {
    const props = o.properties as Record<string, unknown> | undefined;
    html = `<strong>${props?.ZONE_CLASS ?? "Unknown"}</strong>`;
  } else if (lid === "transit-stations") {
    const s = o as unknown as TransitStation;
    const lineInfo = s.type === "cta_rail" && s.lines?.length
      ? `<br/>${s.lines.join(", ")}`
      : s.line ? `<br/>${s.line}` : "";
    html = `<strong>${s.name}</strong>${lineInfo}<br/><span style="opacity:0.7">${s.type === "cta_rail" ? "CTA Rail" : "Metra"}</span>`;
  } else if (lid === "overlay-districts") {
    const props = o.properties as Record<string, unknown> | undefined;
    const overlayType = (props?.overlay_type as string) ?? "";
    const label = overlayLabel(overlayType);
    const featureName = (props?.NAME ?? props?.DIST_NAME ?? props?.PD_NAME ?? "") as string;
    html = `<strong>${label}</strong>${featureName && featureName !== label ? `<br/>${featureName}` : ""}`;
  } else if (lid === "incentive-zones") {
    const props = o.properties as Record<string, unknown> | undefined;
    const zt = (props?.zone_type as string) ?? "";
    const name = (props?.name as string) ?? "";
    html = `<strong>${incentiveLabel(zt)}</strong>${name ? `<br/>${name}` : ""}`;
  } else {
    return null;
  }

  return { html, style: TOOLTIP_STYLE };
}
