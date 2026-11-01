// The Profile's identity line (redesign plan §6b, decision Item 50; Jack's second pass, item 1): the
// address alone, then ONE "Parcel details ▾" disclosure holding the area, ward, PIN (with copy and the
// Assessor link) and how the address was matched. Exception that stays visible: an approximate match
// or a withheld PIN is one amber label, because it changes whether any figure on the page applies.
// No check mark on an exact match: a verified identity needs no label (the same rule as figures).
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ParcelResolutionRecord } from "../../lib/api";
import { StatusLabel } from "../ui/StatusLabel";
import { Toggletip } from "../ui/Toggletip";
import { ParcelResolution } from "./ParcelResolution";

function formatPin(pin: string): string {
  const d = pin.replace(/\D/g, "");
  return d.length === 14 ? `${d.slice(0, 2)}-${d.slice(2, 4)}-${d.slice(4, 7)}-${d.slice(7, 10)}-${d.slice(10)}` : pin;
}

export function ProfileHeader({
  title,
  pin,
  identity,
  areaName,
  ward,
  resolution,
}: {
  title: string;
  pin: string | null;
  /** exact = a confirmed parcel; approximate = placed near a parcel; unconfirmed = no PIN. */
  identity: "exact" | "approximate" | "unconfirmed" | null;
  areaName?: string | null;
  ward?: number | string | null;
  resolution?: ParcelResolutionRecord | null;
}) {
  const { t } = useTranslation("pages");
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const regionId = useId();

  const copy = async () => {
    if (!pin) return;
    try {
      await navigator.clipboard.writeText(formatPin(pin));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // no clipboard permission: the PIN is still on screen to select
    }
  };

  const warnKey = identity === "unconfirmed" ? "unconfirmed" : identity === "approximate" ? "approximate" : null;

  return (
    <div data-testid="profile-header">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <h1 className="text-section text-text-primary min-w-0">{title}</h1>
        {warnKey && (
          <span className="inline-flex items-center gap-1" data-testid="identity-warning">
            <StatusLabel tone="warning">{t(`scorecard.badges.${warnKey}`)}</StatusLabel>
            <Toggletip label={t(`scorecard.badges.${warnKey}`)}>{t(`scorecard.badges.${warnKey}Title`)}</Toggletip>
          </span>
        )}
      </div>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={regionId}
        onClick={() => setOpen((v) => !v)}
        data-testid="parcel-details-toggle"
        className="mt-1 inline-flex items-center gap-1 rounded text-caption text-text-secondary cursor-pointer hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        {t("scorecard.header.details")}
        <span aria-hidden className={`transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
      </button>
      {open && (
        <div id={regionId} className="mt-2 max-w-xl space-y-1.5 rounded-lg border border-dark-border bg-dark-surface p-3 text-caption text-text-secondary" data-testid="parcel-details">
          {(areaName || ward) && (
            <p>{[areaName, ward ? t("scorecard.wardLabel", { ward }) : null].filter(Boolean).join(" · ")}</p>
          )}
          {pin && (
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="font-mono text-text-primary">PIN {formatPin(pin)}</span>
              <button
                type="button"
                onClick={copy}
                className="rounded px-1 text-link cursor-pointer hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                {copied ? t("scorecard.header.copied") : t("scorecard.header.copyPin")}
              </button>
              <a
                href={`https://www.cookcountyassessor.com/pin/${pin.replace(/\D/g, "")}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-link hover:underline"
              >
                {t("scorecard.header.assessor")} ↗
              </a>
            </p>
          )}
          <ParcelResolution resolution={resolution} flat />
        </div>
      )}
    </div>
  );
}
