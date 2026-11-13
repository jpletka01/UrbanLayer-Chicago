// One chat session's lifecycle, shared by today's chat workspace (App.tsx) and the new UI's full chat page
// (ui-next/chat, Phase 8): a conversation loaded from /c/:id or a share link, stored after each answer, created on
// the first question, and the doors into chat from other pages (?q= autosend, ?pin= grounding, ?handoff= from the
// Profile's quick chat, ?ask=1). Lifted out of App.tsx unchanged in behavior so the two UIs never fork the chat
// path; what each page shows beside the conversation (today's data rail, the new UI's previews) stays in the page,
// fed by the callbacks below.
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { PendingAttachment } from "../components/ChatInput";
import {
  createConversation,
  getConversation,
  getConversationChanges,
  getSharedChanges,
  getSharedConversation,
  uploadFiles,
} from "./api";
import { appendMessages, clearAllHistory, deleteConversation, generateId, loadConversations, migrateLocalStorageToSQLite } from "./history";
import type { ContextObject, Conversation, ConversationDetail, MapData, Message, RetrievalPlan, ScorecardContext, SinceThenResult, UploadMeta } from "./types";
import { useChat } from "./useChat";
import { useConversationRouter } from "./useConversationRouter";
import { useSelectedParcel } from "../contexts/SelectedParcelContext";
import { useAuthContext } from "../contexts/AuthContext";
import { buildScorecardContext } from "./scorecardContext";
import { takeHandoff } from "./openInNewTab";
import { track } from "./tracking";

export interface ChatSessionCallbacks {
  onContext?: (ctx: ContextObject) => void;
  onPlan?: (plan: RetrievalPlan) => void;
  onMapData?: (data: MapData) => void;
  /** A stored conversation (or a shared one) was put on screen. */
  onLoaded?: (messages: Message[]) => void;
  /** A turn finished streaming (stored first when the conversation persists). */
  onTurnDone?: (messages: Message[]) => void;
  /** The conversation was cleared (new chat, back to the start). The page resets what it shows beside it. */
  onCleared?: () => void;
}

export interface ChatSessionOptions extends ChatSessionCallbacks {
  /** Where "New chat" and "back to the start" go: today's workspace lives at "/", the new UI's at "/chat". */
  startPath?: string;
}

/** A stored message as the chat holds it. */
export function messagesFromDetail(detail: ConversationDetail, withCreatedAt = true): Message[] {
  return detail.messages.map((m) => ({
    role: m.role as "user" | "assistant",
    content: m.content,
    context: m.context ?? undefined,
    plan: m.plan ?? undefined,
    mapData: m.map_data ?? undefined,
    mapFetchedAt: m.map_fetched_at ?? undefined,
    ...(withCreatedAt ? { createdAt: m.created_at ?? undefined } : {}),
  }));
}

export function useChatSession(options: ChatSessionOptions = {}) {
  const { t: tc } = useTranslation("common");
  const { startPath = "/" } = options;
  const cb = useRef<ChatSessionCallbacks>(options);
  useEffect(() => { cb.current = options; });

  const { conversationIdFromUrl, shareTokenFromUrl, navigateToConversation, navigateReplace: go, navigateBack } = useConversationRouter();
  const navigate = useNavigate();
  const { scorecard: heldScorecard, select: selectParcel } = useSelectedParcel();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAuthenticated, authRequired, loading: authLoading } = useAuthContext();

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loadingConversation, setLoadingConversation] = useState(!!conversationIdFromUrl);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [showAuthModal, setShowAuthModal] = useState(false);
  // True only in the empty "New Chat" state: keeps the workspace mounted (with an empty composer) when there are
  // no messages yet. Set by newChat; cleared on exit-to-start and on the first send.
  const [composing, setComposing] = useState(false);
  const [isSharedView, setIsSharedView] = useState(false);
  // "Since then" notes for a reopened or shared conversation, by message index (WS6 M9).
  const [sinceThen, setSinceThen] = useState<Record<string, SinceThenResult>>({});
  const conversationIdRef = useRef<string | null>(null);
  const prevStreamingRef = useRef(false);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  const chat = useChat({
    onContext: (c) => cb.current.onContext?.(c),
    onPlan: (p) => cb.current.onPlan?.(p),
    onMapData: (d) => cb.current.onMapData?.(d),
    conversationId,
    language: localStorage.getItem("urbanlayer-language") || "en",
  });
  const { messages, setMessages, streaming, clearTurnState, reset: resetChat, setGrounding, sendMessage: sendChat } = chat;

  // Anonymous visitors chat in-memory only: no server-side conversation, no history, no uploads.
  const canPersist = !authRequired || isAuthenticated;

  // URL → state: load a conversation when the URL changes (direct link, back/forward).
  useEffect(() => {
    if (conversationIdFromUrl && conversationIdFromUrl !== conversationId) {
      setLoadingConversation(true);
      (async () => {
        // A network failure throws: stop loading and say so, instead of an outline that never ends (owner review
        // 2026-11-12, the backend down while the page opened).
        let detail: Awaited<ReturnType<typeof getConversation>>;
        try {
          detail = await getConversation(conversationIdFromUrl);
        } catch {
          setLoadError(tc("loadConversationError"));
          setLoadingConversation(false);
          return;
        }
        if (!detail) {
          go(startPath);
          setLoadingConversation(false);
          return;
        }
        const loaded = messagesFromDetail(detail);
        setMessages(loaded);
        setSinceThen({});
        void getConversationChanges(conversationIdFromUrl).then((notes) => {
          if (conversationIdRef.current === conversationIdFromUrl) setSinceThen(notes);
        });
        setConversationId(conversationIdFromUrl);
        conversationIdRef.current = conversationIdFromUrl;
        clearTurnState();
        cb.current.onLoaded?.(loaded);
        setLoadingConversation(false);
      })();
    } else if (!conversationIdFromUrl && conversationId) {
      // Navigated back to the start.
      resetChat();
      setComposing(false);
      setConversationId(null);
      conversationIdRef.current = null;
      cb.current.onCleared?.();
    } else if (!conversationIdFromUrl) {
      setLoadingConversation(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationIdFromUrl]);

  // A shared conversation (/s/:token), read only.
  useEffect(() => {
    if (!shareTokenFromUrl) {
      if (isSharedView) setIsSharedView(false);
      return;
    }
    setLoadingConversation(true);
    (async () => {
      const detail = await getSharedConversation(shareTokenFromUrl).catch(() => null);
      if (!detail) {
        go(startPath);
        setLoadingConversation(false);
        return;
      }
      const loaded = messagesFromDetail(detail);
      setMessages(loaded);
      setSinceThen({});
      void getSharedChanges(shareTokenFromUrl).then(setSinceThen);
      setIsSharedView(true);
      clearTurnState();
      cb.current.onLoaded?.(loaded);
      setLoadingConversation(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shareTokenFromUrl]);

  // The visitor's conversations, once auth has resolved (anonymous visitors have none: the endpoints 401).
  useEffect(() => {
    if (authLoading) return;
    if (authRequired && !isAuthenticated) return;
    (async () => {
      await migrateLocalStorageToSQLite();
      setConversations(await loadConversations());
    })();
  }, [authLoading, authRequired, isAuthenticated]);

  // Store the turn once its answer has finished streaming.
  useEffect(() => {
    if (prevStreamingRef.current && !streaming) {
      if (messages.length >= 2) {
        const lastTwo = messages.slice(-2);
        if (lastTwo[0]?.role === "user" && lastTwo[1]?.role === "assistant") {
          const cid = conversationIdRef.current;
          if (cid) {
            appendMessages(cid, lastTwo)
              .then(() => loadConversations().then(setConversations))
              .catch((err) => console.error("Failed to save messages:", err));
          }
        }
      }
      cb.current.onTurnDone?.(messages);
    }
    prevStreamingRef.current = streaming;
  }, [streaming, messages]);

  // The conversation the last question created. If the allowance refuses that question (Quotas, Item 120), the
  // empty conversation is removed again, so a refused question never leaves a chat with no answer in the list.
  const createdForQuestionRef = useRef<string | null>(null);
  useEffect(() => {
    const cid = createdForQuestionRef.current;
    if (!chat.atQuota || !cid || cid !== conversationIdRef.current) return;
    if (messages.some((m) => m.role === "assistant" && m.content)) return;
    createdForQuestionRef.current = null;
    void deleteConversation(cid)
      .then(() => loadConversations().then(setConversations))
      .catch(() => { /* the list will show it until reload; nothing else depends on it */ });
    exitToStart();
  }, [chat.atQuota]); // eslint-disable-line react-hooks/exhaustive-deps

  async function sendMessage(text: string, _attachments?: undefined, opts?: { parcelPin?: string | null; scorecardContext?: ScorecardContext | null }) {
    let cid = conversationId;
    // A question the allowance will refuse (Quotas, Item 120) must not leave an empty chat in the list.
    if (!cid && canPersist && !chat.atQuota) {
      cid = generateId();
      const title = text.length > 50 ? text.slice(0, 47) + "..." : text;
      try {
        await createConversation(cid, title, localStorage.getItem("urbanlayer-language") || "en");
      } catch (err) {
        console.error("Failed to create conversation:", err);
        setShowAuthModal(true);
        return;
      }
      setConversationId(cid);
      conversationIdRef.current = cid;
      createdForQuestionRef.current = cid;
      navigateToConversation(cid);
    }

    let uploadMetas: UploadMeta[] | undefined;
    if (pendingAttachments.length > 0 && cid) {
      try {
        uploadMetas = await uploadFiles(cid, pendingAttachments.map((a) => a.file));
      } catch (err) {
        console.error("Upload failed:", err);
      }
      for (const att of pendingAttachments) {
        if (att.previewUrl) URL.revokeObjectURL(att.previewUrl);
      }
      setPendingAttachments([]);
    }

    track("chat_message_sent");
    sendChat(text, uploadMetas, opts);
    // Clear the empty-state flag only now: sendChat has synchronously appended the user message, so the
    // workspace never dips to "inactive" mid-send (the splash-swallows-answer race, 2026-07-03).
    setComposing(false);
  }

  // ?q= autosend (Investigate buttons, Discovery, persona cards). ?pin= rides along so the turn resolves the exact
  // parcel and reads the facts the Profile already resolved (truth-model §3).
  const qConsumedRef = useRef(false);
  // A visit that arrived via ?q=: declining sign-in without an answer goes back to where the visitor was.
  const handoffOriginRef = useRef(false);
  useEffect(() => {
    const q = searchParams.get("q");
    if (!q || qConsumedRef.current) return;
    if (authLoading || conversationIdFromUrl || shareTokenFromUrl) return;
    if (messages.length > 0 || streaming) return;
    qConsumedRef.current = true;
    handoffOriginRef.current = true;
    const pin = searchParams.get("pin");
    setSearchParams({}, { replace: true });
    if (!pin) {
      setGrounding(null);
      sendMessage(q);
      return;
    }
    (async () => {
      const resp = heldScorecard?.resolved_pin === pin ? heldScorecard : await selectParcel({ pin });
      const scorecardContext = resp?.resolved_pin === pin ? buildScorecardContext(resp) : null;
      setGrounding(scorecardContext);
      sendMessage(q, undefined, { parcelPin: pin, scorecardContext });
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, searchParams, conversationIdFromUrl, shareTokenFromUrl, messages.length, streaming]);

  // Bare ?pin= ("Ask about this property"): open the grounded empty state, hydrating the parcel once if needed.
  useEffect(() => {
    const pin = searchParams.get("pin");
    if (!pin || searchParams.get("q")) return;
    if (conversationIdFromUrl || shareTokenFromUrl) return;
    setComposing(true);
    if (heldScorecard?.resolved_pin !== pin) selectParcel({ pin });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, conversationIdFromUrl, shareTokenFromUrl, heldScorecard]);

  // ?handoff=<id>: the Profile's quick chat continued here in a new tab (Item 72). Seeded once; never over an
  // active chat.
  const handoffConsumedRef = useRef(false);
  const handoffId = searchParams.get("handoff");
  useEffect(() => {
    if (handoffConsumedRef.current || !handoffId) return;
    if (conversationIdFromUrl || shareTokenFromUrl) return;
    handoffConsumedRef.current = true;
    const seeded = takeHandoff(handoffId);
    if (!seeded?.length || messages.length > 0 || streaming) return;
    setComposing(true);
    setMessages(seeded.map((m) => ({ role: m.role, content: m.content })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handoffId, conversationIdFromUrl, shareTokenFromUrl, messages.length, streaming]);

  // Bare ?ask=1: an empty, ungrounded chat (the general "Ask the analyst" door).
  useEffect(() => {
    if (!searchParams.get("ask")) return;
    if (conversationIdFromUrl || shareTokenFromUrl) return;
    setGrounding(null);
    setComposing(true);
    setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, conversationIdFromUrl, shareTokenFromUrl]);

  // Grounding for the empty-state starters: only when chat was entered for a parcel (?pin= and the held Profile
  // matches it).
  const entryPin = searchParams.get("pin");
  const groundedContext = useMemo(
    () => (entryPin && heldScorecard?.resolved_pin === entryPin ? buildScorecardContext(heldScorecard) : null),
    [entryPin, heldScorecard],
  );
  // The parcel grounding lasts the whole conversation: only ever set here, cleared by reset() (New chat).
  useEffect(() => {
    if (groundedContext) setGrounding(groundedContext);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groundedContext]);

  function sendPropertyStarter(question: string) {
    if (!groundedContext) return;
    // The question carries the address: a deictic "this lot" routes to clarification before grounding is read.
    const addr = groundedContext.address;
    sendMessage(addr ? `${question} — ${addr}` : question, undefined, {
      parcelPin: groundedContext.pin,
      scorecardContext: groundedContext,
    });
  }

  function attach(files: File[]) {
    const remaining = 3 - pendingAttachments.length;
    const added: PendingAttachment[] = files.slice(0, remaining).map((file) => ({
      file,
      previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
    }));
    setPendingAttachments((prev) => [...prev, ...added]);
  }

  function removeAttachment(index: number) {
    setPendingAttachments((prev) => {
      const next = [...prev];
      const removed = next.splice(index, 1)[0];
      if (removed?.previewUrl) URL.revokeObjectURL(removed.previewUrl);
      return next;
    });
  }

  // Shared teardown for "back to the start" and "new chat": aborts any stream and clears the conversation.
  function clear() {
    resetChat();
    setConversationId(null);
    conversationIdRef.current = null;
    setLoadError(null);
    cb.current.onCleared?.();
  }

  /** Back to the start (today's splash): clear everything, composing off. */
  function exitToStart() {
    clear();
    setComposing(false);
    navigate(startPath);
  }

  /** New chat in place: the same teardown, an empty composer. Navigates so a refresh can't resurrect /c/:id. */
  function newChat() {
    clear();
    setComposing(true);
    navigate(startPath);
  }

  async function openConversation(conv: Conversation) {
    setLoadError(null);
    const detail = await getConversation(conv.id);
    if (!detail) {
      setLoadError(tc("loadConversationError"));
      return;
    }
    const loaded = messagesFromDetail(detail, false);
    setMessages(loaded);
    setConversationId(conv.id);
    conversationIdRef.current = conv.id;
    clearTurnState();
    navigateToConversation(conv.id);
    cb.current.onLoaded?.(loaded);
  }

  async function removeConversation(id: string) {
    await deleteConversation(id);
    setConversations(await loadConversations());
    if (conversationId === id) exitToStart();
  }

  async function removeAll() {
    await clearAllHistory();
    setConversations([]);
    exitToStart();
  }

  /** The sign-in card was dismissed. A ?q= visit that never got an answer goes back to where it came from. */
  function dismissAuth() {
    setShowAuthModal(false);
    const gotAnswer = messages.some((m) => m.role === "assistant" && m.content);
    if (handoffOriginRef.current && !gotAnswer) {
      handoffOriginRef.current = false;
      navigateBack();
    }
  }

  return {
    ...chat,
    conversationId,
    conversationIdRef,
    conversations,
    loadingConversation,
    loadError,
    setLoadError,
    isSharedView,
    sinceThen,
    composing,
    active: messages.length > 0 || streaming || composing,
    canPersist,
    groundedContext,
    pendingAttachments,
    showAuthModal,
    setShowAuthModal,
    sendMessage,
    sendPropertyStarter,
    attach,
    removeAttachment,
    exitToStart,
    newChat,
    openConversation,
    removeConversation,
    removeAll,
    dismissAuth,
  };
}

export type ChatSession = ReturnType<typeof useChatSession>;
