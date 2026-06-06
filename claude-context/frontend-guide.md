# Frontend Guide — UrbanLayer

## Layout Architecture

Two global UI states:

**Splash Screen** (`/`): Full-screen hero slideshow (5 Unsplash photos, 8s interval, 2s crossfade) + centered chat input + suggestion chips + animated stats footer. Transitions to workspace on first message.

**Split-Screen Workspace** (`/c/:id`): Chat (left, ~60%) + collapsible sidebar (right, ~40%). Sidebar starts closed (44px rail with document icon + source count badge). Auto-opens when context data arrives. Drag-to-resize left edge handle; snap-close at <200px, max 60% viewport.

**Shared View** (`/s/:shareToken`): Read-only conversation view. Reuses `<App />` with `isSharedView` flag. Header shows "UrbanLayer — Shared" + "Try UrbanLayer" CTA instead of new-chat/auth controls. Chat input replaced with "shared conversation — read only" banner. Sidebar loads normally with map + data cards.

Other routes: `/admin` (dashboard), `/about` (technical deep dive).

## Component Reference

### Chat
| Component | Purpose |
|-----------|---------|
| `ChatInterface` | Message list, input, per-question click handling, message limit UI |
| `ChatInput` | Two variants: `hero` (glassmorphism, splash) and `compact` (workspace). Address autocomplete |
| `MessageBubble` | react-markdown rendering, citation/data pill injection, typewriter effect, click-to-select for user messages |
| `ActivityStatus` | Below-bubble API call tracker with cycling label, expandable checklist |
| `CitationPill` | `[N]` → `§ section` reference with hover tooltip, click opens/expands source |
| `DataPill` | `[data:*]` → colored marker, click opens Data tab |
| `CrossRefPill` | Clickable cross-reference with hover preview of target section |
| `ShareModal` | Create/copy/revoke share links. Checks existing share status on open |
| `DisclaimerBanner` | Amber legal disclaimer |
| `HeroSlideshow` | Landing page photo carousel |
| `CountUp` | Animated stat counter (Framer Motion `useMotionValue`) |

### Sidebar
| Component | Purpose |
|-----------|---------|
| `SidebarPanel` | Desktop: drag-to-resize container with collapsed rail, Data/Sources tab toggle |
| `MobileSidebarSheet` | Mobile: bottom sheet with snap heights (20/70/90vh), 3-tab Map/Data/Sources, touch drag, GL context preservation |
| `DataView` | Data lag note + analytics (map above data cards with vertical drag divider) |
| `SourcesView` | Ranked code chunks with citations |
| `SourceCitation` | Source card: rank badge, § pill, score, expandable text, cross-refs |
| `SourceDetailDrawer` | Full-section viewer for cross-referenced sections |
| `MapView` | Mapbox + deck.gl with click popups (Google Street View links), flyTo, zoning overlay, overlay/incentive polygons. `isMobile` prop: compact layer toggles + filter popover |
| `MapLayerToggles` | Dynamic toggle pills (crime types / 311 departments / source-level) |
| `MapLegend` | Compact legend, zoning category legend in points-off mode |
| `ArrestFilter` | Arrest status segmented control (crime mode) |
| `StatusFilter` | Open/Closed filter (311 mode) |
| `CostFilter` | Cost bucket filter (permits mode) |
| `DateRangeSlider` | Dual-handle date range slider |
| `AnalyticsSection` | Pie chart + trend table orchestrator by filter mode |
| `PieChart` | SVG donut with hover expansion + thin-slice ring + expandable legend |
| `TrendTable` | MoM trend rows with sortable columns, colored arrows |
| `CollapsibleCard` | Reusable pattern for sidebar data cards |
| `PropertyCard` | Parcel info, assessment history, sales |
| `RegulatoryCard` | Zoning overlays, status badges, flood zone, ARO housing projects (count + units + project list) — all with InfoTooltip hover definitions |
| `IncentivesCard` | TIF/OZ/EZ status with fund analysis financials, city grant programs (SBIF/NOF total + recent projects), tax incentive class badge (6b/7a/etc.), per-district cards for neighborhood queries, expandable annual history table, InfoTooltip definitions, census tract links |
| `InfoTooltip` | Dotted-underline hover/tap popover for domain terms. Wraps children, looks up `termDefinitions.ts` |
| `NeighborhoodCard` | Demographics, transit, Walk Score |
| `ViolationsCard` | Building violations |
| `BusinessCard` | Nearby business licenses |

### Admin
| Component | Purpose |
|-----------|---------|
| `AdminDashboard` | Full `/admin` page |
| `StatCard` | Animated metric card |
| `TimeSeriesChart` | SVG area/line chart with hover crosshair |
| `BarChart` | Horizontal bar chart (benchmark grades) |
| `LatencyTable` | p50/p90/p99 with color thresholds |
| `RequestsTable` | Paginated request log with expandable rows |
| `BenchmarkSection` | Score cards + grade bars + pie + per-query table |

## State Management

```
useChat hook:
  messages, plan, context, streaming, showDisclaimer, errorMsg, atMessageLimit

App.tsx state:
  conversationId (synced with URL), sidebarOpen, sidebarView ('data'|'sources'|'map'),
  mapData, selectedMessageIndex (per-question toggling), historyOpen, loadingConversation,
  isSharedView (read-only mode for /s/:token), shareModalOpen,
  mapTabViewed (mobile badge tracking)
```

**Auto-behaviors:**
- Sidebar auto-opens when `context` arrives
- Conversations auto-persist to SQLite via API
- Scroll auto-follows new messages
- Smart default tab (mobile): Map for spatial queries, Data for domain queries, Sources for legal questions
- Desktop: Sources tab default when code chunks exist; Data tab when zoning data present
- URL auto-syncs with conversation ID

## SSE Event Types

```
plan     → RetrievalPlan (router output)
context  → ContextObject (all retrieved data)
map_data → MapDataResponse (geo-located rows)
token    → streaming text chunk
done     → end of stream
```

Each assistant message stores the full context/plan/mapData from its turn, enabling per-question toggling.

## Map System

Layer order (bottom → top): zoning polygons → overlay districts (semi-transparent fills) → incentive zones (dashed outlines) → parcel boundary (blue outline) → data dots (ScatterplotLayer) → transit stations (star markers) → address pin.

Color assignment: zoning uses prefix-based palette (`ZONE_PREFIX_COLORS`), overlays use type-based palette (`OVERLAY_TYPE_COLORS`), incentive zones use deterministic hash-to-HSL per district name (`incentiveZoneColor` in `mapColors.ts`) so each TIF/EZ district gets a unique color automatically.

Empty-state label ("Ask a question to see data on the map") hides when any renderable data is present: point data (crimes, 311, permits), zoning polygons, incentive zones, or overlay districts.

Zoning/Points toggle (top-left): Points off hides scatter dots, shows zoning category legend.

Click popups use `pickMultipleObjects` for overlapping features. Multi-zone clicks show combined popup with Base Zoning + Regulatory Overlays + Incentive Zones sections.

Zoning hover tooltip shows zone class + category label (e.g. "RS-3 / Residential Single-Unit").

## Animations

| Element | Duration | Easing |
|---------|----------|--------|
| Sidebar width | 300ms | ease-in-out |
| View transitions | 300ms | ease-out |
| Button hover | 150ms | ease |
| Hero slideshow | 2000ms | ease-in-out |
| Splash entrance | 500ms | Framer Motion, staggered |

Framer Motion used for splash animations and CountUp stats. Sidebar uses CSS pixel-width + drag instead of Framer.

## Responsive

- **Mobile** (<768px): Single-column chat. Sidebar is `MobileSidebarSheet` — bottom sheet with 3 snap heights (20vh peek / 70vh default / 90vh full). Touch-drag handle with direct DOM manipulation during drag. 3-tab layout (Map / Data / Sources) bypasses `DataMapLayout`, rendering `MapView` and `DataView` independently at full height. MapView stays mounted (`display: none/block` toggle) to preserve GL context across tab switches. Smart default tab based on query type. `MapView isMobile={true}` activates compact layer toggles and filter popover (vs inline desktop controls). `MapLegend` hidden on mobile.
- **Desktop** (768px+): Dual-pane, `SidebarPanel` with `hidden md:flex`. 2-tab Data/Sources with `DataMapLayout` stacking map + data cards. Drag-to-resize sidebar.
- Hero title: `text-4xl md:text-5xl`.
- Chat: `w-full` mobile, `w-[60%]` desktop (sidebar open).
