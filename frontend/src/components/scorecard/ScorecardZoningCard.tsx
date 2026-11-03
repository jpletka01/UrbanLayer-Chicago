// Page-scale Zoning card — the capacity centerpiece. "What can I build here" is the
// product's core answer, so the standards read at body scale (not a mono ledger) and
// FAR utilization is drawn as a meter when building data exists. Data unchanged:
// ZoneDefinition from the scorecard API + the verdict's FAR signals.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Provenance, TypicalLot, ZoneDefinition } from "../../lib/api";
import type { CodeCurrency, CodeVintage, CoverageNote, PassedNotOnMap, UnitYield, ZoningSummary } from "../../lib/types";
import { formatDay, localizeZoningValue } from "../../lib/format";
import { SubSection } from "./ProfileModule";
import { Chip } from "../ui/Chip";
import { CodeSourceModal } from "./CodeSourceModal";
import { Scale } from "lucide-react";
import { ToolTray } from "../ui/ToolTray";
import { ConfidenceCaption } from "../ui/Confidence";
import { useFact } from "../../lib/provenanceContext";
import { displayState } from "../../lib/confidence";

const ZoningIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
  </svg>
);

/** FAR utilization meter: fill = built share of as-of-right envelope; the unfilled
    track is a lighter step of the same hue so state reads across the whole bar. */
function FarMeter({ existing, allowed }: { existing: number; allowed: number }) {
  const { t } = useTranslation("pages");
  const share = Math.min(existing / allowed, 1);
  // FAR used is our arithmetic on the building and lot areas, so it inherits the weakest input.
  const entry = useFact("property.far_used");
  const state = displayState(entry);
  if (state === "withheld") return <ConfidenceCaption entry={entry} />;
  return (
    <div>
      <div className="flex justify-between items-baseline text-caption mb-1">
        <span className="text-text-muted">{t("scorecard.zoningCard.farUsed")}</span>
        <span className="text-text-secondary">
          {existing.toFixed(2)} / {allowed.toFixed(1)}
        </span>
      </div>
      <div className="h-2.5 rounded-full bg-accent/15 overflow-hidden">
        <div className={`h-full rounded-full ${state === "low" ? "bg-accent/40 bg-hatch" : "bg-accent"}`}
          style={{ width: `${Math.max(share * 100, 2)}%` }} />
      </div>
      <ConfidenceCaption entry={entry} className="mt-1" />
      {share < 1 && (
        <div className="text-caption text-text-muted mt-1">
          {t("scorecard.zoningCard.farHeadroom", { pct: Math.round((1 - share) * 100) })}
        </div>
      )}
    </div>
  );
}

export function ScorecardZoningCard({ def, mapUrl, existingFar, allowedFar, ordinanceNum, unitYield, freshness, codeVintage, codeCurrency, provenance, passedNotOnMap, typicalLot, typicalLotEntry, lotSqft, areaName }: {
  def: ZoneDefinition;
  mapUrl?: string | null;
  existingFar?: number | null;
  allowedFar?: number | null;
  ordinanceNum?: string | null;
  unitYield?: UnitYield | null;
  /** The district's own freshness facts (ordinance date, record-updated date, clerk link). */
  freshness?: Pick<ZoningSummary, "ordinance_num" | "ordinance_date" | "map_updated" | "clerk_url" | "recently_rezoned"> | null;
  codeVintage?: CodeVintage | null;
  /** The Council amendments passed since that vintage; the count rides the stamp (never "none" when unchecked). */
  codeCurrency?: CodeCurrency | null;
  /** Dated sources per fact (backend provenance); a standard's code section opens in the viewer. */
  provenance?: Record<string, Provenance> | null;
  /** Where the analysis stops for this parcel (backend coverage_notes). */
  /** No longer rendered here: the page's Sources & coverage sheet shows it (decision Item 51). */
  coverageNotes?: CoverageNote[] | null;
  /** Passed rezonings listing this address that the City's map doesn't show yet (WS1 M5). */
  passedNotOnMap?: PassedNotOnMap[] | null;
  /** The district's typical lot in this community area (WS5 PR3, Item 66); null when too few lots. */
  typicalLot?: TypicalLot | null;
  typicalLotEntry?: Provenance;
  /** This parcel's lot area, for the comparison behind the Info tool. */
  lotSqft?: number | null;
  areaName?: string | null;
}) {
  const { t } = useTranslation("pages");
  const [openSection, setOpenSection] = useState<string | null>(null);
  const laterAmendments = codeCurrency?.since?.title17 ?? 0;
  // PD/PMD standards are negotiated per-ordinance, not tabulated in Title 17 —
  // say so explicitly instead of omitting the rows (a blank FAR on a PD parcel
  // read as missing data, not as "set by ordinance").
  const isPd = /^PMD|^PD/.test(def.zone_class.trim().toUpperCase());
  const standards: Array<{ label: string; value: string; prov?: string }> = [];
  if (def.far != null) standards.push({ label: t("scorecard.zoningCard.far"), value: String(def.far), prov: "zoning.far" });
  else if (isPd) standards.push({ label: t("scorecard.zoningCard.far"), value: t("scorecard.zoningCard.setByPdOrdinance") });
  if (def.max_height) standards.push({ label: t("scorecard.zoningCard.maxHeight"), value: localizeZoningValue(def.max_height), prov: "zoning.max_height" });
  else if (isPd) standards.push({ label: t("scorecard.zoningCard.maxHeight"), value: t("scorecard.zoningCard.setByPdOrdinance") });
  if (def.lot_coverage) standards.push({ label: t("scorecard.zoningCard.lotCoverage"), value: localizeZoningValue(def.lot_coverage) });
  if (def.min_lot_sqft != null) standards.push({ label: t("scorecard.zoningCard.minLotArea"), value: `${def.min_lot_sqft.toLocaleString()} ft²` });
  if (def.min_lot_area_per_unit != null)
    standards.push({ label: t("scorecard.zoningCard.minLotAreaPerUnit"), value: `${def.min_lot_area_per_unit.toLocaleString()} ft²`, prov: "zoning.min_lot_area_per_unit" });
  if (isPd && ordinanceNum) standards.push({ label: t("scorecard.zoningCard.pdOrdinance"), value: ordinanceNum });
  const ft2 = (n: number) => `${Math.round(n).toLocaleString()} ft²`;

  return (
    <SubSection
      icon={ZoningIcon}
      title={t("scorecard.zoningCard.title")}
      meta={
        <span className="inline-flex items-center gap-2">
          <Chip tone="accent" mono size="sm">{def.zone_class}</Chip>
          {/* The card's evidence, one click away (decision Item 54): dates, the chapter, the City's map,
              and what the district allows in words. */}
          <ToolTray
            label={t("scorecard.zoningCard.title")}
            dates={(freshness?.map_updated || codeVintage) ? (
              <dl className="space-y-0.5" data-testid="freshness-stamps">
                {freshness?.map_updated && (
                  <div className="flex justify-between gap-3">
                    <dt>{t("scorecard.zoningCard.zoningRecordUpdated")}</dt>
                    <dd className="text-text-primary">{formatDay(freshness.map_updated)}</dd>
                  </div>
                )}
                {codeVintage && (
                  <div className="flex justify-between gap-3">
                    <dt>{t("scorecard.zoningCard.codeCurrentThrough")}</dt>
                    <dd className="text-text-primary">
                      {formatDay(codeVintage.current_through)}
                      {laterAmendments > 0 && (
                        <span data-testid="later-amendments">{" · "}{t("scorecard.zoningCard.laterAmendments", { count: laterAmendments })}</span>
                      )}
                    </dd>
                  </div>
                )}
              </dl>
            ) : undefined}
            code={def.code_section ? <span className="font-mono">{def.code_section}</span> : undefined}
            source={mapUrl ? { href: mapUrl, title: t("scorecard.zoningCard.viewMap") } : undefined}
            explain={(def.uses || def.lot_area_note || def.notes) ? (
              <span className="block space-y-1.5">
                {def.uses && <span className="block">{def.uses}</span>}
                {def.lot_area_note && <span className="block text-text-muted">{def.lot_area_note}</span>}
                {def.notes && <span className="block text-text-muted">{def.notes}</span>}
              </span>
            ) : undefined}
          />
        </span>
      }
      className="flex-1"
    >
      <div className="space-y-4">
        <p className="text-body font-medium text-text-primary">{def.name}</p>

        {standards.length > 0 && (
          <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3">
            {standards.map((s) => (
              <div key={s.label}>
                <dt className="text-caption text-text-muted">{s.label}</dt>
                <dd className="text-body text-text-primary mt-0.5">{s.value}</dd>
                {s.prov && provenance?.[s.prov]?.section && (
                  // The rule's code text, behind the Scale icon (decision Item 54); the section stays as
                  // screen-reader text and in the tooltip.
                  <button type="button" onClick={() => setOpenSection(provenance[s.prov!].section)}
                    aria-label={`${t("tools.code", { ns: "common", label: s.label })} §${provenance[s.prov!].section}`}
                    className="mt-0.5 inline-flex items-center rounded text-text-muted cursor-pointer transition-colors hover:text-link focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                    title={`§${provenance[s.prov!].section} · ${t("scorecard.codeSource.open")}`} data-testid={`source-${s.prov}`}>
                    <Scale aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
                    <span className="sr-only">§{provenance[s.prov!].section}</span>
                  </button>
                )}
              </div>
            ))}
          </dl>
        )}

        {typicalLot && (
          // One figure; the sample, the middle half and this lot's own area sit behind the Info tool (Item 66).
          <div data-testid="typical-lot">
            <div className="flex items-baseline justify-between gap-3">
              <span className="inline-flex items-center gap-1 text-caption text-text-muted">
                {t("scorecard.zoningCard.typicalLot")}
                <ToolTray
                  label={t("scorecard.zoningCard.typicalLot")}
                  align="start"
                  explain={
                    <span className="block space-y-1.5" data-testid="typical-lot-explain">
                      <span className="block">
                        {t("scorecard.zoningCard.typicalLotExplain", {
                          count: typicalLot.n, n: typicalLot.n.toLocaleString(), zone: def.zone_class, area: areaName ?? t("scorecard.zoningCard.typicalLotThisArea"),
                          p25: ft2(typicalLot.p25_lot_sqft), p75: ft2(typicalLot.p75_lot_sqft),
                        })}
                        {lotSqft != null && lotSqft > 0 && <>{" "}{t("scorecard.zoningCard.typicalLotThisLot", { lot: ft2(lotSqft) })}</>}
                      </span>
                      <span className="block text-text-muted">{t("scorecard.zoningCard.typicalLotMethod")}</span>
                    </span>
                  }
                />
              </span>
              <span className="text-body text-text-primary">{ft2(typicalLot.median_lot_sqft)}</span>
            </div>
            <ConfidenceCaption entry={typicalLotEntry} size="micro" />
          </div>
        )}

        {existingFar != null && allowedFar != null && allowedFar > 0 && (
          <FarMeter existing={existingFar} allowed={allowedFar} />
        )}

        {unitYield && (
          <div className="rounded-lg border border-border-subtle bg-surface-raised/40 px-3 py-2.5" data-testid="unit-yield">
            <div className="flex items-baseline justify-between gap-3">
              <span className="inline-flex items-center gap-1 text-caption text-text-muted">
                {t("scorecard.zoningCard.maxUnitsByLotArea")}
                <ToolTray
                  label={t("scorecard.zoningCard.maxUnitsByLotArea")}
                  align="start"
                  explain={
                    <span className="block space-y-1.5" data-testid="unit-yield-explain">
                      <span className="block font-mono">{unitYield.arithmetic}</span>
                      <span className="block">{t("scorecard.zoningCard.unitYieldCaveat")}</span>
                    </span>
                  }
                />
              </span>
              <span className="text-body font-medium text-text-primary">{unitYield.units}</span>
            </div>
            {unitYield.rule_606 === "applied" && unitYield.base_units != null && unitYield.units > unitYield.base_units && (
              <p className="text-caption text-text-secondary mt-1" data-testid="unit-yield-606">
                {t("scorecard.zoningCard.unitYield606Applied", { base: unitYield.base_units, units: unitYield.units })}
              </p>
            )}
            {unitYield.rule_block_face === "met" && unitYield.rule_606 !== "applied" && unitYield.base_units != null
              && unitYield.units > unitYield.base_units && (
              <p className="text-caption text-text-secondary mt-1" data-testid="unit-yield-block-face">
                {t("scorecard.zoningCard.unitYieldBlockFaceApplied", { base: unitYield.base_units, units: unitYield.units })}
              </p>
            )}
            {unitYield.rule_block_face === "unchecked" && unitYield.rule_606 !== "applied" && (
              <p className="text-caption text-text-secondary mt-1" data-testid="unit-yield-block-face-unchecked">
                {t("scorecard.zoningCard.unitYieldBlockFaceUnchecked")}
              </p>
            )}
            {unitYield.rule_606 === "unchecked" && (
              <p className="text-caption text-text-secondary mt-1" data-testid="unit-yield-606-unchecked">
                {t("scorecard.zoningCard.unitYield606Unchecked")}
              </p>
            )}
          </div>
        )}


        {(passedNotOnMap ?? []).map((hit) => (
          <p key={hit.record} className="text-caption text-text-primary rounded-lg border border-state-warning/40 bg-state-warning/10 px-3 py-2" data-testid="passed-not-on-map">
            {t("scorecard.zoningCard.passedNotOnMap", { date: formatDay(hit.passed_on), record: hit.record })}
            {" "}
            <a href={hit.url} target="_blank" rel="noopener noreferrer" className="underline">{hit.record} ↗</a>
            {hit.to_district && hit.from_district && (
              <span className="block mt-1" data-testid="passed-district">
                {t("scorecard.zoningCard.passedDistrict", { from: hit.from_district, to: hit.to_district })}
              </span>
            )}
          </p>
        ))}

        {freshness?.recently_rezoned && freshness.ordinance_date && (
          <p className="text-caption text-text-primary rounded-lg border border-accent/40 bg-accent/10 px-3 py-2" data-testid="recently-rezoned">
            {t("scorecard.zoningCard.recentlyRezoned", { date: freshness.ordinance_date })}
            {freshness.ordinance_num && (
              freshness.clerk_url ? (
                <> <a href={freshness.clerk_url} target="_blank" rel="noopener noreferrer" className="underline">{freshness.ordinance_num} ↗</a></>
              ) : (
                <> ({freshness.ordinance_num})</>
              )
            )}
          </p>
        )}

        {/* "What this page doesn't cover" moved to the page's Sources & coverage sheet (decision Item 51). */}

      </div>
      {openSection && <CodeSourceModal sectionId={openSection} onClose={() => setOpenSection(null)} />}
    </SubSection>
  );
}
