import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ChatInput } from "./components/ChatInput";
import { ChatInterface } from "./components/ChatInterface";
import { CountUp } from "./components/CountUp";
import { HeroSlideshow } from "./components/HeroSlideshow";
import { HistorySidebar } from "./components/HistorySidebar";
import { MobileSidebarSheet } from "./components/MobileSidebarSheet";
import { PromptSuggestionChip } from "./components/PromptSuggestionChip";
import { SidebarPanel } from "./components/SidebarPanel";
import { SourceDetailDrawer, type SectionView } from "./components/SourceDetailDrawer";
import type { PendingAttachment } from "./components/ChatInput";
import {
  fetchMapData,
  fetchSection,
  getConversation,
  updateMessageMapData,
  uploadFiles,
} from "./lib/api";
import { SPLASH_STATS, SUGGESTIONS } from "./lib/constants";
import { Footer } from "./components/landing/Footer";
import { NeighborhoodExplorer } from "./components/landing/NeighborhoodExplorer";
import { ScrollIndicator } from "./components/landing/ScrollIndicator";
import { StorySection } from "./components/landing/StorySection";
import { ValueProps } from "./components/landing/ValueProps";
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

const MAP_STALE_MS = 24 * 60 * 60 * 1000; // 24 hours

export function App() {
  const { conversationIdFromUrl, navigateToConversation, navigateToSplash, navigateReplace } =
    useConversationRouter();

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loadingConversation, setLoadingConversation] = useState(!!conversationIdFromUrl);
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
  const [selectedMessageIndex, setSelectedMessageIndex] = useState<number | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
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
      setConversationId(null);
      conversationIdRef.current = null;
      setSidebarOpen(false);
      setSidebarView("data");
      setHighlightedSourceIndex(null);
      setActiveSidebarContext(null);
      setMapData(null);
      setMapLoading(false);
      setMapSources([]);
      setSelectedMessageIndex(null);
    } else if (!conversationIdFromUrl) {
      setLoadingConversation(false);
    }
  }, [conversationIdFromUrl]);

  function handleContext(ctx: ContextObject) {
    setActiveSidebarContext(ctx);
    openSidebarResponsive();
    setSidebarView(ctx.parcel_zoning ? "data" : ctx.code_chunks?.length ? "sources" : "data");
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
    atMessageLimit,
    sendMessage: sendChat,
    clearTurnState,
    reset: resetChat,
  } = useChat({
    onContext: handleContext,
    onPlan: handlePlan,
    onMapData: handleMapData,
    conversationId,
  });

  useEffect(() => {
    planRef.current = plan;
  }, [plan]);

  // Init: migrate localStorage, load conversations
  useEffect(() => {
    (async () => {
      await migrateLocalStorageToSQLite();
      const convos = await loadConversations();
      setConversations(convos);
    })();
  }, []);

  // Save messages to SQLite after stream completes
  useEffect(() => {
    if (prevStreamingRef.current && !streaming && messages.length >= 2) {
      const lastTwo = messages.slice(-2);
      if (lastTwo[0]?.role === "user" && lastTwo[1]?.role === "assistant") {
        const cid = conversationIdRef.current;
        if (cid) {
          appendMessages(cid, lastTwo).then(() => {
            loadConversations().then(setConversations);
          });
        }
        // Auto-select the latest question
        setSelectedMessageIndex(messages.length - 2);
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

  const active = messages.length > 0 || streaming;

  async function sendMessage(text: string) {
    setHistoryOpen(false);
    let cid = conversationId;
    if (!cid) {
      cid = generateId();
      const title = text.length > 50 ? text.slice(0, 47) + "..." : text;
      await createConversation(cid, title);
      setConversationId(cid);
      conversationIdRef.current = cid;
      navigateToConversation(cid);
    }

    let uploadMetas: import("./lib/types").UploadMeta[] | undefined;
    if (pendingAttachments.length > 0) {
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

    sendChat(text, uploadMetas);
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

  function reset() {
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
    setSelectedMessageIndex(null);
    navigateToSplash();
  }

  async function loadConv(conv: Conversation) {
    const detail = await getConversation(conv.id);
    if (!detail) return;

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
        setSidebarView(assistantMsg.context.code_chunks?.length ? "sources" : "data");
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
      }

      // Load map data with staleness check
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
              // Update stored map data
              const cid = conversationIdRef.current;
              if (cid) {
                updateMessageMapData(cid, messageIndex + 1, data);
              }
            }
            setMapLoading(false);
          });
        } else {
          setMapData(assistantMsg.mapData);
        }
      } else if (assistantMsg.context?.community_area && assistantMsg.plan) {
        // No saved map data — fetch it
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

  function handleCitationClick(index: number, messageContext?: ContextObject) {
    if (messageContext) {
      setActiveSidebarContext(messageContext);
    }
    openSidebarResponsive();
    setSidebarView("sources");
    setHighlightedSourceIndex(index);
    setSourceFlash((f) => f + 1);
  }

  function handleDataClick(_source: DataSource, messageContext?: ContextObject) {
    openSidebarResponsive();
    setSidebarView("data");
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

  if (loadingConversation) {
    return <div className="w-full min-h-screen bg-[#0d0d0d]" />;
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
            <div className="relative">
              <HeroSlideshow />

              {/* Hero section — full viewport */}
              <div className="relative z-10 min-h-screen flex flex-col">
                {conversations.length > 0 && (
                  <motion.button
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    onClick={() => setHistoryOpen(true)}
                    className="absolute top-4 left-4 z-20 w-10 h-10 rounded-xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white/80 hover:text-white hover:bg-white/20 transition-all"
                    title="View history"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                  </motion.button>
                )}

                <div className="flex-1 flex flex-col justify-center items-center px-4 py-20">
                  <div className="text-center max-w-2xl space-y-8">
                    <motion.div
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1, duration: 0.5 }}
                    >
                      <h1 className="text-4xl md:text-5xl font-semibold tracking-tight text-white mb-4">
                        UrbanLayer
                      </h1>
                      <p className="text-lg text-white/80 leading-relaxed">
                        Chicago public data, explored through conversation.
                      </p>
                    </motion.div>

                    <motion.div
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.2, duration: 0.5 }}
                    >
                      <ChatInput onSubmit={sendMessage} variant="hero" />
                    </motion.div>

                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.4, duration: 0.5 }}
                      className="flex flex-wrap gap-2 justify-center"
                    >
                      {SUGGESTIONS.map((s) => (
                        <PromptSuggestionChip
                          key={s}
                          label={s}
                          onClick={() => sendMessage(s)}
                        />
                      ))}
                    </motion.div>
                  </div>
                </div>

                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.5, duration: 0.5 }}
                  className="flex justify-around px-4 md:px-8 pb-6 gap-2"
                >
                  {SPLASH_STATS.map((stat, i) => (
                    <div key={stat.label} className="text-center">
                      <CountUp
                        to={stat.value}
                        format={stat.format}
                        delay={0.6 + i * 0.15}
                        className="text-3xl md:text-4xl font-semibold text-white"
                      />
                      <div className="text-sm text-white/60 uppercase tracking-wider mt-2">{stat.label}</div>
                    </div>
                  ))}
                </motion.div>

                <ScrollIndicator />
              </div>

            </div>

            {/* Value props — own background, below the slideshow */}
            <ValueProps />

            {/* Story interstitial — business use case */}
            <StorySection
              image="https://images.unsplash.com/photo-1699898064988-9473dc051320?w=1920&q=80"
              title="Open a business with confidence"
              subtitle="Research zoning regulations, check nearby competition, and understand what permits you'll need — before signing a lease."
              align="left"
            />

            {/* Interactive explorer */}
            <NeighborhoodExplorer />

            {/* Story interstitial — move-in use case */}
            <StorySection
              image="https://images.unsplash.com/photo-1654043342878-7491a4c4d098?w=1920&q=80"
              title="Find the right place to live"
              subtitle="Compare crime trends, check 311 complaint patterns, and see what's being built around your next apartment."
              align="right"
            />

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
            <header className="h-14 px-3 md:px-6 flex items-center justify-between bg-dark-bg shrink-0">
              <div className="flex items-center gap-2 md:gap-4 min-w-0">
                <button
                  onClick={reset}
                  className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors shrink-0"
                >
                  <span className="hidden md:inline">UrbanLayer — Chicago</span>
                  <span className="md:hidden">UrbanLayer</span>
                </button>
                {context?.community_area_name && (
                  <div className="flex items-center gap-2 text-sm min-w-0">
                    <span className="text-text-muted">/</span>
                    <span className="text-text-primary truncate max-w-[120px] md:max-w-none">{context.community_area_name}</span>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {/* Mobile sidebar toggle */}
                <button
                  onClick={() => setMobileSidebarOpen(true)}
                  className="md:hidden relative w-9 h-9 rounded-lg flex items-center justify-center text-text-muted hover:text-text-primary hover:bg-dark-elevated transition-colors"
                  aria-label="Open data panel"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
                  </svg>
                  {(activeSidebarContext?.code_chunks?.length ?? 0) > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 min-w-[1rem] h-4 px-0.5 rounded-full text-[9px] font-semibold flex items-center justify-center bg-accent/20 text-accent">
                      {activeSidebarContext!.code_chunks!.length}
                    </span>
                  )}
                </button>
                <button
                  onClick={reset}
                  className="px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-dark-elevated rounded-lg transition-colors"
                >
                  <span className="hidden md:inline">New chat</span>
                  <svg className="w-4 h-4 md:hidden" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                </button>
                <Link
                  to="/admin"
                  className="hidden md:flex px-2 py-1.5 text-text-muted hover:text-text-secondary transition-colors"
                  title="Admin dashboard"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
                  </svg>
                </Link>
              </div>
            </header>

            {errorMsg && errorMsg !== "MESSAGE_LIMIT_REACHED" && (
              <div className="px-6 py-3 bg-rose-500/10 border-b border-rose-500/20 text-rose-400 text-sm">
                {errorMsg}
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
                onNewChat={reset}
                attachments={pendingAttachments}
                onAttach={handleAttach}
                onRemoveAttachment={handleRemoveAttachment}
              />
              <SidebarPanel
                plan={plan}
                context={activeSidebarContext}
                loading={streaming}
                isOpen={sidebarOpen}
                onToggle={() => setSidebarOpen(!sidebarOpen)}
                activeView={sidebarView}
                onViewChange={setSidebarView}
                highlightedSourceIndex={highlightedSourceIndex}
                sourceFlashSignal={sourceFlash}
                sourceCount={activeSidebarContext?.code_chunks?.length ?? 0}
                onSourceClick={setHighlightedSourceIndex}
                onCrossRefClick={handleCrossRefClick}
                mapData={mapData}
                mapLoading={mapLoading}
                mapSources={mapSources}
              />
            </div>

            <MobileSidebarSheet
              isOpen={mobileSidebarOpen}
              onClose={() => setMobileSidebarOpen(false)}
              plan={plan}
              context={activeSidebarContext}
              loading={streaming}
              activeView={sidebarView}
              onViewChange={setSidebarView}
              highlightedSourceIndex={highlightedSourceIndex}
              sourceFlashSignal={sourceFlash}
              onSourceClick={setHighlightedSourceIndex}
              onCrossRefClick={handleCrossRefClick}
              mapData={mapData}
              mapLoading={mapLoading}
              mapSources={mapSources}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <SourceDetailDrawer
        view={sectionView}
        onClose={() => setSectionView(null)}
        onCrossRefClick={handleCrossRefClick}
      />
    </main>
  );
}
