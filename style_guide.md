1. Design System Tokens & ConstantsColor PaletteWe use a high-contrast, moody palette for the hero section, transitioning to a clean, highly legible interface for data blocks and chat logs.Token NameHex Code / Tailwind ClassPurposeBrand Primary#0284c7 (sky-600)Main brand accent, primary CTA buttons, active states.Background Dark#090d16 (Custom)Base background color for the immersive hero video/slideshow container.Background Light#f8fafc (slate-50)Main canvas background for the application workspace below the fold.Surface Translucentrgba(255,255,255,0.07)Glassmorphism card backgrounds inside the hero overlay.Text Primary Dark#ffffffTypography overlaid on hero graphics.Text Primary Light#0f172a (slate-900)Standard body text for chat responses and metrics.System Alert#e11d48 (rose-600)Error handling, critical data, missing locations.System Warning#d97706 (amber-600)Disclaimer banners (requires_disclaimer: true).TypographyFont Family: Inter, system-ui, sans-serif (Clean, modern geometric neo-grotesque).Scale & Weights:Hero Display Title: text-5xl font-extrabold tracking-tightSection Headers: text-xl font-semibold tracking-normalBody Text / Answers: text-base font-normal leading-relaxedCitations / Metadata / Small Text: text-xs font-medium uppercase tracking-wider text-slate-5002. Layout States & TransitionsYour React application should switch between two global UI states based on whether a prompt retrieval query is active.State 1: The Splash Dashboard (Landing View)Hero Container: w-full h-screen relative flex flex-col justify-center items-center px-4 overflow-hiddenThe Image Slideshow: A background container running an object-cover w-full h-full absolute inset-0 z-0 brightness-50 contrast-125 configuration, featuring a smooth, cross-fade rotation animation of the Chicago skyline.Content Overlay: A vertical stack centered horizontally (z-10 text-center max-w-3xl space-y-6).Below-the-Fold Grid: Standard grid (grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-7xl mx-auto py-12 px-4 bg-slate-50) displaying quick glance metrics or static ingestion stats.State 2: Split-Screen Intelligence Workspace (Active Query View)When a user hits submit, the hero collapses into a slim persistent top banner, and the main layout switches to a non-scrolling, viewport-locked split screen:+-----------------------------------------------------------------------+
|  Slim Top Header Banner (Translucent, Fixed, height: 64px)            |
+-------------------------------------------------------+---------------+
|                                                       |               |
|                                                       |               |
|  LEFT PANEL: Chat History & Claude Responses          | RIGHT PANEL:  |
|  - Scrollable timeline                                | Context &     |
|  - Renders `MessageBubble`                            | Data Insights |
|  - Renders `DisclaimerBanner` if flagged              | - API Status  |
|                                                       | - Code Chunks |
|  (Tailwind: w-full md:w-3/5 overflow-y-auto h-full)   | (w-2/5 map/   |
|                                                       | source panel) |
+-------------------------------------------------------+---------------+
3. Tailwind Component Styling ManualThe Search/Chat Pill InputHTML<!-- Container wrapper with custom drop shadow -->
<div class="relative w-full max-w-2xl mx-auto shadow-2xl rounded-full bg-white/10 backdrop-blur-md border border-white/20 transition-all duration-300 focus-within:bg-white/15 focus-within:border-white/30">
  <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
    <svg class="h-5 w-5 text-white/60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  </div>
  <input 
    type="text" 
    placeholder="What do you need help with in Chicago?" 
    class="w-full bg-transparent pl-12 pr-14 py-4 rounded-full text-white placeholder-white/60 text-lg focus:outline-none focus:ring-0 border-0"
  />
  <button class="absolute right-2 top-2 bottom-2 bg-white text-slate-900 rounded-full w-10 h-10 flex items-center justify-center font-bold shadow-md hover:bg-slate-100 transition-colors">
    →
  </button>
</div>
Prompt Suggestion Chips (Pills)Rendered underneath the main search block to suggest user intents:  HTML<button class="px-4 py-2 text-sm font-medium rounded-full bg-white/10 hover:bg-white/20 border border-white/10 hover:border-white/20 text-white shadow-sm transition-all duration-150">
  🚇 CTA Status
</button>
Claude's Markdown Response ContainerTo prevent long unformatted blocks of text, format Claude's text content with exact spacing rules using Tailwind typography principles or manual classes:Paragraphs: text-slate-800 dark:text-slate-200 text-base leading-relaxed mb-4Inline Citations: Clicking on inline source text formats should interactively cross-reference items in your sidebar context panel. Style as: cursor-pointer text-sky-600 hover:text-sky-700 underline decoration-dotted font-medium.  Disclaimer Banner (requires_disclaimer: true)When the router returns a prompt touching legal topics, append this component instantly below the specific markdown output window:  HTML<div class="flex gap-3 items-start p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-800 text-sm leading-relaxed mt-4">
  <span class="text-base">💡</span>
  <p>
    <strong>Notice:</strong> This information is based on official city documents but does not constitute legal advice. Please consult a licensed attorney or contact the relevant city department for official guidance.
  </p>
</div>
Source Citation & Freshness Sidebar BlockUsed in the secondary side workspace pane to detail retrieved information transparently:  HTML<div class="p-4 rounded-xl bg-white border border-slate-200 shadow-sm space-y-3">
  <div class="flex items-center justify-between">
    <span class="text-xs font-bold tracking-wider text-slate-400 uppercase">Qdrant Vector Search Match</span>
    <span class="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">91% Match</span>
  </div>
  <h4 class="text-sm font-bold text-slate-900">Municipal Code Sec. 17-2-0100: Residential Districts</h4>[cite: 1]
  <p class="text-xs text-slate-600 font-mono bg-slate-50 p-2 rounded max-h-32 overflow-y-auto">
    <!-- Truncated block text from context_object_as_json -->
    ...
  </p>
</div>
4. UI/UX Rules & Invariant ConstraintsStrictly Minimal Comments: As requested in your codebase layout settings, maintain clean styling code inside components without arbitrary block comments interspersed in JSX blocks.No Structural Disruption on Loading: Use skeletal loading boxes (animate-pulse bg-slate-200) inside the Sidebar Panel tracking data layers when parallel Socrata fetches (asyncio.gather) are processing[cite: 1]. This keeps columns properly locked in position.Data Freshness Visibility: Anytime Layer 1 database logs are displayed, include the mandatory 7-day data exclusion note transparently within the sidebar context metadata[cite: 1].