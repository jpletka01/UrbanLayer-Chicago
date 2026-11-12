// The signed-in home (Phase 8, wireframe v5 approved by the owner 2026-11-12): search first, then Saved lots, then
// the last six Recent lots (a bookmark on each, "Clear all", a heading that folds the row away), with Recent chats
// beside them as filler until something more useful takes the column. Lots live in this browser until the Saved
// epic (Phase 9) moves them to the account and adds what changed since a lot was saved.
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bookmark, BookmarkCheck, ChevronRight, Map as MapIcon, MapPin, Plus } from "lucide-react";
import { AddressInput } from "../../components/AddressInput";
import { listConversations } from "../../lib/api";
import type { Conversation } from "../../lib/types";
import { useAuthContext } from "../../contexts/AuthContext";
import { AppFrame } from "../frame/AppFrame";
import { STROKE } from "../icons";
import { lotHref, outlinePath, useLotMemory, type RememberedLot } from "./lotMemory";

const FOLD_KEY = "urbanlayer-next-recent-folded";

export default function HomeNextPage() {
  const { t, i18n } = useTranslation("next");
  const navigate = useNavigate();
  const { isAuthenticated, authRequired } = useAuthContext();
  const { recent, saved, isSaved, toggleSaved, clearRecent } = useLotMemory();
  const [folded, setFolded] = useState(() => { try { return localStorage.getItem(FOLD_KEY) === "1"; } catch { return false; } });
  const [chats, setChats] = useState<Conversation[] | null>(null);
  // "Today" for the cards' dates, read once per visit.
  const [today] = useState(() => startOfDay(Date.now()));
  const canList = isAuthenticated || !authRequired;

  useEffect(() => {
    if (!canList) return;
    let live = true;
    listConversations().then((c) => { if (live) setChats(c.slice(0, 4)); }).catch(() => { if (live) setChats([]); });
    return () => { live = false; };
  }, [canList]);

  const fold = () => setFolded((f) => {
    try { localStorage.setItem(FOLD_KEY, f ? "0" : "1"); } catch { /* per-viewer convenience only */ }
    return !f;
  });
  const dateFmt = new Intl.DateTimeFormat(i18n.language.startsWith("es") ? "es-MX" : "en-US", { month: "short", day: "numeric" });
  const when = (at: number) => {
    const days = Math.floor((today - startOfDay(at)) / 86_400_000);
    return days <= 0 ? t("home.today") : days === 1 ? t("home.yesterday") : dateFmt.format(at);
  };

  return (
    <AppFrame crumbs={[t("nav.home")]}>
      <div className="mx-auto flex max-w-[1040px] flex-col gap-7 px-4 py-8 sm:px-8 sm:py-10" data-testid="home">
        <h1 className="text-[1.875rem] font-semibold tracking-[-0.02em]">{t("home.welcome")}</h1>
        <AddressInput
          variant="page"
          fullWidth
          submitLabel={t("landing.showLot")}
          label={t("home.searchLabel")}
          placeholder={t("home.searchPlaceholder")}
          onSubmit={(a) => navigate(`/scorecard?address=${encodeURIComponent(a)}`)}
        />

        <div className="flex flex-wrap items-start gap-7">
          <div className="flex min-w-0 flex-[999_1_520px] flex-col gap-7">
            <section aria-labelledby="home-saved" className="flex flex-col gap-3" data-testid="home-saved">
              <div className="flex flex-wrap items-baseline gap-2.5">
                <h2 id="home-saved" className="text-[1.0625rem] font-semibold">{t("home.saved")}</h2>
                <span className="text-caption nx-muted">{t("home.savedHere")}</span>
              </div>
              {saved.length === 0 ? (
                <p className="text-caption nx-muted" data-testid="home-saved-empty">{t("home.savedEmpty")}</p>
              ) : (
                <ul role="list" className="grid grid-cols-[repeat(auto-fill,minmax(210px,1fr))] gap-3">
                  {saved.map((lot) => (
                    <LotCard key={lot.key} lot={lot} meta={t("home.savedOn", { date: dateFmt.format(lot.at) })} saved onToggle={() => toggleSaved(lot)} />
                  ))}
                </ul>
              )}
            </section>

            <section aria-labelledby="home-recent" className="flex flex-col gap-3" data-testid="home-recent">
              <div className="flex flex-wrap items-center gap-2.5">
                <button type="button" onClick={fold} aria-expanded={!folded} aria-controls="home-recent-list" className="inline-flex items-center gap-1.5 rounded-lg touch-target">
                  <ChevronRight aria-hidden className={`h-4 w-4 transition-transform ${folded ? "" : "rotate-90"}`} strokeWidth={STROKE} />
                  <h2 id="home-recent" className="text-[1.0625rem] font-semibold">{t("home.recent")}</h2>
                </button>
                <span className="text-caption nx-muted">{t("home.recentHere")}</span>
                <span className="flex-1" />
                {recent.length > 0 && (
                  <button type="button" onClick={clearRecent} className="text-caption font-medium underline underline-offset-2 touch-target" data-testid="home-clear">{t("home.clearAll")}</button>
                )}
              </div>
              <div id="home-recent-list" hidden={folded}>
                {recent.length === 0 ? (
                  <p className="text-caption nx-muted">{t("home.recentEmpty")}</p>
                ) : (
                  <ul role="list" className="grid grid-cols-[repeat(auto-fill,minmax(210px,1fr))] gap-3">
                    {recent.map((lot) => (
                      <LotCard key={lot.key} lot={lot} meta={[lot.zone, lot.area, when(lot.at)].filter(Boolean).join(" · ")} saved={isSaved(lot.key)} onToggle={() => toggleSaved(lot)} />
                    ))}
                  </ul>
                )}
              </div>
            </section>
          </div>

          <section aria-labelledby="home-chats" className="flex min-w-0 flex-[1_1_280px] flex-col gap-2.5" data-testid="home-chats">
            <h2 id="home-chats" className="text-[1.0625rem] font-semibold text-nx-pill-purple">{t("home.chats")}</h2>
            {!canList ? null : chats === null ? (
              <p className="text-caption nx-muted" role="status">{t("frame.loading")}</p>
            ) : chats.length === 0 ? (
              <p className="text-caption nx-muted">{t("frame.noChats")}</p>
            ) : (
              <ul role="list" className="flex flex-col gap-2">
                {chats.map((c) => (
                  <li key={c.id}>
                    <Link to={`/c/${c.id}`} className="flex flex-col gap-0.5 rounded-xl px-3 py-2.5 ring-1 ring-nx-ink/10 hover:bg-nx-ink/5">
                      <span className="truncate font-medium">{c.title || t("frame.untitledChat")}</span>
                      {c.updatedAt ? <span className="text-caption nx-muted">{when(c.updatedAt)}</span> : null}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <Link to="/chat" className="inline-flex items-center gap-2 self-start rounded-full bg-nx-pill-purple-bg px-4 py-2 font-semibold text-nx-pill-purple touch-target">
              <Plus aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
              {t("frame.newChat")}
            </Link>
          </section>
        </div>

        <Link to="/discovery" className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-2xl bg-nx-stat-a px-5 py-4 text-nx-card-ink">
          <MapIcon aria-hidden className="h-[22px] w-[22px]" strokeWidth={STROKE} />
          <span className="font-semibold">{t("home.findLots")}</span>
          <span className="text-caption text-nx-card-ink/70">{t("home.findLotsNote")}</span>
        </Link>
      </div>
    </AppFrame>
  );
}

function startOfDay(ms: number): number {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/** One lot: its outline on a plain block, the address, a line about it, and a bookmark that saves or unsaves it. */
function LotCard({ lot, meta, saved, onToggle }: { lot: RememberedLot; meta: string; saved: boolean; onToggle: () => void }) {
  const { t } = useTranslation("next");
  const Icon = saved ? BookmarkCheck : Bookmark;
  return (
    <li className="relative">
      <Link to={lotHref(lot)} className="flex flex-col gap-2 rounded-2xl bg-nx-block p-3.5 hover:bg-nx-ink/5" data-testid="home-lot">
        <span aria-hidden className="grid h-16 place-items-center rounded-xl bg-nx-stat-b">
          {lot.outline ? (
            <svg viewBox="0 0 120 64" className="h-16 w-[120px]"><path d={outlinePath(lot.outline, 120, 64, 8)} className="fill-nx-lot" /></svg>
          ) : (
            <MapPin className="h-6 w-6 text-nx-card-ink" strokeWidth={STROKE} />
          )}
        </span>
        <span className="truncate pr-9 font-semibold">{lot.address}</span>
        {meta && <span className="truncate text-caption nx-muted">{meta}</span>}
      </Link>
      <button
        type="button"
        onClick={onToggle}
        aria-pressed={saved}
        aria-label={saved ? t("home.unsave", { address: lot.address }) : t("home.save", { address: lot.address })}
        title={saved ? t("home.unsaveShort") : t("home.saveShort")}
        className="absolute right-2 top-2 grid h-8 w-8 place-items-center rounded-lg bg-nx-page hover:bg-nx-ink/5 touch-icon"
        data-testid="home-bookmark"
      >
        <Icon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
      </button>
    </li>
  );
}
