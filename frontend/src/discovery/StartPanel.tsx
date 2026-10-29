// Start panel (redesign Phase 2): what the page shows before anything has been searched,
// instead of silently running a recipe. It offers four honest ways in, and each one is a
// single explicit "search this": a recipe (with what it filters, read from its presets so
// the words cannot drift from the filters), one neighborhood, every parcel, or the user's own
// last search (re-run, never replayed as a result). It renders no result of any kind.

import { useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Chip } from "../components/ui/Chip";
import { chipLabel } from "./chips";
import { CoverageBanner } from "./CoverageBanner";
import { DescribeBox } from "./DescribeBox";
import { SORTED_CAS } from "./communityAreas";
import { coverageOf } from "./coverage";
import { IndexAsOf } from "./IndexAsOf";
import type { SavedSearch } from "./lastSearch";
import { recipeStatus } from "./recipeStatus";
import type { Registry, TopicDef } from "./types";

export type StartChoice =
  | { kind: "recipe"; topic: TopicDef }
  | { kind: "neighborhood"; areaId: number }
  | { kind: "all" }
  | { kind: "resume" };

interface Props {
  registry: Registry;
  resumable: SavedSearch | null;
  onChoose: (choice: StartChoice) => void;
  onForgetResume: () => void;
  /** The free-text draft: "Describe it" is the fifth way in, beside recipes, neighborhoods, all and resume. */
  text: string;
  onTextChange: (text: string) => void;
  onSubmitText: () => void;
  /** What the text compiler made of the phrase (TextFeedback), rendered under the box. */
  textFeedback?: ReactNode;
}

export function StartPanel({
  registry, resumable, onChoose, onForgetResume, text, onTextChange, onSubmitText, textFeedback,
}: Props) {
  const { t } = useTranslation("pages");
  const [query, setQuery] = useState("");

  const coverage = coverageOf(registry);
  const areas = useMemo(
    () => SORTED_CAS.filter((a) => coverage.mode === "all" || coverage.liveAreas.includes(a.id)),
    [coverage.mode, coverage.liveAreas],
  );
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? areas.filter((a) => a.name.toLowerCase().includes(q)) : areas;
  }, [areas, query]);

  const filtersLine = (topic: TopicDef): string =>
    Object.entries(topic.presets)
      .map(([id, predicate]) => chipLabel(id, predicate, registry.filters.find((f) => f.id === id)))
      .join(" · ");

  return (
    <div className="h-full overflow-y-auto p-4 md:p-5" data-testid="discovery-start-panel">
      <h1 className="text-section">{t("discovery.title")}</h1>
      <p className="text-caption text-text-muted">{t("discovery.subtitle")}</p>
      <IndexAsOf registry={registry} className="mt-1" />
      <div className="mt-2"><CoverageBanner registry={registry} /></div>

      <h2 className="mt-5 text-title">{t("discovery.start.heading")}</h2>
      <div className="mt-2">
        <DescribeBox value={text} onChange={onTextChange} onSubmit={onSubmitText} />
        {textFeedback && <div className="mt-2">{textFeedback}</div>}
      </div>

      {resumable && (
        <section className="mt-4 rounded-lg border border-dark-border bg-dark-elevated/40 p-3" data-testid="discovery-start-resume">
          <h3 className="text-overline uppercase text-text-muted">{t("discovery.start.resumeHeading")}</h3>
          <p className="mt-1 text-body text-text-secondary">{resumable.sentence}</p>
          <div className="mt-2 flex items-center gap-3">
            <button
              type="button"
              onClick={() => onChoose({ kind: "resume" })}
              className="rounded-lg bg-action px-3 py-1.5 text-caption font-medium text-text-on-accent transition-colors hover:bg-action-hover"
            >
              {t("discovery.start.resume")}
            </button>
            <button
              type="button"
              onClick={onForgetResume}
              className="text-micro text-text-muted transition-colors hover:text-accent"
            >
              {t("discovery.start.forget")}
            </button>
          </div>
        </section>
      )}

      {registry.topics.length > 0 && (
        <section className="mt-5">
          <h3 className="mb-2 text-overline uppercase text-text-muted">{t("discovery.start.recipes")}</h3>
          <div className="grid grid-cols-1 gap-2">
            {registry.topics.map((topic) => {
              const status = recipeStatus(registry, topic, t);
              return (
                <button
                  key={topic.id}
                  type="button"
                  onClick={() => onChoose({ kind: "recipe", topic })}
                  title={status.title}
                  data-testid={`discovery-start-recipe-${topic.id}`}
                  className={`rounded-lg border border-dark-border p-3 text-left transition-colors hover:border-dark-border-strong ${
                    status.live ? "" : "opacity-70"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-body font-medium text-text-primary">
                      {t(`discovery.topic.${topic.id}.label`, { defaultValue: topic.label ?? "" })}
                    </span>
                    <Chip size="sm" tone={status.tone} className="flex-shrink-0">{status.badge}</Chip>
                  </div>
                  {topic.description && (
                    <p className="mt-0.5 text-caption text-text-muted">
                      {t(`discovery.topic.${topic.id}.description`, topic.description)}
                    </p>
                  )}
                  <p className="mt-1 text-micro text-text-muted" data-testid={`discovery-start-filters-${topic.id}`}>
                    {t("discovery.start.filtersLine", { list: filtersLine(topic) })}
                  </p>
                </button>
              );
            })}
          </div>
        </section>
      )}

      <section className="mt-5">
        <h3 className="mb-2 text-overline uppercase text-text-muted">{t("discovery.start.browse")}</h3>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("discovery.start.browsePlaceholder", { count: areas.length })}
          aria-label={t("discovery.start.browseAria")}
          className="w-full rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none"
        />
        <ul className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-dark-border" data-testid="discovery-start-areas">
          {shown.map((a) => (
            <li key={a.id}>
              <button
                type="button"
                onClick={() => onChoose({ kind: "neighborhood", areaId: a.id })}
                className="w-full px-3 py-2 text-left text-body text-text-secondary transition-colors hover:bg-dark-elevated hover:text-text-primary"
              >
                {a.name}
              </button>
            </li>
          ))}
          {shown.length === 0 && <li className="px-3 py-2 text-caption text-text-muted">{t("discovery.start.browseNone")}</li>}
        </ul>
      </section>

      <p className="mt-5 text-caption text-text-muted">
        <button
          type="button"
          onClick={() => onChoose({ kind: "all" })}
          data-testid="discovery-start-all"
          className="text-link underline-offset-2 hover:underline"
        >
          {t("discovery.start.all")}
        </button>{" "}
        {t("discovery.start.allNote")}
      </p>
    </div>
  );
}
