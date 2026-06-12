import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { track } from "../../lib/tracking";

export function buildScorecardHref(pin: string | null | undefined, address: string | null | undefined): string | null {
  if (pin) return `/scorecard?pin=${pin.replace(/\D/g, "")}`;
  if (address) return `/scorecard?address=${encodeURIComponent(address)}`;
  return null;
}

export function ScorecardBridgeCard({ pin, address }: { pin: string | null; address: string | null }) {
  const { t } = useTranslation("sidebar");
  const href = buildScorecardHref(pin, address);
  if (!href) return null;

  return (
    <div className="rounded-lg bg-dark-surface border border-dark-border px-3 py-2.5 flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-xs font-medium text-text-primary truncate">
          <svg className="w-3.5 h-3.5 text-accent shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
          </svg>
          <span className="truncate">{address ?? t("bridge.pin", { pin })}</span>
        </div>
        {address && pin && (
          <div className="text-[10px] text-text-muted font-mono mt-0.5 pl-5">{t("bridge.pin", { pin })}</div>
        )}
      </div>
      <Link
        to={href}
        onClick={() => track("scorecard_bridge_click", { source: "bridge_card", pin, address })}
        className="shrink-0 text-[11px] font-medium text-accent hover:text-accent-hover transition-colors whitespace-nowrap"
      >
        {t("bridge.viewScorecard")} →
      </Link>
    </div>
  );
}
