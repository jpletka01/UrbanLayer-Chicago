import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChatInterface } from "./components/ChatInterface";
import { CountUp } from "./components/CountUp";
import { HeroEntrance } from "./components/landing/HeroEntrance";
import { HeroBackdrop } from "./components/landing/HeroBackdrop";
import { AccentRails } from "./components/landing/AccentRails";
import { HeroScorecardPreview } from "./components/landing/HeroScorecardPreview";
import { HistorySidebar } from "./components/HistorySidebar";
import { MobileSidebarSheet } from "./components/MobileSidebarSheet";
import { SidebarPanel } from "./components/SidebarPanel";
import { SourceDetailDrawer, type SectionView } from "./components/SourceDetailDrawer";
import type { PendingAttachment } from "./components/ChatInput";
import {
  fetchMapData,
  fetchSection,
  getConversation,
  getSharedConversation,
  updateMessageMapData,
  uploadFiles,
} from "./lib/api";
import { SPLASH_STATS } from "./lib/constants";
import { Footer } from "./components/landing/Footer";
import { ValueProps } from "./components/landing/ValueProps";
import { ScrollIndicator } from "./components/landing/ScrollIndicator";
import { StorySection } from "./components/landing/StorySection";
import { ChaosToVerdict } from "./components/landing/ChaosToVerdict";
import { PersonaScenarios } from "./components/landing/PersonaScenarios";
import { HowItWorks } from "./components/landing/HowItWorks";
import {
  appendMessages,
  clearAllHistory,
  deleteConversation,
  generateId,
  loadConversations,
  migrateLocalStorageToSQLite,
} from "./lib/history";
import { createConversation } from "./lib/api";
import type {
  Conversation,
  ContextObject,
  DataSource,
  MapData,
  RetrievalPlan,
  SidebarView,
  SourceTag,
} from "./lib/types";
import { useChat } from "./lib/useChat";
import { useConversationRouter } from "./lib/useConversationRouter";
import { useSelectedParcel } from "./contexts/SelectedParcelContext";
import { buildScorecardContext } from "./lib/scorecardContext";
import { buildReportData, type ReportData } from "./lib/reportBuilder";
import { ExportReport } from "./components/ExportReport";
import { ShareModal } from "./components/ShareModal";
import ConversationMenu from "./components/ConversationMenu";
import { useAuthContext } from "./contexts/AuthContext";
import { useThemeContext } from "./contexts/ThemeContext";
import AuthModal from "./components/AuthModal";
import FloatingNav from "./components/FloatingNav";
import { useTranslation } from "react-i18next";
import { track } from "./lib/tracking";
import { countDataCategories } from "./lib/contextSummary";

const MAP_STALE_MS = 24 * 60 * 60 * 1000; // 24 hours

export function App() {
  const { t } = useTranslation("landing");
  const { resolvedTheme } = useThemeContext();
  const heroLight = resolvedTheme === "light";
  const { t: tc } = useTranslation("common");
  const { conversationIdFromUrl, shareTokenFromUrl, navigateToConversation, navigateToSplash, navigateReplace, navigateBack } =
    useConversationRouter();
  const { scorecard: heldScorecard, select: selectParcel } = useSelectedParcel();
  const [searchParams, setSearchParams] = useSearchParams();

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loadingConversation, setLoadingConversation] = useState(!!conversationIdFromUrl);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [sidebarView, setSidebarView] = useState<SidebarView>("data");
  const [highlightedSourceIndex, setHighlightedSourceIndex] = useState<number | null>(null);
  const [sourceFlash, setSourceFlash] = useState(0);
  const [activeSidebarContext, setActiveSidebarContext] = useState<ContextObject | null>(null);
  const [sectionView, setSectionView] = useState<SectionView | null>(null);
  const [mapData, setMapData] = useState<MapData | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapSources, setMapSources] = useState<SourceTag[]>([]);
  const [mapIntent, setMapIntent] = useState<string | null>(null);
  const [selectedMessageIndex, setSelectedMessageIndex] = useState<number | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
  const [dataTabViewed, setDataTabViewed] = useState(true);
  const [sourcesTabViewed, setSourcesTabViewed] = useState(true);
  const [mapTabViewed, setMapTabViewed] = useState(true);
  const [exportReport, setExportReport] = useState<ReportData | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);
  // True only in the empty "New Chat" state: keeps the workspace mounted (with an
  // empty composer) when there are no messages yet. Set in handleNewChat; cleared
  // on exit-to-home (reset) and on the first send.
  const [composing, setComposing] = useState(false);
  const [isSharedView, setIsSharedView] = useState(false);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const { isAuthenticated, authRequired, loading: authLoading, signIn } = useAuthContext();
  const planRef = useRef<RetrievalPlan | null>(null);
  const prevStreamingRef = useRef(false);
  const conversationIdRef = useRef<string | null>(null);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  // Sync URL → state: load conversation when URL changes (direct link, browser back/forward)
  useEffect(() => {
    if (conversationIdFromUrl && conversationIdFromUrl !== conversationId) {
      setLoadingConversation(true);
      (async () => {
        const detail = await getConversation(conversationIdFromUrl);
        if (!detail) {
          navigateReplace("/");
          setLoadingConversation(false);
          return;
        }
        const loaded = detail.messages.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
          context: m.context ?? undefined,
          plan: m.plan ?? undefined,
          mapData: m.map_data ?? undefined,
          mapFetchedAt: m.map_fetched_at ?? undefined,
        }));
        setMessages(loaded);
        setConversationId(conversationIdFromUrl);
        conversationIdRef.current = conversationIdFromUrl;
        setHistoryOpen(false);
        clearTurnState();
        const lastUserIdx = loaded.length - 2;
        if (lastUserIdx >= 0) {
          handleMessageClick(lastUserIdx, loaded);
        }
        setLoadingConversation(false);
      })();
    } else if (!conversationIdFromUrl && conversationId) {
      // Browser navigated back to splash
      resetChat();
      setComposing(false);
      setConversationId(null);
      conversationIdRef.current = null;
      setSidebarOpen(false);
      setSidebarView("data");
      setHighlightedSourceIndex(null);
      setActiveSidebarContext(null);
      setMapData(null);
      setMapLoading(false);
      setMapSources([]);
      setMapIntent(null);
      setSelectedMessageIndex(null);
      setDataTabViewed(true);
      setSourcesTabViewed(true);
      setMapTabViewed(true);
    } else if (!conversationIdFromUrl) {
      setLoadingConversation(false);
    }
  }, [conversationIdFromUrl]);

  // Load shared conversation when navigating to /s/:token
  useEffect(() => {
    if (!shareTokenFromUrl) {
      if (isSharedView) setIsSharedView(false);
      return;
    }
    setLoadingConversation(true);
    (async () => {
      const detail = await getSharedConversation(shareTokenFromUrl);
      if (!detail) {
        navigateReplace("/");
        setLoadingConversation(false);
        return;
      }
      const loaded = detail.messages.map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
        context: m.context ?? undefined,
        plan: m.plan ?? undefined,
        mapData: m.map_data ?? undefined,
        mapFetchedAt: m.map_fetched_at ?? undefined,
      }));
      setMessages(loaded);
      setIsSharedView(true);
      setHistoryOpen(false);
      clearTurnState();
      const lastUserIdx = loaded.length - 2;
      if (lastUserIdx >= 0) {
        handleMessageClick(lastUserIdx, loaded);
      }
      setLoadingConversation(false);
    })();
  }, [shareTokenFromUrl]);

  function handleContext(ctx: ContextObject) {
    setActiveSidebarContext(ctx);
    openSidebarResponsive();
    const hasDomain = ctx.parcel_zoning || ctx.property || ctx.regulatory || ctx.incentives || ctx.neighborhood;
    const isMobile = window.innerWidth < 768;

    let autoView: SidebarView;
    if (isMobile) {
      autoView = hasDomain ? "data" : ctx.code_chunks?.length ? "sources" : "data";
    } else {
      autoView = hasDomain ? "data" : ctx.code_chunks?.length ? "sources" : "data";
    }
    setSidebarView(autoView);
    setDataTabViewed(autoView === "data");
    setSourcesTabViewed(autoView === "sources");
    setMapTabViewed((autoView as string) === "map");
  }

  function handleMapData(data: MapData) {
    setMapData(data);
    setMapLoading(false);
    const p = planRef.current;
    const relevantSources = (p?.sources ?? []).filter(
      (s): s is SourceTag => s === "crime_api" || s === "311_api" || s === "permits_api",
    );
    setMapSources(
      relevantSources.length > 0
        ? relevantSources
        : (["crime_api", "311_api", "permits_api"] as SourceTag[]),
    );
    setMapIntent(p?.intent ?? null);
    const hasSpatialData = data.crimes.length > 0 || data.requests_311.length > 0 ||
      data.building_permits.length > 0 ||
      !!(data.zoning && ((data.zoning as Record<string, unknown>).features as unknown[] | undefined)?.length);
    if (hasSpatialData && window.innerWidth < 768) {
      setSidebarView("map");
      setMapTabViewed(true);
    }
  }

  function handlePlan(p: RetrievalPlan) {
    if (p.location?.resolved_community_area) {
      setMapLoading(true);
    }
  }

  const {
    messages,
    setMessages,
    streaming,
    plan,
    context,
    showDisclaimer,
    errorMsg,
    rateLimited,
    atMessageLimit,
    messagesRemaining,
    activities,
    sendMessage: sendChat,
    clearTurnState,
    reset: resetChat,
    setGrounding,
  } = useChat({
    onContext: handleContext,
    onPlan: handlePlan,
    onMapData: handleMapData,
    conversationId,
    language: localStorage.getItem("urbanlayer-language") || "en",
  });

  useEffect(() => {
    planRef.current = plan;
  }, [plan]);

  // Init: migrate localStorage, load conversations (wait for auth to resolve first).
  // Anonymous visitors have no server-side persistence — skip entirely (the
  // conversation endpoints 401 without a session).
  useEffect(() => {
    if (authLoading) return;
    if (authRequired && !isAuthenticated) return;
    (async () => {
      await migrateLocalStorageToSQLite();
      const convos = await loadConversations();
      setConversations(convos);
    })();
  }, [authLoading, authRequired, isAuthenticated]);

  // Save messages to SQLite after stream completes
  useEffect(() => {
    if (prevStreamingRef.current && !streaming) {
      setMapLoading(false);
      if (messages.length >= 2) {
        const lastTwo = messages.slice(-2);
        if (lastTwo[0]?.role === "user" && lastTwo[1]?.role === "assistant") {
          const cid = conversationIdRef.current;
          if (cid) {
            appendMessages(cid, lastTwo)
              .then(() => loadConversations().then(setConversations))
              .catch((err) => console.error("Failed to save messages:", err));
          }
          setSelectedMessageIndex(messages.length - 2);
        }
      }
    }
    prevStreamingRef.current = streaming;
  }, [streaming, messages]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        setSidebarOpen((prev) => !prev);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const active = messages.length > 0 || streaming || composing;

  // Anonymous visitors chat in-memory only: no server-side conversation,
  // no history, no uploads. Auth is asked for where identity is needed
  // (save/share/purchase) — never as a precondition for the first answer.
  const canPersist = !authRequired || isAuthenticated;

  async function sendMessage(
    text: string,
    _attachments?: undefined,
    opts?: { parcelPin?: string | null; scorecardContext?: import("./lib/types").ScorecardContext | null },
  ) {
    setHistoryOpen(false);
    let cid = conversationId;
    if (!cid && canPersist) {
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
      navigateToConversation(cid);
    }

    let uploadMetas: import("./lib/types").UploadMeta[] | undefined;
    if (pendingAttachments.length > 0 && cid) {
      try {
        uploadMetas = await uploadFiles(cid, pendingAttachments.map((a) => a.file));
      } catch (err) {
        console.error("Upload failed:", err);
      }
      // Clean up preview URLs
      for (const att of pendingAttachments) {
        if (att.previewUrl) URL.revokeObjectURL(att.previewUrl);
      }
      setPendingAttachments([]);
    }

    track("chat_message_sent");
    sendChat(text, uploadMetas, opts);
    // Clear the empty-state flag only now: sendChat has synchronously appended
    // the user message, so `active` never dips false mid-send. Clearing it
    // before the awaited conversation creation opened a ~200ms active=false
    // window in which AnimatePresence (mode="wait") began swapping the splash
    // in and dropped the workspace's re-entry when `active` flipped back —
    // stranding the app on the splash while the answer streamed unseen
    // (flaky, mostly mobile; diagnosed 2026-07-03).
    setComposing(false);
  }

  // Auto-send ?q= query parameter (from Investigate buttons on Scorecard).
  // ?pin= rides along so the turn resolves the exact parcel instead of
  // re-geocoding the address text (read-only handoff — truth-model §3), and
  // carries pre-resolved grounding (scorecard_context) so the answer reads the
  // facts the Scorecard already resolved instead of re-fetching them.
  const qConsumedRef = useRef(false);
  // True when this chat visit is a handoff from another page (?q= deep link).
  // If the user then declines the sign-in modal without ever getting an
  // answer, dismissing returns them to the page they came from instead of
  // stranding them on an empty workspace.
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
      // Ungrounded ?q= handoff (Discovery area seam, persona cards, Scorecard
      // failure-recovery): no parcel named, so clear any sticky grounding left
      // from a prior in-session conversation before sending. Same defensive
      // clean-open as the ?ask=1 doors — closes stale grounding on all three.
      setGrounding(null);
      sendMessage(q);
      return;
    }
    // Reuse the held ScorecardResponse from the in-SPA navigation; on a cold
    // deep-link it isn't there, so hydrate once via the scorecard endpoint.
    (async () => {
      const resp = heldScorecard?.resolved_pin === pin ? heldScorecard : await selectParcel({ pin });
      const scorecardContext = resp?.resolved_pin === pin ? buildScorecardContext(resp) : null;
      // Persist as the conversation's grounding so typed follow-ups stay grounded.
      setGrounding(scorecardContext);
      sendMessage(q, undefined, { parcelPin: pin, scorecardContext });
    })();
  }, [authLoading, searchParams, conversationIdFromUrl, shareTokenFromUrl, messages.length, streaming]);

  // Bare ?pin= (the "Ask about this property" entry — no ?q=, so no auto-send):
  // activate the workspace (composing) so the grounded empty-state renders
  // instead of the splash, and ensure the parcel is held so the starters can
  // build. On in-SPA navigation it's already held; on a cold deep-link, hydrate
  // once. composing must be set even when already held, so it can't sit behind
  // the hydration short-circuit.
  useEffect(() => {
    const pin = searchParams.get("pin");
    if (!pin || searchParams.get("q")) return;
    if (conversationIdFromUrl || shareTokenFromUrl) return;
    setComposing(true);
    if (heldScorecard?.resolved_pin !== pin) selectParcel({ pin });
  }, [searchParams, conversationIdFromUrl, shareTokenFromUrl, heldScorecard]);

  // Bare ?ask=1 — the labeled "Ask the analyst" door (Home hero + page nav).
  // Opens an EMPTY, UNGROUNDED chat: the user hasn't named a parcel here, so
  // clear any sticky grounding left from a prior in-session conversation and just
  // activate the composer. This is the general navigation door — deliberately
  // distinct from the Scorecard's grounded handoff (?pin=/?q=), which carries
  // parcel context. Here the chat knows nothing about a parcel, by design.
  useEffect(() => {
    if (!searchParams.get("ask")) return;
    if (conversationIdFromUrl || shareTokenFromUrl) return;
    setGrounding(null);
    setComposing(true);
    setSearchParams({}, { replace: true });
  }, [searchParams, conversationIdFromUrl, shareTokenFromUrl]);

  // Grounding for the empty-state starters: shown only when the workspace was
  // entered for a parcel (?pin= present and the held Scorecard matches it), so
  // the generic librarian entry never surfaces property starters by accident.
  const entryPin = searchParams.get("pin");
  const groundedContext = useMemo(
    () => (entryPin && heldScorecard?.resolved_pin === entryPin ? buildScorecardContext(heldScorecard) : null),
    [entryPin, heldScorecard],
  );

  // Persist the parcel grounding for the whole conversation. Only ever sets (never
  // clears) here, so it survives the autosend's searchParams reset — follow-up
  // turns stay grounded. Cleared only by reset() (New Chat).
  useEffect(() => {
    if (groundedContext) setGrounding(groundedContext);
  }, [groundedContext]);

  function sendPropertyStarter(question: string) {
    if (!groundedContext) return;
    // Embed the address so the router types the turn as an address query — that
    // is what lets _apply_parcel_hint anchor it to the pin (a deictic "this lot"
    // routes to clarification before grounding is ever read). Mirrors the
    // address-bearing InvestigateButton questions.
    const addr = groundedContext.address;
    const text = addr ? `${question} — ${addr}` : question;
    sendMessage(text, undefined, {
      parcelPin: groundedContext.pin,
      scorecardContext: groundedContext,
    });
  }

  function handleAttach(files: File[]) {
    const remaining = 3 - pendingAttachments.length;
    const toAdd = files.slice(0, remaining);
    const newAttachments: PendingAttachment[] = toAdd.map((file) => ({
      file,
      previewUrl: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
    }));
    setPendingAttachments((prev) => [...prev, ...newAttachments]);
  }

  function handleRemoveAttachment(index: number) {
    setPendingAttachments((prev) => {
      const next = [...prev];
      const removed = next.splice(index, 1)[0];
      if (removed?.previewUrl) URL.revokeObjectURL(removed.previewUrl);
      return next;
    });
  }

  // Shared teardown for both "exit to home" (reset) and "new chat in place"
  // (handleNewChat): aborts any in-flight stream, clears the conversation,
  // sidebar, and map state. Does NOT touch `composing` or the URL — the two
  // callers differ only in those.
  function clearWorkspace() {
    resetChat();
    setConversationId(null);
    conversationIdRef.current = null;
    setSidebarOpen(false);
    setMobileSidebarOpen(false);
    setSidebarView("data");
    setHighlightedSourceIndex(null);
    setActiveSidebarContext(null);
    setMapData(null);
    setMapLoading(false);
    setMapSources([]);
    setMapIntent(null);
    setSelectedMessageIndex(null);
    setDataTabViewed(true);
    setSourcesTabViewed(true);
    setMapTabViewed(true);
    setLoadError(null);
  }

  // Exit to home: clear everything and show the splash. `composing` must go
  // false here, or active stays true and the splash never renders.
  function reset() {
    clearWorkspace();
    setComposing(false);
    navigateToSplash();
  }

  // New Chat (in place): same teardown, but stay in the workspace with an empty
  // composer. Navigates to `/` so a refresh can't resurrect the old /c/:id;
  // `composing` keeps `/` on the workspace instead of the splash.
  function handleNewChat() {
    clearWorkspace();
    setComposing(true);
    navigateToSplash();
    setHistoryOpen(false); // no-op from the header (drawer already closed); closes it when invoked from the history drawer
  }

  async function loadConv(conv: Conversation) {
    setLoadError(null);
    const detail = await getConversation(conv.id);
    if (!detail) {
      setLoadError(tc("loadConversationError"));
      return;
    }

    const loaded = detail.messages.map((m) => ({
      role: m.role as "user" | "assistant",
      content: m.content,
      context: m.context ?? undefined,
      plan: m.plan ?? undefined,
      mapData: m.map_data ?? undefined,
      mapFetchedAt: m.map_fetched_at ?? undefined,
    }));

    setMessages(loaded);
    setConversationId(conv.id);
    conversationIdRef.current = conv.id;
    setHistoryOpen(false);
    clearTurnState();
    navigateToConversation(conv.id);

    // Load the last question's state into the sidebar
    const lastUserIdx = loaded.length - 2;
    if (lastUserIdx >= 0) {
      handleMessageClick(lastUserIdx, loaded);
    }
  }

  async function handleDeleteConversation(id: string) {
    await deleteConversation(id);
    const convos = await loadConversations();
    setConversations(convos);
    if (conversationId === id) {
      reset();
    }
  }

  async function handleClearAll() {
    await clearAllHistory();
    setConversations([]);
    reset();
  }

  // Per-question state toggling
  const handleMessageClick = useCallback(
    (messageIndex: number, msgs?: typeof messages) => {
      const allMessages = msgs ?? messages;
      const assistantMsg = allMessages[messageIndex + 1];
      if (!assistantMsg || assistantMsg.role !== "assistant") return;

      setSelectedMessageIndex(messageIndex);

      // Load context
      if (assistantMsg.context) {
        setActiveSidebarContext(assistantMsg.context);
        openSidebarResponsive();
        const hasDomain = assistantMsg.context.parcel_zoning || assistantMsg.context.property ||
          assistantMsg.context.regulatory || assistantMsg.context.incentives || assistantMsg.context.neighborhood;
        const isMobile = window.innerWidth < 768;
        const hasSpatialData = assistantMsg.mapData && (
          assistantMsg.mapData.crimes.length > 0 || assistantMsg.mapData.requests_311.length > 0 ||
          assistantMsg.mapData.building_permits.length > 0 ||
          !!(assistantMsg.mapData.zoning && ((assistantMsg.mapData.zoning as Record<string, unknown>).features as unknown[] | undefined)?.length)
        );
        let autoView: SidebarView;
        if (isMobile && hasSpatialData) {
          autoView = "map";
        } else {
          autoView = hasDomain ? "data" : assistantMsg.context.code_chunks?.length ? "sources" : "data";
        }
        setSidebarView(autoView);
        setDataTabViewed(autoView === "data");
        setSourcesTabViewed(autoView === "sources");
        setMapTabViewed(autoView === "map");
      }

      // Load plan
      if (assistantMsg.plan) {
        planRef.current = assistantMsg.plan;
        const relevantSources = (assistantMsg.plan.sources ?? []).filter(
          (s): s is SourceTag => s === "crime_api" || s === "311_api" || s === "permits_api",
        );
        setMapSources(
          relevantSources.length > 0
            ? relevantSources
            : (["crime_api", "311_api", "permits_api"] as SourceTag[]),
        );
        setMapIntent(assistantMsg.plan.intent ?? null);
      }

      // Load map data with staleness check
      setMapLoading(false);
      if (assistantMsg.mapData) {
        const isStale =
          assistantMsg.mapFetchedAt &&
          Date.now() - assistantMsg.mapFetchedAt > MAP_STALE_MS;

        if (isStale && assistantMsg.context?.community_area && assistantMsg.plan) {
          setMapLoading(true);
          const p = assistantMsg.plan;
          const sources = (p.sources ?? []).filter(
            (s) => s === "crime_api" || s === "311_api" || s === "permits_api",
          );
          fetchMapData({
            community_area: assistantMsg.context.community_area,
            time_range_days: p.time_range_days ?? 90,
            sources: sources.length > 0 ? sources : ["crime_api", "311_api", "permits_api"],
            address_lat: p.location?.resolved_lat ?? undefined,
            address_lon: p.location?.resolved_lon ?? undefined,
            address_label: assistantMsg.context.resolved_address ?? undefined,
          }).then((data) => {
            if (data) {
              setMapData(data);
              const cid = conversationIdRef.current;
              if (cid) {
                updateMessageMapData(cid, messageIndex + 1, data);
              }
            }
            setMapLoading(false);
          }).catch(() => {
            setMapLoading(false);
          });
        } else {
          setMapData(assistantMsg.mapData);
        }
      } else if (assistantMsg.context?.community_area && assistantMsg.plan) {
        setMapLoading(true);
        const p = assistantMsg.plan;
        const sources = (p.sources ?? []).filter(
          (s) => s === "crime_api" || s === "311_api" || s === "permits_api",
        );
        fetchMapData({
          community_area: assistantMsg.context.community_area,
          time_range_days: p.time_range_days ?? 90,
          sources: sources.length > 0 ? sources : ["crime_api", "311_api", "permits_api"],
        }).then((data) => {
          setMapData(data);
          setMapLoading(false);
        }).catch(() => {
          setMapLoading(false);
        });
      }
    },
    [messages],
  );

  function openSidebarResponsive() {
    if (window.innerWidth < 768) {
      setMobileSidebarOpen(true);
    } else {
      setSidebarOpen(true);
    }
  }

  function handleViewChange(view: SidebarView) {
    setSidebarView(view);
    if (view === "data") setDataTabViewed(true);
    if (view === "sources") setSourcesTabViewed(true);
    if (view === "map") setMapTabViewed(true);
  }

  function handleCitationClick(index: number, messageContext?: ContextObject) {
    if (messageContext) {
      setActiveSidebarContext(messageContext);
    }
    openSidebarResponsive();
    setSidebarView("sources");
    setSourcesTabViewed(true);
    setHighlightedSourceIndex(index);
    setSourceFlash((f) => f + 1);
  }

  function handleDataClick(_source: DataSource, messageContext?: ContextObject) {
    openSidebarResponsive();
    setSidebarView("data");
    setDataTabViewed(true);
    setHighlightedSourceIndex(null);
    if (messageContext) {
      setActiveSidebarContext(messageContext);
    }
  }

  async function handleCrossRefClick(sectionId: string) {
    setSectionView({ loading: true, chunk: null });
    const chunk = await fetchSection(sectionId);
    setSectionView({ loading: false, chunk });
  }

  function handleExport() {
    let mapScreenshot: string | null = null;
    try {
      const canvas = document.querySelector(".mapboxgl-canvas") as HTMLCanvasElement | null;
      if (canvas) mapScreenshot = canvas.toDataURL("image/png");
    } catch { /* WebGL context lost — skip map */ }

    const title = context?.resolved_address || context?.community_area_name || tc("transcriptTitle");
    const report = buildReportData(messages, mapScreenshot, title);
    setExportReport(report);
  }

  if (loadingConversation) {
    return <div className="w-full min-h-screen bg-dark-bg" />;
  }

  return (
    <main className="w-full min-h-screen text-text-primary">
      <HistorySidebar
        isOpen={historyOpen}
        onClose={() => setHistoryOpen(false)}
        conversations={conversations}
        onSelect={loadConv}
        onDelete={handleDeleteConversation}
        onClearAll={handleClearAll}
        onNewChat={handleNewChat}
      />

      <AnimatePresence mode="wait">
        {!active ? (
          <motion.div
            key="splash"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="w-full"
          >
            {/* Persistent floating nav — stays pinned at the top as the page scrolls, and
                follows the page theme (a themed pill over the always-dark hero). */}
            <FloatingNav
              position="floating"
              languageVariant="splash"
              onBrandClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              contextLeft={
                conversations.length > 0 ? (
                  <button
                    onClick={() => setHistoryOpen(true)}
                    className="w-8 h-8 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-colors shrink-0"
                    title={tc("viewHistory")}
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                  </button>
                ) : null
              }
            />

            {/* Hero is a mode-locked dark island (Bento geometric canvas) regardless of theme.
                Negative top-margin pulls it up under the sticky nav so the nav floats over it —
                it must equal the nav's FLOW height (h-14; sticky top-3 shifts the stuck position,
                not the flow slot), or the hero ends short of the fold by the difference. */}
            {/* overflow-x-clip: the hero's decorative bleeds (stat halos, preview bloom)
                extend past the viewport on phones and widened the page (audit 2026-07-05).
                clip (not hidden) — no scroll container, sticky/vertical flow unaffected. */}
            <div className="relative bg-dark-bg -mt-14 overflow-x-clip" data-theme={heroLight ? undefined : "dark"}>
              <HeroBackdrop />
              {/* Light-mode paper scrim: lets the full-bleed halftone recede behind the
                  left text column so grey text isn't sitting on grey dots. Dots stay full
                  strength in the periphery / behind the card. Dark mode uses the DotMatrix
                  mask + drop-shadows for the same job, so this is light-only. */}
              {heroLight && (
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0"
                  style={{
                    background:
                      "radial-gradient(ellipse 54% 58% at 27% 44%, rgb(var(--bg) / 0.96), rgb(var(--bg) / 0.68) 46%, transparent 74%)",
                  }}
                />
              )}

              {/* Hero section — full viewport */}
              <div className="relative z-10 min-h-screen flex flex-col">
                <div className="flex-1 flex items-center px-4 md:px-8 py-16 pt-28">
                  <div className="w-full max-w-7xl mx-auto grid lg:grid-cols-2 gap-10 lg:gap-14 items-center">
                    {/* Left: message + entry (left-aligned on desktop, centered on mobile) */}
                    <div className="text-center lg:text-left space-y-8 max-w-2xl mx-auto lg:mx-0 w-full">
                      <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1, duration: 0.5 }}
                      >
                        {/* Badge pill — live-status dot + provenance */}
                        <div
                          className={`inline-flex items-center gap-2 rounded-full border px-4 py-1.5 backdrop-blur-sm mb-7 ${heroLight ? "border-dark-border-strong bg-dark-surface/70" : "border-white/15 bg-white/[0.03]"}`}
                          style={{ boxShadow: "0 0 20px rgba(249,164,116,0.10)" }}
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                          <span className={`text-caption tracking-wide ${heroLight ? "text-text-secondary" : "text-white/70"}`}>{t("heroBadge")}</span>
                        </div>
                        <h1
                          className={`text-display mb-5 bg-gradient-to-b bg-clip-text text-transparent [text-wrap:balance] ${heroLight ? "from-text-primary via-text-primary to-text-primary/60" : "from-white via-white to-white/55"}`}
                          style={{ filter: heroLight ? "none" : "drop-shadow(0 2px 24px rgba(0,0,0,0.45))" }}
                        >
                          {t("heroSubtitle")}
                        </h1>
                        <p className={`text-lead max-w-xl mx-auto lg:mx-0 leading-relaxed ${heroLight ? "text-text-secondary" : "text-white/75"}`}>
                          {t("heroSubline")}
                        </p>
                      </motion.div>

                      <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2, duration: 0.5 }}
                      >
                        <HeroEntrance />
                      </motion.div>
                    </div>

                    {/* Right: live product preview — the Scorecard, on the first screen */}
                    <motion.div
                      initial={{ opacity: 0, y: 24 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.35, duration: 0.6, ease: "easeOut" }}
                      className="w-full"
                    >
                      <HeroScorecardPreview />
                    </motion.div>
                  </div>
                </div>

                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.5, duration: 0.5 }}
                  className="grid grid-cols-2 gap-x-2 gap-y-7 justify-items-center sm:flex sm:justify-around sm:gap-2 px-4 md:px-8 pb-6"
                >
                  {SPLASH_STATS.map((stat, i) => {
                    const labelKeys = ["stats.dataSources", "stats.codeSections", "stats.communityAreas", "stats.regulatoryLayers"];
                    return (
                      <div key={i} className="relative text-center">
                        {/* Local dark halo — same job as the headline's masked tint: keeps the
                            stat legible where the skyline dot lattice runs at full strength. */}
                        <div
                          aria-hidden="true"
                          className="absolute -inset-x-14 -inset-y-6"
                          style={{
                            background: heroLight
                              ? "radial-gradient(ellipse closest-side, rgba(250,250,249,0.95) 45%, rgba(250,250,249,0.6) 75%, transparent 100%)"
                              : "radial-gradient(ellipse closest-side, rgba(10,10,10,0.95) 45%, rgba(10,10,10,0.6) 75%, transparent 100%)",
                          }}
                        />
                        <div className="relative">
                          <CountUp
                            to={stat.value}
                            format={stat.format}
                            delay={0.6 + i * 0.15}
                            className={`text-3xl md:text-4xl font-semibold ${heroLight ? "text-text-primary" : "text-white"}`}
                          />
                          <div className={`text-sm uppercase tracking-wider mt-2 ${heroLight ? "text-text-secondary" : "text-white/60"}`}>{t(labelKeys[i])}</div>
                        </div>
                      </div>
                    );
                  })}
                </motion.div>

                <ScrollIndicator />
              </div>

            </div>

            {/* Below-hero sections share faint accent plat-rails along the page margins,
                continuing the hero backdrop's survey-map language. */}
            <div className="relative">
              <AccentRails />

            {/* Chaos → Verdict — the dense, coded municipal source material collapsing into one
                cited verdict. Visualizes the problem (fragmentation) and the value (clarity). */}
            <ChaosToVerdict />

            {/* Value Props — professional positioning */}
            <ValueProps />

            {/* Story interstitial — site feasibility (Chicago cityscape). Swap the URL freely. */}
            <StorySection
              image="https://images.unsplash.com/photo-1494522855154-9297ac14b55f?w=1400&q=80"
              title={t("story.feasibilityTitle")}
              subtitle={t("story.feasibilitySubtitle")}
              align="left"
            />

            {/* Persona Scenarios — professional personas */}
            <PersonaScenarios />

            {/* Story interstitial — report workflow (construction/build). Swap the URL freely. */}
            <StorySection
              image="https://images.unsplash.com/photo-1541888946425-d81bb19240f5?w=1400&q=80"
              title={t("story.reportTitle")}
              subtitle={t("story.reportSubtitle")}
              align="right"
            />

            {/* How It Works — trust / architecture */}
            <HowItWorks />
            </div>

            <Footer />
          </motion.div>
        ) : (
          <motion.div
            key="workspace"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="w-full h-screen flex flex-col bg-dark-bg"
          >
            {isSharedView ? (
              <FloatingNav
                position="floating"
                maxWidthClass="max-w-7xl"
                showNav={false}
                hideUtilities
                brandTo="/"
                brandSuffix={<span className="hidden md:inline text-sm text-text-secondary">— {tc("shared")}</span>}
                contextRight={
                  <Link
                    to="/"
                    className="px-3 py-1.5 text-xs font-medium text-accent hover:text-accent/80 hover:bg-dark-elevated rounded-lg transition-colors"
                  >
                    {tc("tryUrbanLayer")}
                  </Link>
                }
              />
            ) : (
              <FloatingNav
                position="floating"
                maxWidthClass="max-w-7xl"
                languageVariant="workspace"
                omitNavKey="nav.askAnalyst"
                compactBrand
                onBrandClick={reset}
                brandSuffix={
                  <>
                    <span className="hidden md:inline text-sm text-text-secondary">— Chicago</span>
                    {context?.community_area_name && (
                      <span className="hidden md:flex items-center gap-2 text-sm min-w-0">
                        <span className="text-text-muted">/</span>
                        <span className="text-text-primary truncate max-w-[120px] md:max-w-none">
                          {context.community_area_name}
                        </span>
                      </span>
                    )}
                  </>
                }
                contextLeft={
                  conversations.length > 0 ? (
                    <button
                      onClick={() => setHistoryOpen(true)}
                      className="w-8 h-8 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-colors shrink-0"
                      title={tc("chatHistory")}
                    >
                      <svg className="w-4.5 h-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                      </svg>
                    </button>
                  ) : null
                }
                signInSlot={
                  !canPersist ? (
                    <button
                      onClick={() => setShowAuthModal(true)}
                      className="px-3 py-1.5 text-xs font-medium text-accent hover:text-accent/80 hover:bg-dark-elevated rounded-lg transition-colors"
                    >
                      {tc("signInToSaveShort")}
                    </button>
                  ) : undefined
                }
                contextRight={
                  <>
                    {/* Mobile sidebar toggle */}
                    <button
                      onClick={() => setMobileSidebarOpen(true)}
                      className="md:hidden relative w-9 h-9 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-colors"
                      aria-label={tc("openDataPanel")}
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
                      </svg>
                    </button>
                    <ConversationMenu
                      canExport={!streaming && messages.some((m) => m.role === "assistant" && m.context)}
                      onExport={handleExport}
                      canShare={!streaming && isAuthenticated && !!conversationId && messages.some((m) => m.role === "assistant" && m.context)}
                      onShare={() => setShareModalOpen(true)}
                    />
                    <button
                      onClick={handleNewChat}
                      className="w-9 h-9 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-colors"
                      title={tc("newChat")}
                      aria-label={tc("newChat")}
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                      </svg>
                    </button>
                  </>
                }
              />
            )}

            {errorMsg && (
              <div className="px-6 py-3 bg-state-negative/10 border-b border-state-negative/20 text-state-negative text-sm flex items-center justify-between gap-4">
                <span>{errorMsg}</span>
                {rateLimited && !canPersist && (
                  <button
                    onClick={() => setShowAuthModal(true)}
                    className="shrink-0 px-3 py-1 text-xs font-medium text-white bg-action hover:bg-action-hover rounded-lg transition-colors"
                  >
                    {tc("signInShort")}
                  </button>
                )}
              </div>
            )}
            {loadError && (
              <div className="px-6 py-3 bg-state-negative/10 border-b border-state-negative/20 text-state-negative text-sm flex items-center justify-between">
                <span>{loadError}</span>
                <button onClick={() => setLoadError(null)} className="ml-4 text-state-negative/60 hover:text-state-negative">
                  &times;
                </button>
              </div>
            )}

            <div className="flex-1 flex overflow-hidden">
              <ChatInterface
                messages={messages}
                streaming={streaming}
                showDisclaimer={showDisclaimer}
                onSubmit={sendMessage}
                onCitationClick={handleCitationClick}
                onDataClick={handleDataClick}
                streamingContext={context}
                onMessageClick={handleMessageClick}
                selectedMessageIndex={selectedMessageIndex}
                atMessageLimit={atMessageLimit}
                messagesRemaining={messagesRemaining}
                onNewChat={handleNewChat}
                attachments={pendingAttachments}
                onAttach={canPersist ? handleAttach : undefined}
                onRemoveAttachment={handleRemoveAttachment}
                activities={activities}
                readOnly={isSharedView}
                propertyContext={groundedContext}
                onPropertyStarterClick={sendPropertyStarter}
                onOpenPanel={(assistantIndex, tab) => {
                  // Load that turn's context/plan/map (also opens the panel or
                  // sheet responsively), then land on the tapped tab. "map" is
                  // a mobile-sheet-only view; on desktop the map lives inside
                  // the Data tab (DataMapLayout).
                  handleMessageClick(assistantIndex - 1);
                  const isMobile = window.innerWidth < 768;
                  handleViewChange(tab === "map" && !isMobile ? "data" : tab);
                }}
              />
              <SidebarPanel
                context={activeSidebarContext}
                loading={streaming}
                isOpen={sidebarOpen}
                onToggle={() => setSidebarOpen(!sidebarOpen)}
                activeView={sidebarView}
                onViewChange={handleViewChange}
                highlightedSourceIndex={highlightedSourceIndex}
                sourceFlashSignal={sourceFlash}
                sourceCount={activeSidebarContext?.code_chunks?.length ?? 0}
                onSourceClick={setHighlightedSourceIndex}
                onCrossRefClick={handleCrossRefClick}
                mapData={mapData}
                mapLoading={mapLoading}
                mapSources={mapSources}
                mapIntent={mapIntent}
                showDataBadge={!dataTabViewed}
                showSourcesBadge={!sourcesTabViewed}
              />
            </div>

            <MobileSidebarSheet
              isOpen={mobileSidebarOpen}
              onClose={() => setMobileSidebarOpen(false)}
              context={activeSidebarContext}
              loading={streaming}
              activeView={sidebarView}
              onViewChange={handleViewChange}
              highlightedSourceIndex={highlightedSourceIndex}
              sourceFlashSignal={sourceFlash}
              onSourceClick={setHighlightedSourceIndex}
              onCrossRefClick={handleCrossRefClick}
              mapData={mapData}
              mapLoading={mapLoading}
              mapSources={mapSources}
              mapIntent={mapIntent}
              showDataBadge={!dataTabViewed}
              showSourcesBadge={!sourcesTabViewed}
              showMapBadge={!mapTabViewed}
              dataCount={countDataCategories(activeSidebarContext)}
              sourceCount={activeSidebarContext?.code_chunks?.length ?? 0}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <SourceDetailDrawer
        view={sectionView}
        onClose={() => setSectionView(null)}
        onCrossRefClick={handleCrossRefClick}
      />

      {exportReport && (
        <ExportReport
          report={exportReport}
          onClose={() => setExportReport(null)}
        />
      )}

      {showAuthModal && (
        <AuthModal
          onSignIn={signIn}
          onClose={() => {
            setShowAuthModal(false);
            // Dead-end handoff: arrived via ?q= from another page and never
            // received an answer (rate-limited / failed). Declining sign-in
            // returns the user to where they actually were.
            const gotAnswer = messages.some((m) => m.role === "assistant" && m.content);
            if (handoffOriginRef.current && !gotAnswer) {
              handoffOriginRef.current = false;
              navigateBack();
            }
          }}
        />
      )}

      {shareModalOpen && conversationId && (
        <ShareModal
          conversationId={conversationId}
          onClose={() => setShareModalOpen(false)}
        />
      )}
    </main>
  );
}
