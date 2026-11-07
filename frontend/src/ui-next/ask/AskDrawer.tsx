// The Ask drawer (brief "Chat"; decision Items 74, 76): opened from the Ask icon, it covers about a third of the
// page on the right (the whole screen on a phone), with the question box at the top. The conversation lives in
// the page (useParcelChat), so it survives closing the drawer and switching tabs. "Open in full chat" opens a
// new tab and never replaces the page. Same chat path as today's dock: no new endpoint, no new model call path.
import { useEffect, useId, useRef, useState, type RefObject } from "react";
import { useTranslation } from "react-i18next";
import { ArrowUp, RotateCcw, SquareArrowOutUpRight, X } from "lucide-react";
import { MessageBubble } from "../../components/MessageBubble";
import type { useParcelChat } from "../../lib/useParcelChat";
import { ICON, STROKE } from "../icons";

type ParcelChat = ReturnType<typeof useParcelChat>;

export function AskDrawer({
  chat,
  onClose,
  returnFocusRef,
  tabLabel,
}: {
  chat: ParcelChat;
  onClose: () => void;
  /** The Ask button: focus goes back to it on close. */
  returnFocusRef: RefObject<HTMLElement | null>;
  /** The Profile tab the visitor is on (shown as what the analyst knows). */
  tabLabel: string;
}) {
  const { t } = useTranslation(["next", "chat", "common"]);
  const titleId = useId();
  const [draft, setDraft] = useState("");
  const boxRef = useRef<HTMLTextAreaElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const AskIcon = ICON.ask;

  useEffect(() => {
    boxRef.current?.focus();
    const back = returnFocusRef.current;
    return () => back?.focus();
  }, [returnFocusRef]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat.messages, chat.streaming]);

  const submit = () => {
    if (!draft.trim()) return;
    chat.ask(draft);
    setDraft("");
  };

  return (
    <section
      role="dialog"
      aria-modal="false"
      aria-labelledby={titleId}
      data-testid="ask-drawer"
      onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } }}
      className="fixed inset-0 z-50 flex flex-col gap-4 bg-nx-page p-5 lg:sticky lg:top-0 lg:z-auto lg:h-dvh lg:w-[min(33vw,480px)] lg:min-w-[360px] lg:shrink-0 lg:border-l lg:border-nx-ink/10"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id={titleId} className="truncate text-body font-semibold">
            {chat.address ? t("next:ask.titleAt", { address: chat.address }) : t("next:ask.title")}
          </h2>
          <p className="text-caption nx-muted">{t("next:ask.notSaved")}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("next:ask.close")}
          className="grid h-8 w-8 shrink-0 place-items-center rounded-lg hover:bg-nx-ink/5 touch-target"
        >
          <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        </button>
      </div>

      {/* The question box: SnowUI's lavender-to-blue edge, the only place the gradient appears. */}
      <form
        className="nx-ai-edge rounded-2xl focus-within:shadow-[0_0_0_3px_rgb(var(--nx-ai-a)/0.6)]"
        onSubmit={(e) => { e.preventDefault(); submit(); }}
      >
        <div className="flex flex-col gap-2 rounded-[15px] bg-nx-page px-3 py-2.5">
          <label htmlFor={`${titleId}-q`} className="sr-only">{t("next:ask.label")}</label>
          <textarea
            id={`${titleId}-q`}
            ref={boxRef}
            rows={2}
            value={draft}
            disabled={chat.atMessageLimit}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            placeholder={t("next:ask.placeholder")}
            className="w-full resize-none bg-transparent text-body text-nx-ink placeholder:text-nx-ink/[0.64] focus:outline-none focus-visible:outline-none disabled:opacity-50"
          />
          <div className="flex items-center justify-between gap-2">
            <span className="text-caption nx-muted">{t("next:ask.knows", { tab: tabLabel })}</span>
            <button
              type="submit"
              disabled={chat.streaming || chat.atMessageLimit || !draft.trim()}
              className="nx-ai-send inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-caption font-medium disabled:opacity-50 touch-target"
            >
              <ArrowUp aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
              {t("next:ask.send")}
            </button>
          </div>
        </div>
      </form>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto" aria-live="polite">
        {chat.messages.length === 0 && !chat.streaming ? (
          <div className="flex flex-col gap-2">
            <p className="text-caption nx-muted">{t("next:ask.startersHint")}</p>
            {chat.starterKeys.map((k) => {
              const q = t(`chat:propertyStarters.${k}`);
              return (
                <button
                  key={k}
                  type="button"
                  onClick={() => chat.ask(q)}
                  className="flex items-start gap-2 rounded-xl bg-nx-block px-3 py-2 text-left text-caption hover:bg-nx-ink/5"
                >
                  <AskIcon aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={STROKE} />
                  {q}
                </button>
              );
            })}
          </div>
        ) : (
          chat.messages.map((m, i) => {
            const streamingThis = m.role === "assistant" && i === chat.messages.length - 1 && chat.streaming;
            const ctx = streamingThis ? chat.context : m.context;
            return (
              <MessageBubble
                key={i}
                message={m}
                streaming={streamingThis}
                codeChunks={ctx?.code_chunks ?? []}
                activities={streamingThis ? chat.activities : undefined}
              />
            );
          })
        )}
        {chat.errorMsg && (
          <div className="rounded-xl bg-nx-pill-red-bg px-3 py-2 text-caption text-nx-pill-red" role="alert">
            <p>{chat.errorMsg}</p>
            {chat.canRetry && (
              <button type="button" onClick={chat.retry} className="mt-1.5 inline-flex items-center gap-1.5 underline underline-offset-2">
                <RotateCcw aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
                {t("chat:turnError.retry")}
              </button>
            )}
          </div>
        )}
      </div>

      <div className="border-t border-nx-ink/10 pt-3">
        <button
          type="button"
          onClick={() => chat.escalate("next_ask_escalate")}
          className="inline-flex items-center gap-1 text-caption underline underline-offset-2 hover:no-underline"
        >
          {t("next:ask.openFull")}
          <SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
          <span className="sr-only">{t("common:opensInNewTab")}</span>
        </button>
        {chat.tabBlocked && (
          <p className="mt-1 text-caption nx-muted" role="status" data-testid="ask-tab-blocked">{t("common:newTabBlocked")}</p>
        )}
      </div>
    </section>
  );
}
