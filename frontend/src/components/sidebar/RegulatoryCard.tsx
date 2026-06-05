import type { RegulatorySummary } from "../../lib/types";
import { CollapsibleCard } from "./CollapsibleCard";
import { InfoTooltip } from "../InfoTooltip";

const ShieldIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
  </svg>
);

const FLAG_LABELS: Record<string, string> = {
  in_planned_development: "Planned Development",
  in_landmark_district: "Landmark District",
  is_landmark_building: "Landmark Building",
  in_historic_district: "Historic District",
  on_national_register: "National Register",
  in_lakefront_protection: "Lakefront Protection",
  on_pedestrian_street: "Pedestrian Street",
  in_special_district: "Special District",
  in_pmd: "Planned Mfg. District",
  in_tod_area: "TOD Area",
  in_adu_area: "ADU Area",
  in_aro_zone: "ARO Zone",
  in_ssa: "Special Service Area",
};

const FLAG_KEYS = Object.keys(FLAG_LABELS) as (keyof typeof FLAG_LABELS)[];

function formatLayerType(t: string): string {
  return t.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function RegulatoryCard({ data }: { data: RegulatorySummary }) {
  const activeFlags = FLAG_KEYS.filter(k => data[k as keyof RegulatorySummary] === true);

  return (
    <CollapsibleCard title="Regulatory" icon={ShieldIcon}>
      <div className="space-y-3">
        {/* Active Overlays */}
        {data.overlays.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">Overlays</span>
            {data.overlays.map((ov, i) => (
              <div key={i} className="rounded-lg bg-dark-elevated/60 border-l-2 border-accent/60 px-3 py-2">
                <span className="text-[10px] text-accent/80 uppercase tracking-wider">
                  <InfoTooltip term={ov.layer_type}>{formatLayerType(ov.layer_type)}</InfoTooltip>
                </span>
                {ov.name && (
                  <p className="text-[11px] text-text-primary mt-0.5">{ov.name}</p>
                )}
                {ov.description && (
                  <p className="text-[10px] text-text-muted mt-0.5">{ov.description}</p>
                )}
                {ov.ordinance && (
                  <p className="text-[10px] text-text-muted mt-0.5">Ord. {ov.ordinance}</p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Regulatory Status Badges */}
        {activeFlags.length > 0 ? (
          <div className="space-y-1.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">Status</span>
            <div className="flex flex-wrap gap-1.5">
              {activeFlags.map(key => (
                <span
                  key={key}
                  className="inline-flex items-center gap-1 bg-emerald-500/15 text-emerald-400
                             border border-emerald-500/30 rounded-md px-2 py-0.5 text-[10px]"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <InfoTooltip term={key}>{FLAG_LABELS[key]}</InfoTooltip>
                  {key === "in_ssa" && data.ssa_name && (
                    <span className="text-emerald-400/70 ml-0.5">({data.ssa_name})</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        ) : data.overlays.length === 0 ? (
          <p className="text-[11px] text-text-muted">No regulatory overlays apply to this location.</p>
        ) : null}

        {/* Flood Zone */}
        {data.flood_zone && (
          <div className="space-y-1">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">Flood Zone</span>
            <div className={`rounded-lg px-3 py-2 text-[11px] ${
              data.in_special_flood_hazard
                ? "bg-amber-500/10 border border-amber-500/20"
                : "bg-dark-elevated/60 border border-dark-border"
            }`}>
              <div className="flex items-center gap-2">
                <span className={`font-mono font-medium ${data.in_special_flood_hazard ? "text-amber-400" : "text-text-primary"}`}>
                  <InfoTooltip term={`flood:${data.flood_zone}`}>Zone {data.flood_zone}</InfoTooltip>
                </span>
                {data.in_special_flood_hazard && (
                  <span className="bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded px-1.5 py-0.5 text-[9px] uppercase font-medium">
                    Special Flood Hazard
                  </span>
                )}
              </div>
              {data.flood_zone_subtype && (
                <p className="text-text-muted mt-0.5">{data.flood_zone_subtype}</p>
              )}
            </div>
          </div>
        )}

        {/* ARO Housing */}
        {data.aro_housing && data.aro_housing.total_projects > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">
              Affordable Housing (ARO)
            </span>
            <div className="rounded-lg bg-dark-elevated/60 border border-dark-border px-3 py-2 space-y-1">
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-text-muted text-[11px]">Projects</span>
                <span className="text-text-primary text-[11px] font-mono">{data.aro_housing.total_projects}</span>
              </div>
              <div className="flex justify-between items-baseline gap-2">
                <span className="text-text-muted text-[11px]">Total Units</span>
                <span className="text-text-primary text-[11px] font-mono">{data.aro_housing.total_units.toLocaleString()}</span>
              </div>
              {data.aro_housing.projects.slice(0, 5).map((proj, i) => (
                <div key={i} className="text-[10px] leading-tight pl-1 border-l border-dark-border mt-1">
                  <p className="text-text-primary">{proj.name}</p>
                  <div className="flex gap-2 text-text-muted">
                    {proj.units != null && <span>{proj.units} units</span>}
                    {proj.property_type && <span>{proj.property_type}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Brownfield Sites */}
        {data.brownfield_sites.length > 0 && (
          <div className="space-y-1">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">
              Nearby Brownfield Sites ({data.brownfield_sites.length})
            </span>
            {data.brownfield_sites.map((site, i) => (
              <div key={i} className="rounded-lg bg-amber-500/5 border border-amber-500/15 px-3 py-2 text-[11px]">
                <p className="text-text-primary">{(site as Record<string, string>).site_name ?? "Unknown site"}</p>
                {(site as Record<string, string>).interest_type && (
                  <p className="text-text-muted text-[10px] mt-0.5">{(site as Record<string, string>).interest_type}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </CollapsibleCard>
  );
}
