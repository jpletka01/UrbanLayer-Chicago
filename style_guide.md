# Chicago City Intelligence — Style Guide

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
|           Chicago City Intelligence              |
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
- Starts closed, auto-opens when context data arrives
- Toggle via button or keyboard shortcut (Cmd/Ctrl+B)
- Animated width transition (300ms ease-in-out)
- View toggle: Data / Sources

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
<aside> (motion.aside with animated width)
├── SidebarToggle (circular button at -left-3)
├── SidebarHeader (title + view toggle)
└── Content area (scrollable)
    ├── DataView (sources, latency, crime, 311, permits)
    └── SourcesView (code chunks)
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

```typescript
// View switching
<AnimatePresence mode="wait">
  {!active ? <SplashView /> : <WorkspaceView />}
</AnimatePresence>

// Sidebar animation
<motion.aside
  animate={{ width: isOpen ? "40%" : "0%" }}
  transition={{ duration: 0.3, ease: "easeInOut" }}
/>

// Staggered entrance
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ delay: 0.1, duration: 0.5 }}
/>
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
├── App.tsx                      # Root component, state management
├── components/
│   ├── ChatInput.tsx            # Text input (hero + compact variants)
│   ├── ChatInterface.tsx        # Message list container
│   ├── MessageBubble.tsx        # Individual message rendering
│   ├── SidebarPanel.tsx         # Collapsible context panel
│   ├── SidebarToggle.tsx        # Toggle button component
│   ├── SidebarHeader.tsx        # Header with view toggles
│   ├── SourceCitation.tsx       # Code chunk display
│   ├── HeroSlideshow.tsx        # Background image carousel
│   ├── DisclaimerBanner.tsx     # Legal notice component
│   ├── PromptSuggestionChip.tsx # Quick action buttons
│   └── sidebar/
│       ├── DataView.tsx         # Data cards (crime, 311, etc.)
│       └── SourcesView.tsx      # Code references view
├── lib/
│   ├── api.ts                   # SSE streaming client
│   ├── history.ts               # localStorage persistence
│   └── types.ts                 # TypeScript interfaces
└── index.css                    # Global styles + Tailwind imports
```

---

## 7. State Management

### App-Level State

```typescript
// Core data
messages: Message[]              // Conversation history
plan: RetrievalPlan | null       // Router output
context: ContextObject | null    // Retrieved data
streaming: boolean               // Active generation
timings: PhaseTimings            // Latency metrics

// UI state
sidebarOpen: boolean             // Panel visibility
sidebarView: 'data' | 'sources'  // Active view tab
showDisclaimer: boolean          // Legal notice flag
errorMsg: string | null          // Error display
```

### Auto-Behaviors

- Sidebar auto-opens when `context` arrives
- History auto-saves to localStorage on message change
- Scroll auto-follows new messages

### Keyboard Shortcuts

- `Cmd/Ctrl + B`: Toggle sidebar
