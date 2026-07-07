// Page-scale Zoning card — the capacity centerpiece. "What can I build here" is the
// product's core answer, so the standards read at body scale (not a mono ledger) and
// FAR utilization is drawn as a meter when building data exists. Data unchanged:
// ZoneDefinition from the scorecard API + the verdict's FAR signals.
import { useTranslation } from "react-i18next";
import type { ZoneDefinition } from "../../lib/api";
import { localizeZoningValue } from "../../lib/format";
import { SubSection } from "./ProfileModule";
import { Chip } from "../ui/Chip";

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
  return (
    <div>
      <div className="flex justify-between items-baseline text-caption mb-1">
        <span className="text-text-muted">{t("scorecard.zoningCard.farUsed")}</span>
        <span className="text-text-secondary">
          {existing.toFixed(2)} / {allowed.toFixed(1)}
        </span>
      </div>
      <div className="h-2.5 rounded-full bg-accent/15 overflow-hidden">
        <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(share * 100, 2)}%` }} />
      </div>
      {share < 1 && (
        <div className="text-caption text-text-muted mt-1">
          {t("scorecard.zoningCard.farHeadroom", { pct: Math.round((1 - share) * 100) })}
        </div>
      )}
    </div>
  );
}

export function ScorecardZoningCard({ def, mapUrl, existingFar, allowedFar, ordinanceNum }: {
  def: ZoneDefinition;
  mapUrl?: string | null;
  existingFar?: number | null;
  allowedFar?: number | null;
  ordinanceNum?: string | null;
}) {
  const { t } = useTranslation("pages");
  // PD/PMD standards are negotiated per-ordinance, not tabulated in Title 17 —
  // say so explicitly instead of omitting the rows (a blank FAR on a PD parcel
  // read as missing data, not as "set by ordinance").
  const isPd = /^PMD|^PD/.test(def.zone_class.trim().toUpperCase());
  const standards: Array<{ label: string; value: string }> = [];
  if (def.far != null) standards.push({ label: t("scorecard.zoningCard.far"), value: String(def.far) });
  else if (isPd) standards.push({ label: t("scorecard.zoningCard.far"), value: t("scorecard.zoningCard.setByPdOrdinance") });
  if (def.max_height) standards.push({ label: t("scorecard.zoningCard.maxHeight"), value: localizeZoningValue(def.max_height) });
  else if (isPd) standards.push({ label: t("scorecard.zoningCard.maxHeight"), value: t("scorecard.zoningCard.setByPdOrdinance") });
  if (def.lot_coverage) standards.push({ label: t("scorecard.zoningCard.lotCoverage"), value: localizeZoningValue(def.lot_coverage) });
  if (def.min_lot_sqft != null) standards.push({ label: t("scorecard.zoningCard.minLotArea"), value: `${def.min_lot_sqft.toLocaleString()} ft²` });
  if (isPd && ordinanceNum) standards.push({ label: t("scorecard.zoningCard.pdOrdinance"), value: ordinanceNum });

  return (
    <SubSection
      icon={ZoningIcon}
      title={t("scorecard.zoningCard.title")}
      meta={<Chip tone="accent" mono size="sm">{def.zone_class}</Chip>}
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
              </div>
            ))}
          </dl>
        )}

        {existingFar != null && allowedFar != null && allowedFar > 0 && (
          <FarMeter existing={existingFar} allowed={allowedFar} />
        )}

        {def.uses && <p className="text-caption text-text-secondary leading-relaxed">{def.uses}</p>}
        {def.notes && <p className="text-caption text-text-muted leading-relaxed">{def.notes}</p>}

        <div className="flex items-center justify-between gap-2 text-caption text-text-muted">
          <span className="font-mono">{def.code_section}</span>
          {mapUrl && (
            <a href={mapUrl} target="_blank" rel="noopener noreferrer"
              className="text-text-secondary hover:text-accent transition-colors">
              {t("scorecard.zoningCard.viewMap")}
            </a>
          )}
        </div>
      </div>
    </SubSection>
  );
}
