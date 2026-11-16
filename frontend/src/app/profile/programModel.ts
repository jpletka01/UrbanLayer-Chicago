// A program's page in the right panel (decision Item 99): what an incentive program means for THIS lot, read from the
// Profile, so a visitor can learn it by reading rather than by asking (owner: questions cost money). Pure functions;
// the words live in the `next` catalog. Facts only, no projections and no advice (rule 11): eligibility, dates,
// money already spent, who decides.
import type { ScorecardResponse } from "../../lib/api";
import type { IncentiveAnswer, IncentiveKey } from "./moneyModel";

export interface FundYear { year: number; balance: number; revenue: number | null; spent: number | null }
export interface TifProject { name: string; status: string | null; publicFunds: number | null; privateFunds: number | null; year: string | null }

export interface ProgramDetail {
  key: IncentiveKey;
  answer: IncentiveAnswer;
  /** The district or zone's own name, when the record gives one. */
  name: string | null;
  /** The tract the program is keyed to (OZ, QCT, NMTC). */
  tract: string | null;
  /** TIF only. */
  tif?: {
    start: number | null;
    end: number | null;
    yearsLeft: number | null;
    balance: number | null;
    spentLastYear: number | null;
    reportYear: string | null;
    funds: FundYear[];
    projects: TifProject[];
  };
  /** NMTC only. */
  nmtc?: { povertyRate: number | null; severe: boolean };
  /** City grants in the community area (SBIF is paid from TIF funds; NOF from downtown density fees). */
  grants?: { projects: number; funding: number; byProgram: Record<string, number> } | null;
  /** The provenance period (the report year) behind the answer. */
  period: string | null;
}

const num = (v: unknown): number | null => {
  const n = typeof v === "number" ? v : typeof v === "string" && v.trim() !== "" ? Number(v) : NaN;
  return Number.isFinite(n) ? n : null;
};
const str = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v.trim() : null);

const PROV: Record<IncentiveKey, string> = {
  tif: "incentive.tif", oz: "incentive.opportunity_zone", ez: "incentive.enterprise_zone", qct: "incentive.lihtc", nmtc: "incentive.nmtc",
};

export function programDetail(data: ScorecardResponse, key: IncentiveKey, answer: IncentiveAnswer, now = new Date()): ProgramDetail {
  const inc = data.context?.incentives ?? null;
  const period = data.provenance?.[PROV[key]]?.period ?? null;
  const base: ProgramDetail = { key, answer, name: null, tract: null, period };
  if (!inc) return base;

  if (key === "tif") {
    const funds = (inc.tif_fund_history ?? [])
      .map((r) => ({ year: num(r.year), balance: num(r.fund_balance), revenue: num(r.revenue), spent: num(r.expenditure) }))
      .filter((r): r is FundYear => r.year != null && r.balance != null)
      .sort((a, b) => a.year - b.year);
    const projects = (inc.tif_financials ?? [])
      .map((r) => ({
        name: str(r.project_name) ?? str(r.annual_report_name) ?? "",
        status: str(r.status),
        publicFunds: num(r.public_funds),
        privateFunds: num(r.private_funds),
        year: str(r.report_year),
      }))
      .filter((p) => p.name)
      .sort((a, b) => (b.publicFunds ?? 0) - (a.publicFunds ?? 0));
    const end = inc.tif_end_year ?? null;
    return {
      ...base,
      name: inc.tif_name,
      grants: grantsOf(inc),
      tif: answer === "yes" ? {
        start: inc.tif_year_start ?? null,
        end,
        yearsLeft: end != null ? Math.max(0, end - now.getFullYear()) : null,
        balance: inc.tif_fund_balance ?? null,
        spentLastYear: inc.tif_annual_expenditure ?? inc.tif_total_expenditure ?? null,
        reportYear: funds.length ? String(funds[funds.length - 1].year) : period,
        funds,
        projects,
      } : undefined,
    };
  }
  if (key === "ez") return { ...base, name: inc.enterprise_zone_name };
  if (key === "oz") return { ...base, tract: inc.oz_tract ?? inc.census_tract };
  if (key === "qct") return { ...base, tract: inc.qct_tract ?? inc.census_tract };
  return { ...base, tract: inc.nmtc_tract ?? inc.census_tract, nmtc: { povertyRate: inc.nmtc_poverty_rate, severe: !!inc.nmtc_severe_distress } };
}

function grantsOf(inc: NonNullable<ScorecardResponse["context"]>["incentives"]): ProgramDetail["grants"] {
  const g = inc?.grant_programs;
  if (!g || !g.total_projects) return null;
  return { projects: g.total_projects, funding: g.total_funding, byProgram: g.by_program ?? {} };
}

/** A Census tract id (17031420700) as people write it ("Tract 4207"). */
export function tractLabel(geoid: string | null): string | null {
  if (!geoid || geoid.length < 11) return geoid;
  const t = geoid.slice(5);
  const whole = String(Number(t.slice(0, 4)));
  const dec = t.slice(4);
  return dec === "00" ? whole : `${whole}.${dec}`;
}
