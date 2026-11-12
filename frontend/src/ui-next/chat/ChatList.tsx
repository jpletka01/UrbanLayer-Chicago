// The chat's own sidebar (owner review 2026-11-12): beside the main panel, which the chat page opens collapsed to its
// icons, so past chats are one click away instead of behind the panel's Chat folder. New chat first, a search over
// titles, then the chats grouped by date with the open one marked. Hiding it folds it to a strip of icons in place,
// like the main panel (owner review 2026-11-12: a list that vanished read as lost); on a phone it opens as a sheet.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LogIn, PanelLeftClose, PanelLeftOpen, Plus, Search } from "lucide-react";
import { listConversations } from "../../lib/api";
import type { Conversation } from "../../lib/types";
import { useAuthContext } from "../../contexts/AuthContext";
import { ICON, STROKE } from "../icons";
import { groupChats } from "./chatListModel";

export function ChatList({
  activeId,
  refreshKey,
  onNewChat,
  onHide,
  onNavigate,
}: {
  activeId: string | null;
  /** Changes when the list should be read again (a new conversation was saved). */
  refreshKey?: unknown;
  onNewChat: () => void;
  /** Absent in the phone sheet, which has its own close button. */
  onHide?: () => void;
  onNavigate?: () => void;
}) {
  const { t } = useTranslation("next");
  const { isAuthenticated, authRequired, signIn } = useAuthContext();
  const canList = isAuthenticated || !authRequired;
  const [chats, setChats] = useState<Conversation[] | null>(null);
  const [query, setQuery] = useState("");
  const [now] = useState(() => Date.now());

  useEffect(() => {
    if (!canList) return;
    let live = true;
    listConversations().then((c) => { if (live) setChats(c); }).catch(() => { if (live) setChats([]); });
    return () => { live = false; };
  }, [canList, refreshKey]);

  const groups = chats ? groupChats(chats, now, query) : [];
  const row = "flex h-9 w-full items-center gap-2 rounded-xl px-2.5 touch-target";

  return (
    <nav aria-label={t("chat.list.label")} className="flex h-full w-[256px] max-w-[85vw] flex-col gap-2 px-3 py-5" data-testid="chat-list">
      <div className="flex items-center gap-2 px-1">
        <h2 className="flex-1 font-medium">{t("chat.list.title")}</h2>
        {onHide && (
          <button type="button" onClick={onHide} aria-label={t("chat.list.hide")} title={t("chat.list.hide")} className="grid h-7 w-7 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon" data-testid="chat-list-hide">
            <PanelLeftClose aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          </button>
        )}
      </div>
      <button type="button" onClick={() => { onNewChat(); onNavigate?.(); }} className={`${row} font-medium ring-1 ring-nx-ink/15 hover:bg-nx-ink/5`} data-testid="chat-list-new">
        <Plus aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />
        {t("frame.newChat")}
      </button>
      {canList && (chats?.length ?? 0) > 0 && (
        <label className="flex h-9 items-center gap-2 rounded-xl bg-nx-block px-2.5">
          <Search aria-hidden className="h-4 w-4 shrink-0 nx-muted" strokeWidth={STROKE} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("chat.list.search")} aria-label={t("chat.list.search")} className="min-w-0 flex-1 bg-transparent text-caption outline-none placeholder:text-nx-ink/50" />
        </label>
      )}
      <div className="-mx-1 mt-1 min-h-0 flex-1 overflow-y-auto px-1">
        {!canList ? (
          <button type="button" onClick={signIn} className={`${row} w-full text-left text-caption nx-muted hover:bg-nx-ink/5`}>
            <LogIn aria-hidden className="h-4 w-4 shrink-0" strokeWidth={STROKE} />
            {t("frame.signInForChats")}
          </button>
        ) : chats === null ? (
          <p className="px-2.5 text-caption nx-muted" role="status">{t("frame.loading")}</p>
        ) : chats.length === 0 ? (
          <p className="px-2.5 text-caption nx-muted">{t("frame.noChats")}</p>
        ) : groups.length === 0 ? (
          <p className="px-2.5 text-caption nx-muted">{t("chat.list.noMatch")}</p>
        ) : (
          groups.map((g) => (
            <section key={g.key} className="mb-3 flex flex-col gap-0.5">
              <h3 className="px-2.5 pb-1 text-caption font-medium nx-muted">{t(`chat.list.group.${g.key}`)}</h3>
              <ul role="list" className="flex flex-col gap-0.5">
                {g.chats.map((c) => {
                  const active = c.id === activeId;
                  return (
                    <li key={c.id}>
                      <Link to={`/c/${c.id}`} onClick={onNavigate} aria-current={active ? "page" : undefined} title={c.title || undefined}
                        className={`${row} text-caption ${active ? "bg-nx-ink/[0.07] font-medium" : "hover:bg-nx-ink/5"}`}>
                        <span className="min-w-0 truncate">{c.title || t("frame.untitledChat")}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))
        )}
      </div>
    </nav>
  );
}

/** The chat list folded: a strip with the button that opens it again where its hide button was, and New chat. */
export function ChatListStrip({ onShow, onNewChat }: { onShow: () => void; onNewChat: () => void }) {
  const { t } = useTranslation("next");
  const btn = "grid h-9 w-9 place-items-center rounded-xl hover:bg-nx-ink/5 touch-icon";
  const Chats = ICON.chats;
  return (
    <nav aria-label={t("chat.list.label")} className="flex h-full w-14 flex-col items-center gap-2 py-5" data-testid="chat-list-strip">
      <button type="button" onClick={onShow} aria-label={t("chat.list.show")} title={t("chat.list.show")} className={`${btn} h-7`} data-testid="chat-list-expand">
        <PanelLeftOpen aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
      </button>
      <button type="button" onClick={onNewChat} aria-label={t("frame.newChat")} title={t("frame.newChat")} className={btn}>
        <Plus aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
      </button>
      <button type="button" onClick={onShow} aria-label={t("chat.list.show")} title={t("chat.list.show")} className={btn}>
        <Chats aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
      </button>
    </nav>
  );
}
