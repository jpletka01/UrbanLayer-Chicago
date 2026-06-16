import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ReportData } from "../lib/reportBuilder";
import type {
  CodeChunk,
  PropertySummary,
  RegulatorySummary,
  IncentivesSummary,
  NeighborhoodSummary,
  CrimeSummary,
  ThreeOneOneSummary,
  PermitSummary,
  ViolationSummary,
  BusinessSummary,
} from "../lib/types";
import { downloadPDF } from "../lib/pdfExport";

interface Props {
  report: ReportData;
  onClose: () => void;
}

const s = {
  page: {
    fontFamily: "'Inter', system-ui, sans-serif",
    backgroundColor: "#ffffff",
    color: "#1a1a1a",
    padding: "40px",
    maxWidth: "800px",
    margin: "0 auto",
    lineHeight: 1.6,
    fontSize: "14px",
  } as React.CSSProperties,
  h1: {
    fontSize: "24px",
    fontWeight: 700,
    color: "#111",
    margin: "0 0 4px",
  } as React.CSSProperties,
  h2: {
    fontSize: "18px",
    fontWeight: 600,
    color: "#222",
    borderBottom: "2px solid #e5e7eb",
    paddingBottom: "6px",
    margin: "32px 0 16px",
  } as React.CSSProperties,
  subtitle: {
    fontSize: "13px",
    color: "#666",
    margin: "0 0 2px",
  } as React.CSSProperties,
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: "13px",
    margin: "12px 0",
  },
  th: {
    textAlign: "left" as const,
    padding: "8px 12px",
    backgroundColor: "#f9fafb",
    borderBottom: "1px solid #e5e7eb",
    fontWeight: 600,
    color: "#374151",
    fontSize: "12px",
  } as React.CSSProperties,
  td: {
    padding: "8px 12px",
    borderBottom: "1px solid #f3f4f6",
    color: "#1f2937",
  } as React.CSSProperties,
  qa: {
    margin: "16px 0",
    padding: "12px 16px",
    backgroundColor: "#f9fafb",
    borderRadius: "6px",
    borderLeft: "3px solid #3b82f6",
  } as React.CSSProperties,
  question: {
    fontWeight: 600,
    color: "#1e40af",
    margin: "0 0 8px",
    fontSize: "14px",
  } as React.CSSProperties,
  answer: {
    color: "#374151",
    margin: 0,
    whiteSpace: "pre-wrap" as const,
    fontSize: "13px",
  } as React.CSSProperties,
  disclaimer: {
    backgroundColor: "#fefce8",
    border: "1px solid #fde68a",
    borderRadius: "6px",
    padding: "12px 16px",
    fontSize: "12px",
    color: "#92400e",
    marginTop: "24px",
  } as React.CSSProperties,
  map: {
    width: "100%",
    borderRadius: "8px",
    border: "1px solid #e5e7eb",
    margin: "12px 0",
  } as React.CSSProperties,
  badge: {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: "4px",
    fontSize: "11px",
    fontWeight: 600,
    marginRight: "6px",
    marginBottom: "4px",
  } as React.CSSProperties,
  badgeGreen: { backgroundColor: "#dcfce7", color: "#166534" },
  badgeRed: { backgroundColor: "#fee2e2", color: "#991b1b" },
  badgeBlue: { backgroundColor: "#dbeafe", color: "#1e40af" },
  badgeGray: { backgroundColor: "#f3f4f6", color: "#374151" },
};

function getLocale(): string {
  try {
    const lang = localStorage.getItem("urbanlayer-language");
    return lang === "es" ? "es-ES" : "en-US";
  } catch { return "en-US"; }
}

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString(getLocale());
}

function fmtCurrency(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString(getLocale(), { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

function PropertyTable({ data, t }: { data: PropertySummary; t: (key: string, opts?: Record<string, unknown>) => string }) {
  const rows: [string, string][] = [];
  if (data.pin14) rows.push([t("report.pin"), data.pin14]);
  if (data.address) rows.push([t("report.address"), data.address]);
  if (data.bldg_class_description) rows.push([t("report.buildingClass"), `${data.bldg_class ?? ""} — ${data.bldg_class_description}`]);
  if (data.bldg_sqft) rows.push([t("report.buildingSqFt"), fmt(data.bldg_sqft)]);
  if (data.land_sqft) rows.push([t("report.landSqFt"), fmt(data.land_sqft)]);
  if (data.stories) rows.push([t("report.stories"), String(data.stories)]);
  if (data.units) rows.push([t("report.units"), String(data.units)]);
  if (data.bedrooms) rows.push([t("report.bedrooms"), String(data.bedrooms)]);
  if (data.bldg_age) rows.push([t("report.buildingAge"), t("report.yearsUnit", { count: data.bldg_age })]);
  if (data.total_assessed_value) rows.push([t("report.totalAssessedValue"), fmtCurrency(data.total_assessed_value)]);
  if (data.estimated_annual_tax) rows.push([t("report.estAnnualTax"), fmtCurrency(data.estimated_annual_tax)]);

  return (
    <table style={s.table}>
      <tbody>
        {rows.map(([label, val]) => (
          <tr key={label}>
            <td style={{ ...s.td, fontWeight: 600, width: "40%" }}>{label}</td>
            <td style={s.td}>{val}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RegulatoryTable({ data, t }: { data: RegulatorySummary; t: (key: string, opts?: Record<string, unknown>) => string }) {
  const flagKeys: [string, boolean | undefined][] = [
    ["in_planned_development", data.in_planned_development],
    ["in_landmark_district", data.in_landmark_district],
    ["is_landmark_building", data.is_landmark_building],
    ["in_historic_district", data.in_historic_district],
    ["on_national_register", data.on_national_register],
    ["in_lakefront_protection", data.in_lakefront_protection],
    ["on_pedestrian_street", data.on_pedestrian_street],
    ["in_tod_area", data.in_tod_area],
    ["in_adu_area", data.in_adu_area],
    ["in_aro_zone", data.in_aro_zone],
  ];
  const flags = flagKeys
    .filter(([, v]) => v)
    .map(([k]) => t(`regulatory.flags.${k}`));
  if (data.in_ssa) flags.push(`${t("regulatory.flags.in_ssa")}: ${data.ssa_name || t("report.yes")}`);

  return (
    <div>
      {data.overlays.length > 0 && (
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>{t("report.overlayType")}</th>
              <th style={s.th}>{t("report.name")}</th>
            </tr>
          </thead>
          <tbody>
            {data.overlays.map((o, i) => (
              <tr key={i}>
                <td style={s.td}>{o.layer_type}</td>
                <td style={s.td}>{o.name || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {flags.length > 0 && (
        <div style={{ margin: "8px 0" }}>
          {flags.map((f) => (
            <span key={f} style={{ ...s.badge, ...s.badgeBlue }}>{f}</span>
          ))}
        </div>
      )}
      {data.flood_zone && (
        <p style={{ fontSize: "13px", color: "#92400e" }}>
          {t("report.floodZone")}: {data.flood_zone}{data.flood_zone_subtype ? ` (${data.flood_zone_subtype})` : ""}
          {data.in_special_flood_hazard && ` — ${t("report.specialFloodHazard")}`}
        </p>
      )}
      {data.brownfield_sites.length > 0 && (
        <p style={{ fontSize: "13px", color: "#92400e" }}>
          {t("report.brownfieldSites", { count: data.brownfield_sites.length })}
        </p>
      )}
    </div>
  );
}

function IncentivesTable({ data, t }: { data: IncentivesSummary; t: (key: string, opts?: Record<string, unknown>) => string }) {
  return (
    <div>
      <div style={{ margin: "8px 0" }}>
        {data.in_tif_district && (
          <span style={{ ...s.badge, ...s.badgeGreen }}>{t("incentives.inTif")}</span>
        )}
        {data.in_opportunity_zone && (
          <span style={{ ...s.badge, ...s.badgeGreen }}>{t("incentives.opportunityZone")}</span>
        )}
        {data.in_enterprise_zone && (
          <span style={{ ...s.badge, ...s.badgeGreen }}>{t("incentives.enterpriseZone")}</span>
        )}
      </div>
      {data.in_tif_district && (
        <table style={s.table}>
          <tbody>
            {data.tif_name && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>{t("report.tifDistrict")}</td><td style={s.td}>{data.tif_name}</td></tr>}
            {data.tif_year_start && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>{t("report.startYear")}</td><td style={s.td}>{data.tif_year_start}</td></tr>}
            {data.tif_end_year && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>{t("report.endYear")}</td><td style={s.td}>{data.tif_end_year}</td></tr>}
            {data.tif_total_revenue != null && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>{t("report.totalRevenue")}</td><td style={s.td}>{fmtCurrency(data.tif_total_revenue)}</td></tr>}
            {data.tif_total_expenditure != null && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>{t("report.totalExpenditure")}</td><td style={s.td}>{fmtCurrency(data.tif_total_expenditure)}</td></tr>}
          </tbody>
        </table>
      )}
      {data.in_opportunity_zone && data.oz_tract && (
        <p style={{ fontSize: "13px", color: "#374151" }}>{t("report.censusTract")}: {data.oz_tract}</p>
      )}
    </div>
  );
}

function NeighborhoodTable({ data, t }: { data: NeighborhoodSummary; t: (key: string, opts?: Record<string, unknown>) => string }) {
  const d = data.demographics;
  const tr = data.transit;
  const w = data.walkscore;

  return (
    <div>
      {d && (
        <table style={s.table}>
          <thead><tr><th style={s.th} colSpan={2}>{t("report.demographics")}</th></tr></thead>
          <tbody>
            <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>{t("report.population")}</td><td style={s.td}>{fmt(d.population)}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.medianHouseholdIncome")}</td><td style={s.td}>{fmtCurrency(d.median_household_income)}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.medianHomeValue")}</td><td style={s.td}>{fmtCurrency(d.median_home_value)}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.medianAge")}</td><td style={s.td}>{d.median_age ?? "—"}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.povertyRate")}</td><td style={s.td}>{fmtPct(d.poverty_rate)}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.unemployment")}</td><td style={s.td}>{fmtPct(d.unemployment_rate)}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.ownerOccupied")}</td><td style={s.td}>{fmtPct(d.owner_occupied_pct)}</td></tr>
          </tbody>
        </table>
      )}
      {w && (w.walk_score != null || w.transit_score != null || w.bike_score != null) && (
        <table style={s.table}>
          <thead><tr><th style={s.th} colSpan={2}>{t("report.walkScoreSection")}</th></tr></thead>
          <tbody>
            {w.walk_score != null && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>{t("report.walkScore")}</td><td style={s.td}>{w.walk_score} — {w.walk_description}</td></tr>}
            {w.transit_score != null && <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.transitScore")}</td><td style={s.td}>{w.transit_score} — {w.transit_description}</td></tr>}
            {w.bike_score != null && <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.bikeScore")}</td><td style={s.td}>{w.bike_score} — {w.bike_description}</td></tr>}
          </tbody>
        </table>
      )}
      {tr && (
        <table style={s.table}>
          <thead><tr><th style={s.th} colSpan={2}>{t("report.transitAccess")}</th></tr></thead>
          <tbody>
            {tr.nearest_cta_rail && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>{t("report.nearestCtaRail")}</td><td style={s.td}>{tr.nearest_cta_rail} ({tr.cta_rail_distance_mi?.toFixed(2)} mi)</td></tr>}
            {tr.cta_lines.length > 0 && <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.ctaLines")}</td><td style={s.td}>{tr.cta_lines.join(", ")}</td></tr>}
            {tr.nearest_metra && <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.nearestMetra")}</td><td style={s.td}>{tr.nearest_metra} ({tr.metra_distance_mi?.toFixed(2)} mi)</td></tr>}
            {tr.tod_eligible && <tr><td style={{ ...s.td, fontWeight: 600 }}>{t("report.todEligible")}</td><td style={s.td}>{tr.tod_type || t("report.yes")}</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SafetySection({ data, t }: { data: { crime: CrimeSummary | null; three11: ThreeOneOneSummary | null; permits: PermitSummary | null; violations: ViolationSummary | null; businesses: BusinessSummary | null }; t: (key: string, opts?: Record<string, unknown>) => string }) {
  const { crime, three11, permits, violations, businesses } = data;
  return (
    <div>
      {crime && (
        <>
          <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#374151", margin: "12px 0 8px" }}>{t("report.crimeLast90")}</h3>
          <p style={{ fontSize: "13px", margin: "0 0 8px" }}>{t("report.totalIncidents", { total: fmt(crime.total), rate: fmtPct(crime.arrest_rate) })}</p>
          <table style={s.table}>
            <thead><tr><th style={s.th}>{t("report.type")}</th><th style={s.th}>{t("report.count")}</th></tr></thead>
            <tbody>
              {Object.entries(crime.by_type).slice(0, 10).map(([type, count]) => (
                <tr key={type}><td style={s.td}>{type}</td><td style={s.td}>{fmt(count)}</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {three11 && (
        <>
          <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#374151", margin: "12px 0 8px" }}>{t("report.threeOneOneRequests")}</h3>
          <p style={{ fontSize: "13px", margin: "0 0 8px" }}>{t("report.openRequests", { total: fmt(three11.total) })}{three11.oldest_open_days != null ? t("report.oldestDays", { days: three11.oldest_open_days }) : ""}</p>
        </>
      )}
      {permits && (
        <>
          <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#374151", margin: "12px 0 8px" }}>{t("report.permitsLastYear")}</h3>
          <p style={{ fontSize: "13px", margin: "0 0 8px" }}>{t("report.permitsTotal", { total: fmt(permits.total), cost: fmtCurrency(permits.total_estimated_cost) })}</p>
        </>
      )}
      {violations && (
        <>
          <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#374151", margin: "12px 0 8px" }}>{t("report.buildingViolations")}</h3>
          <p style={{ fontSize: "13px", margin: "0 0 8px" }}>{t("report.violationsTotal", { total: fmt(violations.total), open: fmt(violations.open_count) })}</p>
        </>
      )}
      {businesses && (
        <>
          <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#374151", margin: "12px 0 8px" }}>{t("report.businessLicenses")}</h3>
          <p style={{ fontSize: "13px", margin: "0 0 8px" }}>{t("report.businessTotal", { total: fmt(businesses.total) })}</p>
        </>
      )}
    </div>
  );
}

export function ExportReport({ report, onClose }: Props) {
  const reportRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  const { t } = useTranslation("data");

  const handleDownload = useCallback(async () => {
    if (!reportRef.current) return;
    setExporting(true);
    try {
      const slug = (report.address || report.communityArea || "chicago")
        .replace(/[^a-zA-Z0-9]+/g, "_")
        .toLowerCase()
        .slice(0, 40);
      const date = new Date().toISOString().slice(0, 10);
      await downloadPDF(reportRef.current, `${slug}_${date}_transcript.pdf`);
    } finally {
      setExporting(false);
    }
  }, [report]);

  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  return (
    <div
      className="export-report"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        backgroundColor: "rgba(0,0,0,0.85)",
      }}
    >
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "12px 24px",
        backgroundColor: "#111",
        borderBottom: "1px solid #333",
        flexShrink: 0,
      }}>
        <h2 style={{ color: "#fff", fontSize: "16px", fontWeight: 600, margin: 0 }}>{t("report.reportPreview")}</h2>
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={handlePrint}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "1px solid #555",
              backgroundColor: "transparent",
              color: "#ccc",
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            {t("report.print")}
          </button>
          <button
            onClick={handleDownload}
            disabled={exporting}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "#3b82f6",
              color: "#fff",
              fontSize: "13px",
              fontWeight: 600,
              cursor: exporting ? "wait" : "pointer",
              opacity: exporting ? 0.7 : 1,
            }}
          >
            {exporting ? t("report.generatingPdf") : t("report.downloadPdf")}
          </button>
          <button
            onClick={onClose}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: "1px solid #555",
              backgroundColor: "transparent",
              color: "#ccc",
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            {t("report.close")}
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "24px" }}>
        <div ref={reportRef} style={s.page}>
          {report.sections.map((section, i) => {
            switch (section.type) {
              case "header": {
                const h = section.content as { address: string | null; communityArea: string | null; generatedAt: string };
                return (
                  <div key={i}>
                    <h1 style={s.h1}>{t("report.siteReport")}</h1>
                    {h.address && <p style={s.subtitle}>{h.address}</p>}
                    {h.communityArea && <p style={s.subtitle}>{h.communityArea}</p>}
                    <p style={{ ...s.subtitle, color: "#999" }}>{t("report.generated", { date: h.generatedAt })}</p>
                  </div>
                );
              }
              case "map":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <img src={section.content as string} alt={t("sidebar:map")} style={s.map} />
                  </div>
                );
              case "property":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <PropertyTable data={section.content as PropertySummary} t={t} />
                  </div>
                );
              case "regulatory":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <RegulatoryTable data={section.content as RegulatorySummary} t={t} />
                  </div>
                );
              case "incentives":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <IncentivesTable data={section.content as IncentivesSummary} t={t} />
                  </div>
                );
              case "neighborhood":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <NeighborhoodTable data={section.content as NeighborhoodSummary} t={t} />
                  </div>
                );
              case "safety":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <SafetySection data={section.content as { crime: CrimeSummary | null; three11: ThreeOneOneSummary | null; permits: PermitSummary | null; violations: ViolationSummary | null; businesses: BusinessSummary | null }} t={t} />
                  </div>
                );
              case "qa": {
                const pairs = section.content as Array<{ question: string; answer: string }>;
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    {pairs.map((qa, j) => (
                      <div key={j} style={s.qa}>
                        <p style={s.question}>{t("report.questionPrefix")} {qa.question}</p>
                        <p style={s.answer}>{qa.answer}</p>
                      </div>
                    ))}
                  </div>
                );
              }
              case "sources": {
                const chunks = section.content as CodeChunk[];
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    {chunks.map((chunk, j) => (
                      <div key={j} style={{ margin: "12px 0", padding: "8px 12px", backgroundColor: "#f9fafb", borderRadius: "4px", fontSize: "12px" }}>
                        <p style={{ fontWeight: 600, margin: "0 0 4px", color: "#374151" }}>
                          [{j + 1}] {chunk.section_title} ({chunk.section})
                        </p>
                        <p style={{ color: "#6b7280", margin: 0, whiteSpace: "pre-wrap", maxHeight: "120px", overflow: "hidden" }}>
                          {chunk.text.slice(0, 500)}{chunk.text.length > 500 ? "…" : ""}
                        </p>
                      </div>
                    ))}
                  </div>
                );
              }
              case "disclaimer": {
                const d = section.content as { hasDisclaimer: boolean; dataLag: string | null; dataAsOf: string | null };
                return (
                  <div key={i} style={s.disclaimer}>
                    <h2 style={{ ...s.h2, borderColor: "#fde68a", color: "#92400e", margin: "0 0 8px", fontSize: "15px" }}>{section.title}</h2>
                    {d.hasDisclaimer && (
                      <p style={{ margin: "0 0 8px" }}>
                        {t("report.disclaimerText")}
                      </p>
                    )}
                    {d.dataAsOf && <p style={{ margin: "0 0 4px" }}>{t("report.dataAsOf", { date: d.dataAsOf })}</p>}
                    {d.dataLag && <p style={{ margin: 0 }}>{d.dataLag}</p>}
                    <p style={{ margin: "8px 0 0", fontSize: "11px", color: "#b45309" }}>
                      {t("report.generatedBy")}
                    </p>
                  </div>
                );
              }
              default:
                return null;
            }
          })}
        </div>
      </div>
    </div>
  );
}
