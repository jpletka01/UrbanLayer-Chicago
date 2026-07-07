// Record-module violations block (de-carded): counts in the header meta, top
// categories as caption rows, descriptions visible top-N + ShowMore. Address-
// exact scope label preserved (2026-06-30 policy).
import { useTranslation } from "react-i18next";
import type { ViolationSummary } from "../../lib/types";
import { SubSection, ShowMore } from "./ProfileModule";

const AlertIcon = (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
  </svg>
);

export function ScorecardViolationsCard({ data, scopeLabel }: { data: ViolationSummary; scopeLabel?: string }) {
  const { t } = useTranslation("data");

  const categories = Object.entries(data.by_category ?? {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  return (
    <SubSection
      title={t("violations.title")}
      icon={AlertIcon}
      meta={
        <>
          {data.total.toLocaleString()} {t("violations.total").toLowerCase()}
          {data.open_count > 0 && (
            <span className="text-state-warning"> · {data.open_count} {t("violations.open").toLowerCase()}</span>
          )}
        </>
      }
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
          <ShowMore
            items={data.top_descriptions}
            limit={2}
            render={(visible) => (
              <ul className="space-y-1">
                {visible.map((desc, i) => (
                  <li key={i} className="text-caption text-text-muted leading-snug">{desc}</li>
                ))}
              </ul>
            )}
          />
        )}

        {data.capped && (
          <p className="text-caption text-text-muted italic">
            {t("violations.showingFirst", { count: data.total.toLocaleString() })}
          </p>
        )}
      </div>
    </SubSection>
  );
}
