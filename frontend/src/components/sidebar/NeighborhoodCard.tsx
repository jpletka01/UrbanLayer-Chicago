import { useState } from "react";
import type { CensusTractDemographics, DistributionBucket, NeighborhoodSummary } from "../../lib/types";
import { BarChart } from "./BarChart";
import { CollapsibleCard } from "./CollapsibleCard";

const PeopleIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
  </svg>
);

const CTA_LINE_COLORS: Record<string, string> = {
  Red: "#c60c30",
  Blue: "#00a1de",
  Brown: "#62361b",
  Green: "#009b3a",
  Orange: "#f9461c",
  Purple: "#522398",
  Pink: "#e27ea6",
  Yellow: "#f9e300",
};

function fmtNum(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString();
}

function fmtDollar(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-sm font-semibold text-text-primary">{value}</div>
      <div className="text-[10px] text-text-muted mt-0.5">{label}</div>
    </div>
  );
}

function KV({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value || value === "—") return null;
  return (
    <div className="flex justify-between items-baseline gap-2">
      <span className="text-text-muted text-[11px]">{label}</span>
      <span className="text-text-primary text-[11px] font-mono text-right">{value}</span>
    </div>
  );
}

function scoreColor(score: number): string {
  if (score >= 90) return "#22c55e";
  if (score >= 70) return "#4ade80";
  if (score >= 50) return "#facc15";
  if (score >= 25) return "#f97316";
  return "#ef4444";
}

function ScoreBar({ score, description, label }: { score: number; description: string | null; label: string }) {
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between items-baseline">
        <span className="text-[10px] text-text-muted">{label}</span>
        <span className="text-[11px] text-text-primary font-mono">{score}</span>
      </div>
      <div className="h-1.5 bg-dark-elevated rounded-full overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{ width: `${score}%`, backgroundColor: scoreColor(score) }}
        />
      </div>
      {description && (
        <p className="text-[10px] text-text-muted">{description}</p>
      )}
    </div>
  );
}

function DistSection({ title, bars, defaultOpen = false }: { title: string; bars: DistributionBucket[]; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  if (bars.length === 0) return null;
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 w-full text-left group"
      >
        <svg
          className={`w-2.5 h-2.5 text-text-muted transition-transform ${open ? "rotate-90" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span className="text-[10px] text-text-muted uppercase tracking-wider group-hover:text-text-secondary transition-colors">
          {title}
        </span>
      </button>
      {open && (
        <div className="mt-1.5 ml-1">
          <BarChart bars={bars} />
        </div>
      )}
    </div>
  );
}

function CensusTractSection({ ct }: { ct: CensusTractDemographics }) {
  const tractNum = ct.tract_name || `Tract ${ct.tract_fips}`;
  const incomeContext = ct.city_median_income && ct.median_household_income
    ? ct.median_household_income > ct.city_median_income
      ? `${Math.round((ct.median_household_income / ct.city_median_income - 1) * 100)}% above Chicago`
      : ct.median_household_income < ct.city_median_income
        ? `${Math.round((1 - ct.median_household_income / ct.city_median_income) * 100)}% below Chicago`
        : "at Chicago median"
    : null;

  return (
    <div className="space-y-2 border-t border-dark-border pt-2">
      <span className="text-[10px] text-text-muted uppercase tracking-wider">{tractNum}</span>

      <div className="grid grid-cols-3 gap-2 py-0.5">
        <StatBox label="Population" value={fmtNum(ct.population)} />
        <div className="text-center">
          <div className="text-sm font-semibold text-text-primary">{fmtDollar(ct.median_household_income)}</div>
          <div className="text-[10px] text-text-muted mt-0.5">Med. Income</div>
          {incomeContext && (
            <div className="text-[9px] text-text-muted">{incomeContext}</div>
          )}
        </div>
        <StatBox label="Poverty" value={fmtPct(ct.poverty_rate)} />
      </div>

      <div className="space-y-0.5">
        <KV label="Per Capita Income" value={fmtDollar(ct.per_capita_income)} />
        <KV label="Home Value" value={fmtDollar(ct.median_home_value)} />
        <KV label="Bachelor's+" value={fmtPct(ct.bachelors_or_higher_pct)} />
        <KV label="Foreign Born" value={fmtPct(ct.foreign_born_pct)} />
      </div>

      <div className="space-y-1.5">
        <DistSection title="Age Distribution" bars={ct.age_distribution} defaultOpen />
        <DistSection title="Household Income" bars={ct.income_distribution} />
        <DistSection title="Race & Ethnicity" bars={ct.race_distribution} />
        <DistSection title="Education" bars={ct.education_distribution} />
        <DistSection title="Transportation to Work" bars={ct.transportation_distribution} />
      </div>

      {ct.census_reporter_url && (
        <a
          href={ct.census_reporter_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 underline transition-colors"
        >
          View full profile on Census Reporter
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>
      )}
    </div>
  );
}

export function NeighborhoodCard({ data }: { data: NeighborhoodSummary }) {
  const demo = data.demographics;
  const transit = data.transit;

  return (
    <CollapsibleCard title="Neighborhood" icon={PeopleIcon}>
      <div className="space-y-3">
        {/* Community Area Demographics */}
        {demo && (
          <>
            {/* Headline stats */}
            <div className="grid grid-cols-3 gap-2 py-1">
              <StatBox label="Population" value={fmtNum(demo.population)} />
              <StatBox label="Med. Income" value={fmtDollar(demo.median_household_income)} />
              <StatBox label="Home Value" value={fmtDollar(demo.median_home_value)} />
            </div>

            {/* Secondary stats */}
            <div className="space-y-0.5">
              <KV label="Median Rent" value={fmtDollar(demo.median_gross_rent)} />
              <KV label="Median Age" value={demo.median_age != null ? String(demo.median_age) : null} />
              <KV label="Poverty Rate" value={fmtPct(demo.poverty_rate)} />
              <KV label="Unemployment" value={fmtPct(demo.unemployment_rate)} />
              <KV label="Owner-Occupied" value={fmtPct(demo.owner_occupied_pct)} />
              <KV label="Bachelor's Degree" value={fmtPct(demo.bachelors_degree_pct)} />
              <KV label="Vacancy Rate" value={fmtPct(demo.vacancy_rate)} />
            </div>
          </>
        )}

        {/* Census Tract Demographics */}
        {data.census_tract && <CensusTractSection ct={data.census_tract} />}

        {/* Transit Access */}
        {transit && (transit.nearest_cta_rail || transit.nearest_metra) && (
          <div className="space-y-1.5">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">Transit</span>

            {/* CTA Rail */}
            {transit.nearest_cta_rail && (
              <div className="rounded-lg bg-dark-elevated/60 px-3 py-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[11px] text-text-primary">{transit.nearest_cta_rail}</span>
                  {transit.cta_rail_distance_mi != null && (
                    <span className="text-[10px] text-text-muted font-mono shrink-0">
                      {transit.cta_rail_distance_mi.toFixed(2)} mi
                    </span>
                  )}
                </div>
                {transit.cta_lines.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {transit.cta_lines.map(line => (
                      <span
                        key={line}
                        className="rounded px-1.5 py-0.5 text-[9px] font-medium"
                        style={{
                          backgroundColor: (CTA_LINE_COLORS[line] ?? "#666") + "25",
                          color: CTA_LINE_COLORS[line] ?? "#999",
                          border: `1px solid ${(CTA_LINE_COLORS[line] ?? "#666")}40`,
                        }}
                      >
                        {line}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Metra */}
            {transit.nearest_metra && (
              <div className="rounded-lg bg-dark-elevated/60 px-3 py-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[11px] text-text-primary">{transit.nearest_metra}</span>
                  {transit.metra_distance_mi != null && (
                    <span className="text-[10px] text-text-muted font-mono shrink-0">
                      {transit.metra_distance_mi.toFixed(2)} mi
                    </span>
                  )}
                </div>
                {transit.metra_line && (
                  <p className="text-[10px] text-text-muted mt-0.5">{transit.metra_line}</p>
                )}
              </div>
            )}

            {/* TOD Eligibility */}
            {transit.tod_eligible && (
              <span className="inline-flex items-center gap-1 bg-emerald-500/15 text-emerald-400
                             border border-emerald-500/30 rounded-md px-2 py-0.5 text-[10px]">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                TOD Eligible
                {transit.tod_type && <span className="text-emerald-400/70">({transit.tod_type})</span>}
              </span>
            )}
          </div>
        )}

        {/* Walk Score */}
        {data.walkscore && (data.walkscore.walk_score != null || data.walkscore.transit_score != null || data.walkscore.bike_score != null) && (
          <div className="space-y-2">
            <span className="text-[10px] text-text-muted uppercase tracking-wider">Walk Score</span>
            {data.walkscore.walk_score != null && (
              <ScoreBar score={data.walkscore.walk_score} description={data.walkscore.walk_description} label="Walk" />
            )}
            {data.walkscore.transit_score != null && (
              <ScoreBar score={data.walkscore.transit_score} description={data.walkscore.transit_description} label="Transit" />
            )}
            {data.walkscore.bike_score != null && (
              <ScoreBar score={data.walkscore.bike_score} description={data.walkscore.bike_description} label="Bike" />
            )}
            <a
              href={data.walkscore.ws_link || "https://www.walkscore.com"}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[9px] text-text-muted hover:text-text-secondary transition-colors underline"
            >
              Walk Score®
            </a>
          </div>
        )}

        {/* No data state */}
        {!demo && !transit && !data.walkscore && (
          <p className="text-[11px] text-text-muted">No neighborhood data available.</p>
        )}
      </div>
    </CollapsibleCard>
  );
}
