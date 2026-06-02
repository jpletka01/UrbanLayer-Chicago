# UrbanLayer — Chicago: Style Guide

## 1. Design System Tokens & Constants

### Color Palette

We use a very dark, high-contrast palette throughout the application.

| Token Name | Hex Code | Tailwind Class | Purpose |
|---|---|---|---|
| Background | `#0d0d0d` | `bg-dark-bg` | Main application background |
| Surface | `#171717` | `bg-dark-surface` | Elevated surfaces, cards |
| Elevated | `#1f1f1f` | `bg-dark-elevated` | Further elevated elements |
| Border | `#2a2a2a` | `border-dark-border` | Standard borders |
| User Bubble | `#2a2a2a` | `bg-[#2a2a2a]` | User message background |
| Assistant Bubble | `#1a1a1a` | `bg-[#1a1a1a]` | Assistant message background |
| Accent | `#c96442` | `bg-accent` / `text-accent` | Primary accent, CTAs, active states |
| Accent Hover | `#d97a5a` | `hover:bg-accent-hover` | Hover state for accent elements |
| Accent Muted | `rgba(201, 100, 66, 0.15)` | `bg-accent-muted` | Subtle accent backgrounds |
| Text Primary | `#eeeeee` | `text-text-primary` | Main body text |
| Text Secondary | `#a3a098` | `text-text-secondary` | Supporting text |
| Text Muted | `#6b6962` | `text-text-muted` | De-emphasized text |
| System Alert | `#f43f5e` | `text-rose-400` | Error handling |
| System Warning | `#fbbf24` | `text-amber-400` | Disclaimers and warnings |

### Typography

**Font Family:** Inter, system-ui, sans-serif

**Scale & Weights:**
- **Hero Display Title:** `text-4xl md:text-5xl font-semibold tracking-tight`
- **Section Headers:** `text-sm font-semibold`
- **Body Text / Answers:** `text-base leading-[1.7]`
- **Small Text / Labels:** `text-xs font-medium uppercase tracking-wider`
- **Monospace (code/metrics):** `font-mono text-sm`

---

## 2. Layout Architecture

### Two Global UI States

The application switches between two layout modes based on conversation state.

#### State 1: Splash Screen (Landing View)

Full-screen immersive view with:
- **HeroSlideshow:** Background image carousel with crossfade transitions (8s interval, 2s fade)
- **Centered Content:** Title, subtitle, search input, suggestion chips
- **Stats Footer:** Three metrics displayed at bottom with `justify-around` spacing

```
+--------------------------------------------------+
|                                                  |
|              [Background Slideshow]              |
|                                                  |
|                  UrbanLayer                      |
|        Ask about crime, 311, zoning...           |
|                                                  |
|            [  Search Input  ]                    |
|                                                  |
|      [Chip] [Chip] [Chip] [Chip]                 |
|                                                  |
|   14,628          5           77                 |
|   Code sections   Datasets    Areas              |
+--------------------------------------------------+
```

#### State 2: Split-Screen Workspace (Active Chat)

Dual-pane layout with collapsible sidebar:

```
+--------------------------------------------------+
|  Header (bg-dark-bg, h-14)                       |
+-----------------------------+--------------------+
|                             | [Toggle]           |
|  Chat Interface (60%)       |  Sidebar (40%)     |
|  - Message list             |  - Header + Toggle |
|  - Auto-scroll              |  - Data/Sources    |
|  - Streaming support        |  - Context cards   |
|                             |                    |
|  [Input Bar]                |                    |
+-----------------------------+--------------------+
```

**Sidebar Behavior:**
- Starts closed (collapsed rail: 44px, document icon, source count badge)
- Auto-opens when context data arrives
- Toggle via collapsed rail click or keyboard shortcut (Cmd/Ctrl+B)
- Drag-to-resize left edge handle; snap-close at <200px, max 60% viewport
- View toggle: Data / Sources (Sources default when code chunks exist; Data when zoning present)

---

## 3. Component Specifications

### ChatInput

Two variants: `hero` and `compact`

**Hero Variant (Splash Screen):**
```
- Transparent background, white/20 border
- On text input: glassmorphism effect (bg-dark-surface/80 backdrop-blur-md)
- White text and placeholder
- Rounded-2xl
```

**Compact Variant (Workspace):**
```
- bg-dark-surface with border-dark-border
- Flex layout: [Attachment btn] [Input] [Send btn]
- Accent-colored send button
- focus-within:border-accent/50
```

### MessageBubble

**User Messages:**
```css
.user-message {
  justify-content: flex-end;
  background: #2a2a2a;
  border-radius: 1rem;
  padding: 0.75rem 1rem;
  max-width: 85%;
}
```

**Assistant Messages:**
```css
.assistant-message {
  justify-content: flex-start;
  background: #1a1a1a;
  border-radius: 1rem;
  padding: 0.75rem 1rem;
  max-width: 85%;
}
```

**Assistant Icon:** Sparkle icon in `bg-accent/20` circle

**Streaming State:** Blinking cursor (animate-blink) at text end

**Thinking State:** Three pulsing dots with staggered delays (0ms, 150ms, 300ms)

### SidebarPanel

**Structure:**
```
<aside> (pixel-width panel with drag-to-resize handle)
├── Collapsed rail (44px, document icon, source count badge, vertical "Sources" label)
├── SidebarHeader (title + Data/Sources view toggle)
└── Content area (scrollable)
    ├── DataView
    │   ├── DataMapLayout (map ~75%, data cards ~25%, vertical drag divider)
    │   │   ├── MapView (Mapbox + deck.gl, zoning overlay, filter controls)
    │   │   └── Data section (data lag note, zoning codes table, analytics)
    │   └── AnalyticsSection (pie chart + trend table)
    └── SourcesView (code chunks with citations)
```

**GlassCard Pattern:**
```css
.glass-card {
  background: rgba(23, 23, 23, 0.8);
  backdrop-filter: blur(4px);
  border: 1px solid #2a2a2a;
  border-radius: 0.75rem;
  padding: 1rem;
}
```

### PromptSuggestionChip

```css
.suggestion-chip {
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 0.5rem;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  transition: all 150ms;
}
.suggestion-chip:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
}
```

### DisclaimerBanner

```css
.disclaimer {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.2);
  color: rgba(251, 191, 36, 0.9);
  border-radius: 0.5rem;
  padding: 0.75rem;
  font-size: 0.875rem;
}
```

### SourceCitation

Code chunk display with relevance score badge:
- `>=85%`: Emerald badge (`bg-emerald-500/15 text-emerald-400`)
- `>=70%`: Amber badge (`bg-amber-500/15 text-amber-400`)
- `<70%`: Muted badge (`bg-dark-elevated text-text-muted`)

---

## 4. Animations & Transitions

### Keyframes (tailwind.config.js)

```javascript
keyframes: {
  'fade-in': {
    '0%': { opacity: '0' },
    '100%': { opacity: '1' },
  },
  'blink': {
    '0%, 100%': { opacity: '1' },
    '50%': { opacity: '0' },
  },
}
```

### Transition Patterns

| Element | Duration | Easing | Property |
|---------|----------|--------|----------|
| Sidebar width | 300ms | ease-in-out | width |
| Chat pane width | 300ms | ease-in-out | width |
| View transitions | 300ms | ease-out | opacity |
| Button hover | 150ms | ease | background, color |
| Hero slideshow | 2000ms | ease-in-out | opacity |
| Toggle chevron | 300ms | ease-in-out | transform (rotate) |

### Framer Motion Usage

Framer Motion is used for splash page animations and view transitions. The sidebar uses CSS pixel-width + drag-to-resize instead of Framer Motion.

```typescript
// Splash page entrance animations
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ delay: 0.1, duration: 0.5 }}
/>

// CountUp stats (useMotionValue + animate)
const value = useMotionValue(0);
animate(value, target, { duration: 1.5, ease: [0.16, 1, 0.3, 1] });

// Source citations (expand/collapse)
<motion.div animate={{ height }} />
```

---

## 5. Responsive Behavior

### Breakpoints

- **Mobile (default):** Single-column, sidebar hidden
- **md (768px+):** Dual-pane layout, sidebar visible

### Mobile Adaptations

- Sidebar: `hidden md:flex`
- Chat pane: `w-full` on mobile, `w-[60%]` on desktop (when sidebar open)
- Hero title: `text-4xl md:text-5xl`

---

## 6. File Structure

```
frontend/src/
├── App.tsx                      # Root component, state machine, URL routing, per-question toggling
├── main.tsx                     # BrowserRouter with "/" and "/c/:id" routes
├── components/
│   ├── ChatInput.tsx            # Text input (hero + compact variants) with address autocomplete
│   ├── ChatInterface.tsx        # Message list container, per-question click handling, message limit UI
│   ├── MessageBubble.tsx        # Markdown rendering, citation/data pills, typewriter, click-to-select
│   ├── CitationPill.tsx         # [N] → § section pill with hover tooltip
│   ├── DataPill.tsx             # [data:*] → colored data source pill
│   ├── CrossRefPill.tsx         # Clickable cross-reference with hover preview
│   ├── SidebarPanel.tsx         # Drag-to-resize, collapsed rail, Data/Sources tabs
│   ├── SidebarHeader.tsx        # Header with view toggles
│   ├── SourceCitation.tsx       # Source card with rank, score, expandable text
│   ├── SourceDetailDrawer.tsx   # Full-section viewer for cross-refs
│   ├── HeroSlideshow.tsx        # Background image carousel
│   ├── HistorySidebar.tsx       # Conversation history list
│   ├── CountUp.tsx              # Animated stat counter (motion useMotionValue)
│   ├── ChunkText.tsx            # Chunk text renderer (delegates tables to ChunkTable)
│   ├── ChunkTable.tsx           # Formatted HTML table for table-bearing chunks
│   ├── Tooltip.tsx              # Shared hover tooltip (position: fixed, viewport clamping)
│   ├── DisclaimerBanner.tsx     # Legal notice component
│   ├── PromptSuggestionChip.tsx # Quick action buttons
│   └── sidebar/
│       ├── MapView.tsx          # Mapbox + deck.gl with click popups, zoning overlay
│       ├── MapLayerToggles.tsx  # Dynamic toggle pills (crime types, 311 types, source-level)
│       ├── MapLegend.tsx        # Compact legend, zoning category legend in points-off mode
│       ├── ArrestFilter.tsx     # Arrest status segmented control (crime mode)
│       ├── StatusFilter.tsx     # Open/Closed status filter (311 mode)
│       ├── CostFilter.tsx       # Cost bucket filter (permits mode)
│       ├── DateRangeSlider.tsx  # Dual-handle date range slider
│       ├── DataView.tsx         # Data lag note + analytics (data cards removed)
│       ├── AnalyticsSection.tsx # Pie chart + trend table orchestrator
│       ├── PieChart.tsx         # SVG donut with hover expansion + thin-slice ring
│       ├── TrendTable.tsx       # MoM trend rows with sortable columns
│       └── SourcesView.tsx      # Code references view
├── lib/
│   ├── api.ts                   # SSE streaming, conversation CRUD, map data, fetchSection
│   ├── useChat.ts               # Chat state hook with message limit, SSE consumption
│   ├── history.ts               # Async API-backed persistence + localStorage migration
│   ├── types.ts                 # TypeScript types matching backend Pydantic models
│   ├── analytics.ts             # Client-side trend/pie computation
│   ├── mapColors.ts             # Shared color constants for map + charts + zone colors
│   ├── sse.ts                   # SSE parser
│   ├── useConversationRouter.ts # URL ↔ conversationId sync (useParams + useNavigate)
│   ├── useTypewriter.ts         # Character reveal animation
│   ├── useCopyButton.ts         # Copy-to-clipboard hook
│   ├── constants.ts             # Suggestions, splash stats, timers
│   ├── codeRefs.ts              # Section ID helpers (isResolvableSection, stripHeader)
│   ├── clipboard.ts             # Copy utility
│   └── parseTable.ts            # Table markup parser for ChunkTable
└── index.css                    # Global styles + Tailwind imports
```

---

## 7. State Management

### App-Level State

Most chat state lives in the `useChat` hook (`lib/useChat.ts`):

```typescript
// useChat hook (lib/useChat.ts)
messages: Message[]              // Conversation history
plan: RetrievalPlan | null       // Router output
context: ContextObject | null    // Retrieved data
streaming: boolean               // Active generation
showDisclaimer: boolean          // Legal notice flag
errorMsg: string | null          // Error display
atMessageLimit: boolean          // 10-message limit reached

// App.tsx state
conversationId: string | null   // Active conversation (synced with URL)
sidebarOpen: boolean             // Panel visibility
sidebarView: 'data' | 'sources' // Active view tab
mapData: MapData | null          // Geo-located rows for map
selectedMessageIndex: number | null // Per-question state toggling
historyOpen: boolean             // History sidebar visibility
loadingConversation: boolean     // URL-sync loading guard
```

### Auto-Behaviors

- Sidebar auto-opens when `context` arrives
- Conversations auto-persist to SQLite via API
- Scroll auto-follows new messages
- Sources tab is default when code chunks exist; Data tab when zoning data is present
- URL auto-syncs with conversation ID (`/c/:id`)

### Keyboard Shortcuts

- `Cmd/Ctrl + B`: Toggle sidebar
