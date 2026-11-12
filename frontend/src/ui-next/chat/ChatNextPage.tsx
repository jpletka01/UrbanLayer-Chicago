// The full chat page in the new frame (Phase 8; brief "Chat", chat wireframe approved 2026-11-06): the side panel with
// its chats on the left, the conversation at reading width, a nearly empty first screen with one example question
// typing itself, and answers that lead with text, their lot, map and sources waiting as small previews. An opened
// preview fills the space above the message box; minimize puts it back. Same chat path as today's workspace
// (lib/useChatSession.ts): /c/:id, the doors from other pages, storing, limits and errors are shared, not forked.
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { FileDown, Map as MapIcon, Minimize2, Plus, RotateCcw, Share2, SquareArrowOutUpRight, BookText, MapPin, LogIn, X, Table2 } from "lucide-react";
import { DataView } from "../../components/sidebar/DataView";
import { AppFrame, ToolButton } from "../frame/AppFrame";
import { FrameOutline } from "../frame/FrameOutline";
import { MessageBubble } from "../../components/MessageBubble";
import { AnsweredOnNote } from "../../components/AnsweredOnNote";
import { ExportReport } from "../../components/ExportReport";
import { ShareModal } from "../../components/ShareModal";
import { buildReportData, type ReportData } from "../../lib/reportBuilder";
import { propertyStarterKeys } from "../../lib/scorecardContext";
import { useChatSession } from "../../lib/useChatSession";
import { useAuthContext } from "../../contexts/AuthContext";
import type { Message } from "../../lib/types";
import { STROKE } from "../icons";
import { Composer } from "./Composer";
import { ChatMap } from "./ChatMap";
import { SourcesList } from "./SourcesList";
import { ThinkingSteps } from "./ThinkingSteps";
import { chatTitle, previewsFor, type Preview } from "./chatModel";

/** The open preview: which answer, which kind, and the source to open first. */
interface OpenPreview { message: number; kind: "map" | "data" | "sources"; source: number | null }

export default function ChatNextPage() {
  const { t } = useTranslation(["next", "chat", "common"]);
  const session = useChatSession({ startPath: "/chat" });
  const { signIn } = useAuthContext();
  const { messages, streaming, context, activities, errorMsg, canRetry, retry, rateLimited, atMessageLimit, messagesRemaining } = session;
  const [draft, setDraft] = useState("");
  const [open, setOpen] = useState<OpenPreview | null>(null);
  const [exportReport, setExportReport] = useState<ReportData | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const scroller = useRef<HTMLDivElement | null>(null);
  const savedScroll = useRef<number | null>(null);
  const stickToEnd = useRef(true);

  const examples = useMemo(() => [t("next:chat.examples.lot"), t("next:chat.examples.code"), t("next:chat.examples.area")], [t]);
  const title = chatTitle(messages);
  const empty = messages.length === 0 && !streaming;
  const grounded = session.groundedContext;
  const starters = useMemo(() => propertyStarterKeys(grounded), [grounded]);
  const answered = messages.some((m) => m.role === "assistant" && m.context);

  // New text keeps the thread at its end, unless the visitor scrolled up to read.
  useEffect(() => {
    const el = scroller.current;
    if (el && stickToEnd.current) el.scrollTop = el.scrollHeight;
  }, [messages, streaming, activities]);
  // A new conversation (new chat, another chat from the panel) closes any open preview.
  useEffect(() => { setOpen(null); }, [session.conversationId]);

  const send = (text = draft) => {
    const q = text.trim();
    if (!q || streaming || atMessageLimit) return;
    stickToEnd.current = true;
    setOpen(null);
    setDraft("");
    session.sendMessage(q);
  };

  const openPreview = (p: OpenPreview) => {
    if (!open) savedScroll.current = scroller.current?.scrollTop ?? null;
    setOpen(p);
  };
  const minimize = () => {
    setOpen(null);
    // Back to the same spot in the thread.
    requestAnimationFrame(() => {
      if (scroller.current && savedScroll.current != null) scroller.current.scrollTop = savedScroll.current;
    });
  };

  const openMessage: Message | undefined = open ? messages[open.message] : undefined;
  const needsSignIn = (rateLimited && !session.canPersist) || session.showAuthModal;

  const tools = (
    <>
      {answered && !streaming && (
        <ToolButton
          label={t("next:chat.export")}
          icon={FileDown}
          onClick={() => setExportReport(buildReportData(messages, null, context?.resolved_address || context?.community_area_name || t("common:transcriptTitle")))}
          testId="chat-export"
        />
      )}
      {answered && !streaming && session.conversationId && session.canPersist && (
        <ToolButton label={t("next:chat.share")} icon={Share2} onClick={() => setShareOpen(true)} testId="chat-share" />
      )}
      <ToolButton label={t("next:frame.newChat")} icon={Plus} onClick={() => { setDraft(""); session.newChat(); }} testId="chat-new" />
    </>
  );

  if (session.loadingConversation) return <FrameOutline />;

  const composer = (
    <Composer
      value={draft}
      onChange={setDraft}
      onSend={() => send()}
      streaming={streaming}
      disabled={atMessageLimit || session.isSharedView}
      placeholder={empty ? t("next:chat.placeholder") : t("next:chat.followUp")}
      examples={empty && !grounded ? examples : undefined}
      // No autofocus on a new conversation: a focused box hides the example that types itself (brief "Chat").
      onAttach={session.canPersist ? session.attach : undefined}
      attachments={session.pendingAttachments}
      onRemoveAttachment={session.removeAttachment}
      above={grounded ? (
        <p className="px-2 text-caption nx-muted" data-testid="chat-about">
          {t("next:chat.about")} <span className="font-medium text-nx-ink">{grounded.address}</span>
        </p>
      ) : undefined}
    />
  );

  return (
    <AppFrame crumbs={[t("next:nav.chat"), title ?? t("next:frame.newChat")]} tools={tools} fill>
      <div className="relative flex min-h-0 flex-1 flex-col" data-testid="chat-page">
        {open && openMessage ? (
          <section className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-2 pt-4 sm:px-7" aria-label={t(`next:chat.preview.${open.kind}`)} data-testid="chat-preview">
            <div className="flex items-center gap-2">
              <h2 className="min-w-0 flex-1 truncate text-body font-medium">
                {open.kind === "map"
                  ? t("next:chat.mapTitle", { place: openMessage.mapData?.queried_address?.label ?? openMessage.context?.community_area_name ?? "" })
                  : open.kind === "data"
                    ? t("next:chat.dataTitle", { place: openMessage.context?.resolved_address ?? openMessage.context?.community_area_name ?? "" })
                    : t("next:chat.sourcesTitle", { count: openMessage.context?.code_chunks?.length ?? 0 })}
              </h2>
              <button type="button" onClick={minimize} aria-label={t("next:chat.minimize")} title={t("next:chat.minimize")} className="grid h-9 w-9 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon" data-testid="chat-minimize">
                <Minimize2 aria-hidden className="h-5 w-5" strokeWidth={STROKE} />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {open.kind === "map" && openMessage.mapData
                ? <ChatMap data={openMessage.mapData} />
                : open.kind === "data"
                  // The records behind the answer, as today's chat shows them (its data cards), at reading width.
                  ? <div className="mx-auto max-w-[760px]" data-testid="chat-data"><DataView context={openMessage.context ?? null} loading={false} mapData={openMessage.mapData ?? null} /></div>
                  : <div className="mx-auto max-w-[760px]"><SourcesList chunks={openMessage.context?.code_chunks ?? []} openIndex={open.source} /></div>}
            </div>
          </section>
        ) : (
          <div
            ref={scroller}
            onScroll={(e) => { const el = e.currentTarget; stickToEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}
            className="min-h-0 flex-1 overflow-y-auto px-4 sm:px-7"
          >
            {empty ? (
              <div className="mx-auto flex min-h-full max-w-[760px] flex-col justify-center gap-6 py-10">
                <h1 className="text-center text-[1.75rem] font-semibold leading-tight tracking-[-0.02em]">
                  {grounded ? t("next:chat.headingAt", { address: grounded.address }) : t("next:chat.heading")}
                </h1>
                {composer}
                {grounded ? (
                  <div className="flex flex-wrap justify-center gap-2">
                    {starters.map((k) => {
                      const q = t(`chat:propertyStarters.${k}`);
                      return (
                        <button key={k} type="button" onClick={() => session.sendPropertyStarter(q)} className="rounded-full bg-nx-block px-3 py-1.5 text-caption hover:bg-nx-ink/5 touch-target">
                          {q}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-center text-caption nx-muted">{t("next:chat.hint")}</p>
                )}
              </div>
            ) : (
              <div className="mx-auto flex max-w-[760px] flex-col gap-5 py-6" aria-live="polite">
                {messages.map((m, i) => {
                  const streamingThis = m.role === "assistant" && i === messages.length - 1 && streaming;
                  const ctx = streamingThis ? context : m.context;
                  const previews = streamingThis ? [] : previewsFor(m);
                  // The steps belong to the answer of this visit's latest turn: live while it streams, then one line.
                  // One element for both phases, so its clock runs from the question to the first words.
                  const isLatest = m.role === "assistant" && i === messages.length - 1 && activities.length > 0;
                  const waiting = streamingThis && !m.content;
                  return (
                    <div key={i} className="flex flex-col gap-2">
                    {isLatest && <ThinkingSteps activities={activities} answering={!waiting} />}
                    {!waiting && <MessageBubble
                      message={m}
                      streaming={streamingThis}
                      hideThinking
                      codeChunks={ctx?.code_chunks ?? []}
                      onCitationClick={(n) => { if ((m.context?.code_chunks?.length ?? 0) > 0) openPreview({ message: i, kind: "sources", source: Math.max(0, n - 1) }); }}
                      onDataClick={() => { if (m.context) openPreview({ message: i, kind: "data", source: null }); }}
                      footer={m.role === "assistant" && !streamingThis ? (
                        <>
                          {previews.length > 0 && <PreviewRow previews={previews} onOpen={(kind) => openPreview({ message: i, kind, source: null })} />}
                          {m.createdAt != null && (
                            <AnsweredOnNote
                              createdAt={m.createdAt}
                              note={session.sinceThen[String(i)]}
                              profileHref={previews.find((p) => p.kind === "lot")?.href ?? null}
                              onAskAgain={!session.isSharedView && i > 0 && messages[i - 1].role === "user" ? () => send(messages[i - 1].content) : undefined}
                            />
                          )}
                        </>
                      ) : undefined}
                    />}
                    </div>
                  );
                })}
                {errorMsg && (
                  <div className="rounded-xl bg-nx-pill-red-bg px-3 py-2 text-caption text-nx-pill-red" role="alert" data-testid="chat-error">
                    <p>{errorMsg}</p>
                    {canRetry && (
                      <button type="button" onClick={retry} className="mt-1.5 inline-flex items-center gap-1.5 underline underline-offset-2 touch-target" data-testid="chat-retry">
                        <RotateCcw aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
                        {t("chat:turnError.retry")}
                      </button>
                    )}
                  </div>
                )}
                {session.loadError && (
                  <p className="rounded-xl bg-nx-pill-red-bg px-3 py-2 text-caption text-nx-pill-red" role="alert">{session.loadError}</p>
                )}
              </div>
            )}
          </div>
        )}

        {!empty || open ? (
          <div className="px-4 pb-4 pt-2 sm:px-7">
            <div className="mx-auto flex max-w-[760px] flex-col gap-1.5">
              {composer}
              {atMessageLimit ? (
                <p className="flex flex-wrap items-center gap-2 px-2 text-caption nx-muted" role="status" data-testid="chat-limit">
                  {t("next:chat.atLimit")}
                  <button type="button" onClick={() => session.newChat()} className="font-medium text-nx-ink underline underline-offset-2">{t("next:frame.newChat")}</button>
                </p>
              ) : messagesRemaining <= 2 && messages.length > 0 ? (
                <p className="px-2 text-caption nx-muted" role="status">{t("next:chat.remaining", { count: messagesRemaining })}</p>
              ) : null}
            </div>
          </div>
        ) : null}

        {needsSignIn && <SignInCard onSignIn={signIn} onClose={() => { session.dismissAuth(); }} />}
      </div>

      {exportReport && <ExportReport report={exportReport} onClose={() => setExportReport(null)} />}
      {shareOpen && session.conversationId && <ShareModal conversationId={session.conversationId} onClose={() => setShareOpen(false)} />}
    </AppFrame>
  );
}

/** The small previews under an answer: each says what it is in two words. Only the lot leaves the page (new tab). */
function PreviewRow({ previews, onOpen }: { previews: Preview[]; onOpen: (kind: "map" | "data" | "sources") => void }) {
  const { t } = useTranslation("next");
  const chip = "inline-flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-caption ring-1 ring-nx-ink/10 hover:bg-nx-ink/5 touch-target";
  return (
    <div className="mt-2 flex flex-wrap gap-2 pl-9" data-testid="chat-previews">
      {previews.map((p) => p.kind === "lot" ? (
        <a key="lot" href={p.href} target="_blank" rel="noopener noreferrer" className={chip} data-testid="preview-lot">
          <MapPin aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          <span><span className="font-medium">{p.address}</span> · {t("chat.preview.lot")}</span>
          <SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
          <span className="sr-only">{t("common:opensInNewTab")}</span>
        </a>
      ) : p.kind === "map" ? (
        <button key="map" type="button" onClick={() => onOpen("map")} className={chip} data-testid="preview-map">
          <MapIcon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          <span><span className="font-medium">{t("chat.preview.map")}</span> · {t("chat.points", { count: p.points })}</span>
        </button>
      ) : p.kind === "data" ? (
        <button key="data" type="button" onClick={() => onOpen("data")} className={chip} data-testid="preview-data">
          <Table2 aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          <span><span className="font-medium">{t("chat.preview.data")}</span> · {p.count}</span>
        </button>
      ) : (
        <button key="sources" type="button" onClick={() => onOpen("sources")} className={chip} data-testid="preview-sources">
          <BookText aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          <span><span className="font-medium">{t("chat.preview.sources")}</span> · {p.count}</span>
        </button>
      ))}
    </div>
  );
}

/** At the limit: the conversation frosts and a sign-in card comes forward (a bottom sheet on a phone). */
function SignInCard({ onSignIn, onClose }: { onSignIn: () => void; onClose: () => void }) {
  const { t } = useTranslation("next");
  return (
    <div className="absolute inset-0 z-30 flex items-end justify-center bg-nx-page/50 backdrop-blur-sm sm:items-center" data-testid="chat-signin">
      <div role="dialog" aria-modal="true" aria-labelledby="chat-signin-title" className="relative flex w-full flex-col gap-3 rounded-t-3xl bg-nx-page p-5 shadow-[0_-8px_32px_rgb(0_0_0/0.16)] sm:max-w-sm sm:rounded-3xl sm:shadow-[0_8px_40px_rgb(0_0_0/0.2)]">
        <button type="button" onClick={onClose} aria-label={t("chat.signInClose")} className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon">
          <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        </button>
        <h2 id="chat-signin-title" className="pr-8 text-[1.0625rem] font-semibold">{t("chat.signInTitle")}</h2>
        <p className="text-caption nx-muted">{t("chat.signInBody")}</p>
        <button type="button" onClick={onSignIn} autoFocus className="inline-flex items-center justify-center gap-2 rounded-xl bg-nx-primary px-4 py-2.5 font-medium text-nx-primary-fg touch-target">
          <LogIn aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          {t("chat.signInGoogle")}
        </button>
      </div>
    </div>
  );
}
