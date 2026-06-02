import { useCallback, useRef, useState } from "react";
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

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US");
}

function fmtCurrency(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

function PropertyTable({ data }: { data: PropertySummary }) {
  const rows: [string, string][] = [];
  if (data.pin14) rows.push(["PIN", data.pin14]);
  if (data.address) rows.push(["Address", data.address]);
  if (data.bldg_class_description) rows.push(["Building Class", `${data.bldg_class ?? ""} — ${data.bldg_class_description}`]);
  if (data.bldg_sqft) rows.push(["Building Sq Ft", fmt(data.bldg_sqft)]);
  if (data.land_sqft) rows.push(["Land Sq Ft", fmt(data.land_sqft)]);
  if (data.stories) rows.push(["Stories", String(data.stories)]);
  if (data.units) rows.push(["Units", String(data.units)]);
  if (data.bedrooms) rows.push(["Bedrooms", String(data.bedrooms)]);
  if (data.bldg_age) rows.push(["Building Age", `${data.bldg_age} years`]);
  if (data.total_assessed_value) rows.push(["Total Assessed Value", fmtCurrency(data.total_assessed_value)]);
  if (data.estimated_annual_tax) rows.push(["Estimated Annual Tax", fmtCurrency(data.estimated_annual_tax)]);

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

function RegulatoryTable({ data }: { data: RegulatorySummary }) {
  const flags: string[] = [];
  if (data.in_planned_development) flags.push("Planned Development");
  if (data.in_landmark_district) flags.push("Landmark District");
  if (data.is_landmark_building) flags.push("Landmark Building");
  if (data.in_historic_district) flags.push("Historic District");
  if (data.on_national_register) flags.push("National Register");
  if (data.in_lakefront_protection) flags.push("Lakefront Protection");
  if (data.on_pedestrian_street) flags.push("Pedestrian Street");
  if (data.in_tod_area) flags.push("Transit-Oriented Development");
  if (data.in_adu_area) flags.push("ADU Eligible");
  if (data.in_aro_zone) flags.push("ARO Zone");
  if (data.in_ssa) flags.push(`SSA: ${data.ssa_name || "Yes"}`);

  return (
    <div>
      {data.overlays.length > 0 && (
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>Overlay Type</th>
              <th style={s.th}>Name</th>
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
          Flood Zone: {data.flood_zone}{data.flood_zone_subtype ? ` (${data.flood_zone_subtype})` : ""}
          {data.in_special_flood_hazard && " — Special Flood Hazard Area"}
        </p>
      )}
      {data.brownfield_sites.length > 0 && (
        <p style={{ fontSize: "13px", color: "#92400e" }}>
          {data.brownfield_sites.length} brownfield site(s) nearby
        </p>
      )}
    </div>
  );
}

function IncentivesTable({ data }: { data: IncentivesSummary }) {
  return (
    <div>
      <div style={{ margin: "8px 0" }}>
        {data.in_tif_district && (
          <span style={{ ...s.badge, ...s.badgeGreen }}>TIF District</span>
        )}
        {data.in_opportunity_zone && (
          <span style={{ ...s.badge, ...s.badgeGreen }}>Opportunity Zone</span>
        )}
        {data.in_enterprise_zone && (
          <span style={{ ...s.badge, ...s.badgeGreen }}>Enterprise Zone</span>
        )}
      </div>
      {data.in_tif_district && (
        <table style={s.table}>
          <tbody>
            {data.tif_name && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>TIF District</td><td style={s.td}>{data.tif_name}</td></tr>}
            {data.tif_year_start && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>Start Year</td><td style={s.td}>{data.tif_year_start}</td></tr>}
            {data.tif_end_year && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>End Year</td><td style={s.td}>{data.tif_end_year}</td></tr>}
            {data.tif_total_revenue != null && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>Total Revenue</td><td style={s.td}>{fmtCurrency(data.tif_total_revenue)}</td></tr>}
            {data.tif_total_expenditure != null && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>Total Expenditure</td><td style={s.td}>{fmtCurrency(data.tif_total_expenditure)}</td></tr>}
          </tbody>
        </table>
      )}
      {data.in_opportunity_zone && data.oz_tract && (
        <p style={{ fontSize: "13px", color: "#374151" }}>Census Tract: {data.oz_tract}</p>
      )}
    </div>
  );
}

function NeighborhoodTable({ data }: { data: NeighborhoodSummary }) {
  const d = data.demographics;
  const t = data.transit;
  const w = data.walkscore;

  return (
    <div>
      {d && (
        <table style={s.table}>
          <thead><tr><th style={s.th} colSpan={2}>Demographics</th></tr></thead>
          <tbody>
            <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>Population</td><td style={s.td}>{fmt(d.population)}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>Median Household Income</td><td style={s.td}>{fmtCurrency(d.median_household_income)}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>Median Home Value</td><td style={s.td}>{fmtCurrency(d.median_home_value)}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>Median Age</td><td style={s.td}>{d.median_age ?? "—"}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>Poverty Rate</td><td style={s.td}>{fmtPct(d.poverty_rate)}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>Unemployment</td><td style={s.td}>{fmtPct(d.unemployment_rate)}</td></tr>
            <tr><td style={{ ...s.td, fontWeight: 600 }}>Owner-Occupied</td><td style={s.td}>{fmtPct(d.owner_occupied_pct)}</td></tr>
          </tbody>
        </table>
      )}
      {w && (w.walk_score != null || w.transit_score != null || w.bike_score != null) && (
        <table style={s.table}>
          <thead><tr><th style={s.th} colSpan={2}>Walk Score</th></tr></thead>
          <tbody>
            {w.walk_score != null && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>Walk Score</td><td style={s.td}>{w.walk_score} — {w.walk_description}</td></tr>}
            {w.transit_score != null && <tr><td style={{ ...s.td, fontWeight: 600 }}>Transit Score</td><td style={s.td}>{w.transit_score} — {w.transit_description}</td></tr>}
            {w.bike_score != null && <tr><td style={{ ...s.td, fontWeight: 600 }}>Bike Score</td><td style={s.td}>{w.bike_score} — {w.bike_description}</td></tr>}
          </tbody>
        </table>
      )}
      {t && (
        <table style={s.table}>
          <thead><tr><th style={s.th} colSpan={2}>Transit Access</th></tr></thead>
          <tbody>
            {t.nearest_cta_rail && <tr><td style={{ ...s.td, fontWeight: 600, width: "40%" }}>Nearest CTA Rail</td><td style={s.td}>{t.nearest_cta_rail} ({t.cta_rail_distance_mi?.toFixed(2)} mi)</td></tr>}
            {t.cta_lines.length > 0 && <tr><td style={{ ...s.td, fontWeight: 600 }}>CTA Lines</td><td style={s.td}>{t.cta_lines.join(", ")}</td></tr>}
            {t.nearest_metra && <tr><td style={{ ...s.td, fontWeight: 600 }}>Nearest Metra</td><td style={s.td}>{t.nearest_metra} ({t.metra_distance_mi?.toFixed(2)} mi)</td></tr>}
            {t.tod_eligible && <tr><td style={{ ...s.td, fontWeight: 600 }}>TOD Eligible</td><td style={s.td}>{t.tod_type || "Yes"}</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SafetySection({ data }: { data: { crime: CrimeSummary | null; three11: ThreeOneOneSummary | null; permits: PermitSummary | null; violations: ViolationSummary | null; businesses: BusinessSummary | null } }) {
  const { crime, three11, permits, violations, businesses } = data;
  return (
    <div>
      {crime && (
        <>
          <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#374151", margin: "12px 0 8px" }}>Crime (Last 90 Days)</h3>
          <p style={{ fontSize: "13px", margin: "0 0 8px" }}>Total incidents: {fmt(crime.total)} | Arrest rate: {fmtPct(crime.arrest_rate)}</p>
          <table style={s.table}>
            <thead><tr><th style={s.th}>Type</th><th style={s.th}>Count</th></tr></thead>
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
          <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#374151", margin: "12px 0 8px" }}>311 Service Requests</h3>
          <p style={{ fontSize: "13px", margin: "0 0 8px" }}>Open requests: {fmt(three11.total)}{three11.oldest_open_days != null ? ` | Oldest: ${three11.oldest_open_days} days` : ""}</p>
        </>
      )}
      {permits && (
        <>
          <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#374151", margin: "12px 0 8px" }}>Building Permits (Last Year)</h3>
          <p style={{ fontSize: "13px", margin: "0 0 8px" }}>Total: {fmt(permits.total)} | Est. cost: {fmtCurrency(permits.total_estimated_cost)}</p>
        </>
      )}
      {violations && (
        <>
          <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#374151", margin: "12px 0 8px" }}>Building Violations</h3>
          <p style={{ fontSize: "13px", margin: "0 0 8px" }}>Total: {fmt(violations.total)} | Open: {fmt(violations.open_count)}</p>
        </>
      )}
      {businesses && (
        <>
          <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#374151", margin: "12px 0 8px" }}>Business Licenses</h3>
          <p style={{ fontSize: "13px", margin: "0 0 8px" }}>Total: {fmt(businesses.total)}</p>
        </>
      )}
    </div>
  );
}

export function ExportReport({ report, onClose }: Props) {
  const reportRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);

  const handleDownload = useCallback(async () => {
    if (!reportRef.current) return;
    setExporting(true);
    try {
      const slug = (report.address || report.communityArea || "chicago")
        .replace(/[^a-zA-Z0-9]+/g, "_")
        .toLowerCase()
        .slice(0, 40);
      const date = new Date().toISOString().slice(0, 10);
      await downloadPDF(reportRef.current, `${slug}_${date}_report.pdf`);
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
        <h2 style={{ color: "#fff", fontSize: "16px", fontWeight: 600, margin: 0 }}>Report Preview</h2>
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
            Print
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
            {exporting ? "Generating PDF..." : "Download PDF"}
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
            Close
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
                    <h1 style={s.h1}>UrbanLayer Site Report</h1>
                    {h.address && <p style={s.subtitle}>{h.address}</p>}
                    {h.communityArea && <p style={s.subtitle}>{h.communityArea}</p>}
                    <p style={{ ...s.subtitle, color: "#999" }}>Generated {h.generatedAt}</p>
                  </div>
                );
              }
              case "map":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <img src={section.content as string} alt="Map" style={s.map} />
                  </div>
                );
              case "property":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <PropertyTable data={section.content as PropertySummary} />
                  </div>
                );
              case "regulatory":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <RegulatoryTable data={section.content as RegulatorySummary} />
                  </div>
                );
              case "incentives":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <IncentivesTable data={section.content as IncentivesSummary} />
                  </div>
                );
              case "neighborhood":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <NeighborhoodTable data={section.content as NeighborhoodSummary} />
                  </div>
                );
              case "safety":
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    <SafetySection data={section.content as { crime: CrimeSummary | null; three11: ThreeOneOneSummary | null; permits: PermitSummary | null; violations: ViolationSummary | null; businesses: BusinessSummary | null }} />
                  </div>
                );
              case "qa": {
                const pairs = section.content as Array<{ question: string; answer: string }>;
                return (
                  <div key={i}>
                    <h2 style={s.h2}>{section.title}</h2>
                    {pairs.map((qa, j) => (
                      <div key={j} style={s.qa}>
                        <p style={s.question}>Q: {qa.question}</p>
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
                        This report is for informational purposes only and does not constitute legal, zoning, or financial advice.
                        Always verify information with official city records and consult qualified professionals before making decisions.
                      </p>
                    )}
                    {d.dataAsOf && <p style={{ margin: "0 0 4px" }}>Data as of: {d.dataAsOf}</p>}
                    {d.dataLag && <p style={{ margin: 0 }}>{d.dataLag}</p>}
                    <p style={{ margin: "8px 0 0", fontSize: "11px", color: "#b45309" }}>
                      Generated by UrbanLayer — Chicago City Intelligence Platform
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
