// Page-scale Violations card, Tier-3 compact: counts in the header, top categories
// as caption rows, descriptions behind a disclosure. Address-exact scope label
// preserved (2026-06-30 policy).
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { ViolationSummary } from "../../lib/types";
import { Card } from "../ui/Card";

const AlertIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
  </svg>
);

export function ScorecardViolationsCard({ data, scopeLabel }: { data: ViolationSummary; scopeLabel?: string }) {
  const { t } = useTranslation("data");
  const [showDescriptions, setShowDescriptions] = useState(false);

  const categories = Object.entries(data.by_category ?? {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  return (
    <Card
      title={t("violations.title")}
      icon={AlertIcon}
      headerRight={
        <span className="text-caption text-text-muted">
          {data.total.toLocaleString()} {t("violations.total").toLowerCase()}
          {data.open_count > 0 && (
            <span className="text-state-warning"> · {data.open_count} {t("violations.open").toLowerCase()}</span>
          )}
        </span>
      }
      divider
      className="flex-1"
    >
      <div className="space-y-3">
        {scopeLabel && <p className="text-caption text-text-muted">{scopeLabel}</p>}

        {categories.length > 0 && (
          <div className="space-y-1.5">
            {categories.map(([cat, count]) => (
              <div key={cat} className="flex justify-between items-baseline gap-3 text-caption">
                <span className="text-text-secondary truncate">{t(`violations.categoryLabels.${cat}`, { defaultValue: cat })}</span>
                <span className="text-text-primary tabular-nums shrink-0">{count}</span>
              </div>
            ))}
          </div>
        )}

        {data.top_descriptions?.length > 0 && (
          <div>
            <button
              onClick={() => setShowDescriptions((s) => !s)}
              className="flex items-center gap-1.5 text-caption text-text-muted hover:text-text-secondary transition-colors"
            >
              <svg className={`w-3 h-3 transition-transform duration-200 ${showDescriptions ? "" : "-rotate-90"}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
              {t("violations.topDescriptions")}
            </button>
            {showDescriptions && (
              <ul className="mt-1.5 space-y-1">
                {data.top_descriptions.map((desc, i) => (
                  <li key={i} className="text-caption text-text-muted leading-snug pl-3">{desc}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {data.capped && (
          <p className="text-caption text-text-muted italic">
            {t("violations.showingFirst", { count: data.total.toLocaleString() })}
          </p>
        )}
      </div>
    </Card>
  );
}
