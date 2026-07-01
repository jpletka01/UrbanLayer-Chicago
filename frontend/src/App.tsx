import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChatInterface } from "./components/ChatInterface";
import { CountUp } from "./components/CountUp";
import { HeroEntrance } from "./components/landing/HeroEntrance";
import { HeroBackdrop } from "./components/landing/HeroBackdrop";
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
import { IntelligenceStack } from "./components/landing/IntelligenceStack";
import { DepthShowcase } from "./components/landing/DepthShowcase";
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
import { useAuthContext } from "./contexts/AuthContext";
import AuthModal from "./components/AuthModal";
import FloatingNav from "./components/FloatingNav";
import { useTranslation } from "react-i18next";
import { track } from "./lib/tracking";

const MAP_STALE_MS = 24 * 60 * 60 * 1000; // 24 hours

function countDataCategories(ctx: ContextObject | null): number {
  if (!ctx) return 0;
  let count = 0;
  if (ctx.crime_last_90d) count++;
  if (ctx.open_311_requests) count++;
  if (ctx.permits) count++;
  if (ctx.violations) count++;
  if (ctx.businesses) count++;
  if (ctx.parcel_zoning) count++;
  if (ctx.regulatory) count++;
  if (ctx.property) count++;
  if (ctx.incentives) count++;
  if (ctx.neighborhood) count++;
  return count;
}

export function App() {
  const { t } = useTranslation("landing");
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
  const { user, isAuthenticated, authRequired, loading: authLoading, signIn } = useAuthContext();
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
    // The empty-state flag has done its job once a message exists; clearing it
    // here keeps it from lingering true into later message-clearing paths.
    setComposing(false);
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
            {/* Hero + value props — slideshow covers both */}
            {/* Hero is a mode-locked dark island (Bento geometric canvas) regardless of theme. */}
            <div className="relative bg-dark-bg" data-theme="dark">
              <HeroBackdrop />

              {/* Hero section — full viewport */}
              <div className="relative z-10 min-h-screen flex flex-col">
                {/* Top header bar — the unified floating nav, over-image variant */}
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.2 }}
                >
                  <FloatingNav
                    position="hero"
                    tone="overImage"
                    languageVariant="splash"
                    onBrandClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
                    contextLeft={
                      conversations.length > 0 ? (
                        <button
                          onClick={() => setHistoryOpen(true)}
                          className="w-9 h-9 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white/80 hover:text-white hover:bg-white/20 transition-all shrink-0"
                          title={tc("viewHistory")}
                        >
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                          </svg>
                        </button>
                      ) : null
                    }
                  />
                </motion.div>

                <div className="flex-1 flex flex-col justify-center items-center px-4 py-20">
                  <div className="text-center max-w-3xl space-y-8">
                    <motion.div
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1, duration: 0.5 }}
                    >
                      {/* Badge pill — live-status dot + provenance */}
                      <div
                        className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.03] px-4 py-1.5 backdrop-blur-sm mb-7"
                        style={{ boxShadow: "0 0 20px rgba(249,164,116,0.10)" }}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                        <span className="text-caption tracking-wide text-white/70">{t("heroBadge")}</span>
                      </div>
                      <h1
                        className="text-display mb-5 bg-gradient-to-b from-white via-white to-white/55 bg-clip-text text-transparent [text-wrap:balance]"
                        style={{ filter: "drop-shadow(0 2px 24px rgba(0,0,0,0.45))" }}
                      >
                        {t("heroSubtitle")}
                      </h1>
                      <p className="text-lead text-white/60 max-w-2xl mx-auto leading-relaxed">
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
                </div>

                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.5, duration: 0.5 }}
                  className="flex justify-around px-4 md:px-8 pb-6 gap-2"
                >
                  {SPLASH_STATS.map((stat, i) => {
                    const labelKeys = ["stats.dataSources", "stats.codeSections", "stats.communityAreas", "stats.regulatoryLayers"];
                    return (
                      <div key={i} className="text-center">
                        <CountUp
                          to={stat.value}
                          format={stat.format}
                          delay={0.6 + i * 0.15}
                          className="text-3xl md:text-4xl font-semibold text-white"
                        />
                        <div className="text-sm text-white/60 uppercase tracking-wider mt-2">{t(labelKeys[i])}</div>
                      </div>
                    );
                  })}
                </motion.div>

                <ScrollIndicator />
              </div>

            </div>

            {/* Value Props — professional positioning */}
            <ValueProps />

            {/* Intelligence Stack — breadth: 6 domain cards */}
            <IntelligenceStack />

            {/* Story interstitial — site feasibility */}
            <StorySection
              image="https://images.unsplash.com/photo-1581373449483-37449f962b6c?w=1920&q=80"
              title={t("story.feasibilityTitle")}
              subtitle={t("story.feasibilitySubtitle")}
              align="left"
            />

            {/* Depth Showcase — product UI previews */}
            <DepthShowcase />

            {/* Persona Scenarios — professional personas */}
            <PersonaScenarios />

            {/* Story interstitial — report workflow */}
            <StorySection
              image="https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=1920&q=80"
              title={t("story.reportTitle")}
              subtitle={t("story.reportSubtitle")}
              align="right"
            />

            {/* How It Works — trust / architecture */}
            <HowItWorks />

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
                onBrandClick={reset}
                brandSuffix={
                  <>
                    <span className="hidden md:inline text-sm text-text-secondary">— Chicago</span>
                    {context?.community_area_name && (
                      <span className="flex items-center gap-2 text-sm min-w-0">
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
                      {tc("signInToSave")}
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
                      {((!dataTabViewed && countDataCategories(activeSidebarContext) > 0) || (!sourcesTabViewed && (activeSidebarContext?.code_chunks?.length ?? 0) > 0) || (!mapTabViewed && mapData)) && (
                        <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-accent" />
                      )}
                    </button>
                    {!streaming && messages.some((m) => m.role === "assistant" && m.context) && (
                      <button
                        onClick={handleExport}
                        className="flex w-9 h-9 md:w-auto md:h-auto md:px-3 md:py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-dark-elevated rounded-lg transition-colors items-center justify-center md:justify-start gap-1.5"
                        title={tc("export")}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                        </svg>
                        <span className="hidden md:inline">{tc("export")}</span>
                      </button>
                    )}
                    {!streaming && isAuthenticated && conversationId && messages.some((m) => m.role === "assistant" && m.context) && (
                      <button
                        onClick={() => setShareModalOpen(true)}
                        className="flex w-9 h-9 md:w-auto md:h-auto md:px-3 md:py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-dark-elevated rounded-lg transition-colors items-center justify-center md:justify-start gap-1.5"
                        title={tc("shareConversation")}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101M10.172 13.828a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                        </svg>
                        <span className="hidden md:inline">{tc("share")}</span>
                      </button>
                    )}
                    <button
                      onClick={handleNewChat}
                      className="px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-dark-elevated rounded-lg transition-colors"
                    >
                      <span className="hidden md:inline">{tc("newChat")}</span>
                      <svg className="w-4 h-4 md:hidden" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                      </svg>
                    </button>
                    {user?.tier === "admin" && (
                      <Link
                        to="/admin"
                        className="hidden md:flex px-2 py-1.5 text-text-muted hover:text-text-secondary transition-colors"
                        title={tc("admin")}
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
                        </svg>
                      </Link>
                    )}
                  </>
                }
              />
            )}

            {errorMsg && errorMsg !== "MESSAGE_LIMIT_REACHED" && (
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
                onNewChat={handleNewChat}
                attachments={pendingAttachments}
                onAttach={canPersist ? handleAttach : undefined}
                onRemoveAttachment={handleRemoveAttachment}
                activities={activities}
                readOnly={isSharedView}
                propertyContext={groundedContext}
                onPropertyStarterClick={sendPropertyStarter}
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
