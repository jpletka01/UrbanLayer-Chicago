import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { ChatInput } from "./components/ChatInput";
import { ChatInterface } from "./components/ChatInterface";
import { CountUp } from "./components/CountUp";
import { HeroSlideshow } from "./components/HeroSlideshow";
import { HistorySidebar } from "./components/HistorySidebar";
import { PromptSuggestionChip } from "./components/PromptSuggestionChip";
import { SidebarPanel } from "./components/SidebarPanel";
import { SourceDetailDrawer, type SectionView } from "./components/SourceDetailDrawer";
import { fetchMapData, fetchSection } from "./lib/api";
import { SPLASH_STATS, SUGGESTIONS } from "./lib/constants";
import {
  clearAllHistory,
  deleteConversation,
  loadConversations,
  migrateOldHistory,
  saveConversation,
  setCurrentConversationId,
} from "./lib/history";
import type { Conversation, ContextObject, DataSource, MapData, RetrievalPlan, SidebarView, SourceTag } from "./lib/types";
import { useChat } from "./lib/useChat";

export function App() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarView, setSidebarView] = useState<SidebarView>("data");
  const [highlightedSourceIndex, setHighlightedSourceIndex] = useState<number | null>(null);
  const [highlightedDataSource, setHighlightedDataSource] = useState<DataSource | null>(null);
  const [sourceFlash, setSourceFlash] = useState(0);
  const [activeSidebarContext, setActiveSidebarContext] = useState<ContextObject | null>(null);
  const [sectionView, setSectionView] = useState<SectionView | null>(null);
  const [mapData, setMapData] = useState<MapData | null>(null);
  const [mapLoading, setMapLoading] = useState(false);
  const [mapSources, setMapSources] = useState<SourceTag[]>([]);
  const planRef = useRef<RetrievalPlan | null>(null);

  // When a turn's context arrives, surface it in the sidebar. Focus the Sources
  // tab whenever code sections were used; only fall back to Data when there are none.
  // Also pre-fetch map data if a community area was resolved.
  function handleContext(ctx: ContextObject) {
    setActiveSidebarContext(ctx);
    setSidebarOpen(true);
    setSidebarView(ctx.code_chunks?.length ? "sources" : "data");

    if (ctx.community_area) {
      const p = planRef.current;
      const relevantSources = (p?.sources ?? []).filter(
        (s): s is SourceTag => s === "crime_api" || s === "311_api" || s === "permits_api"
      );
      const sourcesToFetch = relevantSources.length > 0 ? relevantSources : (["crime_api", "311_api", "permits_api"] as SourceTag[]);
      setMapSources(sourcesToFetch);
      setMapLoading(true);
      fetchMapData({
        community_area: ctx.community_area,
        time_range_days: p?.time_range_days ?? 90,
        sources: sourcesToFetch,
        address_lat: p?.location.resolved_lat ?? undefined,
        address_lon: p?.location.resolved_lon ?? undefined,
        address_label: ctx.resolved_address ?? undefined,
      }).then((data) => {
        setMapData(data);
        setMapLoading(false);
      });
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
    sendMessage: sendChat,
    clearTurnState,
    reset: resetChat,
  } = useChat({ onContext: handleContext });

  useEffect(() => { planRef.current = plan; }, [plan]);

  // Migrate old history format on first load
  useEffect(() => {
    migrateOldHistory();
    setConversations(loadConversations());
  }, []);

  // Save conversation when messages change
  useEffect(() => {
    if (messages.length > 0) {
      const id = saveConversation(messages, conversationId || undefined);
      if (!conversationId) {
        setConversationId(id);
      }
      setConversations(loadConversations());
    }
  }, [messages, conversationId]);

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

  function sendMessage(text: string) {
    setHistoryOpen(false);
    sendChat(text);
  }

  function reset() {
    resetChat();
    setConversationId(null);
    setCurrentConversationId(null);
    setSidebarOpen(false);
    setSidebarView("data");
    setHighlightedSourceIndex(null);
    setHighlightedDataSource(null);
    setActiveSidebarContext(null);
    setMapData(null);
    setMapLoading(false);
    setMapSources([]);
  }

  function loadConversation(conv: Conversation) {
    setMessages(conv.messages);
    setConversationId(conv.id);
    setCurrentConversationId(conv.id);
    setHistoryOpen(false);
    clearTurnState();
  }

  function handleDeleteConversation(id: string) {
    deleteConversation(id);
    setConversations(loadConversations());
    if (conversationId === id) {
      reset();
    }
  }

  function handleClearAll() {
    clearAllHistory();
    setConversations([]);
    reset();
  }

  function handleCitationClick(index: number, messageContext?: ContextObject) {
    if (messageContext) {
      setActiveSidebarContext(messageContext);
    }
    setSidebarOpen(true);
    setSidebarView("sources");
    setHighlightedSourceIndex(index);
    setHighlightedDataSource(null);
    // Bump the flash signal so the target source re-flashes even when it's
    // already the highlighted one (clicking the same citation twice).
    setSourceFlash((f) => f + 1);
  }

  function handleDataClick(source: DataSource, messageContext?: ContextObject) {
    setSidebarOpen(true);
    setSidebarView("data");
    setHighlightedDataSource(source);
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
        onSelect={loadConversation}
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
            {/* History button */}
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
                    Chicago City Intelligence
                  </h1>
                  <p className="text-lg text-white/80 leading-relaxed">
                    Ask about crime patterns, 311 complaints, building activity, and zoning rules — anywhere in the city.
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
                  Chicago City Intelligence
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

            {errorMsg && (
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
                highlightedDataSource={highlightedDataSource}
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
