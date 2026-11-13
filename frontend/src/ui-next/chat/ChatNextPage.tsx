// The full chat page in the new frame (Phase 8; brief "Chat", chat wireframe approved 2026-11-06): the side panel with
// its chats on the left, the conversation at reading width, a nearly empty first screen with one example question
// typing itself, and answers that lead with text, their lot, map and sources waiting as small previews. A preview or a
// citation opens the evidence panel on the right (owner, 2026-11-12: read the answer and its sources side by side; a
// sheet over the lower half on a phone), with Sources, Records and Map tabs for that answer; the map can also go full
// screen to explore. Same chat path as today's workspace (lib/useChatSession.ts): /c/:id, the doors from other pages,
// storing, limits and errors are shared, not forked.
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import * as Dialog from "@radix-ui/react-dialog";
import { FileDown, Map as MapIcon, Maximize2, Minimize2, Plus, RotateCcw, Share2, SquareArrowOutUpRight, BookText, MapPin, X } from "lucide-react";
import { AppFrame, ToolButton } from "../frame/AppFrame";
import { RightDrawer } from "../ui/RightDrawer";
import { FrameOutline } from "../frame/FrameOutline";
import { AnsweredOnNote } from "../../components/AnsweredOnNote";
import { ExportReport } from "../../components/ExportReport";
import { ShareModal } from "../../components/ShareModal";
import { buildReportData, type ReportData } from "../../lib/reportBuilder";
import { propertyStarterKeys } from "../../lib/scorecardContext";
import { useChatSession } from "../../lib/useChatSession";
import { useAuthContext } from "../../contexts/AuthContext";
import ProviderButtons from "../../components/auth/ProviderButtons";
import { NEXT_PROVIDER_BUTTON } from "../frame/signInLook";
import type { Message } from "../../lib/types";
import { ICON, STROKE } from "../icons";
import { ChatList, ChatListStrip } from "./ChatList";
import { ChatMessage } from "./ChatMessage";
import { Composer } from "./Composer";
import { ChatMap } from "./ChatMap";
import { EvidenceSources, type MapLayer } from "./EvidenceSources";
import { sourcesFor } from "./evidenceModel";
import { ThinkingSteps } from "./ThinkingSteps";
import { chatTitle, evidenceTabs, previewsFor, type EvidenceTab, type Preview } from "./chatModel";

/** The evidence panel: which answer, which tab, the source (its number) to open first, and a map layer a source asked
    to show ("Show on map"). */
interface Panel { message: number; tab: EvidenceTab; source: number | null; show?: MapLayer }

const LIST_KEY = "urbanlayer-next-chatlist";

export default function ChatNextPage() {
  const { t } = useTranslation(["next", "chat", "common"]);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [closing, setClosing] = useState(false);
  // While the panel is open it follows the newest answer, on the same tab when that answer has it.
  const session = useChatSession({
    startPath: "/chat",
    onTurnDone: (msgs) => setPanel((p) => {
      if (!p) return p;
      const last = msgs.length - 1;
      const tabs = evidenceTabs(msgs[last]);
      if (tabs.length === 0) return p;
      return { message: last, tab: tabs.includes(p.tab) ? p.tab : tabs[0], source: null };
    }),
  });
  const { signIn } = useAuthContext();
  const { messages, streaming, context, activities, errorMsg, canRetry, retry, rateLimited, atQuota, questionsLeft, usagePlan, quotaMessage } = session;
  const [draft, setDraft] = useState("");
  const [exportReport, setExportReport] = useState<ReportData | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  // The chat list beside the panel (owner review 2026-11-12): open on every visit to a wide screen; hiding it lasts
  // for this tab only (sessionStorage), so the next visit opens it again. A sheet on a phone.
  const [listShown, setListShown] = useState(() => { try { return sessionStorage.getItem(LIST_KEY) !== "hidden"; } catch { return true; } });
  const [listSheet, setListSheet] = useState(false);
  const showList = (on: boolean) => {
    setListShown(on);
    try { sessionStorage.setItem(LIST_KEY, on ? "shown" : "hidden"); } catch { /* per-viewer convenience only */ }
  };
  const scroller = useRef<HTMLDivElement | null>(null);
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
  // A new conversation (new chat, another chat from the side panel) closes the evidence.
  useEffect(() => { setPanel(null); }, [session.conversationId]);

  const send = (text = draft) => {
    const q = text.trim();
    if (!q || streaming || atQuota) return;
    stickToEnd.current = true;
    setDraft("");
    session.sendMessage(q);
  };

  const openEvidence = (p: Panel) => { setClosing(false); setPanel(p); };
  const closeEvidence = () => {
    setClosing(true);
    window.setTimeout(() => { setPanel(null); setClosing(false); }, 200);
  };

  const panelMessage: Message | undefined = panel ? messages[panel.message] : undefined;
  const needsSignIn = (rateLimited && !session.canPersist) || session.showAuthModal;

  const startNew = () => { setDraft(""); session.newChat(); };
  const tools = (
    <>
      <span className="lg:hidden">
        <ToolButton label={t("next:chat.list.show")} icon={ICON.chats} onClick={() => setListSheet(true)} testId="chat-list-show" />
      </span>
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
      <ToolButton label={t("next:frame.newChat")} icon={Plus} onClick={startNew} testId="chat-new" />
    </>
  );

  if (session.loadingConversation) return <FrameOutline />;

  const composer = (
    <Composer
      value={draft}
      onChange={setDraft}
      onSend={() => send()}
      streaming={streaming}
      disabled={atQuota || session.isSharedView}
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

  const drawer = panel && panelMessage ? (
    <RightDrawer
      testId="chat-evidence"
      size="wide"
      phoneSheet
      preferTall={panel.tab === "map"}
      closing={closing}
      onClose={closeEvidence}
      closeLabel={t("next:chat.evidence.close")}
      title={t("next:chat.evidence.title")}
      subtitle={(() => {
        const q = messages[panel.message - 1]?.content;
        return q ? <span className="line-clamp-1">{t("next:chat.evidence.forAnswer", { question: q })}</span> : undefined;
      })()}
    >
      <EvidencePanel
        message={panelMessage}
        tab={panel.tab}
        source={panel.source}
        show={panel.show}
        onTab={(tab) => setPanel({ ...panel, tab, source: null, show: undefined })}
        onShowOnMap={(layer) => setPanel({ ...panel, tab: "map", source: null, show: layer })}
      />
    </RightDrawer>
  ) : null;

  return (
    <AppFrame
      crumbs={[t("next:nav.chat"), title ?? t("next:frame.newChat")]} tools={tools} fill drawer={drawer}
      secondary={listShown
        ? <ChatList activeId={session.conversationId} refreshKey={session.conversationId} onNewChat={startNew} onHide={() => showList(false)} />
        : <ChatListStrip onShow={() => showList(true)} onNewChat={startNew} />}
    >
      <Dialog.Root open={listSheet} onOpenChange={setListSheet}>
        <Dialog.Portal>
          <div className="ui-next">
            <Dialog.Overlay className="fixed inset-0 z-[65] bg-black/30" />
            <Dialog.Content className="fixed inset-y-0 left-0 z-[66] bg-nx-page text-body text-nx-ink shadow-[0_8px_32px_rgb(0_0_0/0.2)] focus:outline-none" data-testid="chat-list-sheet">
              <Dialog.Title className="sr-only">{t("next:chat.list.label")}</Dialog.Title>
              <Dialog.Description className="sr-only">{t("next:chat.list.search")}</Dialog.Description>
              <Dialog.Close className="absolute right-3 top-4 grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon" aria-label={t("next:chat.list.hide")}>
                <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
              </Dialog.Close>
              <ChatList activeId={session.conversationId} refreshKey={session.conversationId} onNewChat={startNew} onNavigate={() => setListSheet(false)} />
            </Dialog.Content>
          </div>
        </Dialog.Portal>
      </Dialog.Root>
      <div className="relative flex min-h-0 flex-1 flex-col" data-testid="chat-page">
        {(
          <div
            ref={scroller}
            onScroll={(e) => { const el = e.currentTarget; stickToEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}
            className="min-h-0 flex-1 overflow-y-auto px-4 sm:px-7"
          >
            {empty ? (
              <div className="mx-auto flex min-h-full max-w-[760px] flex-col justify-center gap-6 py-10">
                {session.loadError && (
                  <p className="rounded-xl bg-nx-pill-red-bg px-3 py-2 text-caption text-nx-pill-red" role="alert" data-testid="chat-load-error">{session.loadError}</p>
                )}
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
                ) : atQuota && quotaMessage ? (
                  // The allowance is spent: say so where the visitor is looking, with sign-in for a signed-out visitor.
                  <p className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-center text-caption nx-muted" role="status" data-testid="chat-limit-empty">
                    {quotaMessage}
                    {usagePlan === "anonymous" && (
                      <button type="button" onClick={signIn} className="font-semibold text-nx-ink underline underline-offset-2 touch-target">{t("next:frame.signIn")}</button>
                    )}
                  </p>
                ) : (
                  <p className="text-center text-caption nx-muted">{t("next:chat.hint")}</p>
                )}
              </div>
            ) : (
              <div className="mx-auto flex max-w-[760px] flex-col gap-5 py-6" aria-live="polite">
                {messages.map((m, i) => {
                  const streamingThis = m.role === "assistant" && i === messages.length - 1 && streaming;
                  const previews = streamingThis ? [] : previewsFor(m);
                  // The steps belong to the answer of this visit's latest turn: live while it streams, then one line.
                  // One element for both phases, so its clock runs from the question to the first words.
                  const isLatest = m.role === "assistant" && i === messages.length - 1 && activities.length > 0;
                  const waiting = streamingThis && !m.content;
                  return (
                    <div key={i} className="flex flex-col gap-2">
                    {isLatest && <ThinkingSteps activities={activities} answering={!waiting} />}
                    {!waiting && <ChatMessage
                      message={m}
                      streaming={streamingThis}
                      onOpenSource={(n) => openEvidence({ message: i, tab: "sources", source: n })}
                      footer={m.role === "assistant" && !streamingThis && previews.length > 0
                        ? <PreviewRow previews={previews} onOpen={(tab) => openEvidence({ message: i, tab, source: null })} active={panel?.message === i ? panel.tab : null} />
                        : undefined}
                      meta={m.role === "assistant" && !streamingThis && m.createdAt != null ? (
                        <AnsweredOnNote
                          inset={false}
                          createdAt={m.createdAt}
                          note={session.sinceThen[String(i)]}
                          profileHref={previews.find((p) => p.kind === "lot")?.href ?? null}
                          onAskAgain={!session.isSharedView && i > 0 && messages[i - 1].role === "user" ? () => send(messages[i - 1].content) : undefined}
                        />
                      ) : undefined}
                    />}
                    </div>
                  );
                })}
                {errorMsg && !atQuota && (
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

        {!empty ? (
          <div className="px-4 pb-4 pt-2 sm:px-7">
            <div className="mx-auto flex max-w-[760px] flex-col gap-1.5">
              {composer}
              {/* The allowance (Quotas, Item 120): its message once used up, the count only when 10 or fewer are left. */}
              {atQuota ? (
                <p className="px-2 text-caption nx-muted" role="status" data-testid="chat-limit">{quotaMessage}</p>
              ) : questionsLeft != null && questionsLeft > 0 && questionsLeft <= 10 ? (
                <p className="px-2 text-caption nx-muted" role="status" data-testid="chat-left">
                  {usagePlan === "anonymous" ? t("common:quota.left", { count: questionsLeft }) : t("common:quota.leftMonth", { count: questionsLeft })}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}

        {needsSignIn && <SignInCard onClose={() => { session.dismissAuth(); }} />}
      </div>

      {exportReport && <ExportReport report={exportReport} onClose={() => setExportReport(null)} />}
      {shareOpen && session.conversationId && <ShareModal conversationId={session.conversationId} onClose={() => setShareOpen(false)} />}
    </AppFrame>
  );
}

/** The small previews under an answer: each says what it is in two words. Only the lot leaves the page (new tab). */
function PreviewRow({ previews, onOpen, active }: { previews: Preview[]; onOpen: (tab: EvidenceTab) => void; active: EvidenceTab | null }) {
  const { t } = useTranslation("next");
  const base = "inline-flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-caption ring-1 hover:bg-nx-ink/5 touch-target";
  const chip = `${base} ring-nx-ink/10`;
  // The chip whose evidence is in the panel reads as selected.
  const chipFor = (tab: EvidenceTab) => (active === tab ? `${base} bg-nx-pill-purple-bg ring-nx-pill-purple/40` : chip);
  return (
    <div className="flex flex-wrap gap-2" data-testid="chat-previews">
      {previews.map((p) => p.kind === "lot" ? (
        <a key="lot" href={p.href} target="_blank" rel="noopener noreferrer" className={chip} data-testid="preview-lot">
          <MapPin aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          <span><span className="font-medium">{p.address}</span> · {t("chat.preview.lot")}</span>
          <SquareArrowOutUpRight aria-hidden className="h-3.5 w-3.5" strokeWidth={STROKE} />
          <span className="sr-only">{t("common:opensInNewTab")}</span>
        </a>
      ) : p.kind === "map" ? (
        <button key="map" type="button" onClick={() => onOpen("map")} aria-pressed={active === "map"} className={chipFor("map")} data-testid="preview-map">
          <MapIcon aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          <span><span className="font-medium">{t("chat.preview.map")}</span> · {t(`chat.lens.chip.${p.lens}${p.near || p.lens === "lot" || p.lens === "area" ? "" : "Area"}`, { count: p.count })}</span>
        </button>
      ) : (
        <button key="sources" type="button" onClick={() => onOpen("sources")} aria-pressed={active === "sources"} className={chipFor("sources")} data-testid="preview-sources">
          <BookText aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
          <span><span className="font-medium">{t("chat.preview.sources")}</span> · {p.count}</span>
        </button>
      ))}
    </div>
  );
}

/** The evidence for one answer: its tabs (only those it has), then the chosen one filling the panel. */
function EvidencePanel({ message, tab, source, show, onTab, onShowOnMap }: {
  message: Message; tab: EvidenceTab; source: number | null; show?: MapLayer; onTab: (t: EvidenceTab) => void; onShowOnMap: (l: MapLayer) => void;
}) {
  const { t } = useTranslation("next");
  // Full screen is the same map grown to cover the screen (as on the Profile, owner's review 2026-11-12): no second
  // map, no reload, the camera and tiles carry over. Escape or the corner button shrinks it back into the panel.
  const [focused, setFocused] = useState(false);
  const tabs = evidenceTabs(message);
  const shown: EvidenceTab = tabs.includes(tab) ? tab : (tabs[0] ?? tab);
  const label: Record<EvidenceTab, string> = { sources: `${t("chat.preview.sources")} · ${sourcesFor(message).length}`, map: t("chat.preview.map") };
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center gap-1 border-b border-nx-ink/10">
      <div role="tablist" aria-label={t("chat.evidence.tabs")} className="flex flex-1 items-center gap-1">
        {tabs.map((k) => (
          <button
            key={k}
            type="button"
            role="tab"
            aria-selected={shown === k}
            onClick={() => onTab(k)}
            className={`-mb-px border-b-2 px-3 py-2 text-caption touch-target ${shown === k ? "border-nx-ink font-semibold" : "border-transparent nx-muted hover:text-nx-ink"}`}
            data-testid={`evidence-tab-${k}`}
          >
            {label[k]}
          </button>
        ))}
      </div>
      </div>
      <div role="tabpanel" className={`min-h-0 flex-1 ${shown === "map" ? "" : "overflow-y-auto"}`}>
        {shown === "map" && message.mapData ? (
          <div
            role={focused ? "dialog" : undefined}
            aria-modal={focused || undefined}
            aria-label={focused ? t("chat.preview.map") : undefined}
            onKeyDown={(e) => { if (focused && e.key === "Escape") { e.stopPropagation(); setFocused(false); } }}
            className={focused ? "fixed inset-0 z-[70] bg-nx-page p-3 sm:p-6" : "relative h-full"}
            data-testid={focused ? "chat-fullmap" : undefined}
          >
            <ChatMap data={message.mapData} plan={message.plan} show={show} />
            <button
              type="button"
              onClick={() => setFocused((f) => !f)}
              aria-expanded={focused}
              aria-label={focused ? t("chat.minimize") : t("chat.evidence.fullScreen")}
              title={focused ? t("chat.minimize") : t("chat.evidence.fullScreen")}
              className={`absolute z-10 grid h-8 w-8 place-items-center rounded-lg bg-nx-page shadow-[0_1px_2px_rgb(0_0_0/0.15)] hover:bg-nx-block touch-icon ${focused ? "bottom-5 right-5 sm:bottom-8 sm:right-8" : "bottom-2 right-2"}`}
              data-testid={focused ? "chat-minimize" : "evidence-fullscreen"}
            >
              {focused ? <Minimize2 aria-hidden className="h-4 w-4" strokeWidth={STROKE} /> : <Maximize2 aria-hidden className="h-4 w-4" strokeWidth={STROKE} />}
            </button>
          </div>
        )
          : <EvidenceSources message={message} openN={source} onShowOnMap={onShowOnMap} />}
      </div>
    </div>
  );
}

/** At the limit: the conversation frosts and a sign-in card comes forward (a bottom sheet on a phone). */
function SignInCard({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation("next");
  const { providers, signInWith } = useAuthContext();
  return (
    <div className="absolute inset-0 z-30 flex items-end justify-center bg-nx-page/50 backdrop-blur-sm sm:items-center" data-testid="chat-signin">
      <div role="dialog" aria-modal="true" aria-labelledby="chat-signin-title" className="relative flex w-full flex-col gap-3 rounded-t-3xl bg-nx-page p-5 shadow-[0_-8px_32px_rgb(0_0_0/0.16)] sm:max-w-sm sm:rounded-3xl sm:shadow-[0_8px_40px_rgb(0_0_0/0.2)]">
        <button type="button" onClick={onClose} aria-label={t("chat.signInClose")} className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-lg hover:bg-nx-ink/5 touch-icon">
          <X aria-hidden className="h-4 w-4" strokeWidth={STROKE} />
        </button>
        <h2 id="chat-signin-title" className="pr-8 text-[1.0625rem] font-semibold">{t("chat.signInTitle")}</h2>
        <p className="text-caption nx-muted">{t("chat.signInBody")}</p>
        <ProviderButtons providers={providers} onChoose={(p) => signInWith(p)} buttonClassName={NEXT_PROVIDER_BUTTON} autoFocus />
      </div>
    </div>
  );
}
