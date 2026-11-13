// "Save search" in Discovery's search summary (Saved, decision Item 119): names the search (the filters, by
// default) and keeps it in the account; Saved then says how many lots match that didn't. Signed out, it offers
// sign-in in place of the name field (a saved search lives on the server, where its matches are counted).
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bookmark, BookmarkCheck, LogIn } from "lucide-react";
import { useAuthContext } from "../../contexts/AuthContext";
import { SavedError, savedApi } from "../../lib/api";
import { buildRequest } from "../../discovery/searchClient";
import type { DiscoveryDraft } from "../../discovery/draftModel";
import type { Registry } from "../../discovery/types";
import { track } from "../../lib/tracking";
import { STROKE } from "../icons";

export function SaveSearch({ draft, registry, defaultName }: { draft: DiscoveryDraft; registry: Registry; defaultName: string }) {
  const { t } = useTranslation("next");
  const { isAuthenticated, authRequired, signIn } = useAuthContext();
  const account = isAuthenticated || !authRequired;
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "saved" | "full" | "failed">("idle");

  if (state === "saved") {
    return (
      <span className="inline-flex items-center gap-1.5" role="status" data-testid="search-saved">
        <BookmarkCheck aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("saved.searchSaved")}
        <Link to="/saved?tab=searches" className="underline underline-offset-2">{t("saved.seeInSaved")}</Link>
      </span>
    );
  }
  if (!open) {
    return (
      <button type="button" onClick={() => { setName(shortName(defaultName)); setOpen(true); }} data-testid="save-search"
        className="inline-flex items-center gap-1 rounded-lg px-2 py-1 hover:bg-nx-ink/5">
        <Bookmark aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("saved.saveSearch")}
      </button>
    );
  }
  if (!account) {
    return (
      <span className="inline-flex flex-wrap items-center gap-2" data-testid="save-search-signin">
        {t("saved.saveSearchSignIn")}
        <button type="button" onClick={signIn} className="inline-flex items-center gap-1 font-semibold underline underline-offset-2">
          <LogIn aria-hidden className="h-4 w-4" strokeWidth={STROKE} />{t("frame.signIn")}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="underline underline-offset-2">{t("saved.cancel")}</button>
      </span>
    );
  }
  const save = async () => {
    const v = name.trim();
    if (!v) return;
    setState("saving");
    try {
      const request = buildRequest({
        panelState: draft.panelState, text: draft.text, sort: draft.sort, topicId: draft.topicId,
        includeUnusual: !!draft.includeUnusual, scope: draft.scope ?? null,
      }, registry);
      await savedApi.saveSearch(v, draft, request);
      track("investigate_click", { card_name: "next_save_search" });
      setState("saved");
    } catch (e) {
      setState(e instanceof SavedError && e.status === 409 ? "full" : "failed");
    }
  };
  return (
    <form onSubmit={(e) => { e.preventDefault(); void save(); }} className="inline-flex flex-wrap items-center gap-2" data-testid="save-search-form">
      <label htmlFor="save-search-name" className="sr-only">{t("saved.searchName")}</label>
      <input id="save-search-name" value={name} maxLength={80} autoFocus onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}
        className="w-56 min-w-0 rounded-lg bg-nx-page px-2 py-1 ring-1 ring-nx-ink/20" />
      <button type="submit" disabled={state === "saving" || !name.trim()} className="rounded-full bg-nx-ink px-3 py-1 font-semibold text-nx-on-ink disabled:opacity-50">
        {t("saved.saveNote")}
      </button>
      <button type="button" onClick={() => setOpen(false)} className="underline underline-offset-2">{t("saved.cancel")}</button>
      {state === "full" && <span role="alert">{t("saved.searchesFull")}</span>}
      {state === "failed" && <span role="alert">{t("saved.saveFailed")}</span>}
    </form>
  );
}

/** A default name within the 80-character limit, cut between filters (or words), never mid-word. */
export function shortName(name: string, max = 80): string {
  if (name.length <= max) return name;
  const cut = name.slice(0, max - 1);
  const at = Math.max(cut.lastIndexOf(", "), cut.lastIndexOf(" "));
  return `${(at > 20 ? cut.slice(0, at) : cut).replace(/[,\s]+$/, "")}…`;
}
