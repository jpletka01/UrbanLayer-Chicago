import { useState, useCallback, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { fetchReport, checkReportAccess, fetchAreaStats, fetchParcelMapLayers, type ScorecardResponse } from "../lib/api";
import type { ParcelQuery } from "../lib/types";
import { useAuthContext } from "../contexts/AuthContext";
import { useSelectedParcel } from "../contexts/SelectedParcelContext";
import ReportPurchasePrompt from "./ReportPurchasePrompt";
import { InvestigateButton } from "./InvestigateButton";
import { setAddress as setTrackingAddress, track } from "../lib/tracking";
import { ScorecardPropertyCard } from "./scorecard/ScorecardPropertyCard";
import { ScorecardComparablesCard } from "./scorecard/ScorecardComparablesCard";
import { ScorecardRegulatoryCard } from "./scorecard/ScorecardRegulatoryCard";
import { ScorecardZoningCard } from "./scorecard/ScorecardZoningCard";
import { ScorecardIncentivesCard } from "./scorecard/ScorecardIncentivesCard";
import { ScorecardViolationsCard } from "./scorecard/ScorecardViolationsCard";
import { ScorecardEnvironmentCard } from "./scorecard/ScorecardEnvironmentCard";
import { ProfileModule, SubSection } from "./scorecard/ProfileModule";
import { KpiStrip, type KpiTile } from "./scorecard/KpiStrip";
import type { NeighborhoodSummary } from "../lib/types";
import { buildScorecardCSV, downloadCSV, buildFilenameSlug } from "../lib/csvExport";
import { VerdictBand, VerdictMethodology, verdictDotClass } from "./VerdictBand";
import { InfoTooltip } from "./InfoTooltip";
import { computeVerdict, type CardId } from "../lib/scorecardVerdict";
import { humanizeShoutyCase } from "../lib/format";
import PageHeader from "./PageHeader";
import { AddressInput } from "./AddressInput";
import { ScorecardFeedback } from "./ScorecardFeedback";
import { MiniChatDock, type DockSignal } from "./MiniChatDock";
import { ParcelMap, type ParcelMapLayers } from "./scorecard/ParcelMap";

// Classify a failed address-resolution input: did the user type an address
// (a typo to fix here) or a code question (redirect to the analyst)? Computed
// once when the error is set, never on every render.
function classifyFailedInput(text: string): "address" | "question" {
  const t = text.trim().toLowerCase();
  if (!t) return "address";
  if (t.endsWith("?")) return "question";
  const QUESTION_WORDS = ["what", "how", "can", "when", "where", "why", "is", "are", "do", "does", "should", "which", "could", "may", "who"];
  const words = t.split(/\s+/);
  if (QUESTION_WORDS.includes(words[0])) return "question";
  // Addresses carry a street number; a multi-word phrase with no digit reads as prose.
  if (!/\d/.test(t) && words.length >= 4) return "question";
  return "address";
}

// Dash-format a 14-digit PIN for display (assessor convention: 2-2-3-3-4).
function formatPin(pin: string): string {
  if (pin.length !== 14) return pin;
  return `${pin.slice(0, 2)}-${pin.slice(2, 4)}-${pin.slice(4, 7)}-${pin.slice(7, 10)}-${pin.slice(10)}`;
}

// Community-area benchmark aggregates for the KPI band (see backend
// retrieval/area_stats.py). All-None when the Discovery index is absent —
// the tiles then render no benchmark line.
interface AreaStats {
  community_area: number;
  n_parcels: number;
  median_assessed: number | null;
  median_av_per_land_sqft: number | null;
}

// Deterministic class-norm effective tax rate: Chicago composite rate (~7% of
// EAV) × state equalizer (~3.0) ≈ 21% of assessed value → norm = 0.21 × the
// class's assessment level (residential 10% → ~2.1%, commercial 25% → ~5.3%).
// The Discovery index holds no tax bills, so this published-rate arithmetic is
// the honest comparison (an "area median eff-rate" would be fabricated).
const EFF_RATE_PER_ASSESSMENT_LEVEL = 0.21;

const crimeIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0-10.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
  </svg>
);

const cleanIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

function CrimeYoYBlock({ data }: { data: ScorecardResponse }) {
  const { t } = useTranslation("pages");
  const crime = data.context.crime_last_90d;
  if (!crime) return null;
  const yoy = (crime.yoy ?? []).slice(0, 5);
  const maxCount = Math.max(1, ...yoy.flatMap((i) => [i.current_count, i.prior_year_count ?? 0]));
  return (
    <SubSection
      icon={crimeIcon}
      title={t("scorecard.crimeArea")}
      meta={t("scorecard.incidents90d", { count: crime.total })}
    >
      <div className="space-y-3">
        {/* Paired bars: prior period (neutral) vs current (accent) — the trend
            reads as marks, not a mono table. Prior-year base keeps big swings
            honest (54 → 209 reads differently than +287%). */}
        {yoy.length > 0 && (
          <div className="space-y-2">
            <div className="text-micro text-text-muted">{crime.yoy_period || t("scorecard.yearOverYear")}</div>
            {yoy.map((item) => (
              <div key={item.category} className="grid grid-cols-[minmax(0,38%)_1fr_auto] items-center gap-x-3">
                <span className="text-caption text-text-secondary truncate">{humanizeShoutyCase(item.category)}</span>
                <span className="min-w-0">
                  <span className="block h-2 rounded-r bg-accent" style={{ width: `${Math.max((item.current_count / maxCount) * 100, 1.5)}%` }} />
                  <span className="block h-2 rounded-r bg-dark-border-strong mt-0.5" style={{ width: `${Math.max(((item.prior_year_count ?? 0) / maxCount) * 100, 1.5)}%` }} />
                </span>
                <span className="text-micro font-mono text-right whitespace-nowrap">
                  <span className="text-text-primary">{item.current_count}</span>
                  <span className="text-text-muted"> / {item.prior_year_count ?? 0}</span>
                  <span className={`ml-2 ${
                    (item.change_pct ?? 0) > 0 ? "text-state-negative" : (item.change_pct ?? 0) < 0 ? "text-state-positive" : "text-text-muted"
                  }`}>
                    {item.change_pct == null ? t("scorecard.newCategory") : `${item.change_pct > 0 ? "+" : ""}${item.change_pct}%`}
                  </span>
                </span>
              </div>
            ))}
            <div className="flex gap-4 text-micro text-text-muted">
              <span><span className="inline-block w-2.5 h-2 rounded-r bg-accent mr-1.5 align-middle" aria-hidden />{t("scorecard.crimeCurrent")}</span>
              <span><span className="inline-block w-2.5 h-2 rounded-r bg-dark-border-strong mr-1.5 align-middle" aria-hidden />{t("scorecard.crimePrior")}</span>
              <span>{t("scorecard.arrestRate")} <span className="font-mono text-text-secondary">{(crime.arrest_rate * 100).toFixed(1)}%</span></span>
            </div>
          </div>
        )}
      </div>
    </SubSection>
  );
}

/** Designed area-context block: access + demographics as a stat row, ward
    representation as a line. Every number here describes the community area —
    the module header carries the scope label. */
function NeighborhoodBlock({ data }: { data: NeighborhoodSummary }) {
  const { t } = useTranslation("pages");
  const demo = data.demographics;
  const ws = data.walkscore;
  const tr = data.transit;
  // Walk Score description strings arrive in English from the API — translate
  // the known canonical set, pass anything novel through untouched.
  const walkDesc = (s: string | null | undefined): string | undefined => {
    if (!s) return undefined;
    const slug = s.toLowerCase().replace(/[^a-z0-9]+/g, "_");
    return t(`scorecard.walkDesc.${slug}`, { defaultValue: s });
  };
  const stats: Array<{ label: string; value: string; sub?: string; tip?: string }> = [];
  if (ws?.walk_score != null) {
    stats.push({ label: t("scorecard.area.walk"), value: String(ws.walk_score), sub: walkDesc(ws.walk_description), tip: t("scorecard.tips.walkScore") });
  }
  if (ws?.transit_score != null) {
    stats.push({ label: t("scorecard.area.transitScore"), value: String(ws.transit_score), sub: walkDesc(ws.transit_description), tip: t("scorecard.tips.transitScore") });
  }
  if (tr?.nearest_cta_rail && tr.cta_rail_distance_mi != null) {
    stats.push({
      label: t("scorecard.area.nearestRail"),
      value: tr.nearest_cta_rail,
      sub: `${tr.cta_rail_distance_mi.toFixed(1)} mi${tr.cta_lines.length ? ` · ${tr.cta_lines.join(", ")}` : ""}`,
    });
  }
  if (demo?.median_household_income != null) {
    stats.push({ label: t("scorecard.area.income"), value: `$${Math.round(demo.median_household_income / 1000)}K` });
  }
  if (demo?.median_gross_rent != null) {
    stats.push({ label: t("scorecard.area.rent"), value: `$${Math.round(demo.median_gross_rent).toLocaleString()}` });
  }
  if (demo?.population != null) {
    stats.push({
      label: t("scorecard.area.population"), value: demo.population.toLocaleString(),
      sub: demo.owner_occupied_pct != null ? t("scorecard.area.ownerOcc", { pct: Math.round(demo.owner_occupied_pct) }) : undefined,
    });
  }
  if (stats.length === 0 && !data.ward) return null;
  return (
    <div className="space-y-4">
      {stats.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-x-6 gap-y-4">
          {stats.map((s) => (
            <div key={s.label} className="min-w-0">
              <div className="text-overline uppercase tracking-wider text-text-muted">
                {s.tip ? (
                  <InfoTooltip content={{ label: s.label, description: s.tip, bullets: [] }}>{s.label}</InfoTooltip>
                ) : (
                  s.label
                )}
              </div>
              <div className="text-subtitle text-text-primary mt-0.5 truncate">{s.value}</div>
              {s.sub && <div className="text-caption text-text-muted mt-0.5 leading-snug">{s.sub}</div>}
            </div>
          ))}
        </div>
      )}
      {data.ward?.ward && (
        <p className="text-caption text-text-secondary">
          {t("scorecard.wardLabel", { ward: data.ward.ward })}
          {data.ward.alderman && <span> · {data.ward.alderman}</span>}
          {tr?.tod_eligible && (
            <span className="text-state-positive">
              {" · "}
              <InfoTooltip term="in_tod_area">{t("scorecard.area.todEligible")}</InfoTooltip>
            </span>
          )}
        </p>
      )}
    </div>
  );
}

const address311Icon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
  </svg>
);

function Address311Block({ data }: { data: ScorecardResponse }) {
  const { t } = useTranslation("pages");
  const addr311 = data.context.address_311;
  if (!addr311) return null;
  return (
    <SubSection
      icon={address311Icon}
      className="flex-1"
      title={t("scorecard.311atAddress")}
      meta={`${addr311.total} ${t("scorecard.pastYear")}`}
    >
      <div className="space-y-2">
        {addr311.open_count > 0 && (
          <div className="text-micro text-state-warning">{t("scorecard.openComplaints", { count: addr311.open_count })}</div>
        )}
        {addr311.high_risk_flags.length > 0 && (
          <div className="space-y-1">
            <div className="text-micro text-state-negative font-medium">{t("scorecard.highRiskFlags")}</div>
            {addr311.high_risk_flags.map((flag) => (
              <div key={flag} className="text-micro text-state-negative flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-state-negative flex-shrink-0" />
                {humanizeShoutyCase(flag)}
              </div>
            ))}
          </div>
        )}
        {Object.entries(addr311.by_type).length > 0 && (
          <div className="space-y-1">
            {Object.entries(addr311.by_type).slice(0, 5).map(([type, count]) => (
              <div key={type} className="flex items-center justify-between text-micro">
                <span className="text-text-secondary truncate flex-1 mr-2">{humanizeShoutyCase(type)}</span>
                <span className="font-mono text-text-primary">{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </SubSection>
  );
}

function ScorecardSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="bg-dark-surface border border-dark-border rounded-xl h-32" />
      <div className="bg-dark-surface border border-dark-border rounded-xl h-24" />
      <div className="bg-dark-surface border border-dark-border rounded-xl h-64" />
    </div>
  );
}

// Dashboard section registry — nav labels + presence drive the sticky rail.
const MODULE_IDS = ["module-build", "module-economics", "module-market", "module-record", "module-area"] as const;
type ModuleId = (typeof MODULE_IDS)[number];

export default function ScorecardPage() {
  const { t } = useTranslation("pages");
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, checkAuth } = useAuthContext();
  const { parcel, select } = useSelectedParcel();
  const [address, setAddress] = useState(searchParams.get("address") || "");
  const [data, setData] = useState<ScorecardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Shape of the failed input, computed once when the error is set: "address"
  // (typo — keep the search prominent) vs "question" (redirect to the analyst).
  const [errorShape, setErrorShape] = useState<"address" | "question" | null>(null);
  const [errorQuery, setErrorQuery] = useState("");
  const [searched, setSearched] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [showPurchasePrompt, setShowPurchasePrompt] = useState(false);
  const [reportAccess, setReportAccess] = useState<{ has_access: boolean; reason: string } | null>(null);
  const [areaStats, setAreaStats] = useState<AreaStats | null>(null);
  const [mapLayers, setMapLayers] = useState<ParcelMapLayers | null>(null);

  const isPro = user?.tier === "premium" || user?.tier === "admin";
  const hasReportAccess = isPro || reportAccess?.has_access === true;

  const triggerDownload = useCallback(async () => {
    if (!parcel || (!parcel.pin && !parcel.address)) return;
    setDownloading(true);
    try {
      const blob = await fetchReport(parcel);
      if (blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        const slug = (parcel.address ?? `pin_${parcel.pin}`).replace(/[^a-z0-9]+/gi, "_").toLowerCase();
        a.download = `${slug}_zoning_report.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } finally {
      setDownloading(false);
    }
  }, [parcel]);

  const handleDownloadPdf = useCallback(async () => {
    if (!parcel || (!parcel.pin && !parcel.address)) return;
    if (hasReportAccess) {
      await triggerDownload();
    } else {
      setShowPurchasePrompt(true);
    }
  }, [parcel, hasReportAccess, triggerDownload]);

  const runQuery = useCallback(async (query: ParcelQuery) => {
    setLoading(true);
    setError(null);
    setErrorShape(null);
    setSearched(true);
    const result = await select(query);
    if (result) {
      setData(result);
      if (result.address) {
        setAddress(result.address);
        setTrackingAddress(result.address);
      }
      track("scorecard_view", {
        confidence: result.resolved_confidence,
        pin_resolved: !!result.resolved_pin,
      });
      // Canonicalize the URL on a confirmed parcel; pin-less results keep
      // their original params. report_purchased survives the rewrite so the
      // post-purchase auto-download still fires.
      if (result.resolved_pin) {
        setSearchParams((prev) => {
          const next = new URLSearchParams({ pin: result.resolved_pin! });
          // address is display-only; keep the previous one when a pin-keyed
          // re-entry resolves without an address so the canonical URL is stable
          const displayAddress = result.address ?? prev.get("address");
          if (displayAddress) next.set("address", displayAddress);
          const purchased = prev.get("report_purchased");
          if (purchased) next.set("report_purchased", purchased);
          return next;
        }, { replace: true });
      }
    } else {
      const isAddress = "address" in query;
      const failedText = isAddress ? query.address : "";
      setError(t(isAddress ? "scorecard.addressNotFound" : "scorecard.locationNotFound"));
      // pin/lat-lon failures have no typed text → treat as address (no question to redirect).
      setErrorShape(isAddress ? classifyFailedInput(failedText) : "address");
      setErrorQuery(failedText);
      setData(null);
    }
    setLoading(false);
  }, [t, select, setSearchParams]);

  const doSearch = useCallback((query: string) => {
    if (!query.trim()) return;
    // Remember the submitted text so the prominent shell can re-seed the input
    // after a failed lookup (the shells swap during loading, dropping DOM state).
    setAddress(query.trim());
    runQuery({ address: query.trim() });
  }, [runQuery]);

  useEffect(() => {
    const pin = searchParams.get("pin");
    const q = searchParams.get("address");
    const lat = searchParams.get("lat");
    const lon = searchParams.get("lon");
    if (pin) {
      if (q) setAddress(q);
      runQuery({ pin });
    } else if (q) {
      setAddress(q);
      runQuery({ address: q });
    } else if (lat && lon) {
      runQuery({ lat: parseFloat(lat), lon: parseFloat(lon) });
    }
  }, []);

  // Fetch report access when profile data loads (for non-pro users)
  useEffect(() => {
    if (!data || !parcel || isPro) return;
    checkReportAccess(parcel).then(setReportAccess);
  }, [data, isPro, parcel]);

  useEffect(() => {
    if (data?.address) setTrackingAddress(data.address);
    return () => setTrackingAddress(null);
  }, [data?.address]);

  // Benchmark aggregates + module-map geometry layers, fetched once per parcel.
  useEffect(() => {
    if (!data) { setAreaStats(null); setMapLayers(null); return; }
    let cancelled = false;
    if (data.community_area != null) {
      fetchAreaStats(data.community_area).then((s) => { if (!cancelled) setAreaStats(s); });
    }
    const mlat = data.resolved_lat ?? data.lat;
    const mlon = data.resolved_lon ?? data.lon;
    fetchParcelMapLayers(mlat, mlon).then((l) => { if (!cancelled) setMapLayers(l); });
    return () => { cancelled = true; };
  }, [data]);

  // Handle post-purchase redirect: auto-download the report
  useEffect(() => {
    if (!data || !parcel || (!parcel.pin && !parcel.address)) return;
    if (searchParams.get("report_purchased") !== "1") return;
    setReportAccess({ has_access: true, reason: "purchased" });
    triggerDownload();
    const url = new URL(window.location.href);
    url.searchParams.delete("report_purchased");
    window.history.replaceState({}, "", url.toString());
  }, [data, parcel, searchParams, triggerDownload]);

  const ctx = data?.context;
  const zoning = ctx?.parcel_zoning;
  const addr = data?.address || ctx?.property?.address || "";

  // The single boolean that selects the layout shell: the search box is
  // prominent exactly when re-entering an address is the user's next action
  // (empty + address-typo). It demotes to a compact bar whenever something
  // else owns the primary area — a load, a result, or a code-question redirect.
  const searchProminent = !loading && !data && errorShape !== "question";

  const zdef = data?.zone_definition;

  // Verdict: leads the profile with a deterministic scored conclusion +
  // module-linked evidence + ONE next step. Thresholds calibrated & signed off
  // 2026-06-29 — see lib/scorecardVerdict.ts (visual redesign only, logic untouched).
  const verdict = data && ctx ? computeVerdict(data, t) : null;

  // KPI strip: the level-1 numbers, each deep-linking to its evidence module.
  // Tiles with missing data are simply omitted (the strip renders at ≥2).
  const fmtMoneyCompact = (n: number): string =>
    n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`
    : n >= 1_000 ? `$${Math.round(n / 1_000)}K`
    : `$${Math.round(n)}`;
  const tiles: KpiTile[] = [];
  if (verdict && ctx) {
    if (zoning) {
      tiles.push({
        anchor: "zoning",
        label: t("scorecard.tiles.zoning"),
        value: zoning.zone_class,
        tip: t("scorecard.tips.zoningTile"),
        sub: verdict.signals.allowedFar != null
          ? t("scorecard.tiles.zoningFar", { far: verdict.signals.allowedFar.toFixed(1) })
          : t("scorecard.verdict.signal.entitlementDefined"),
      });
    }
    const av = ctx.property?.total_assessed_value;
    const estTax = ctx.property?.estimated_annual_tax;
    if (av != null) {
      // Δ since the earliest assessment year, direction-colored (state tokens);
      // second line benchmarks the subject's AV/land-ft² against the area median.
      const hist = (ctx.property?.assessment_history ?? [])
        .filter((a) => a.year != null && a.total != null && a.total > 0)
        .sort((a, b) => a.year! - b.year!);
      const first = hist[0];
      const deltaPct = first?.total && first.total > 0
        ? Math.round(((av - first.total) / first.total) * 100)
        : null;
      const land = ctx.property?.land_sqft;
      const avPsf = land && land > 0 ? av / land : null;
      const medPsf = areaStats?.median_av_per_land_sqft ?? null;
      tiles.push({
        anchor: "property",
        label: t("scorecard.tiles.assessed"),
        value: fmtMoneyCompact(av),
        tip: t("scorecard.tips.assessedTile"),
        sub: (
          <>
            {deltaPct != null && first.year != null && (
              <span className={deltaPct > 0 ? "text-state-positive" : deltaPct < 0 ? "text-state-negative" : ""}>
                <span aria-hidden>{deltaPct > 0 ? "▲" : deltaPct < 0 ? "▼" : "—"}</span>{" "}
                {deltaPct === 0
                  ? t("scorecard.tiles.assessedFlat", { year: first.year })
                  : t("scorecard.tiles.assessedDelta", { pct: `${Math.abs(deltaPct)}%`, year: first.year })}
              </span>
            )}
            {avPsf != null && medPsf != null && medPsf > 0 && (
              <span className="block">
                {t("scorecard.tiles.avBenchmark", {
                  psf: Math.round(avPsf), median: Math.round(medPsf),
                })}
              </span>
            )}
          </>
        ),
      });
    }
    if (estTax != null) {
      const rate = ctx.property?.effective_tax_rate;
      const level = ctx.property?.assessment_level;
      const norm = level != null ? level * EFF_RATE_PER_ASSESSMENT_LEVEL : null;
      tiles.push({
        anchor: "property",
        label: t("scorecard.tiles.tax"),
        value: `${fmtMoneyCompact(estTax)}/yr`,
        tip: t("scorecard.tips.taxTile"),
        sub: rate != null ? (
          <>
            {t("scorecard.tiles.taxRate", { rate: (rate * 100).toFixed(2) })}
            {norm != null && (
              <span className="block">
                {t("scorecard.tiles.taxNorm", { norm: (norm * 100).toFixed(1) })}
              </span>
            )}
          </>
        ) : undefined,
      });
    }
    if (data?.comparables?.median_sale_price != null) {
      tiles.push({
        anchor: "comparables",
        label: t("scorecard.tiles.comps"),
        value: fmtMoneyCompact(data.comparables.median_sale_price),
        tip: t("scorecard.tips.compsTile"),
        sub: t("scorecard.tiles.compsSub", { count: data.comparables.sales_volume }),
      });
    }
  }

  // Per-module takeaways — ONE deterministic, parcel-specific insight sentence
  // per module (the "so what" a first-time reader actually reads). Templated
  // like verdict reasons; null when there's nothing honest to say.
  const takeaways: Record<string, string | null> = { build: null, costs: null, market: null, record: null };
  if (ctx) {
    const far = verdict?.signals.allowedFar;
    const landSq = ctx.property?.land_sqft;
    if (zoning && far != null && far > 0 && landSq && landSq > 0) {
      let s = t("scorecard.takeaway.build", {
        zone: zoning.zone_class, sqft: Math.round(far * landSq).toLocaleString(),
      });
      const exFar = verdict?.signals.existingFar;
      if (exFar != null) {
        s += " " + t("scorecard.takeaway.buildUsed", { pct: Math.min(Math.round((exFar / far) * 100), 100) });
      }
      takeaways.build = s;
    }
    const taxNow = ctx.property?.estimated_annual_tax;
    const rateNow = ctx.property?.effective_tax_rate;
    const levelNow = ctx.property?.assessment_level;
    if (taxNow != null && rateNow != null) {
      let s = t("scorecard.takeaway.costs", {
        year: ctx.property?.tax_year ?? "", tax: `$${Math.round(taxNow).toLocaleString()}`,
        rate: (rateNow * 100).toFixed(2),
      });
      const norm = levelNow != null ? levelNow * EFF_RATE_PER_ASSESSMENT_LEVEL : null;
      if (norm && norm > 0) {
        const ratio = rateNow / norm;
        if (ratio >= 1.3) s += " " + t("scorecard.takeaway.costsHigh", { x: ratio.toFixed(1) });
        else if (ratio <= 0.7) s += " " + t("scorecard.takeaway.costsLow");
        else s += " " + t("scorecard.takeaway.costsTypical");
      }
      takeaways.costs = s;
    }
    if (data?.comparables?.median_sale_price != null) {
      let s = t("scorecard.takeaway.market", {
        count: data.comparables.sales_volume,
        median: fmtMoneyCompact(data.comparables.median_sale_price),
      });
      if ((data.comparables.sales_volume ?? 0) < 3) s += " " + t("scorecard.takeaway.marketThin");
      takeaways.market = s;
    }
    const recParts: string[] = [];
    if (ctx.violations) {
      recParts.push(t("scorecard.takeaway.recordViolations", {
        count: ctx.violations.total, open: ctx.violations.open_count,
      }));
    } else if (data?.violations_checked) {
      recParts.push(t("scorecard.takeaway.recordClean"));
    }
    if (ctx.address_311) recParts.push(t("scorecard.takeaway.record311", { count: ctx.address_311.total }));
    takeaways.record = recParts.join(" ") || null;
  }

  // Sticky condensed verdict: once the lead scrolls out of view, a compact strip
  // (tone dot + headline + tile values) keeps the conclusion and a way back in
  // reach on a long page.
  const bandRef = useRef<HTMLDivElement | null>(null);
  const [bandAway, setBandAway] = useState(false);
  useEffect(() => {
    const el = bandRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setBandAway(!e.isIntersecting && e.boundingClientRect.top < 0));
    io.observe(el);
    return () => io.disconnect();
  }, [data]);

  const scrollToCard = (anchor: CardId | string) => {
    document.getElementById(`scorecard-card-${anchor}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Module presence — drives both rendering and the sticky section rail.
  const hasBuild = !!(zdef || ctx?.regulatory);
  const hasEconomics = !!(ctx?.property || ctx?.incentives);
  const hasMarket = !!(data?.comparables && data.comparables.sales.length > 0);
  const hasRecord = !!(ctx && (ctx.violations || data?.violations_checked || ctx.regulatory?.flood_zone
    || (ctx.regulatory?.brownfield_sites.length ?? 0) > 0 || ctx.address_311));
  const modulePresence: Record<ModuleId, boolean> = {
    "module-build": hasBuild,
    "module-economics": hasEconomics,
    "module-market": hasMarket,
    "module-record": hasRecord,
    "module-area": !!(data?.context.crime_last_90d || ctx?.neighborhood),
  };
  const navSections = MODULE_IDS.filter((id) => modulePresence[id]);

  // Scrollspy for the section rail — topmost intersecting module wins.
  const [activeSection, setActiveSection] = useState<ModuleId | null>(null);
  useEffect(() => {
    if (!data) return;
    const io = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible[0]) setActiveSection(visible[0].target.id as ModuleId);
    }, { rootMargin: "-15% 0px -65% 0px" });
    navSections.forEach((id) => {
      const el = document.getElementById(id);
      if (el) io.observe(el);
    });
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, navSections.join(",")]);

  const jumpToModule = (id: ModuleId) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Quick-chat dock: every on-page ask (module ask chips, verdict next-step,
  // the header ask button) opens/sends in the dock instead of navigating away.
  // The full workspace stays reachable through the dock's escalation link.
  const [dockSignal, setDockSignal] = useState<DockSignal | null>(null);
  const askDock = (question: string | null) =>
    setDockSignal({ question, id: Date.now() });

  const verdictChat = (question: string) => {
    track("investigate_click", { card_name: "verdict" });
    askDock(question);
  };

  // ONE ask affordance per module (replaces the per-card chip sprawl) — the
  // module's most useful grounded question, opened in the dock.
  const moduleAsk = (cardName: string, question: string) => (
    <InvestigateButton
      variant="chip"
      question={question}
      label={t("scorecard.askModule")}
      cardName={cardName}
      pin={parcel?.pin}
      onAsk={askDock}
    />
  );

  return (
    <div className="min-h-screen bg-dark-bg text-text-primary">
      <PageHeader
        contextRight={data && ctx && !loading ? (
          <button
            type="button"
            title={t("scorecard.downloadCsv")}
            aria-label={t("scorecard.downloadCsv")}
            onClick={() => {
              const slug = buildFilenameSlug(data.address || "property");
              const date = new Date().toISOString().slice(0, 10);
              downloadCSV(buildScorecardCSV(ctx, data.address ?? "", data.comparables), `${slug}_scorecard_${date}.csv`);
            }}
            className="p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
          </button>
        ) : undefined}
      />

      {/* Contained column (~74% of a 1440 viewport, dashboard-standard): the
          full-bleed 110rem canvas stretched line lengths and left half-empty
          bands — containment IS the hierarchy. pb-24 clears the dock so the
          footer is never hidden. */}
      <main className={`w-full max-w-7xl mx-auto px-4 md:px-8 py-8 ${data && !loading ? "pb-24" : ""}`}>
        {/* Search shell — prominent (empty / address-typo) vs compact (loading /
            success / code-question redirect). One boolean, two shells. */}
        {searchProminent ? (
          <div className="max-w-2xl mx-auto mb-8">
            <h1 className="text-section mb-2">{t("scorecard.title")}</h1>
            <p className="text-body text-text-muted mb-4">
              {t("scorecard.subtitle")}
            </p>
            {/* Same component as the homepage hero (autocomplete included) — the
                search experience must not degrade between surfaces. key re-seeds
                the typed text after a failed lookup swaps the shells. */}
            <AddressInput
              key={`prominent-${address}`}
              variant="page"
              size="md"
              defaultValue={address}
              placeholder="1601 N Milwaukee Ave"
              onSubmit={doSearch}
              busy={loading}
            />
            {error && errorShape === "address" && (
              <div className="mt-3 text-body text-state-negative bg-state-negative/10 border border-state-negative/20 rounded-lg px-4 py-2.5">
                <div>{error}</div>
                <button
                  type="button"
                  onClick={() => navigate(`/?q=${encodeURIComponent(errorQuery)}`)}
                  className="mt-1.5 text-caption text-text-secondary hover:text-accent transition-colors"
                >
                  {t("scorecard.codeRedirect.orAskAnalyst")}
                </button>
              </div>
            )}
            {searched && !data && !error && (
              <div className="mt-3 text-body text-text-muted">{t("scorecard.noResults")}</div>
            )}
          </div>
        ) : (
          <div className="max-w-2xl mx-auto mb-6">
            {/* Compact re-search: same shared component at the homepage's md
                scale (the sm step read as a different control — Jack 2026-07-07).
                Empty by design — the loaded address lives in the hero below. */}
            <AddressInput
              variant="page"
              size="md"
              placeholder={t("scorecard.searchAnother")}
              onSubmit={doSearch}
              busy={loading}
            />
          </div>
        )}

        {loading && <ScorecardSkeleton />}

        {/* Code-question redirect (state 5): neutral surface, NOT an error color —
            reframes "wrong box" as "right tool" and hands the exact text to the
            analyst via the existing ?q= auto-send. */}
        {errorShape === "question" && !loading && (
          <div className="max-w-2xl mx-auto mb-8 bg-dark-surface border border-dark-border rounded-xl p-5">
            <h2 className="text-subtitle text-text-primary mb-1.5">{t("scorecard.codeRedirect.title")}</h2>
            <p className="text-body text-text-secondary mb-4">{t("scorecard.codeRedirect.body")}</p>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => navigate(`/?q=${encodeURIComponent(errorQuery)}`)}
                className="px-4 py-2 bg-action hover:bg-action-hover text-text-on-accent text-title rounded-lg transition-colors"
              >
                {t("scorecard.codeRedirect.askAnalyst")} →
              </button>
              <button
                type="button"
                onClick={() => { setError(null); setErrorShape(null); setData(null); setSearched(false); setAddress(""); }}
                className="text-body text-text-secondary hover:text-text-primary transition-colors"
              >
                {t("scorecard.codeRedirect.searchInstead")}
              </button>
            </div>
          </div>
        )}

        {data && ctx && !loading && (
          <div>
            {/* ── Hero: the place, the read, the map — nothing else ─────────
                Provenance compresses into ONE meta line; feedback lives in the
                page footer; ask/CSV chips are gone (dock FAB + nav export). */}
            <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(320px,42%)] lg:gap-10 mb-8">
              <div className="min-w-0">
                <h2 className="text-section text-text-primary">
                  {data.address || ctx.property?.address ||
                    (parcel?.pin ? `PIN ${formatPin(parcel.pin)}` : t("scorecard.addressUnavailable"))}
                </h2>
                <div className="text-body text-text-muted mt-1">
                  {[
                    data.community_area_name,
                    ctx.neighborhood?.ward ? t("scorecard.wardLabel", { ward: ctx.neighborhood.ward.ward }) : null,
                  ].filter(Boolean).join(" · ")}
                </div>

                {/* Verdict lead — the conclusion, phrase explained on hover */}
                {verdict && (
                  <div ref={bandRef} className="mt-6">
                    <VerdictBand verdict={verdict} onChat={verdictChat} onScrollTo={scrollToCard} />
                  </div>
                )}

                {/* The ONE money action — a bare violet button, no card; the
                    full sell stays in the purchase modal + sample PDF. */}
                <div className="flex flex-wrap items-center gap-3 mt-2">
                  <button
                    type="button"
                    onClick={handleDownloadPdf}
                    disabled={downloading}
                    className="px-4 py-2 rounded-lg bg-highlight-fill text-highlight-fg hover:opacity-90 transition-opacity text-title disabled:opacity-60"
                  >
                    {downloading
                      ? t("scorecard.reportCTA.generating")
                      : hasReportAccess
                        ? t("scorecard.reportCTA.download")
                        : `${t("scorecard.reportCTA.title")} · $25`}
                  </button>
                  <a
                    href="/sample-report.pdf"
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => track("sample_report_click", { source: "hero_link" })}
                    className="text-caption text-text-muted hover:text-text-secondary transition-colors"
                  >
                    {t("scorecard.reportCTA.viewSample")} ↗
                  </a>
                </div>

                {data.partial_failures.length > 0 && (
                  <div className="mt-4 text-micro text-state-warning">
                    {t("scorecard.someDataUnavailable", { sources: data.partial_failures.join(", ") })}
                  </div>
                )}

                {/* Provenance — one quiet meta line, the only one on the page */}
                <div className="flex items-center gap-3 flex-wrap mt-5 text-micro text-text-muted">
                  {parcel?.pin && (
                    <a
                      href={`https://www.cookcountyassessor.com/pin/${parcel.pin}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-text-secondary hover:text-accent transition-colors"
                    >
                      PIN {formatPin(parcel.pin)} ↗
                    </a>
                  )}
                  {parcel && (parcel.pin === null ? (
                    <InfoTooltip content={{ label: t("scorecard.badges.unconfirmed"), description: t("scorecard.badges.unconfirmedTitle"), bullets: [] }}>
                      <span className="text-state-warning">{t("scorecard.badges.unconfirmed")}</span>
                    </InfoTooltip>
                  ) : parcel.confidence === "authoritative" ? (
                    <InfoTooltip content={{ label: t("scorecard.badges.exact"), description: t("scorecard.badges.exactTitle"), bullets: [] }}>
                      <span className="text-state-positive">✓ {t("scorecard.badges.exact")}</span>
                    </InfoTooltip>
                  ) : (
                    <InfoTooltip content={{ label: t("scorecard.badges.approximate"), description: t("scorecard.badges.approximateTitle"), bullets: [] }}>
                      <span className="text-state-warning">{t("scorecard.badges.approximate")}</span>
                    </InfoTooltip>
                  ))}
                  {data.context.data_as_of && (
                    <span>{t("scorecard.dataAsOf", { date: data.context.data_as_of })}</span>
                  )}
                </div>

                {/* Methodology — provenance, so it lives with the meta line
                    (not between the verdict action and the report button). */}
                {verdict && (
                  <div className="mt-2">
                    <VerdictMethodology verdict={verdict} />
                  </div>
                )}
              </div>

              {/* The place map — satellite default, parcel outline, comps, transit */}
              <div className="mt-6 lg:mt-0 h-72 lg:h-auto lg:min-h-[24rem]">
                <ParcelMap
                  variant="place"
                  lat={data.resolved_lat ?? data.lat}
                  lon={data.resolved_lon ?? data.lon}
                  parcelGeometry={(ctx.property?.parcel_geometry as GeoJSON.Geometry | null) ?? null}
                  comps={data.comparables?.sales}
                  showTransit
                  className="h-full"
                />
              </div>
            </div>

            {/* KPI band — the level-1 numbers row */}
            <KpiStrip tiles={tiles} onScrollTo={scrollToCard} />

            {/* Condensed verdict strip — appears when the lead scrolls away */}
            {verdict && bandAway && (
              <div className="fixed top-[4.25rem] left-1/2 -translate-x-1/2 z-30 w-[calc(100%-2rem)] max-w-7xl">
                <button
                  type="button"
                  onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
                  aria-label={t("scorecard.backToVerdict")}
                  className="w-full flex items-center gap-3 rounded-lg border border-dark-border bg-dark-surface/95 backdrop-blur px-4 py-2 shadow-card text-left hover:border-dark-border-strong transition-colors"
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 ${verdictDotClass(verdict.category)}`} aria-hidden />
                  <span className="text-caption text-text-primary truncate">{verdict.headline}</span>
                  <span className="ml-auto hidden md:flex items-center gap-4 shrink-0">
                    {tiles.slice(0, 4).map((tile) => (
                      <span key={tile.label} className="text-caption text-text-secondary">
                        {tile.value} <span className="text-text-muted">{tile.label}</span>
                      </span>
                    ))}
                  </span>
                  <span aria-hidden className="text-text-muted shrink-0">↑</span>
                </button>
              </div>
            )}

            {/* ── Level 2: the evidence modules + sticky section rail ─────── */}
            <div className="lg:grid lg:grid-cols-[8.5rem_minmax(0,1fr)] lg:gap-10">
              {/* Section rail — wayfinding for the dashboard (desktop only;
                  the condensed verdict strip covers mobile). */}
              <nav aria-label={t("scorecard.sectionsNav")} className="hidden lg:block">
                <div className="sticky top-24 space-y-1">
                  {navSections.map((id) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => jumpToModule(id)}
                      className={`block w-full text-left text-caption rounded-md px-2.5 py-1.5 transition-colors ${
                        activeSection === id
                          ? "text-text-primary bg-dark-elevated"
                          : "text-text-muted hover:text-text-secondary"
                      }`}
                    >
                      {t(`scorecard.moduleNav.${id.replace("module-", "")}`)}
                    </button>
                  ))}
                </div>
              </nav>

              <div className="min-w-0">
                {/* §1 — What you can build: standards beside the zoning quilt,
                    overlay rows beside the boundary map — every spatial claim
                    is SHOWN next to the row that makes it. */}
                {hasBuild && (
                  <ProfileModule
                    id="module-build"
                    title={t("scorecard.sections.capacityTitle")}
                    takeaway={takeaways.build}
                    action={moduleAsk("build", zdef
                      ? `What are the allowed uses, setbacks, and FAR for ${zdef.zone_class} zoning?`
                      : `What are the development restrictions from regulatory overlays at ${addr}?`)}
                  >
                    <div className="grid md:grid-cols-2 gap-x-10 gap-y-8 md:items-stretch">
                      {zdef && (
                        <div id="scorecard-card-zoning" className="scroll-mt-28 flex flex-col">
                          <ScorecardZoningCard
                            def={zdef}
                            mapUrl={zoning?.zoning_map_url}
                            existingFar={verdict?.signals.existingFar}
                            allowedFar={verdict?.signals.allowedFar}
                            ordinanceNum={zoning?.ordinance_num}
                          />
                        </div>
                      )}
                      <ParcelMap
                        variant="zoning"
                        lazy
                        lat={data.resolved_lat ?? data.lat}
                        lon={data.resolved_lon ?? data.lon}
                        parcelGeometry={(ctx.property?.parcel_geometry as GeoJSON.Geometry | null) ?? null}
                        layers={mapLayers}
                        className="min-h-[16rem]"
                      />
                    </div>
                    {ctx.regulatory && (
                      <div className="grid md:grid-cols-2 gap-x-10 gap-y-8 md:items-stretch mt-8">
                        <div id="scorecard-card-regulatory" className="scroll-mt-28 flex flex-col">
                          <ScorecardRegulatoryCard data={ctx.regulatory} />
                        </div>
                        <ParcelMap
                          variant="boundaries"
                          lazy
                          lat={data.resolved_lat ?? data.lat}
                          lon={data.resolved_lon ?? data.lon}
                          parcelGeometry={(ctx.property?.parcel_geometry as GeoJSON.Geometry | null) ?? null}
                          layers={mapLayers}
                          className="min-h-[16rem]"
                        />
                      </div>
                    )}
                  </ProfileModule>
                )}

                {/* §2 — What it costs */}
                {hasEconomics && (
                  <ProfileModule
                    id="module-economics"
                    title={t("scorecard.sections.economicsTitle")}
                    takeaway={takeaways.costs}
                    action={moduleAsk("economics", `Tell me about the building, taxes, and assessment history at ${addr}`)}
                  >
                    <div className="space-y-10">
                      {ctx.property && (
                        <div id="scorecard-card-property" className="scroll-mt-28">
                          <ScorecardPropertyCard data={ctx.property} />
                        </div>
                      )}
                      {ctx.incentives && (
                        <div id="scorecard-card-incentives" className="scroll-mt-28 max-w-3xl">
                          <ScorecardIncentivesCard data={ctx.incentives} />
                        </div>
                      )}
                    </div>
                  </ProfileModule>
                )}

                {/* §3 — The market */}
                {hasMarket && data.comparables && (
                  <ProfileModule
                    id="module-market"
                    title={t("scorecard.sections.marketTitle")}
                    takeaway={takeaways.market}
                    action={moduleAsk("market", `What are the recent comparable sales near ${addr} and what do they suggest about property values?`)}
                  >
                    <div id="scorecard-card-comparables" className="scroll-mt-28">
                      <ScorecardComparablesCard data={data.comparables} />
                    </div>
                  </ProfileModule>
                )}

                {/* §4 — What to watch for */}
                {hasRecord && (
                  <ProfileModule
                    id="module-record"
                    title={t("scorecard.sections.riskTitle")}
                    takeaway={takeaways.record}
                    action={moduleAsk("record", ctx.violations && ctx.violations.total > 0
                      ? `Explain the building violations at ${addr} and typical remediation steps`
                      : `What are the 311 complaint patterns at ${addr} and what do they indicate?`)}
                  >
                    <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-x-10 gap-y-8 md:items-start">
                      {/* Violations tri-state: a record at this address, a confirmed
                          "none on record" (clean — lookup ran, zero rows), or nothing
                          (lookup couldn't run → omitted). The middle state is shown,
                          not silent, so "no block" can't be read as "clean." */}
                      {ctx.violations ? (
                        <div id="scorecard-card-violations" className="scroll-mt-28 flex flex-col">
                          <ScorecardViolationsCard data={ctx.violations} scopeLabel={t("scorecard.violationsScope")} />
                        </div>
                      ) : data.violations_checked ? (
                        <div id="scorecard-card-violations" className="scroll-mt-28 flex flex-col">
                          <SubSection icon={cleanIcon} title={t("scorecard.violations.title")} className="flex-1">
                            <p className="text-body text-state-positive">{t("scorecard.violations.noneOnRecord")}</p>
                            <p className="text-caption text-text-muted mt-0.5">{t("scorecard.violationsScope")}</p>
                          </SubSection>
                        </div>
                      ) : null}
                      {/* 311 is address-point scoped, like the address-scoped violations. */}
                      {data.context.address_311 && <Address311Block data={data} />}
                      {ctx.regulatory && (ctx.regulatory.flood_zone || ctx.regulatory.brownfield_sites.length > 0) && (
                        <ScorecardEnvironmentCard data={ctx.regulatory} />
                      )}
                    </div>
                  </ProfileModule>
                )}

                {/* §5 — The neighborhood: AREA-level context, a designed module
                    (not a buried appendix). The scope label rides the module
                    header so area numbers can never read as parcel facts. */}
                {(data.context.crime_last_90d || ctx.neighborhood) && (
                  <ProfileModule
                    id="module-area"
                    title={t("scorecard.neighborhoodContext.title")}
                    takeaway={data.community_area_name
                      ? t("scorecard.neighborhoodContext.scope", { area: data.community_area_name })
                      : null}
                    action={moduleAsk("neighborhood", `What's the neighborhood like around ${addr}?`)}
                  >
                    {ctx.neighborhood && <NeighborhoodBlock data={ctx.neighborhood} />}
                    {data.context.crime_last_90d && (
                      <div className="mt-8 max-w-3xl">
                        <CrimeYoYBlock data={data} />
                      </div>
                    )}
                  </ProfileModule>
                )}

                {/* Page footer — feedback lives with the end of the read */}
                <div className="border-t border-dark-border mt-10 pt-5 flex items-center justify-between flex-wrap gap-3">
                  <ScorecardFeedback key={data.resolved_pin ?? data.address ?? "none"} />
                  {data.context.data_as_of && (
                    <span className="text-micro text-text-muted">
                      {t("scorecard.dataAsOf", { date: data.context.data_as_of })}
                    </span>
                  )}
                </div>
              </div>
            </div>

          </div>
        )}

      </main>

      {/* Quick-chat dock — keyed per parcel so a new address opens fresh
          (ephemeral by design; escalation carries the transcript out). */}
      {data && ctx && !loading && (
        <MiniChatDock key={data.resolved_pin ?? data.address ?? "parcel"} data={data} signal={dockSignal} />
      )}

      {showPurchasePrompt && data && parcel && (
        <ReportPurchasePrompt
          parcel={parcel}
          onClose={() => setShowPurchasePrompt(false)}
          onAccessGranted={() => {
            // Voucher redeemed: the user is now comp-premium server-side.
            setShowPurchasePrompt(false);
            setReportAccess({ has_access: true, reason: "subscription" });
            checkAuth();
          }}
        />
      )}
    </div>
  );
}
