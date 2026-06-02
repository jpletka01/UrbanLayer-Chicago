# Frontend — UrbanLayer

## Stack

React + TypeScript + Vite + Tailwind v3. Map: Mapbox GL JS (dark-v11) + deck.gl via `@deck.gl/mapbox` MapboxOverlay. State: React hooks (no external state library). Build: ~322KB JS, 16KB CSS.

## Key Files

| File | Purpose |
|------|---------|
| `src/App.tsx` | State machine: splash → workspace. Conversation lifecycle, per-question toggling, URL routing |
| `src/lib/useChat.ts` | SSE consumption, message limit (10), activity tracking, plan/context/mapData attachment |
| `src/lib/types.ts` | TypeScript types matching backend Pydantic models |
| `src/lib/api.ts` | SSE streaming, conversation CRUD, map data, admin endpoints, fetchSection cache |
| `src/lib/mapColors.ts` | Shared colors for map + charts + zone categories + OVERLAY_INFO/ZONE_INFO definitions |
| `src/lib/termDefinitions.ts` | Unified term lookup: overlays, zones, incentives, flood zones → `getTermInfo()` |
| `src/components/InfoTooltip.tsx` | Hover/tap popover for domain terms (dotted underline trigger, portal-based) |
| `src/lib/analytics.ts` | Client-side trend/pie computation from map data |
| `src/lib/history.ts` | Async API-backed persistence + localStorage→SQLite migration |

## Design Tokens

| Token | Value | Tailwind |
|-------|-------|----------|
| Background | `#0d0d0d` | `bg-dark-bg` |
| Surface | `#171717` | `bg-dark-surface` |
| Elevated | `#1f1f1f` | `bg-dark-elevated` |
| Border | `#2a2a2a` | `border-dark-border` |
| Accent | `#c96442` | `bg-accent` / `text-accent` |
| Text Primary | `#eeeeee` | `text-text-primary` |
| Text Secondary | `#a3a098` | `text-text-secondary` |
| Text Muted | `#6b6962` | `text-text-muted` |
| Font | Inter, system-ui, sans-serif | — |

## Patterns

- **Per-message context**: each assistant message stores its own `context`, `plan`, `mapData`, `mapFetchedAt`. Citations survive multi-turn. Clicking a past user message loads that turn's data into the sidebar.
- **Sidebar**: drag-to-resize, collapsed rail (44px). Data tab (map + analytics) / Sources tab (code chunks). Auto-opens when context arrives.
- **New sidebar card**: use `CollapsibleCard` pattern from `sidebar/CollapsibleCard.tsx`.
- **Citations**: `[N]` → `CitationPill` (§ section reference), `[data:X]` → `DataPill` (opens Data tab).
- **Map layer order** (bottom → top): zoning polygons → overlay districts → incentive zones → parcel boundary → data dots (crime/311/permits) → transit stations → address pin.
- **Tooltip**: `position: fixed` via `createPortal` to `document.body`, viewport-clamped with `useLayoutEffect`.
- **InfoTooltip**: Wrap term text in `<InfoTooltip term="key">{text}</InfoTooltip>` for hover/tap definitions. Uses `termDefinitions.ts` for lookups across overlays, zones, incentives, flood zones. Dotted underline trigger, 150ms hover persistence, click-away dismiss on mobile.
- **Charts**: `PieChart` (SVG donut) and `BarChart` (SVG horizontal bars) are custom — no chart library. `BarChart` takes `DistributionBucket[]` and renders labeled horizontal bars with hover state.
- **Routing**: `/` (splash), `/c/:id` (conversation), `/admin` (dashboard), `/about` (technical deep dive).

## Commands

```bash
npm run dev          # dev server on :5173
npx tsc --noEmit     # type check
npm run build        # production build (~322KB JS)
```
