import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ScorecardResponse } from "../lib/api";
import { useParcelChat } from "../lib/useParcelChat";
import { track } from "../lib/tracking";
import { MessageBubble } from "./MessageBubble";
import { RotateCcw, SquareArrowOutUpRight } from "lucide-react";

// Persistent quick-chat dock (bottom-right of the Scorecard). The old model —
// every investigate chip navigating to the full workspace — made a one-line
// question cost the whole page. The dock answers in place: text-only (no map,
// no sidebar), grounded on the loaded parcel for EVERY turn via the same
// pin + scorecard_context handoff the workspace uses. Chats here are
// ephemeral by design (quick question ≠ research session); "Continue in the
// full analyst" carries the transcript over, where it becomes a real, saved
// conversation. It opens in a NEW tab (Jack, 2026-11-06): the Profile stays where
// it was. Mount with key={pin ?? address} so a new parcel opens fresh.

/** A question pushed into the dock from page chrome (investigate chips, the
 *  verdict next-step). question=null opens the dock without sending. `id`
 *  makes repeat asks of the same text re-fire. */
export interface DockSignal {
  question: string | null;
  id: number;
}

const chatIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
  </svg>
);

export function MiniChatDock({ data, signal, launcherBelowMd = true }: {
  data: ScorecardResponse;
  signal: DockSignal | null;
  /** false when the page has its own phone action bar that opens the dock (the Profile's one sticky band). */
  launcherBelowMd?: boolean;
}) {
  const { t, i18n } = useTranslation(["pages", "chat", "common"]);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const consumedSignalRef = useRef<number | null>(null);

  // Grounding, the address-carrying ask and the new-tab escalation live in useParcelChat (shared with the
  // new UI's Ask drawer).
  const {
    messages,
    streaming,
    context: streamingContext,
    errorMsg,
    canRetry,
    retry,
    atQuota,
    activities,
    address,
    ask,
    starterKeys,
    escalate,
    tabBlocked,
  } = useParcelChat(data, i18n.language);

  // Page chrome pushed a question (or just an open request).
  useEffect(() => {
    if (!signal || consumedSignalRef.current === signal.id) return;
    consumedSignalRef.current = signal.id;
    setOpen(true);
    if (signal.question) ask(signal.question);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signal]);

  // Keep the transcript pinned to the newest turn. Scroll the container
  // directly — scrollIntoView would also scroll the page under the dock.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, streaming]);

  const starters = useMemo(
    () => starterKeys.map((k) => t(`chat:propertyStarters.${k}`)),
    [starterKeys, t],
  );

  const submitDraft = () => {
    if (!draft.trim()) return;
    ask(draft);
    setDraft("");
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => {
          track("investigate_click", { card_name: "dock_open" });
          setOpen(true);
        }}
        aria-label={t("pages:scorecard.dock.title")}
        className={`fixed bottom-4 right-4 z-40 ${launcherBelowMd ? "inline-flex" : "hidden md:inline-flex"} items-center gap-2 rounded-full bg-action hover:bg-action-hover text-text-on-accent pl-4 pr-4 sm:pr-5 py-3 shadow-glow transition-colors`}
      >
        {chatIcon}
        <span className="text-title hidden sm:inline">{t("pages:scorecard.dock.open")}</span>
      </button>
    );
  }

  return (
    <section
      aria-label={t("pages:scorecard.dock.title")}
      className="fixed bottom-4 right-4 z-40 flex flex-col w-[min(400px,calc(100vw-2rem))] h-[min(560px,calc(100dvh-6rem))] rounded-bento-sm border border-dark-border bg-dark-surface shadow-modal overflow-hidden"
    >
      {/* Header — what this is (quick + ephemeral) and what it knows (the address) */}
      <div className="flex items-start gap-3 px-4 py-3 border-b border-dark-border bg-dark-elevated/40">
        <div className="min-w-0 flex-1">
          <div className="text-title text-text-primary">{t("pages:scorecard.dock.title")}</div>
          <div className="text-micro text-text-muted truncate mt-0.5">
            {address
              ? t("pages:scorecard.dock.groundedOn", { address })
              : t("pages:scorecard.dock.notSaved")}
            {address ? ` · ${t("pages:scorecard.dock.notSaved")}` : ""}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-label={t("pages:scorecard.dock.minimize")}
          className="shrink-0 text-text-muted hover:text-text-primary transition-colors p-1"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12h-15" />
          </svg>
        </button>
      </div>

      {/* Transcript */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {messages.length === 0 && !streaming ? (
          <div className="h-full flex flex-col justify-end gap-2">
            <p className="text-caption text-text-secondary px-1">{t("pages:scorecard.dock.startersHint")}</p>
            {starters.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => {
                  track("investigate_click", { card_name: "dock_starter" });
                  ask(q);
                }}
                className="text-left text-caption text-text-secondary bg-dark-bg border border-dark-border rounded-lg px-3 py-2 hover:border-accent/40 hover:text-text-primary transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        ) : (
          messages.map((m, i) => {
            const isLastAssistant = m.role === "assistant" && i === messages.length - 1;
            const isStreaming = isLastAssistant && streaming;
            const messageContext = isStreaming ? streamingContext : m.context;
            return (
              <MessageBubble
                key={i}
                message={m}
                streaming={isStreaming}
                codeChunks={messageContext?.code_chunks ?? []}
                activities={isStreaming ? activities : undefined}
              />
            );
          })
        )}
        {errorMsg && (
          <div className="text-caption text-state-negative bg-state-negative/10 border border-state-negative/20 rounded-lg px-3 py-2">
            <p>{errorMsg}</p>
            {canRetry && (
              <button
                type="button"
                onClick={retry}
                data-testid="dock-retry"
                className="mt-1.5 inline-flex items-center gap-1.5 text-link hover:text-accent transition-colors"
              >
                <RotateCcw aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
                {t("chat:turnError.retry")}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Escalation — the door to the saved, full-context session */}
      {messages.length > 0 && (
        <div className="px-4 py-2 border-t border-dark-border">
          <button
            type="button"
            onClick={() => escalate()}
            className="text-caption text-link hover:text-accent transition-colors inline-flex items-center gap-1"
          >
            {t("pages:scorecard.dock.escalate")}
            <SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
            <span className="sr-only">{t("common:opensInNewTab")}</span>
          </button>
          {tabBlocked && (
            <p className="mt-1 text-caption text-text-secondary" role="status" data-testid="dock-tab-blocked">
              {t("common:newTabBlocked")}
            </p>
          )}
        </div>
      )}

      {/* Composer */}
      <div className="flex gap-2 px-3 py-3 border-t border-dark-border bg-dark-elevated/40">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitDraft()}
          placeholder={t("pages:scorecard.dock.placeholder")}
          disabled={atQuota}
          className="flex-1 min-w-0 rounded-lg bg-dark-bg border border-dark-border px-3 py-2 text-body text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent disabled:opacity-50"
        />
        <button
          type="button"
          onClick={submitDraft}
          disabled={streaming || atQuota || !draft.trim()}
          aria-label={t("pages:scorecard.dock.send")}
          className="shrink-0 rounded-lg bg-action hover:bg-action-hover text-text-on-accent px-3 disabled:opacity-40 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
          </svg>
        </button>
      </div>
    </section>
  );
}
