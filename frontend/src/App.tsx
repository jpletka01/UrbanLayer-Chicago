import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
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
import { fetchMapData, fetchSection, isNotCodified, updateMessageMapData } from "./lib/api";
import { SPLASH_STATS } from "./lib/constants";
import { Footer } from "./components/landing/Footer";
import { ValueProps } from "./components/landing/ValueProps";
import { ScrollIndicator } from "./components/landing/ScrollIndicator";
import { StorySection } from "./components/landing/StorySection";
import { ChaosToVerdict } from "./components/landing/ChaosToVerdict";
import { PersonaScenarios } from "./components/landing/PersonaScenarios";
import { HowItWorks } from "./components/landing/HowItWorks";
import type {
  Conversation,
  ContextObject,
  DataSource,
  MapData,
  RetrievalPlan,
  SidebarView,
  SourceTag,
} from "./lib/types";
import { useChatSession } from "./lib/useChatSession";
import { buildReportData, type ReportData } from "./lib/reportBuilder";
import { ExportReport } from "./components/ExportReport";
import { ShareModal } from "./components/ShareModal";
import ConversationMenu from "./components/ConversationMenu";
import { useAuthContext } from "./contexts/AuthContext";
import { useThemeContext } from "./contexts/ThemeContext";
import AuthModal from "./components/AuthModal";
import FloatingNav from "./components/FloatingNav";
import { useTranslation } from "react-i18next";
import { countDataCategories } from "./lib/contextSummary";
import { RotateCcw } from "lucide-react";

const MAP_STALE_MS = 24 * 60 * 60 * 1000; // 24 hours

export function App() {
  const { t } = useTranslation("landing");
  const { resolvedTheme } = useThemeContext();
  const heroLight = resolvedTheme === "light";
  const { t: tc } = useTranslation("common");
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
  const [dataTabViewed, setDataTabViewed] = useState(true);
  const [sourcesTabViewed, setSourcesTabViewed] = useState(true);
  const [mapTabViewed, setMapTabViewed] = useState(true);
  const [exportReport, setExportReport] = useState<ReportData | null>(null);
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const { isAuthenticated, signIn } = useAuthContext();
  const planRef = useRef<RetrievalPlan | null>(null);

  function handleContext(ctx: ContextObject) {
    setActiveSidebarContext(ctx);
    openSidebarResponsive();
    const hasDomain = ctx.parcel_zoning || ctx.property || ctx.regulatory || ctx.incentives || ctx.neighborhood;
    const autoView: SidebarView = hasDomain ? "data" : ctx.code_chunks?.length ? "sources" : "data";
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

  // Clear what sits beside the conversation (the data rail and its map); the session clears the conversation.
  function clearSidebar() {
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
  }

  // The chat session (lib/useChatSession.ts, shared with the new UI's full chat page): loading, storing,
  // creating conversations and the doors into chat from other pages.
  const session = useChatSession({
    onContext: handleContext,
    onPlan: handlePlan,
    onMapData: handleMapData,
    onLoaded: (loaded) => {
      setHistoryOpen(false);
      // Load the last question's state into the sidebar.
      const lastUserIdx = loaded.length - 2;
      if (lastUserIdx >= 0) handleMessageClick(lastUserIdx, loaded);
    },
    onTurnDone: (msgs) => {
      setMapLoading(false);
      const lastTwo = msgs.slice(-2);
      if (msgs.length >= 2 && lastTwo[0]?.role === "user" && lastTwo[1]?.role === "assistant") {
        setSelectedMessageIndex(msgs.length - 2);
      }
    },
    onCleared: clearSidebar,
  });
  const {
    messages,
    streaming,
    plan,
    context,
    showDisclaimer,
    errorMsg,
    canRetry,
    retry,
    rateLimited,
    atQuota,
    questionsLeft,
    usagePlan,
    quotaMessage,
    activities,
    conversationId,
    conversationIdRef,
    conversations,
    loadingConversation,
    loadError,
    setLoadError,
    isSharedView,
    sinceThen,
    active,
    canPersist,
    groundedContext,
    pendingAttachments,
    showAuthModal,
    setShowAuthModal,
    sendPropertyStarter,
  } = session;

  useEffect(() => {
    planRef.current = plan;
  }, [plan]);

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

  function sendMessage(
    text: string,
    _attachments?: undefined,
    opts?: { parcelPin?: string | null; scorecardContext?: import("./lib/types").ScorecardContext | null },
  ) {
    setHistoryOpen(false);
    return session.sendMessage(text, undefined, opts);
  }

  const handleAttach = session.attach;
  const handleRemoveAttachment = session.removeAttachment;

  // Exit to home: clear everything and show the splash.
  function reset() {
    session.exitToStart();
  }

  // New Chat (in place): the same teardown, but stay in the workspace with an empty composer.
  function handleNewChat() {
    session.newChat();
    setHistoryOpen(false); // closes the history drawer when invoked from it
  }

  async function loadConv(conv: Conversation) {
    await session.openConversation(conv);
  }

  async function handleDeleteConversation(id: string) {
    await session.removeConversation(id);
  }

  async function handleClearAll() {
    await session.removeAll();
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
    [messages, conversationIdRef],
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
    const found = await fetchSection(sectionId);
    setSectionView(
      isNotCodified(found) ? { loading: false, chunk: null, notice: found } : { loading: false, chunk: found },
    );
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

            {errorMsg && !atQuota && (
              <div className="px-6 py-3 bg-state-negative/10 border-b border-state-negative/20 text-state-negative text-sm flex items-center justify-between gap-4">
                <span>{errorMsg}</span>
                {canRetry && (
                  <button
                    type="button"
                    onClick={retry}
                    data-testid="chat-retry"
                    className="shrink-0 inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium border border-state-negative/40 rounded-lg hover:bg-state-negative/10 transition-colors"
                  >
                    <RotateCcw aria-hidden className="h-3.5 w-3.5" strokeWidth={2} />
                    {tc("chat:turnError.retry")}
                  </button>
                )}
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
                quotaNotice={atQuota ? quotaMessage : null}
                questionsLeft={questionsLeft}
                usagePlan={usagePlan}
                attachments={pendingAttachments}
                onAttach={canPersist ? handleAttach : undefined}
                onRemoveAttachment={handleRemoveAttachment}
                activities={activities}
                readOnly={isSharedView}
                sinceThen={sinceThen}
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
          // A ?q= visit that never got an answer goes back to where the visitor was (useChatSession).
          onClose={session.dismissAuth}
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
