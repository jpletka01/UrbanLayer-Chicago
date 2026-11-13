// Saved (Phase 9, decision Item 119): the lots and Discovery searches a visitor kept, and what changed since.
// Lots: each card says what changed on the lot since it was saved (a sale, a permit, a violation, a rezoning filed
// or passed, its zoning or overlays), checked when the card scrolls into view, and keeps a private note.
// Searches: each says how many lots match now that didn't when it was saved, and opens in Discovery.
// Signed out, saved lots live in this browser and one quiet line offers sign-in; nothing is locked.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import * as Tabs from "@radix-ui/react-tabs";
import { Bookmark, Check, LogIn, Map as MapIcon, MessageCircle, Pencil, RefreshCw, Search, SquareArrowOutUpRight, Trash2 } from "lucide-react";
import { useAuthContext } from "../../contexts/AuthContext";
import { savedApi, type SavedLotChanges, type SavedSearchNew, type SavedSearchWire } from "../../lib/api";
import { loadRegistry } from "../../discovery/registryClient";
import { summarize } from "../../discovery/summary";
import type { CQS, Registry } from "../../discovery/types";
import { track } from "../../lib/tracking";
import { AppFrame } from "../frame/AppFrame";
import { STROKE } from "../icons";
import { Pill } from "../ui/Blocks";
import { lotHref } from "../home/lotMemory";
import { BlockSlice } from "../ui/BlockSlice";
import { BOOKMARK_ON } from "./bookmark";
import { familyOf } from "./savedModel";
import { useSaved, type SavedLot } from "./savedStore";
import { changeLine, limiter, uncheckedWords } from "./savedModel";

type TabId = "lots" | "searches";
const checks = limiter(3);
const SHOWN_CHANGES = 4;

export default function SavedNextPage() {
  const { t } = useTranslation("next");
  const { signIn } = useAuthContext();
  const saved = useSaved();
  const [params] = useSearchParams();
  const [tab, setTab] = useState<TabId>(() => (params.get("tab") === "searches" ? "searches" : "lots"));

  return (
    <AppFrame crumbs={[t("nav.saved")]}>
      <div className="mx-auto flex max-w-[1040px] flex-col gap-6 px-4 py-8 sm:px-8 sm:py-10" data-testid="saved">
        <div className="flex flex-wrap items-end gap-3">
          <h1 className="text-[1.875rem] font-semibold tracking-[-0.02em]">{t("saved.title")}</h1>
          <span className="flex-1" />
          <Link to="/chat" className="inline-flex items-center gap-1.5 text-caption font-medium underline underline-offset-2 touch-target" data-testid="saved-chats">
            <MessageCircle aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("saved.chats")}
          </Link>
        </div>

        {!saved.account && (
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption nx-muted" data-testid="saved-signin">
            {t("saved.browserOnly")}
            <button type="button" onClick={signIn} className="inline-flex items-center gap-1.5 font-semibold text-nx-ink underline underline-offset-2 touch-target">
              <LogIn aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("frame.signIn")}
            </button>
          </p>
        )}
        {saved.moved && saved.moved.added > 0 && (
          <p role="status" className="flex items-center gap-2 rounded-xl bg-nx-block px-4 py-3 text-caption" data-testid="saved-moved">
            <Check aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />
            {t("saved.moved", { count: saved.moved.added })}
            {saved.moved.kept > 0 && ` ${t("saved.kept", { count: saved.moved.kept })}`}
          </p>
        )}
        {saved.full && (
          <p role="alert" className="rounded-xl bg-nx-block px-4 py-3 text-caption" data-testid="saved-full">{t("saved.full", { max: saved.max })}</p>
        )}

        <Tabs.Root value={tab} onValueChange={(v) => setTab(v as TabId)} className="flex flex-col gap-5">
          <Tabs.List aria-label={t("saved.title")} className="flex gap-5 border-b border-nx-ink/10">
            {(["lots", "searches"] as const).map((id) => (
              <Tabs.Trigger key={id} value={id} data-testid={`saved-tab-${id}`}
                className="whitespace-nowrap py-2 text-nx-ink/[0.64] hover:text-nx-ink data-[state=active]:font-semibold data-[state=active]:text-nx-ink data-[state=active]:shadow-[inset_0_-2px_0_rgb(var(--nx-ink))] touch-target">
                {t(`saved.tabs.${id}`)}{id === "lots" && saved.lots.length > 0 ? ` · ${saved.lots.length}` : ""}
              </Tabs.Trigger>
            ))}
          </Tabs.List>
          <Tabs.Content value="lots" className="outline-none">
            <LotsTab />
          </Tabs.Content>
          <Tabs.Content value="searches" className="outline-none">
            {saved.account ? <SearchesTab /> : (
              <p className="nx-muted" data-testid="saved-searches-signin">{t("saved.searchesSignIn")}</p>
            )}
          </Tabs.Content>
        </Tabs.Root>
      </div>
    </AppFrame>
  );
}

function LotsTab() {
  const { t } = useTranslation("next");
  const saved = useSaved();
  if (saved.status === "loading" && saved.lots.length === 0) return <p role="status" className="nx-muted">{t("frame.loading")}</p>;
  if (saved.status === "error") return <p role="alert" className="nx-muted" data-testid="saved-error">{t("saved.loadFailed")}</p>;
  if (saved.lots.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-[20px] bg-nx-block p-5" data-testid="saved-empty">
        <p className="flex items-start gap-2"><Bookmark aria-hidden className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={STROKE} />{t("saved.empty")}</p>
        <Link to="/discovery" className="inline-flex items-center gap-2 rounded-full bg-nx-ink px-4 py-2 font-semibold text-nx-on-ink touch-target">
          <MapIcon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("home.findLots")}
        </Link>
      </div>
    );
  }
  return (
    <ul role="list" className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,300px),1fr))] gap-4" data-testid="saved-lots">
      {saved.lots.map((lot) => <SavedLotCard key={lot.key} lot={lot} onUnsave={() => void saved.toggle(lot)} account={saved.account} />)}
    </ul>
  );
}

function SavedLotCard({ lot, onUnsave, account }: { lot: SavedLot; onUnsave: () => void; account: boolean }) {
  const { t, i18n } = useTranslation("next");
  const locale = i18n.language.startsWith("es") ? "es-MX" : "en-US";
  const dateFmt = useMemo(() => new Intl.DateTimeFormat(locale, { month: "short", day: "numeric", year: "numeric" }), [locale]);
  const day = (iso: string) => dateFmt.format(new Date(`${iso}T12:00:00`));
  const money = (v: number) => `$${Math.round(v).toLocaleString(locale)}`;
  const changes = useLotChanges(account ? lot.id : null);

  return (
    <li className="relative flex flex-col overflow-hidden rounded-2xl bg-nx-block" data-testid="saved-lot" ref={changes.observe}>
      {/* The block around the lot, as Discovery's list draws it (owner, 2026-11-12). */}
      <Link to={lotHref(lot)} tabIndex={-1} aria-hidden className="block hover:opacity-90">
        <BlockSlice pin10={lot.pin ? lot.pin.slice(0, 10) : null} zoneTag={lot.zone} family={familyOf(lot.zone)} outline={lot.outline} />
      </Link>
      <button type="button" onClick={onUnsave} aria-pressed aria-label={t("home.unsave", { address: lot.address })} title={t("home.unsaveShort")}
        className={`absolute right-2 top-2 z-10 grid h-8 w-8 place-items-center rounded-lg touch-icon ${BOOKMARK_ON}`} data-testid="saved-unsave">
        <Bookmark aria-hidden className="h-4 w-4" strokeWidth={STROKE} fill="currentColor" />
      </button>
      <div className="flex flex-col gap-3 p-4">
      <Link to={lotHref(lot)} className="flex min-w-0 flex-col gap-0.5 rounded-xl hover:opacity-80">
        <span className="font-semibold [overflow-wrap:anywhere]">{lot.address}</span>
        <span className="text-caption nx-muted">{[lot.area, t("home.savedOn", { date: dateFmt.format(lot.at) })].filter(Boolean).join(" · ")}</span>
      </Link>

      {account && lot.id ? (
        <ChangesBlock state={changes} lot={lot} day={day} money={money} />
      ) : (
        <p className="text-caption nx-muted">{t("saved.changesSignIn")}</p>
      )}
      {account && lot.id && <NoteEditor id={lot.id} note={lot.note} address={lot.address} />}
      </div>
    </li>
  );
}

type ChangesState = { observe: (el: HTMLElement | null) => void; data: SavedLotChanges | null; failed: boolean; retry: () => void };

/** Ask what changed on one saved lot once its card is near the screen (at most three checks run at once). */
function useLotChanges(id: string | null): ChangesState {
  const [el, setEl] = useState<HTMLElement | null>(null);
  // Without IntersectionObserver (old browsers, tests) every card checks at once, still three at a time.
  const [visible, setVisible] = useState(() => typeof IntersectionObserver === "undefined");
  const [data, setData] = useState<SavedLotChanges | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!el || visible) return;
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) setVisible(true); }, { rootMargin: "300px" });
    io.observe(el);
    return () => io.disconnect();
  }, [el, visible]);
  useEffect(() => {
    if (!id || !visible) return;
    let live = true;
    checks(() => savedApi.changes(id)).then((d) => { if (live) setData(d); }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [id, visible, attempt]);
  const retry = useCallback(() => { setFailed(false); setAttempt((n) => n + 1); }, []);
  return { observe: setEl, data, failed, retry };
}

function ChangesBlock({ state, lot, day, money }: { state: ChangesState; lot: SavedLot; day: (iso: string) => string; money: (v: number) => string }) {
  const { t } = useTranslation("next");
  const [all, setAll] = useState(false);
  const { data, failed } = state;
  if (failed) {
    return (
      <p className="flex flex-wrap items-center gap-2 text-caption nx-muted" data-testid="saved-changes-failed">
        {t("saved.changesFailed")}
        <button type="button" onClick={state.retry} className="inline-flex items-center gap-1 font-medium text-nx-ink underline underline-offset-2 touch-target">
          <RefreshCw aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />{t("saved.retry")}
        </button>
      </p>
    );
  }
  if (!data) return <p role="status" className="text-caption nx-muted">{t("saved.checking")}</p>;
  const lines = data.changes.map((c) => changeLine(c, lot, t, money));
  const shown = all ? lines : lines.slice(0, SHOWN_CHANGES);
  return (
    <div className="flex flex-col gap-2" data-testid="saved-changes">
      <p className="text-caption font-semibold">{t("saved.since", { date: day(data.since) })}</p>
      {lines.length === 0 ? (
        <p className="text-caption nx-muted" data-testid="saved-nothing-new">{data.status === "partial" ? t("saved.nothingFound") : t("saved.nothingNew")}</p>
      ) : (
        <ul role="list" className="flex flex-col gap-1.5">
          {shown.map((l, i) => (
            <li key={i}>
              {l.external ? (
                <a href={l.href} target="_blank" rel="noopener noreferrer" className="inline-flex max-w-full items-center gap-2 hover:underline" data-testid="saved-change">
                  <Pill tone={l.tone} icon={l.icon}>{l.date ? day(l.date) : t("saved.recently")}</Pill>
                  <span className="truncate text-caption" title={l.text}>{l.text}</span>
                  <SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
                </a>
              ) : (
                <Link to={l.href} className="inline-flex max-w-full items-center gap-2 hover:underline" data-testid="saved-change">
                  <Pill tone={l.tone} icon={l.icon}>{l.date ? day(l.date) : t("saved.recently")}</Pill>
                  <span className="truncate text-caption" title={l.text}>{l.text}</span>
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}
      {lines.length > SHOWN_CHANGES && (
        <button type="button" onClick={() => setAll((a) => !a)} className="self-start text-caption font-medium underline underline-offset-2 touch-target">
          {all ? t("saved.fewer") : t("saved.more", { count: lines.length - SHOWN_CHANGES })}
        </button>
      )}
      {data.unchecked.length > 0 && (
        <p className="text-caption nx-muted" data-testid="saved-unchecked">{t("saved.couldntCheck", { what: uncheckedWords(data.unchecked, t) })}</p>
      )}
      {data.watching_since && !data.unchecked.includes("zoning") && (
        <p className="text-caption nx-muted">{t("saved.watchingZoning", { date: day(data.watching_since) })}</p>
      )}
    </div>
  );
}

function NoteEditor({ id, note, address }: { id: string; note: string; address: string }) {
  const { t } = useTranslation("next");
  const saved = useSaved();
  const [draft, setDraft] = useState(note);
  const [editing, setEditing] = useState(false);
  const [state, setState] = useState<"idle" | "saving" | "failed">("idle");
  const box = useRef<HTMLTextAreaElement | null>(null);
  useEffect(() => { if (editing) box.current?.focus(); }, [editing]);
  const save = async () => {
    setState("saving");
    const ok = await saved.setNote(id, draft);
    setState(ok ? "idle" : "failed");
    if (ok) setEditing(false);
  };
  if (!editing) {
    return (
      <button type="button" onClick={() => { setDraft(note); setEditing(true); }} data-testid="saved-note"
        className="flex items-start gap-2 rounded-xl px-3 py-2 text-left text-caption ring-1 ring-nx-ink/10 hover:bg-nx-ink/5">
        <Pencil aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
        <span className={`whitespace-pre-wrap [overflow-wrap:anywhere] ${note ? "" : "nx-muted"}`}>{note || t("saved.addNote")}</span>
      </button>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <label className="sr-only" htmlFor={`note-${id}`}>{t("saved.noteFor", { address })}</label>
      <textarea id={`note-${id}`} ref={box} value={draft} maxLength={2000} rows={3} onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Escape") { setDraft(note); setEditing(false); } }}
        className="w-full rounded-xl bg-nx-page px-3 py-2 text-caption ring-1 ring-nx-ink/20 focus:outline-none focus:ring-2 focus:ring-nx-ink/50" data-testid="saved-note-input" />
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => void save()} disabled={state === "saving"} data-testid="saved-note-save"
          className="rounded-full bg-nx-ink px-4 py-1.5 text-caption font-semibold text-nx-on-ink disabled:opacity-50 touch-target">{t("saved.saveNote")}</button>
        <button type="button" onClick={() => { setDraft(note); setEditing(false); }} className="text-caption underline underline-offset-2 touch-target">{t("saved.cancel")}</button>
        <span className="text-caption nx-muted">{t("saved.notePrivate")}</span>
        {state === "failed" && <span role="alert" className="text-caption">{t("saved.noteFailed")}</span>}
      </div>
    </div>
  );
}

function SearchesTab() {
  const { t } = useTranslation("next");
  const [searches, setSearches] = useState<SavedSearchWire[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [registry, setRegistry] = useState<Registry | null>(null);
  useEffect(() => {
    let live = true;
    savedApi.searches().then((r) => { if (live) setSearches(r.searches); }).catch(() => { if (live) setFailed(true); });
    loadRegistry().then((r) => { if (live) setRegistry(r); }).catch(() => {});
    return () => { live = false; };
  }, []);
  if (failed) return <p role="alert" className="nx-muted">{t("saved.loadFailed")}</p>;
  if (!searches) return <p role="status" className="nx-muted">{t("frame.loading")}</p>;
  if (searches.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-[20px] bg-nx-block p-5" data-testid="saved-searches-empty">
        <p className="flex items-start gap-2"><Search aria-hidden className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={STROKE} />{t("saved.searchesEmpty")}</p>
        <Link to="/discovery" className="inline-flex items-center gap-2 rounded-full bg-nx-ink px-4 py-2 font-semibold text-nx-on-ink touch-target">
          <MapIcon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("home.findLots")}
        </Link>
      </div>
    );
  }
  return (
    <ul role="list" className="flex flex-col gap-3" data-testid="saved-searches">
      {searches.map((s) => (
        <SearchCard key={s.id} search={s} registry={registry}
          onChange={(next) => setSearches((list) => (list ?? []).map((x) => (x.id === next.id ? next : x)))}
          onDelete={() => setSearches((list) => (list ?? []).filter((x) => x.id !== s.id))} />
      ))}
    </ul>
  );
}

function SearchCard({ search, registry, onChange, onDelete }: {
  search: SavedSearchWire; registry: Registry | null; onChange: (s: SavedSearchWire) => void; onDelete: () => void;
}) {
  const { t, i18n } = useTranslation("next");
  const navigate = useNavigate();
  const locale = i18n.language.startsWith("es") ? "es-MX" : "en-US";
  const [news, setNews] = useState<SavedSearchNew | null>(null);
  const [newsFailed, setNewsFailed] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(search.name);
  useEffect(() => {
    let live = true;
    checks(() => savedApi.searchNew(search.id)).then((n) => { if (live) setNews(n); }).catch(() => { if (live) setNewsFailed(true); });
    return () => { live = false; };
  }, [search.id]);
  const sentence = useMemo(() => {
    if (!registry) return null;
    try { return summarize(search.cqs as unknown as CQS, registry); } catch { return null; }
  }, [registry, search.cqs]);
  const n = (v: number) => v.toLocaleString(locale);
  const open = () => {
    track("investigate_click", { card_name: "next_saved_search_open" });
    navigate(`/discovery?saved=${encodeURIComponent(search.id)}`);
  };
  const rename = async () => {
    const v = name.trim();
    if (!v || v === search.name) { setRenaming(false); setName(search.name); return; }
    try { onChange(await savedApi.renameSearch(search.id, v)); setRenaming(false); } catch { /* keep the field open */ }
  };
  const remove = async () => {
    try { await savedApi.deleteSearch(search.id); onDelete(); } catch { /* stays listed */ }
  };

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl bg-nx-block p-4" data-testid="saved-search">
      <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-1">
        {renaming ? (
          <form onSubmit={(e) => { e.preventDefault(); void rename(); }} className="flex items-center gap-2">
            <label className="sr-only" htmlFor={`name-${search.id}`}>{t("saved.searchName")}</label>
            <input id={`name-${search.id}`} value={name} maxLength={80} autoFocus onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Escape") { setName(search.name); setRenaming(false); } }}
              className="min-w-0 flex-1 rounded-lg bg-nx-page px-2 py-1 ring-1 ring-nx-ink/20" />
            <button type="submit" className="text-caption font-semibold underline underline-offset-2 touch-target">{t("saved.saveNote")}</button>
          </form>
        ) : (
          <span className="font-semibold [overflow-wrap:anywhere]">{search.name}</span>
        )}
        {sentence && <span className="text-caption nx-muted">{sentence}</span>}
        <span className="text-caption" data-testid="saved-search-news">
          {newsFailed ? t("saved.newsFailed")
            : !news ? t("saved.checking")
            : news.new > 0 ? (news.exact ? t("saved.newMatches", { count: news.new, total: n(news.total) }) : t("saved.moreMatches", { count: news.new, total: n(news.total) }))
            : t("saved.noNewMatches", { total: n(news.total) })}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={open} className="inline-flex items-center gap-2 rounded-full bg-nx-ink px-4 py-2 font-semibold text-nx-on-ink touch-target" data-testid="saved-search-open">
          <MapIcon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("saved.openSearch")}
        </button>
        <button type="button" onClick={() => setRenaming(true)} aria-label={t("saved.rename", { name: search.name })} title={t("saved.renameShort")}
          className="grid h-9 w-9 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon"><Pencil aria-hidden className="h-4 w-4" strokeWidth={STROKE} /></button>
        <button type="button" onClick={() => void remove()} aria-label={t("saved.deleteSearch", { name: search.name })} title={t("saved.deleteShort")}
          className="grid h-9 w-9 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon" data-testid="saved-search-delete"><Trash2 aria-hidden className="h-4 w-4" strokeWidth={STROKE} /></button>
      </div>
    </li>
  );
}
