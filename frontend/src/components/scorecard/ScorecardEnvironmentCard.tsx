// Page-scale Environment card: flood zone + nearby brownfields — the environmental
// risk facts, split out of the regulatory/overlays card so risk lives in the
// "what to watch for" section. Renders null when there's nothing to report.
import { useTranslation } from "react-i18next";
import type { RegulatorySummary } from "../../lib/types";
import { InfoTooltip } from "../InfoTooltip";
import { translateFloodSubtype } from "../../lib/format";
import { SubSection } from "./ProfileModule";

const WaterIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m-18.432 0A8.959 8.959 0 013 12c0-.778.099-1.533.284-2.253" />
  </svg>
);

export function ScorecardEnvironmentCard({ data }: { data: RegulatorySummary }) {
  const { t } = useTranslation("data");
  if (!data.flood_zone && data.brownfield_sites.length === 0) return null;

  return (
    <SubSection title={t("regulatory.environment")} icon={WaterIcon} className="flex-1">
      <div className="space-y-4">
        {data.flood_zone && (
          <div>
            <div className="text-overline uppercase tracking-wider text-text-muted mb-2">
              {t("regulatory.floodZone")}
            </div>
            <div className={`rounded-lg border px-3 py-2.5 ${
              data.in_special_flood_hazard
                ? "bg-state-warning/10 border-state-warning/25"
                : "bg-dark-elevated/40 border-dark-border"
            }`}>
              <div className="flex items-center gap-2">
                <span className={`text-body font-medium ${data.in_special_flood_hazard ? "text-state-warning" : "text-text-primary"}`}>
                  <InfoTooltip term={`flood:${data.flood_zone}`}>{t("regulatory.zone", { code: data.flood_zone })}</InfoTooltip>
                </span>
                {data.in_special_flood_hazard && (
                  <span className="bg-state-warning/20 text-state-warning border border-state-warning/30 rounded px-1.5 py-0.5 text-micro uppercase font-medium">
                    {t("regulatory.specialFloodHazard")}
                  </span>
                )}
              </div>
              {data.flood_zone_subtype && (
                <p className="text-caption text-text-muted mt-0.5">{translateFloodSubtype(data.flood_zone_subtype)}</p>
              )}
            </div>
          </div>
        )}

        {data.brownfield_sites.length > 0 && (
          <div>
            <div className="text-overline uppercase tracking-wider text-text-muted mb-2">
              {t("regulatory.nearbyBrownfield", { count: data.brownfield_sites.length })}
            </div>
            <div className="space-y-2">
              {data.brownfield_sites.map((site, i) => (
                <div key={i} className="rounded-lg bg-state-warning/5 border border-state-warning/15 px-3 py-2.5">
                  <p className="text-body text-text-primary">{(site as Record<string, string>).site_name ?? t("regulatory.unknownSite")}</p>
                  {(site as Record<string, string>).interest_type && (
                    <p className="text-caption text-text-muted mt-0.5">{(site as Record<string, string>).interest_type}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </SubSection>
  );
}
