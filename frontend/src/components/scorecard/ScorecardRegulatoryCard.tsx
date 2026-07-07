// Page-scale Regulatory card. Replaces the sidebar RegulatoryCard on the Scorecard
// page: overlays are severity-sorted into constraints (reviews/restrictions) vs
// opportunities/context instead of seven identical boxes, and type is body-scale.
// Classification is presentational only — the same overlays render, grouped.
import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import type { RegulatorySummary } from "../../lib/types";
import { InfoTooltip } from "../InfoTooltip";
import { humanizeShoutyCase } from "../../lib/format";
import { getTermInfo } from "../../lib/termDefinitions";
import { SubSection, ShowMore } from "./ProfileModule";

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

// Presentational severity: does this layer add review/restriction friction, or is
// it an entitlement/context layer? Unknown types fall to "context" (never hidden).
const CONSTRAINT_PAT = /landmark|historic|national_register|planned_development|lakefront|pmd|pedestrian|demolition/;
const OPPORTUNITY_PAT = /tod|adu|aro|ssa|special_service|enterprise|transit/;
type Severity = "constraint" | "opportunity" | "context";

function severityOf(key: string): Severity {
  const k = key.toLowerCase();
  if (CONSTRAINT_PAT.test(k)) return "constraint";
  if (OPPORTUNITY_PAT.test(k)) return "opportunity";
  return "context";
}

function formatLayerType(t: string): string {
  return t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function normLabel(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]/g, "").replace(/s$/, "");
}
const GENERIC_TOKENS = new Set(["area", "zone", "district", "street", "cta", "metra"]);
function flagCore(s: string): string {
  return s.replace(/^(in|on|is)_/, "").split("_").filter((w) => !GENERIC_TOKENS.has(w)).join(" ");
}

const TONE: Record<Severity, { row: string; icon: ReactElement | null }> = {
  constraint: {
    row: "border-state-warning/25 bg-state-warning/5",
    icon: (
      <svg className="w-4 h-4 text-state-warning shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
    ),
  },
  opportunity: {
    row: "border-state-positive/20 bg-state-positive/5",
    icon: (
      <svg className="w-4 h-4 text-state-positive shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  context: { row: "border-dark-border bg-dark-elevated/40", icon: null },
};

interface OverlayRow {
  key: string;
  severity: Severity;
  title: string;
  type: string | null;
  detail: string | null;
  term: string;
}

function OverlayRowView({ row }: { row: OverlayRow }) {
  const tone = TONE[row.severity];
  return (
    <div className={`flex items-start gap-2.5 rounded-lg border px-3 py-2.5 ${tone.row}`}>
      {tone.icon}
      <div className="min-w-0">
        <div className="text-body text-text-primary leading-snug">
          <InfoTooltip term={row.term}>{row.title}</InfoTooltip>
        </div>
        {(row.type || row.detail) && (
          <div className="text-caption text-text-muted mt-0.5 leading-snug">
            {[row.type, row.detail].filter(Boolean).join(" — ")}
          </div>
        )}
      </div>
    </div>
  );
}

// Content budget: the module's height must not track overlay volume (the old
// "card = data source, height = data volume" model is what left its pair card
// with a dead-space flank). Top-N rows always visible, the tail discloses.
const CONSTRAINT_BUDGET = 6;

export function ScorecardRegulatoryCard({ data }: { data: RegulatorySummary }) {
  const { t } = useTranslation("data");

  // Same dedup as the sidebar card: status flags that restate an overlay are dropped.
  const overlayCores = new Set(data.overlays.map((ov) => flagCore(ov.layer_type)));
  const activeFlags = FLAG_KEYS.filter(
    (k) => data[k as keyof RegulatorySummary] === true && !overlayCores.has(flagCore(k)),
  );

  const rows: OverlayRow[] = [
    ...data.overlays.map((ov, i): OverlayRow => {
      const rawTypeLabel = formatLayerType(ov.layer_type);
      const typeLabel = getTermInfo(ov.layer_type)?.label || rawTypeLabel;
      const name = ov.name && normLabel(ov.name) !== normLabel(rawTypeLabel) ? humanizeShoutyCase(ov.name) : null;
      const description = ov.description &&
        normLabel(ov.description) !== normLabel(rawTypeLabel) &&
        (!ov.name || normLabel(ov.description) !== normLabel(ov.name))
        ? ov.description : null;
      return {
        key: `ov-${i}`,
        severity: severityOf(ov.layer_type),
        title: name ?? typeLabel,
        type: name ? typeLabel : null,
        detail: [description, ov.ordinance ? `${t("regulatory.ord")} ${ov.ordinance}` : null].filter(Boolean).join(" · ") || null,
        term: ov.layer_type,
      };
    }),
    ...activeFlags.map((key): OverlayRow => ({
      key,
      severity: severityOf(key),
      title: t(`regulatory.flags.${key}`),
      type: key === "in_ssa" && data.ssa_name ? data.ssa_name : null,
      detail: null,
      term: key,
    })),
  ];

  const constraints = rows.filter((r) => r.severity === "constraint");
  const others = rows.filter((r) => r.severity !== "constraint");

  return (
    <SubSection title={t("regulatory.title")} icon={ShieldIcon}
      meta={rows.length > 0 ? t("regulatory.constraintCount", { count: constraints.length }) : undefined}
      className="flex-1"
    >
      <div className="space-y-5">
        {rows.length === 0 && <p className="text-body text-text-muted">{t("regulatory.noOverlays")}</p>}

        {constraints.length > 0 && (
          <div>
            <div className="text-overline uppercase tracking-wider text-text-muted mb-2">
              {t("regulatory.constraints")}
            </div>
            <ShowMore
              items={constraints}
              limit={CONSTRAINT_BUDGET}
              render={(visible) => (
                <div className="space-y-2">
                  {visible.map((r) => (
                    <OverlayRowView key={r.key} row={r} />
                  ))}
                </div>
              )}
            />
          </div>
        )}

        {others.length > 0 && (
          <div>
            <div className="text-overline uppercase tracking-wider text-text-muted mb-2">
              {t("regulatory.opportunities")}
            </div>
            {/* Pills, not rows: opportunities are context, and full rows made this
                card the page's height driver. Definitions stay on the tooltip. */}
            <div className="flex flex-wrap gap-1.5">
              {others.map((r) => (
                <span key={r.key}
                  className="inline-flex items-center gap-1.5 rounded-md border border-state-positive/25 bg-state-positive/5 px-2.5 py-1 text-caption text-text-primary">
                  <svg className="w-3.5 h-3.5 text-state-positive shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <InfoTooltip term={r.term}>{r.title}</InfoTooltip>
                </span>
              ))}
            </div>
          </div>
        )}

        {data.aro_housing && data.aro_housing.total_projects > 0 && (
          <div>
            <div className="text-overline uppercase tracking-wider text-text-muted mb-2">
              <InfoTooltip term="in_aro_zone">{t("regulatory.affordableHousing")}</InfoTooltip>
            </div>
            <div className="rounded-lg bg-dark-elevated/40 border border-dark-border px-3 py-2.5">
              <div className="flex gap-6">
                <div>
                  <div className="text-body text-text-primary">{data.aro_housing.total_projects}</div>
                  <div className="text-caption text-text-muted">{t("regulatory.projects")}</div>
                </div>
                <div>
                  <div className="text-body text-text-primary">{data.aro_housing.total_units.toLocaleString()}</div>
                  <div className="text-caption text-text-muted">{t("regulatory.totalUnits")}</div>
                </div>
              </div>
              {data.aro_housing.projects.length > 0 && (
                <div className="pt-2">
                  <ShowMore
                    items={data.aro_housing.projects.slice(0, 5)}
                    limit={2}
                    render={(visible) => (
                      <>
                        {visible.map((proj, i) => (
                          <div key={i} className="text-caption leading-snug pl-2 border-l border-dark-border mt-2 first:mt-0">
                            <p className="text-text-primary">{proj.name}</p>
                            <div className="flex gap-2 text-text-muted">
                              {proj.units != null && <span>{proj.units} {t("regulatory.units")}</span>}
                              {proj.property_type && <span>{proj.property_type}</span>}
                            </div>
                          </div>
                        ))}
                      </>
                    )}
                  />
                </div>
              )}
            </div>
          </div>
        )}

      </div>
    </SubSection>
  );
}
