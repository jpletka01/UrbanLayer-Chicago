import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { RegulatorySummary } from "../../lib/types";
import { CollapsibleCard } from "./CollapsibleCard";
import { InfoTooltip } from "../InfoTooltip";
import { humanizeShoutyCase, translateFloodSubtype } from "../../lib/format";
import { getTermInfo } from "../../lib/termDefinitions";

const ShieldIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
  </svg>
);

const FLAG_KEYS = [
  "in_planned_development", "in_landmark_district", "is_landmark_building",
  "in_historic_district", "on_national_register", "in_lakefront_protection",
  "on_pedestrian_street", "in_special_district", "in_pmd",
  "in_tod_area", "in_adu_area", "in_aro_zone", "in_ssa",
];

function formatLayerType(t: string): string {
  return t.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// Loose-equality helpers so each overlay is communicated once: the dataset's
// name/description often just restate the layer type ("PEDESTRIAN STREET" /
// "Pedestrian Streets"), and most status flags mirror an overlay entry.
function normLabel(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]/g, "").replace(/s$/, "");
}

const GENERIC_TOKENS = new Set(["area", "zone", "district", "street", "cta", "metra"]);

function flagCore(s: string): string {
  return s
    .replace(/^(in|on|is)_/, "")
    .split("_")
    .filter(w => !GENERIC_TOKENS.has(w))
    .join(" ");
}

export function RegulatoryCard({ data }: { data: RegulatorySummary }) {
  const { t } = useTranslation("data");
  const [showAroProjects, setShowAroProjects] = useState(false);
  const overlayCores = new Set(data.overlays.map(ov => flagCore(ov.layer_type)));
  const activeFlags = FLAG_KEYS.filter(
    k => data[k as keyof RegulatorySummary] === true && !overlayCores.has(flagCore(k))
  );

  return (
    <CollapsibleCard title={t("regulatory.title")} icon={ShieldIcon}>
      <div className="space-y-3">
        {data.overlays.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-micro text-text-muted uppercase tracking-wider">{t("regulatory.overlays")}</span>
            {data.overlays.map((ov, i) => {
              // Dedup against the raw English label (API name/description are English
              // too, so cross-language comparison would never match); display the
              // translated label from the shared term catalog when available.
              const rawTypeLabel = formatLayerType(ov.layer_type);
              const typeLabel = getTermInfo(ov.layer_type)?.label || rawTypeLabel;
              const name = ov.name && normLabel(ov.name) !== normLabel(rawTypeLabel) ? humanizeShoutyCase(ov.name) : null;
              const description = ov.description &&
                normLabel(ov.description) !== normLabel(rawTypeLabel) &&
                (!ov.name || normLabel(ov.description) !== normLabel(ov.name))
                ? ov.description : null;
              return (
                <div key={i} className="rounded-lg bg-dark-elevated/60 border-l-2 border-accent/60 px-3 py-2">
                  <span className="text-micro text-accent/80 uppercase tracking-wider">
                    <InfoTooltip term={ov.layer_type}>{typeLabel}</InfoTooltip>
                  </span>
                  {name && (
                    <p className="text-micro text-text-primary mt-0.5">{name}</p>
                  )}
                  {description && (
                    <p className="text-micro text-text-muted mt-0.5">{description}</p>
                  )}
                  {ov.ordinance && (
                    <p className="text-micro text-text-muted mt-0.5">{t("regulatory.ord")} {ov.ordinance}</p>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {activeFlags.length > 0 ? (
          <div className="space-y-1.5">
            <span className="text-micro text-text-muted uppercase tracking-wider">{t("regulatory.status")}</span>
            <div className="flex flex-wrap gap-1.5">
              {activeFlags.map(key => (
                <span
                  key={key}
                  className="inline-flex items-center gap-1 bg-state-positive/15 text-state-positive
                             border border-state-positive/30 rounded-md px-2 py-0.5 text-micro"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-state-positive" />
                  <InfoTooltip term={key}>{t(`regulatory.flags.${key}`)}</InfoTooltip>
                  {key === "in_ssa" && data.ssa_name && (
                    <span className="text-state-positive/70 ml-0.5">({data.ssa_name})</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        ) : data.overlays.length === 0 ? (
          <p className="text-micro text-text-muted">{t("regulatory.noOverlays")}</p>
        ) : null}

        {data.flood_zone && (
          <div className="space-y-1">
            <span className="text-micro text-text-muted uppercase tracking-wider">{t("regulatory.floodZone")}</span>
            <div className={`rounded-lg px-3 py-2 text-micro ${
              data.in_special_flood_hazard
                ? "bg-state-warning/10 border border-state-warning/20"
                : "bg-dark-elevated/60 border border-dark-border"
            }`}>
              <div className="flex items-center gap-2">
                <span className={`font-mono font-medium ${data.in_special_flood_hazard ? "text-state-warning" : "text-text-primary"}`}>
                  <InfoTooltip term={`flood:${data.flood_zone}`}>{t("regulatory.zone", { code: data.flood_zone })}</InfoTooltip>
                </span>
                {data.in_special_flood_hazard && (
                  <span className="bg-state-warning/20 text-state-warning border border-state-warning/30 rounded px-1.5 py-0.5 text-micro uppercase font-medium">
                    {t("regulatory.specialFloodHazard")}
                  </span>
                )}
              </div>
              {data.flood_zone_subtype && (
                <p className="text-text-muted mt-0.5">{translateFloodSubtype(data.flood_zone_subtype)}</p>
              )}
            </div>
          </div>
        )}

        {data.aro_housing && data.aro_housing.total_projects > 0 && (
          <div className="space-y-1">
            <span className="text-micro text-text-muted uppercase tracking-wider">
              {t("regulatory.affordableHousing")}
            </span>
            <div className="rounded-lg bg-dark-elevated/60 border border-dark-border px-3 py-2 space-y-1">
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-text-muted text-micro">{t("regulatory.projects")}</span>
                <span className="text-text-primary text-micro font-mono">{data.aro_housing.total_projects}</span>
              </div>
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-text-muted text-micro">{t("regulatory.totalUnits")}</span>
                <span className="text-text-primary text-micro font-mono">{data.aro_housing.total_units.toLocaleString()}</span>
              </div>
              {data.aro_housing.projects.length > 0 && (
                <button
                  onClick={() => setShowAroProjects(p => !p)}
                  className="flex items-center gap-1.5 text-micro text-text-muted hover:text-text-secondary transition-colors pt-1"
                >
                  <svg
                    className={`w-2.5 h-2.5 transition-transform duration-150 ${showAroProjects ? "" : "-rotate-90"}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                  {t("regulatory.nearbyProjects")} ({Math.min(data.aro_housing.projects.length, 5)})
                </button>
              )}
              {showAroProjects && data.aro_housing.projects.slice(0, 5).map((proj, i) => (
                <div key={i} className="text-micro leading-tight pl-1 border-l border-dark-border mt-1">
                  <p className="text-text-primary">{proj.name}</p>
                  <div className="flex gap-2 text-text-muted">
                    {proj.units != null && <span>{proj.units} {t("regulatory.units")}</span>}
                    {proj.property_type && <span>{proj.property_type}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.brownfield_sites.length > 0 && (
          <div className="space-y-1">
            <span className="text-micro text-text-muted uppercase tracking-wider">
              {t("regulatory.nearbyBrownfield", { count: data.brownfield_sites.length })}
            </span>
            {data.brownfield_sites.map((site, i) => (
              <div key={i} className="rounded-lg bg-state-warning/5 border border-state-warning/15 px-3 py-2 text-micro">
                <p className="text-text-primary">{(site as Record<string, string>).site_name ?? t("regulatory.unknownSite")}</p>
                {(site as Record<string, string>).interest_type && (
                  <p className="text-text-muted text-micro mt-0.5">{(site as Record<string, string>).interest_type}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </CollapsibleCard>
  );
}
