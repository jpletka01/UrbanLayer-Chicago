// "How we matched this parcel": the record behind the PIN. A green check says the parcel
// was identified; this says WHICH record matched the address, whether several parcels
// share it, whether the two county address sources agree, and when the identity could
// not be confirmed, so a reader can tell a solid match from a plausible guess.
import { useTranslation } from "react-i18next";
import type { ParcelResolutionRecord } from "../../lib/api";

const MAX_CANDIDATES_SHOWN = 8;

function fmtPin(pin: string): string {
  return pin.length === 14 ? `${pin.slice(0, 2)}-${pin.slice(2, 4)}-${pin.slice(4, 7)}-${pin.slice(7, 10)}-${pin.slice(10)}` : pin;
}

export function ParcelResolution({ resolution }: { resolution?: ParcelResolutionRecord | null }) {
  const { t } = useTranslation("pages");
  if (!resolution?.method) return null;
  const r = resolution;
  const method = t(`scorecard.resolution.method.${r.method}`);
  const gap = r.method === "address_points" && r.centroid_gap_ft != null ? r.centroid_gap_ft : null;
  const warn = r.identity_unconfirmed || r.confidence === "approximate";
  // A condominium building can list dozens of unit PINs: show the matched parcel first
  // and a handful of others, and say how many are hidden rather than paging a long list.
  const ordered = [...r.candidates].sort((a, b) => Number(b.used) - Number(a.used));
  const shown = ordered.slice(0, MAX_CANDIDATES_SHOWN);
  const hidden = ordered.length - shown.length;

  return (
    <div className="mt-1.5 text-caption text-text-muted space-y-1" data-testid="parcel-resolution">
      <p className={warn ? "text-state-warning" : undefined}>
        {t("scorecard.resolution.matchedBy", { method })}
        {gap != null && ` · ${t("scorecard.resolution.gap", { ft: gap.toLocaleString() })}`}
      </p>

      {r.identity_unconfirmed && r.unverified_reason && (
        <p className="text-state-warning" data-testid="resolution-unconfirmed">
          {t(`scorecard.resolution.unconfirmed.${r.unverified_reason}`, {
            pin: r.pin ? fmtPin(r.pin) : "",
            other: r.property_record_pin ? fmtPin(r.property_record_pin) : "",
          })}
        </p>
      )}

      {r.multiple_parcels && (
        <details className="group" data-testid="resolution-candidates">
          <summary className="cursor-pointer text-text-secondary hover:text-accent transition-colors">
            {r.condo_units
              ? t("scorecard.resolution.condo", { n: r.condo_units })
              : t("scorecard.resolution.multiple", { n: r.candidates.length })}
            {r.sources_disagree && ` ${t("scorecard.resolution.disagree")}`}
          </summary>
          <ul className="mt-1.5 space-y-0.5">
            {shown.map((c) => (
              <li key={c.pin} className={c.used ? "text-text-primary" : undefined} data-testid={c.used ? "candidate-used" : "candidate"}>
                <span className="font-mono">{fmtPin(c.pin)}</span>
                {c.used && ` — ${t("scorecard.resolution.used")}`}
                <span className="text-text-muted"> · {c.sources.map((s) => t(`scorecard.resolution.source.${s}`)).join(", ")}</span>
              </li>
            ))}
          </ul>
          {hidden > 0 && <p className="mt-1">{t("scorecard.resolution.more", { n: hidden })}</p>}
        </details>
      )}
    </div>
  );
}
