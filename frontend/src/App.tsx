import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChatInput } from "./components/ChatInput";
import { ChatInterface } from "./components/ChatInterface";
import { CountUp } from "./components/CountUp";
import { HeroSlideshow } from "./components/HeroSlideshow";
import { HistorySidebar } from "./components/HistorySidebar";
import { PromptSuggestionChip } from "./components/PromptSuggestionChip";
import { SidebarPanel } from "./components/SidebarPanel";
import { SourceDetailDrawer, type SectionView } from "./components/SourceDetailDrawer";
import {
  fetchMapData,
  fetchSection,
  getConversation,
  updateMessageMapData,
} from "./lib/api";
import { SPLASH_STATS, SUGGESTIONS } from "./lib/constants";
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

const MAP_STALE_MS = 24 * 60 * 60 * 1000; // 24 hours

export function App() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarView, setSidebarView] = useState<SidebarView>("data");
  const [highlightedSourceIndex, setHighlightedSourceIndex] = useState<number | null>(null);
  const [sourceFlash, setSourceFlash] = useState(0);
  const [activeSidebarContext, setActiveSidebarContext] = useState<ContextObject | null>(null);
  const [sectionView, setSectionView] = useState<SectionView | null>(null);
  const [mapData, setMapData] = useState<MapData | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapSources, setMapSources] = useState<SourceTag[]>([]);
  const [selectedMessageIndex, setSelectedMessageIndex] = useState<number | null>(null);
  const planRef = useRef<RetrievalPlan | null>(null);
  const prevStreamingRef = useRef(false);
  const conversationIdRef = useRef<string | null>(null);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  function handleContext(ctx: ContextObject) {
    setActiveSidebarContext(ctx);
    setSidebarOpen(true);
    // Default to Data tab (map) for zoning questions so the user sees the zoning overlay
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
    // Create conversation on first message
    if (!conversationId) {
      const id = generateId();
      const title = text.length > 50 ? text.slice(0, 47) + "..." : text;
      await createConversation(id, title);
      setConversationId(id);
      conversationIdRef.current = id;
    }
    sendChat(text);
  }

  function reset() {
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
        setSidebarOpen(true);
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

  function handleCitationClick(index: number, messageContext?: ContextObject) {
    if (messageContext) {
      setActiveSidebarContext(messageContext);
    }
    setSidebarOpen(true);
    setSidebarView("sources");
    setHighlightedSourceIndex(index);
    setSourceFlash((f) => f + 1);
  }

  function handleDataClick(_source: DataSource, messageContext?: ContextObject) {
    setSidebarOpen(true);
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
            className="relative w-full min-h-screen flex flex-col"
          >
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

            <div className="relative flex-1 flex flex-col justify-center items-center px-4 py-20">
              <HeroSlideshow />
              <div className="relative z-10 text-center max-w-2xl space-y-8">
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
              className="absolute bottom-12 left-0 right-0 z-10 flex justify-around px-8"
            >
              {SPLASH_STATS.map((stat, i) => (
                <div key={stat.label} className="text-center">
                  <CountUp
                    to={stat.value}
                    format={stat.format}
                    delay={0.6 + i * 0.15}
                    className="text-4xl font-semibold text-white"
                  />
                  <div className="text-sm text-white/60 uppercase tracking-wider mt-2">{stat.label}</div>
                </div>
              ))}
            </motion.div>
          </motion.div>
        ) : (
          <motion.div
            key="workspace"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
            className="w-full h-screen flex flex-col bg-dark-bg"
          >
            <header className="h-14 px-6 flex items-center justify-between bg-dark-bg shrink-0">
              <div className="flex items-center gap-4">
                <button
                  onClick={reset}
                  className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors"
                >
                  UrbanLayer — Chicago
                </button>
                {context?.community_area_name && (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-text-muted">/</span>
                    <span className="text-text-primary">{context.community_area_name}</span>
                  </div>
                )}
              </div>
              <button
                onClick={reset}
                className="px-3 py-1.5 text-xs font-medium text-text-secondary hover:text-text-primary hover:bg-dark-elevated rounded-lg transition-colors"
              >
                New chat
              </button>
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
