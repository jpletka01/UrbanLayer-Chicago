// One Discovery flow in the new frame (decision Item 76; brief "Discovery"): one search box for a description,
// the goals as "Try" chips, results as cards, and every card opens its Profile. Same search engine as today's
// page (useDiscoverySearch → searchClient → /api/discovery/search); the list only, the map comes with M1–M3.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, LoaderCircle, Search, TriangleAlert } from "lucide-react";
import { loadRegistry } from "../../discovery/registryClient";
import { useDiscoverySearch } from "../../discovery/useDiscoverySearch";
import { recipeStatus } from "../../discovery/recipeStatus";
import { rowTitle } from "../../discovery/rowFigures";
import type { Registry, ResultRow } from "../../discovery/types";
import { track } from "../../lib/tracking";
import { AppFrame } from "../frame/AppFrame";
import { ICON, STROKE } from "../icons";
import { Pill } from "../ui/Blocks";

export default function DiscoveryNextPage() {
  const { t } = useTranslation("next");
  const { t: tp } = useTranslation("pages");
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [registryFailed, setRegistryFailed] = useState(false);
  const search = useDiscoverySearch(registry, {
    onCommit: (_inputs, response) => track("discovery_search", { total: response.result.total, source: "next_text" }),
  });

  useEffect(() => {
    loadRegistry().then((r) => (r ? setRegistry(r) : setRegistryFailed(true))).catch(() => setRegistryFailed(true));
  }, []);

  const topics = (registry?.topics ?? []).filter((topic) => recipeStatus(registry!, topic, tp).live).slice(0, 6);
  const response = search.applied;
  const rows = search.rows;

  return (
    <AppFrame crumbs={[t("discovery.crumb")]}>
      <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8 sm:px-7">
        <div className="flex flex-col gap-2">
          <h1 className="text-nx-figure">{t("discovery.title")}</h1>
          <p className="nx-muted">{t("discovery.lead")}</p>
        </div>

        <form
          role="search"
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => { e.preventDefault(); search.apply(); }}
        >
          <label htmlFor="nx-discovery-q" className="sr-only">{t("discovery.label")}</label>
          <div className="flex min-w-0 flex-1 items-center gap-2 rounded-xl bg-nx-ink/5 px-3">
            <Search aria-hidden className="h-4 w-4 shrink-0 nx-muted" strokeWidth={STROKE} />
            <input
              id="nx-discovery-q"
              type="search"
              value={search.draft.text}
              onChange={(e) => search.setText(e.target.value)}
              placeholder={t("discovery.placeholder")}
              className="h-11 min-w-0 flex-1 bg-transparent text-body text-nx-ink placeholder:text-nx-ink/[0.64] focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={!registry || search.draftIsInFlight}
            className="inline-flex h-11 items-center justify-center gap-1.5 rounded-xl bg-nx-primary px-4 font-medium text-nx-primary-fg disabled:opacity-50"
          >
            {search.loading ? <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" strokeWidth={STROKE} /> : <Search aria-hidden className="h-4 w-4" strokeWidth={STROKE} />}
            {t("discovery.search")}
          </button>
        </form>

        {topics.length > 0 && (
          <div className="flex flex-wrap items-center gap-2" aria-label={t("discovery.try")} role="group">
            <span className="text-caption nx-muted">{t("discovery.try")}</span>
            {topics.map((topic) => (
              <button
                key={topic.id}
                type="button"
                onClick={() => search.pickRecipe(topic)}
                className="rounded-full bg-nx-block px-3 py-1.5 text-caption hover:bg-nx-ink/10 touch-target"
              >
                {tp(`discovery.topic.${topic.id}.label`, { defaultValue: topic.label ?? topic.id })}
              </button>
            ))}
          </div>
        )}

        {registryFailed && <p role="alert" className="nx-muted">{t("discovery.unavailable")}</p>}
        {search.textNotice && (
          <p role="status" className="text-caption">
            <Pill tone="yellow" icon={TriangleAlert}>{t("discovery.notUnderstood")}</Pill>{" "}
            <span className="nx-muted">{search.textNotice.words.join(", ")}</span>
          </p>
        )}
        {search.unavailable && <p role="alert" className="nx-muted">{t("discovery.searchFailed")}</p>}

        {response && (
          <section aria-labelledby="nx-results" aria-busy={search.refreshing || undefined} className={search.refreshing ? "opacity-60" : ""}>
            <div role="status"><h2 id="nx-results" className="mb-4 text-body font-semibold">
              {response.result.total === 0
                ? t("discovery.none")
                : response.result.gated
                  ? t("discovery.countTop", { shown: rows.length, total: response.result.total.toLocaleString() })
                  : t("discovery.count", { count: response.result.total, total: response.result.total.toLocaleString() })}
            </h2></div>
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-7 lg:grid-cols-3" data-testid="next-results">
              {rows.map((row) => <ResultCard key={row.pin} row={row} />)}
            </ul>
            {search.nextOffset != null && !response.result.gated && (
              <button
                type="button"
                onClick={() => void search.loadMore()}
                disabled={search.loadingMore}
                className="mt-6 inline-flex items-center gap-1.5 rounded-xl bg-nx-ink/5 px-4 py-2 hover:bg-nx-ink/10 disabled:opacity-50"
              >
                {search.loadingMore && <LoaderCircle aria-hidden className="h-4 w-4 animate-spin" strokeWidth={STROKE} />}
                {t("discovery.more")}
              </button>
            )}
          </section>
        )}
      </div>
    </AppFrame>
  );
}

function ResultCard({ row }: { row: ResultRow }) {
  const { t, i18n } = useTranslation("next");
  const navigate = useNavigate();
  const { title, approx } = rowTitle(row);
  const n = (v: number) => Math.round(v).toLocaleString(i18n.language);
  const zone = row.zone_class ?? row.zoning_group ?? null;
  const room = row.allowed_far != null && row.lot_sqft != null && row.bldg_sqft != null
    ? Math.max(0, row.allowed_far * row.lot_sqft - row.bldg_sqft)
    : null;
  const open = () => {
    const q = new URLSearchParams({ pin: row.pin });
    if (row.address && !approx) q.set("address", title);
    navigate(`/scorecard?${q}`);
  };
  const facts: Array<[keyof typeof ICON, string, string]> = [];
  if (zone) facts.push(["zoning", t("discovery.card.zoning"), zone]);
  if (row.lot_sqft != null) facts.push(["lot", t("discovery.card.lot"), t("profile.build.sqft", { value: n(row.lot_sqft) })]);
  if (room != null) facts.push(["floorArea", t("discovery.card.room"), t("profile.build.sqft", { value: n(room) })]);
  if (row.last_sale_price != null && row.last_sale_date) {
    facts.push(["sale", t("discovery.card.sale"), t("discovery.card.saleValue", { price: `$${n(row.last_sale_price)}`, year: row.last_sale_date.slice(0, 4) })]);
  }
  return (
    <li className="flex min-w-0">
      <button type="button" onClick={open} className="flex w-full flex-col gap-3 rounded-2xl bg-nx-block p-5 text-left hover:bg-nx-ink/5" data-pin={row.pin}>
        <span className="flex items-start justify-between gap-2">
          <span className="font-semibold [overflow-wrap:anywhere]">{approx ? t("discovery.card.near", { address: title }) : title}</span>
        </span>
        <dl className="grid grid-cols-1 gap-1.5 text-caption">
          {facts.map(([icon, label, value]) => {
            const Icon = ICON[icon];
            return (
              <div key={label} className="flex items-center gap-2">
                <Icon aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
                <dt className="nx-muted">{label}</dt>
                <dd className="ml-auto tabular-nums">{value}</dd>
              </div>
            );
          })}
        </dl>
        {row.nominal_assessment && <Pill tone="yellow" icon={TriangleAlert}>{t("discovery.card.nominal")}</Pill>}
        <span className="mt-auto inline-flex items-center gap-1 text-caption underline underline-offset-2">
          {t("discovery.card.open")}
          <ArrowRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
        </span>
      </button>
    </li>
  );
}
