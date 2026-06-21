import { useState, useCallback, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { fetchReport, checkReportAccess, type ScorecardResponse, type ZoneDefinition } from "../lib/api";
import type { ParcelQuery } from "../lib/types";
import { useAuthContext } from "../contexts/AuthContext";
import { useSelectedParcel } from "../contexts/SelectedParcelContext";
import ReportPurchasePrompt from "./ReportPurchasePrompt";
import { ReportCTACard } from "./ReportCTACard";
import { InvestigateButton } from "./InvestigateButton";
import { setAddress as setTrackingAddress, track } from "../lib/tracking";
import { PropertyCard } from "./sidebar/PropertyCard";
import { ComparablesCard } from "./sidebar/ComparablesCard";
import { RegulatoryCard } from "./sidebar/RegulatoryCard";
import { IncentivesCard } from "./sidebar/IncentivesCard";
import { NeighborhoodCard } from "./sidebar/NeighborhoodCard";
import { ViolationsCard } from "./sidebar/ViolationsCard";
import { buildScorecardCSV, downloadCSV, buildFilenameSlug } from "../lib/csvExport";
import { FinancialSnapshotStrip } from "./FinancialSnapshotStrip";
import { humanizeShoutyCase, localizeZoningValue } from "../lib/format";
import { ReportTeaser } from "./sidebar/ReportTeaser";
import PageHeader from "./PageHeader";
import { Card } from "./ui/Card";
import { Chip } from "./ui/Chip";

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

// Static location thumbnail (Mapbox Static Images API). Pin-only by design:
// parcel polygon geometry isn't reliably available (county GIS), so the
// default state must not depend on it. Hidden entirely if the image fails.
function MapThumb({ lat, lon }: { lat: number; lon: number }) {
  const [failed, setFailed] = useState(false);
  const token = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined;
  if (!token || failed) return null;
  const pt = `${lon.toFixed(5)},${lat.toFixed(5)}`;
  const url = `https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/pin-s+c96442(${pt})/${pt},15/224x224@2x?access_token=${token}&logo=false`;
  return (
    <img
      src={url}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
      className="hidden sm:block w-28 h-28 rounded-lg border border-dark-border object-cover shrink-0"
    />
  );
}

const zoningIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
  </svg>
);

function ZoningCard({ def, mapUrl }: { def: ZoneDefinition; mapUrl?: string | null }) {
  const { t } = useTranslation("pages");
  return (
    <Card
      padding="sm"
      icon={zoningIcon}
      title={t("scorecard.zoningCard.title")}
      headerRight={<Chip tone="accent" mono size="sm">{def.zone_class}</Chip>}
    >
      <div className="space-y-2">
        <p className="text-caption font-medium text-text-primary">{def.name}</p>
        <div className="space-y-1">
          {def.far != null && (
            <div className="flex justify-between items-baseline gap-2 text-micro">
              <span className="text-text-muted">{t("scorecard.zoningCard.far")}</span>
              <span className="text-text-primary font-mono">{def.far}</span>
            </div>
          )}
          {def.max_height && (
            <div className="flex justify-between items-baseline gap-2 text-micro">
              <span className="text-text-muted">{t("scorecard.zoningCard.maxHeight")}</span>
              <span className="text-text-primary font-mono text-right">{localizeZoningValue(def.max_height)}</span>
            </div>
          )}
          {def.lot_coverage && (
            <div className="flex justify-between items-baseline gap-2 text-micro">
              <span className="text-text-muted">{t("scorecard.zoningCard.lotCoverage")}</span>
              <span className="text-text-primary font-mono text-right">{localizeZoningValue(def.lot_coverage)}</span>
            </div>
          )}
        </div>
        {def.uses && <p className="text-micro text-text-secondary leading-snug">{def.uses}</p>}
        {def.notes && <p className="text-micro text-text-muted leading-snug">{def.notes}</p>}
        <div className="flex items-center justify-between gap-2 text-micro text-text-muted">
          <span className="font-mono">{def.code_section}</span>
          {mapUrl && (
            <a
              href={mapUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-secondary hover:text-accent transition-colors"
            >
              {t("scorecard.zoningCard.viewMap")}
            </a>
          )}
        </div>
        <ReportTeaser text={t("scorecard.zoningCard.reportTeaser")} />
      </div>
    </Card>
  );
}

const crimeIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0-10.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
  </svg>
);

function CrimeYoYCard({ data }: { data: ScorecardResponse }) {
  const { t } = useTranslation("pages");
  const crime = data.context.crime_last_90d;
  if (!crime) return null;
  const yoy = crime.yoy;
  return (
    <Card
      padding="sm"
      icon={crimeIcon}
      title={t("scorecard.crime")}
      headerRight={<span className="text-micro text-text-muted">{t("scorecard.incidents90d", { count: crime.total })}</span>}
    >
      <div className="space-y-2">
        <div className="flex gap-4 text-micro">
          <span className="text-text-muted">{t("scorecard.arrestRate")}</span>
          <span className="text-text-primary font-mono">{(crime.arrest_rate * 100).toFixed(1)}%</span>
        </div>
        {yoy && yoy.length > 0 && (
          <div>
            <div className="text-micro text-text-muted mb-1.5">{crime.yoy_period || t("scorecard.yearOverYear")}</div>
            <div className="space-y-1">
              {yoy.slice(0, 6).map((item) => (
                <div key={item.category} className="flex items-center justify-between text-micro">
                  <span className="text-text-secondary truncate flex-1 mr-2">{humanizeShoutyCase(item.category)}</span>
                  <span className="font-mono text-text-primary w-8 text-right">{item.current_count}</span>
                  {/* prior-year base makes large percentage swings honest (54 → 209 reads differently than +287%) */}
                  <span className="font-mono text-text-muted w-14 text-right">
                    {t("scorecard.vsPrior", { count: item.prior_year_count })}
                  </span>
                  <span className={`font-mono w-14 text-right ${
                    item.change_pct > 0 ? "text-rose-400" : item.change_pct < 0 ? "text-emerald-400" : "text-text-muted"
                  }`}>
                    {item.change_pct > 0 ? "+" : ""}{item.change_pct}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

const address311Icon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
  </svg>
);

function Address311Card({ data }: { data: ScorecardResponse }) {
  const { t } = useTranslation("pages");
  const addr311 = data.context.address_311;
  if (!addr311) return null;
  return (
    <Card
      padding="sm"
      icon={address311Icon}
      title={t("scorecard.311atAddress")}
      headerRight={<span className="text-micro text-text-muted">{addr311.total} {t("scorecard.pastYear")}</span>}
    >
      <div className="space-y-2">
        {addr311.open_count > 0 && (
          <div className="text-micro text-amber-400">{t("scorecard.openComplaints", { count: addr311.open_count })}</div>
        )}
        {addr311.high_risk_flags.length > 0 && (
          <div className="space-y-1">
            <div className="text-micro text-rose-400 font-medium">{t("scorecard.highRiskFlags")}</div>
            {addr311.high_risk_flags.map((flag) => (
              <div key={flag} className="text-micro text-rose-400 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-rose-400 flex-shrink-0" />
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
    </Card>
  );
}


function ScorecardSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="bg-dark-surface border border-dark-border rounded-xl h-48" />
      ))}
    </div>
  );
}

export default function ScorecardPage() {
  const { t } = useTranslation("pages");
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuthContext();
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
  const ctaRef = useRef<HTMLDivElement>(null);
  const [ctaVisible, setCtaVisible] = useState(true);

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
      if (result.address) setAddress(result.address);
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

  // Fetch report access when scorecard data loads (for non-pro users)
  useEffect(() => {
    if (!data || !parcel || isPro) return;
    checkReportAccess(parcel).then(setReportAccess);
  }, [data, isPro, parcel]);

  useEffect(() => {
    if (data?.address) setTrackingAddress(data.address);
    return () => setTrackingAddress(null);
  }, [data?.address]);

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

  useEffect(() => {
    const el = ctaRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setCtaVisible(entry.isIntersecting),
      { threshold: 0 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [data]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doSearch(address);
  };

  const ctx = data?.context;
  const zoning = ctx?.parcel_zoning;
  const addr = data?.address || ctx?.property?.address || "";

  // The single boolean that selects the layout shell: the search box is
  // prominent exactly when re-entering an address is the user's next action
  // (empty + address-typo). It demotes to a compact bar whenever something
  // else owns the primary area — a load, a result, or a code-question redirect.
  const searchProminent = !loading && !data && errorShape !== "question";

  // Facts-only verdict line: every clause restates a flag that is already
  // rendered in a card below — no scoring, no interpretation.
  const zdef = data?.zone_definition;
  const verdictClauses: string[] = [];
  if (ctx) {
    if (zdef) verdictClauses.push(`${zdef.zone_class} ${zdef.name}`);
    const inc = ctx.incentives;
    const reg = ctx.regulatory;
    if (inc?.in_tif_district && inc.tif_name) verdictClauses.push(t("scorecard.verdict.inTif", { name: inc.tif_name }));
    if (inc?.in_opportunity_zone) verdictClauses.push(t("scorecard.verdict.opportunityZone"));
    if (reg?.in_tod_area || ctx.neighborhood?.transit?.tod_eligible) verdictClauses.push(t("scorecard.verdict.todEligible"));
    if (reg?.in_adu_area) verdictClauses.push(t("scorecard.verdict.aduEligible"));
    if (reg?.in_aro_zone) verdictClauses.push(t("scorecard.verdict.aroApplies"));
    if (reg?.flood_zone === "X") verdictClauses.push(t("scorecard.verdict.minimalFlood"));
    else if (reg?.flood_zone) verdictClauses.push(t("scorecard.verdict.floodZone", { zone: reg.flood_zone }));
  }

  return (
    <div className="min-h-screen bg-dark-bg text-text-primary">
      <PageHeader />

      {/* pb-24 clears the sticky report bar so the last card is never hidden behind it */}
      <main className={`max-w-7xl mx-auto px-4 py-8 ${data && !loading ? "pb-24" : ""}`}>
        {/* Search shell — prominent (empty / address-typo) vs compact (loading /
            success / code-question redirect). One boolean, two shells. */}
        {searchProminent ? (
          <div className="max-w-2xl mx-auto mb-8">
            <h1 className="text-section mb-2">{t("scorecard.title")}</h1>
            <p className="text-body text-text-muted mb-4">
              {t("scorecard.subtitle")}
            </p>
            <form onSubmit={handleSubmit} className="flex gap-2">
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="2400 N Milwaukee Ave"
                className="flex-1 bg-dark-surface border border-dark-border rounded-lg px-4 py-2.5 text-body text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
              />
              <button
                type="submit"
                disabled={loading || !address.trim()}
                className="px-5 py-2.5 bg-accent hover:bg-accent-hover disabled:opacity-50 text-text-on-accent text-title rounded-lg transition-colors"
              >
                {loading ? t("scorecard.loading") : t("scorecard.search")}
              </button>
            </form>
            {error && errorShape === "address" && (
              <div className="mt-3 text-body text-rose-400 bg-rose-400/10 border border-rose-400/20 rounded-lg px-4 py-2.5">
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
            <form onSubmit={handleSubmit} className="flex gap-2 items-center">
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder={t("scorecard.searchAnother")}
                aria-label={t("scorecard.searchAnother")}
                className="flex-1 bg-dark-surface border border-dark-border rounded-lg px-3 py-1.5 text-body text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
              />
              <button
                type="submit"
                disabled={loading || !address.trim()}
                className="px-3 py-1.5 bg-dark-elevated hover:bg-dark-hover disabled:opacity-50 text-text-secondary text-caption font-medium rounded-lg transition-colors shrink-0"
              >
                {loading ? t("scorecard.loading") : t("scorecard.search")}
              </button>
            </form>
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
                className="px-4 py-2 bg-accent hover:bg-accent-hover text-text-on-accent text-title rounded-lg transition-colors"
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
            {/* Address header */}
            <div className="mb-6 pb-4 border-b border-dark-border flex gap-4 items-start">
              <MapThumb lat={data.lat} lon={data.lon} />
              <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-3 flex-wrap">
                <h2 className="text-subtitle">
                  {data.address || ctx.property?.address ||
                    (parcel?.pin ? `PIN ${formatPin(parcel.pin)}` : t("scorecard.addressUnavailable"))}
                </h2>
                {data.community_area_name && (
                  <span className="text-body text-text-muted">{data.community_area_name}</span>
                )}
                {zoning && (
                  <Chip tone="accent" mono size="sm">{zoning.zone_class}</Chip>
                )}
              </div>
              {/* Parcel identity strip */}
              {parcel && (
                <div className="flex items-center gap-3 mt-2 flex-wrap">
                  {parcel.pin && (
                    <a
                      href={`https://www.cookcountyassessor.com/pin/${parcel.pin}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-caption font-mono text-text-secondary hover:text-accent transition-colors"
                    >
                      PIN {formatPin(parcel.pin)}
                    </a>
                  )}
                  {parcel.pin === null ? (
                    <Chip tone="warning" size="sm" title={t("scorecard.badges.unconfirmedTitle")} className="cursor-help">
                      {t("scorecard.badges.unconfirmed")}
                    </Chip>
                  ) : parcel.confidence === "authoritative" ? (
                    <Chip tone="positive" size="sm" title={t("scorecard.badges.exactTitle")} className="cursor-help">
                      ✓ {t("scorecard.badges.exact")}
                    </Chip>
                  ) : (
                    <Chip tone="warning" size="sm" title={t("scorecard.badges.approximateTitle")} className="cursor-help">
                      {t("scorecard.badges.approximate")}
                    </Chip>
                  )}
                </div>
              )}
              {verdictClauses.length > 0 && (
                <p className="mt-2 text-caption text-text-secondary leading-snug">
                  {verdictClauses.join(" · ")}
                </p>
              )}
              {data.context.data_as_of && (
                <div className="mt-2 text-micro text-text-muted">
                  {t("scorecard.dataAsOf", { date: data.context.data_as_of })}
                </div>
              )}
              {data.partial_failures.length > 0 && (
                <div className="mt-2 text-micro text-amber-400">
                  {t("scorecard.someDataUnavailable", { sources: data.partial_failures.join(", ") })}
                </div>
              )}
              {/* Investigate buttons */}
              <div className="flex flex-wrap gap-3 mt-3 items-center">
                {/* Open-ended chat entry: lands on the grounded "Ask about this
                    property" starters (no auto-send) so the contextual path is
                    the obvious one. Pin-only — the workspace hydrates grounding. */}
                {parcel?.pin && (
                  <button
                    type="button"
                    onClick={() => {
                      track("investigate_click", { card_name: "ask_about_property" });
                      navigate(`/?pin=${parcel.pin}`);
                    }}
                    className="group inline-flex items-center gap-1 text-micro text-text-secondary hover:text-accent transition-colors"
                  >
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                    </svg>
                    {t("scorecard.askAboutProperty")}
                    <span aria-hidden className="opacity-0 group-hover:opacity-100 transition-opacity">→</span>
                  </button>
                )}
                <InvestigateButton
                  question={`What's going on near ${data.address}?`}
                  label={t("scorecard.fullAnalysis")}
                  cardName="full_analysis"
                  pin={parcel?.pin}
                />
                <button
                  onClick={() => {
                    const slug = buildFilenameSlug(data.address || "property");
                    const date = new Date().toISOString().slice(0, 10);
                    downloadCSV(buildScorecardCSV(ctx, data.address ?? "", data.comparables), `${slug}_scorecard_${date}.csv`);
                  }}
                  className="inline-flex items-center gap-1 text-micro text-text-secondary hover:text-accent transition-colors"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                  {t("scorecard.downloadCsv")}
                </button>
              </div>
              </div>
            </div>

            {/* Report CTA */}
            <div className="mb-6" ref={ctaRef}>
              <ReportCTACard
                hasReportAccess={hasReportAccess}
                downloading={downloading}
                onDownload={handleDownloadPdf}
                onShowPurchase={() => setShowPurchasePrompt(true)}
              />
            </div>

            {/* Nearest-parcel caveat: identity is unconfirmed and the property/
                tax/comps cards were filled from the nearest (possibly-neighbor)
                parcel — say so before the reader trusts parcel-specific numbers. */}
            {data.nearest_parcel_unverified && (
              <div className="mb-4 text-caption text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded-lg px-4 py-2.5">
                {t("scorecard.nearestParcelCaveat")}
              </div>
            )}

            {/* Financial Snapshot */}
            <FinancialSnapshotStrip
              property={ctx.property}
              comparables={data.comparables}
              incentives={ctx.incentives}
            />

            {/* Card columns — ordered for developer evaluation flow. CSS multicol
                instead of grid: each column flows independently, so a short card
                never strands empty space beside a tall neighbor. break-inside-avoid
                keeps a card and its ask-link together. */}
            <div className="columns-1 md:columns-2 gap-4">
              {ctx.property && (
                <div className="break-inside-avoid mb-4">
                  <PropertyCard data={ctx.property} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`Tell me about the building and property characteristics at ${addr}`}
                      label={t("scorecard.investigate.buildingDetails")}
                      cardName="property"
                      pin={parcel?.pin}
                    />
                  </div>
                </div>
              )}
              {data.comparables && data.comparables.sales.length > 0 && (
                <div className="break-inside-avoid mb-4">
                  <ComparablesCard data={data.comparables} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`What are the recent comparable sales near ${addr} and what do they suggest about property values?`}
                      label={t("scorecard.investigate.comparableSales")}
                      cardName="comparables"
                      pin={parcel?.pin}
                    />
                  </div>
                </div>
              )}
              {zdef && (
                <div className="break-inside-avoid mb-4">
                  <ZoningCard def={zdef} mapUrl={zoning?.zoning_map_url} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`What are the allowed uses, setbacks, and FAR for ${zdef.zone_class} zoning?`}
                      label={t("scorecard.zoningRules", { zone: zdef.zone_class })}
                      cardName="zoning"
                      pin={parcel?.pin}
                    />
                  </div>
                </div>
              )}
              {ctx.incentives && (
                <div className="break-inside-avoid mb-4">
                  <IncentivesCard data={ctx.incentives} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    {/* one ask per card: TIF question when the parcel is in a TIF, else the generic one */}
                    <InvestigateButton
                      question={ctx.incentives.in_tif_district && ctx.incentives.tif_name
                        ? `How much TIF funding is available in ${ctx.incentives.tif_name} and what projects qualify?`
                        : `What tax incentives and grant programs are available near ${addr}?`}
                      label={ctx.incentives.in_tif_district && ctx.incentives.tif_name
                        ? t("scorecard.investigate.tifFunding")
                        : t("scorecard.investigate.incentivePrograms")}
                      cardName="incentives"
                      pin={parcel?.pin}
                    />
                  </div>
                </div>
              )}
              {ctx.regulatory && (
                <div className="break-inside-avoid mb-4">
                  <RegulatoryCard data={ctx.regulatory} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    {ctx.regulatory.flood_zone && ctx.regulatory.flood_zone !== "X" ? (
                      <InvestigateButton
                        question={`What are the development restrictions from regulatory overlays and FEMA flood zone ${ctx.regulatory.flood_zone} at ${addr}?`}
                        label={t("scorecard.investigate.overlaysAndFlood")}
                        cardName="regulatory"
                      pin={parcel?.pin}
                      />
                    ) : (
                      <InvestigateButton
                        question={`What are the development restrictions from regulatory overlays at ${addr}?`}
                        label={t("scorecard.investigate.overlayRestrictions")}
                        cardName="regulatory"
                      pin={parcel?.pin}
                      />
                    )}
                  </div>
                </div>
              )}
              {ctx.violations && (
                <div className="break-inside-avoid mb-4">
                  <ViolationsCard data={ctx.violations} />
                  {ctx.violations.total > 0 && (
                    <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                      <InvestigateButton
                        question={`Explain the building violations at ${addr} and typical remediation steps`}
                        label={t("scorecard.investigate.violationDetails")}
                        cardName="violations"
                      pin={parcel?.pin}
                      />
                    </div>
                  )}
                </div>
              )}
              {data.context.crime_last_90d && (
                <div className="break-inside-avoid mb-4">
                  <CrimeYoYCard data={data} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`What are the crime trends and safety concerns near ${addr}?`}
                      label={t("scorecard.investigate.crimeAnalysis")}
                      cardName="crime"
                      pin={parcel?.pin}
                    />
                  </div>
                </div>
              )}
              {data.context.address_311 && (
                <div className="break-inside-avoid mb-4">
                  <Address311Card data={data} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`What are the 311 complaint patterns at ${addr} and what do they indicate?`}
                      label={t("scorecard.investigate.complaints311")}
                      cardName="311"
                      pin={parcel?.pin}
                    />
                  </div>
                </div>
              )}
              {/* Neighborhood last: deepest card flows at the trailing edge */}
              {ctx.neighborhood && (
                <div className="break-inside-avoid mb-4">
                  <NeighborhoodCard data={ctx.neighborhood} />
                  <div className="flex flex-wrap gap-2 mt-1.5 px-1">
                    <InvestigateButton
                      question={`What's the neighborhood like around ${addr}?`}
                      label={t("scorecard.investigate.neighborhoodOverview")}
                      cardName="neighborhood"
                      pin={parcel?.pin}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

      </main>
      {/* Sticky Report CTA — visible when main CTA scrolls out of view */}
      {!ctaVisible && data && !loading && (
        <div className="fixed bottom-0 left-0 right-0 z-40 bg-dark-surface/95 backdrop-blur-sm border-t border-dark-border animate-slide-up">
          <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <svg className="w-4 h-4 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
              <span className="text-title text-text-primary">{t("scorecard.reportCTA.stickyTitle")}</span>
            </div>
            <button
              onClick={() => { track("report_cta_click"); (hasReportAccess ? handleDownloadPdf : () => setShowPurchasePrompt(true))(); }}
              disabled={downloading}
              className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 text-text-on-accent text-title rounded-lg transition-colors shrink-0"
            >
              {downloading
                ? t("scorecard.reportCTA.generating")
                : hasReportAccess
                  ? t("scorecard.reportCTA.download")
                  : t("scorecard.reportCTA.buyReport")}
            </button>
          </div>
        </div>
      )}

      {showPurchasePrompt && data && parcel && (
        <ReportPurchasePrompt
          parcel={parcel}
          onClose={() => setShowPurchasePrompt(false)}
        />
      )}
    </div>
  );
}
