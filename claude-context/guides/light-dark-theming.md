# Light/Dark Theming — Plan

**Status: Phases 1–2 COMPLETE on branch `feat/light-dark-theming` (2026-06-29) — not merged/pushed.**
The **"Cyanotype on Vellum" palette is implemented** (azure accent now **bright azure, decoupled** from
a deeper `--action-primary` button fill so white labels keep AA). **Phase 2 wired components onto the
action hierarchy:** Card→`shadow-card`, Modal→`shadow-modal`, Chip tones→themed `state-*`; app-action
filled buttons→`bg-action` (azure); money/premium CTAs→`bg-highlight-fill` (terracotta) — the
intentional dual-accent (azure = do work, terracotta = costs money). Reads by FORM (fill/outline/text).
tsc/build/65 tests green. **Phase 3 DONE:** state-tone literals across 22 files → themed `state-*`
(excluding DataPill data-encoding + MapView dark map canvas); `[data-theme="dark"]` re-applies dark
vars so over-image sections (IntelligenceStack, StorySection) mode-lock as dark islands (fixed the
unreadable "One question. Twenty-five sources." section in light mode); `bg-[#0d0d0d]` placeholders →
`bg-dark-bg`. **Deferred:** readable `text-accent` links → `text-link` (targeted follow-up; bright
azure is AA-large as text); charts keep dark-tuned hex (Polish-path); `TimeSeriesChart` stroke +
Mapbox thumbnail `dark-v11`/`c96442` pin (mode-locked map). Builds on the shipped design system
(`guides/design-system.md`).

**Phase 1 shipped (token foundation, zero dark-change):** `tailwind.config.js` color tokens →
`rgb(var(--x) / <alpha-value>)` (class names unchanged) + new `accent-text` / `state-*` / `shadow-card`
/ `shadow-modal` tokens + tokenized `flash`/`text-glow` keyframes; `src/index.css` `:root` (dark) +
`[data-theme=light]` channel-triplet var blocks + var-backed html/body; `index.html` pre-paint FOUC
script + `body bg-dark-bg`; `lib/useTheme.ts` + `contexts/ThemeContext.tsx` (wired in `main.tsx`);
`components/ThemeToggle.tsx` (3-state) in PageHeader + workspace header; `theme.*` i18n keys (en+es).
Verified: tsc clean, 65 vitest pass (incl. i18n parity), build OK, compiled CSS confirms dark vars
resolve identical (`--surface:23 23 23` = `#171717`) and `[data-theme=light]` overrides present.

**Phase 3 carry-over (logged during Phase 1):** stray `bg-[#0d0d0d]` loading/route-guard
placeholders (`App.tsx:715`, `ProtectedRoute.tsx:14,23`) → swap to `bg-dark-bg` in the shell pass;
splash header (over-image, mode-locked) needs an over-image `ThemeToggle` variant; `TimeSeriesChart`
`stroke="#0d0d0d"` (admin chart, mode-locked-ish).

## Goal
Add a light theme alongside the existing dark-only UI, toggleable, with system-preference
default and persistence — without changing the dark appearance and without a chrome rainbow.

## Locked decisions (2026-06-29)
1. **Scope = Polish path.** Theme all chrome/UI. Maps (`dark-v11` basemap) and data-viz charts
   stay a deliberate **dark "data canvas"** inside a light app — no `mapColors` / chart
   recalibration. (Revisit as a fast-follow "full feature path" later if desired.)
2. **Token naming = keep `dark-*` / `text-text-*` class names**, back them with flipping CSS
   variables. ~0 edits across the ~1,400 utility usages. The name `dark-surface` becomes a
   slight misnomer in light mode — accepted (internal token name only). Optional cosmetic
   rename to role names is a separate later PR.
3. **Default = `system`** (follow OS `prefers-color-scheme`, resolve to dark when unknown —
   preserves today's look for dark-OS users). Live-updates on OS change.
4. ~~Light palette = warm off-white~~ **SUPERSEDED by decision 6.**
5. **Toggle = 3-state** (light / dark / system).
6. **Palette = "Cyanotype on Vellum" (HYBRID — CONFIRMED 2026-06-29).** Blueprint-blue accent
   (Direction A) on **warm vellum neutrals** (Direction B) — "blue ink on warm paper", true to
   real blueprints, keeps the approachable warmth. Terracotta demoted to a warm premium highlight.
   §6 override approved: blue is the action/link hue. **Condition: action tiers read by FORM
   (fill / outline / text), not by users distinguishing shades of blue** — a blue button never
   looks like a stray link.

---

## Revised color system — "Cyanotype on Vellum" (2026-06-29, CONFIRMED · token layer implemented)

Supersedes the Phase-1 §2 neutral/accent values. The Phase-1 *mechanism* (CSS-var-backed tokens,
`<alpha-value>` triplets, pre-paint script, ThemeProvider) is unchanged — this is a values + new-roles
revision, not a re-architecture. Reframe: color is **information, not decoration** — a field-native
palette, warm-tinted neutrals with depth, and blue accent reserved for a legible **action hierarchy**.

**Hybrid = Direction-A accent (blueprint blue) on Direction-B neutrals (warm vellum).** AA verified on
every load-bearing pairing in both themes (table below). The cool-on-warm question was checked
explicitly: it is **not a clash** — blue ink on warm paper is what blueprints are. Two minor,
non-blocking consequences: (1) the `accent-muted` **selected-chip fill skews cool** against warm
chrome (`#1f2534` dark / `#e4e8f5` light) — reads as intentional "selected", not muddy; retintable to
terracotta later if desired. (2) the terracotta **highlight pops by fill+form, not hue** on warm
neutrals (the premium CTA is a filled badge) — fine, just weaker as pure-text highlight.

**Action hierarchy reads by FORM first** (the confirmed condition): Primary = filled block · Secondary
= outline · Tertiary = bare text · Inert = neutral. Same blue hue across tiers, but never the same
shape, so a button can't be mistaken for a link. Primary also carries heavier weight + the light-mode
shadow as redundant (non-color) emphasis.

### Industry rationale
For zoning attorneys + developers, the native visual language is **cyanotype blueprint blue** (the
clearest signal of architecture/drafting/planning), **surveyor/construction-safety warm** (terracotta/
amber — Chicago brick, flagging, signage), and **drafting neutrals** (graphite-on-table, vellum). The
zoning-map state convention (emerald/amber/rose = go/caution/stop) already matches our state tones.
Key insight resolving the broken accent: **oranges hit AA only when pushed dark and muddy; blue clears
AA at vivid values.** So blue leads (action/brand), and terracotta moves to the role it's good at — a
warm *highlight* (premium/$25 report, brand mark). This **overrides design-system §6's "links never
blue"** rule: blue is now the brand accent, so blue links are on-brand, not generic.

### Token table (warm vellum neutrals · blueprint-blue accent · contrast vs the paired surface)
Neutral ramp carries a **warm amber undertone (~40°)** — vellum/manila, not flat gray. Hue enters at
every neutral: bg/surface/elevated/hover/borders all warm-shifted. (Values implemented in `index.css`.)

| Token (CSS var) | Class | Dark | Light | Contrast (dark / light) |
|---|---|---|---|---|
| `--bg` | `dark-bg` | `#14110e` | `#f7f3ec` | page (warm near-black / vellum) |
| `--surface` | `dark-surface` | `#1c1813` | `#fffdf9` | card |
| `--elevated` | `dark-elevated` | `#241f18` | `#f0e9dd` | nested/input (manila) |
| `--hover` | `dark-hover` | `#2d271e` | `#e8dfd0` | interactive fill |
| `--border-subtle` | `dark-border-subtle` | `#221c15` | `#efe7d9` | divider (decorative hairline) |
| `--border` | `dark-border` | `#332c22` | `#ddd2c0` | card edge (~1.4:1, decorative) |
| `--border-strong` | `dark-border-strong` | `#443a2c` | `#c4b8a2` | inert emphasis edge |
| `--text-primary` | `text-text-primary` | `#efebe3` | `#211c15` | **14.9 / 16.7** ✓ |
| `--text-secondary` | `text-text-secondary` | `#aaa394` | `#5c5346` | **7.0 / 7.4** ✓ |
| `--text-muted` | `text-text-muted` | `#746d5f` | `#837a6b` | 3.4 / 4.2 — AA-large/UI only (as today) |
| `--accent` (brand/active/selected/focus/secondary-outline/primary-fill) | `accent` | `#2f6fed` | `#1d4ed8` | white-on-fill 4.55 / 6.70; outline vs surface 3.9 / 6.6 ✓ |
| `--accent-text` / `--link` | `accent-text`, `link` | `#6ea8fe` | `#1d4ed8` | **on surface 7.3 / 6.6** ✓ |
| `--accent-muted` (selected fill) | `accent-muted` | blue @ .15 | blue @ .12 | cool-tinted (intentional selected) |
| `--highlight` (premium text/icon) | new `highlight` | `#e0a06a` | `#a84d2e` | as text on surface 7.7 / 5.6 ✓ |
| `--highlight-fill` (premium badge) | new `highlight-fill` | `#a84d2e` | `#a84d2e` | white-on-fill **5.58 / 5.58** ✓ |
| `--state-positive` | `state-positive` | emerald-400 `#34d399` | emerald-700 `#047857` | 9.3 / 5.5 ✓ |
| `--state-negative` | `state-negative` | rose-400 `#fb7185` | rose-700 `#be123c` | 6.7 / 4.7 ✓ |
| `--state-warning` | `state-warning` | amber-400 `#fbbf24` | amber-700 `#b45309` | 10.7 / 5.0 ✓ |
| `--text-on-accent` (= `action-primary-fg`) | `text-on-accent` | `#ffffff` | `#ffffff` | white-on-primary **4.55 / 6.70** ✓ |

### Action hierarchy (new semantic tokens)
A legible fill → outline → text → neutral emphasis ramp. New tokens (all theme-flipping):

| Tier | Visual (both themes) | Tokens (dark / light) | Use |
|---|---|---|---|
| **Primary** | Solid **blue fill**, white text, soft shadow in light. ~One per view. | `--action-primary` `#2f6fed`/`#1d4ed8`, `--action-primary-hover` `#4480f5`/`#1a45c0`, `--action-primary-fg` `#fff` | Buy Report, Submit |
| **Secondary** | Transparent, **blue (accent) 1px outline + blue text**. (Neutral border-strong is too faint at ~1.8:1 to read as a control edge — the outline is the accent.) | `--action-secondary-border` = `--accent`, `--action-secondary-fg` = `--link` | Investigate, Cancel |
| **Tertiary / ghost** | **Blue text only**, hover paints a faint `--hover` fill. | `--link` + `--hover` | inline links, "Maybe later" |
| **Inert / interactive** | **Neutral** chrome — `elevated` bg, `text-secondary`, hover `hover`; *no accent*. Selected → `accent`. | existing neutrals + `--accent` on select | filter chips, toggles, tabs |
| **Premium** (special) | Terracotta **highlight** — text/icon `--highlight`, or `--highlight-fill` badge w/ white text. The only warm in the system; reserved for the paid report. | `--highlight`, `--highlight-fill`, `--highlight-fg` `#fff` | $25 report CTA/badge |

`--focus` = `--accent`, rendered as a ring at partial alpha (UI-contrast 4.1 / 6.2 vs bg ✓).

### What changes vs. the current (Phase-1) tokens
- **Neutrals retinted warm** — all `bg/surface/elevated/hover/border*` gain a ~40° amber/vellum
  undertone (replaces flat dark / the cool Direction-A option). ~14 var values; **class names unchanged.**
- **Accent redefined** — `--accent` + `--accent-text` move from terracotta `#c96442`/`#a84d2e` to
  **blueprint blue**. Flat terracotta retired as the lead.
- **New tokens** — `action-primary{,-hover,-fg}`, `action-secondary-{border,fg}` (alias accent/link),
  `link`, `focus`, `highlight`, `highlight-fill`, `highlight-fg`.
- **§6 rule override** — links are now blue (on-brand), not `text-accent` terracotta.
- **State tones unchanged** (the §1-corrected emerald/rose/amber -400 dark / -700 light).
- **Mechanism unchanged** — still var-backed triplets; Phase-1 plumbing untouched.

### Open follow-ups (decide at implementation)
- Whether to slightly **cool-tint the modal/card shadows** in light (currently neutral black) to
  match the cool neutrals — minor.
- `accent-muted` selected-chip blue tint intensity (.12–.15) — confirm against real chips in Phase 3.
- Mapbox basemap stays `dark-v11` (Polish path) — a cool-neutral light app over a dark map is an
  intentional "data canvas" seam; revisit only if the full-feature map path is taken.

---

## 1. Audit (current state)

Theming infrastructure: **none** — no `data-theme`, `prefers-color-scheme`, `darkMode`, or
`colorScheme` anywhere. Hardcoded dark-only. Colors live in four layers:

| Layer | What | Scale |
|---|---|---|
| `tailwind.config.js` | Token set `dark.{bg,surface,elevated,hover,border-subtle,border,border-strong}`, `accent.{DEFAULT,hover,muted}`, `text.{primary,secondary,muted,on-accent}` + color-bearing keyframes | source of truth |
| `index.css` | `html,body,#root { background:#0d0d0d; color:#eeeeee }` hardcoded | 1 file |
| Tailwind utility classes | `bg-dark-surface`×88, `bg-dark-elevated`×80, `bg-dark-bg`×35, `border-dark-border`×170, `text-text-muted`×378, `text-text-primary`×198, `text-text-secondary`×177, … | ~1,400 uses across 66–77 of 147 files |
| Hardcoded hex / inline styles | charts (Pie/Bar/admin/NeighborhoodCard), Tooltip, ExportReport (PDF), Scorecard thumbnail URL, `mapColors.ts` | 14 files |

**Core structural issue:** tokens are named by *appearance* (`dark-surface`), not *role*. Decision 2
resolves this by backing the existing names with CSS vars rather than renaming.

**Surfaces needing theming:** app shell (`index.css`, `App.tsx`, 3 headers) · primitives
(`Card`/`Chip`/`Modal`) · ~30 sidebar data cards · Scorecard + page-local cards · Discovery
workbench · chat (bubbles/composer/citations) · 4 modals · landing/splash (hero = mode-locked) ·
admin/about/pricing · floating layers (Tooltip/InfoTooltip/drawer). **Mode-locked (do NOT flip):**
hero photography, maps, PDF report, `mapColors` data encoding.

---

## 2. Semantic token architecture

Store each color as a **space-separated RGB channel triplet** in a CSS var so Tailwind's
`<alpha-value>` opacity utilities (`bg-dark-surface/80`) keep working:

```
tailwind.config:  surface: 'rgb(var(--surface) / <alpha-value>)'
:root          :  --surface: 23 23 23;      /* dark default */
[data-theme=light]: --surface: 255 255 255;
```

Class names stay (`bg-dark-surface`); only the *backing* changes. Dark resolves to identical values.

| Role (CSS var) | Class today | Dark | Light (warm) | Notes |
|---|---|---|---|---|
| `--bg` | `dark-bg` | `#0d0d0d` | `#fafaf9` | warm off-white |
| `--surface` | `dark-surface` | `#171717` | `#ffffff` | |
| `--elevated` | `dark-elevated` | `#1f1f1f` | `#f4f3f0` | |
| `--hover` | `dark-hover` | `#242424` | `#ecebe7` | |
| `--border-subtle` | `dark-border-subtle` | `#1f1f1f` | `#eceae6` | direction inverts |
| `--border` | `dark-border` | `#2a2a2a` | `#e0ddd7` | |
| `--border-strong` | `dark-border-strong` | `#383838` | `#c9c4bb` | |
| `--text-primary` | `text-primary` | `#eeeeee` | `#1b1a18` | |
| `--text-secondary` | `text-secondary` | `#a3a098` | `#57544d` | |
| `--text-muted` | `text-muted` | `#6b6962` | `#84817a` | UI/large only (see §4) |
| `--text-on-accent` | `text-on-accent` | `#ffffff` | `#ffffff` | unchanged |
| `--accent` (fills) | `accent` | `#c96442` | `#c96442` | white-on-accent passes both |
| `--accent-text` **(new)** | new `accent-text` | `#c96442` | `#a84d2e` | **links/accent text** — must darken on light |
| `--accent-hover` | `accent-hover` | `#d97a5a` | `#b1522f` | |
| `--accent-muted` | `accent-muted` | terracotta @ .15 | terracotta @ .12 | express as `rgb(var(--accent)/0.12)` |
| `--state-positive` **(new)** | (was emerald-400) | emerald-400 `#34d399` | **emerald-700 `#047857`** | -600 fails AA on light |
| `--state-negative` **(new)** | (was rose-400) | rose-400 `#fb7185` | **rose-700** | |
| `--state-warning` **(new)** | (was amber-400) | amber-400 `#fbbf24` | **amber-700 `#b45309`** | |
| `--shadow-card` / `--shadow-modal` **(new)** | — | none / minimal | real soft shadow | see §4 elevation |

Two semantic splits the migration forces out: **`accent-text`** (accent-as-text must darken on
light) and **themed `state-*` tones** (the dark `text-emerald-400` etc. fail contrast on light).

### Contrast (computed, WCAG 2.1, normal-text 4.5:1 target)
Passing both modes: `text-primary` (13–17:1), `text-secondary` (5.9–7.6:1), `accent-text` links
(4.6–5.6:1), dark state tones (6.7–10.7:1).

Flagged:
- `text-muted` 3.0–3.9:1 (AA-large-only, **both modes**) and **2.83:1 on dark `hover` (FAIL)** —
  *pre-existing*, `muted` is a de-emphasized UI/large-label token, never body. Keep; audit the
  few muted-on-`hover` sites → bump to `secondary`.
- `on-accent` white on accent fill 3.90:1 (AA-large-only, both modes) — *pre-existing*; accent
  fills carry bold/large button labels only. Rule: no small white text on accent.
- **Light state tones at -600 FAIL** (positive 3.77, warning 2.87–3.19) → **fixed by -700**
  (emerald-700 4.94–5.48 ✓, amber-700 4.53–5.02 ✓, rose-700 for elevated). The *only* new AA
  failures light introduces, all closed by -600→-700.

---

## 3. Theming mechanism
- **Propagation:** CSS custom properties — `:root` (dark, the default so empty-prefs users are
  unchanged) + a `[data-theme="light"]` override block in `index.css`. Tailwind tokens reference
  the vars; because class names stay, the ~1,400 utility sites re-resolve for free.
- **Pre-paint FOUC guard:** inline `<script>` in `index.html` (before the bundle) reads
  `localStorage['urbanlayer-theme']` (+ `matchMedia` for `system`) and sets `data-theme` on
  `<html>` before first paint.
- **React layer:** `ThemeProvider` context + `useTheme()` (mirrors `AuthContext` /
  `SelectedParcelContext`), exposing `theme: 'light'|'dark'|'system'` + `resolvedTheme`; writes
  `data-theme`, persists to `localStorage['urbanlayer-theme']` (same convention as
  `urbanlayer-language`).
- **System:** `matchMedia('(prefers-color-scheme: dark)')` listener updates live.
- **Toggle UI:** 3-state control in `PageHeader`, workspace header, splash header (likely folded
  into `UserMenu` + a standalone icon).

---

## 4. Coherence rules
- **Contrast:** AA — body/`primary`/`secondary` ≥4.5:1; `muted`/large/UI/borders ≥3:1. All §2
  values chosen to clear this; automated check gates Phase 4.
- **Elevation inverts.** Dark encodes elevation by getting *lighter* (surface<elevated<hover),
  near-shadowless. Light can't go lighter than white → elevation shifts onto **shadows**:
  `--shadow-card`/`--shadow-modal` are ~none in dark, real soft shadows in light. Modal's
  `shadow-2xl` already leans this way → make token-driven.
- **Accent:** `#c96442` stays for **fills** (buttons, selected chips, pin) both modes;
  **accent-as-text/links** uses `accent-text` (darker on light). Prevents washed-out links.
- **Borders:** direction inverts (lighter-than-bg in dark, darker-than-bg in light) — handled by
  token values, no per-component logic.
- **State tones:** -400 (dark) → -700 (light); translucent `/15` fills stay, paired with the
  darker text token.
- **Non-auto-inverting / mode-locked:** hero photography is its own dark surface (white-over-image
  exemption already isolates it; the chrome flips around it — intentional seam). Map basemap +
  `mapColors` dots stay dark (Decision 1). Charts stay dark-tuned (Polish path). PDF
  (`ExportReport`) stays light in both app themes — confirm isolated from `data-theme`.

---

## 5. Pre-Phase-1 literal checklist (the "zero dark-change" blast radius)
Every color literal NOT expressed as a flipping token — each must be converted (to preserve dark)
or consciously left mode-locked:

**`tailwind.config.js`:**
- `accent.muted: rgba(201,100,66,.15)` — string rgba, no `<alpha-value>`. Convert →
  `rgb(var(--accent)/0.15)` (dark-identical).
- `keyframes.flash` — `rgba(201,100,66,.7/.0)` ×3. Tokenize → `var(--accent)`.
- `keyframes.text-glow` — `#eeeeee`↔`#6b6962` (= `text-primary`↔`text-muted`). **Mode-coupled** —
  tokenize or it's light-text-on-light in light mode.
- The 13 `dark.*`/`accent.*`/`text.*` hex values → convert to channel-triplet vars (dark identical).

**`index.css`:** `html,body,#root` `background:#0d0d0d; color:#eeeeee` → `var(--bg)` /
`var(--text-primary)`. This is what actually flips the page.

**Tailwind built-in palette refs (static, won't flip — 25 files, ~80 occurrences):**
`text-emerald-400`×20, `text-rose-400`×21, `text-amber-400`×17 + `bg-*-500/15`, `border-*-500/20`
families. These reference Tailwind's static palette → var conversion ignores them → dark-tuned hues
leak into light (the §2 failures). **Replace with themed `state-*` tokens incl. translucent-fill
variants.** Largest hand-edit; silent light breakage if skipped. Also normalize strays
(`text-sky-400`, `text-gray-800`, `bg-gray-100`, `text-amber-300`).

**Mode-locked (intentionally static):** `ScorecardPage.tsx:55` thumbnail URL (`dark-v11` +
`pin-s+c96442`) · `useMapboxOverlay.ts:45` deck.gl `dark-v11` · `ExportReport.tsx` PDF hex
(must stay light — verify isolation) · `mapColors.ts` ~40 RGBA arrays.

---

## 6. Edge cases & risks
- Naming misnomer (`dark-*` backed by light values) — document at the token definition.
- FOUC if pre-paint script missing/late.
- Opacity utilities (`/80`, `/10`, `/15`) break unless vars are **channel triplets**.
- Over-image surfaces must be explicitly excluded — seed the new **"mode-locked"** category from
  the design system's existing over-image exemption list.
- `text-muted` on `hover` (2.83:1) pre-existing fail — sweep those sites.
- Selected/`accent-muted` chips going pale on white; focus rings.
- `Modal` overlay `bg-black/60` — consider a lighter scrim on light.
- NeighborhoodCard CTA transit-line brand colors (keep) + walk-score ramp (light-contrast tweak).
- i18n/Sentry/analytics — unaffected.

---

## 7. Phased migration plan
**Phase 0 — Decisions.** Done (above).

**Phase 1 — Token foundation (keystone, zero dark-change).** Convert `tailwind.config.js` color
tokens to `rgb(var(--x)/<alpha-value>)`; define `:root` (dark) + `[data-theme=light]` triplets in
`index.css`; replace html/body hardcodes; tokenize color-bearing keyframes; complete the §5
checklist; add the pre-paint script to `index.html`; build `ThemeProvider`/`useTheme` + 3-state
toggle; add new tokens (`accent-text`, `state-*`, shadow). Dark visual change: **zero**. The
~1,400 utility sites flip for free.

**Phase 2 — Primitive refactor.** `Card`/`Chip`/`Modal`: verify token-only; wire Chip state tones
to themed `state-*`; give Card/Modal the shadow tokens; switch links/accent-text to `accent-text`.

**Phase 3 — Surface rollout (Polish path).** By blast radius: (1) shell + 3 headers → (2) sidebar
cards → (3) Scorecard + page-local cards → (4) Discovery → (5) chat + citations → (6) modals →
(7) landing (apply mode-lock to hero) → (8) admin/about/pricing → confirm PDF isolation. Replace
the §5 built-in palette refs with `state-*` as each surface is touched. Maps/charts: leave dark.

**Phase 4 — Contrast audit + visual QA.** Automated AA check on every role×surface pairing; eyeball
both modes per surface; verify no FOUC; verify PDF stays light. Lands on a branch — **push to
`main` = deploy, so get owner approval + prod visual pass before merge** (same gate the design
system used).

### Sizing (Polish path)
~30–35 hand-edited files (3 primitives + 25 state-tone files + config + `index.css` + 3 headers +
landing mode-lock + PDF check); ~40+ token-backed files flip for free. Mostly mechanical. Full
feature path (maps/charts flip) would add ~12 files but ~1.7–2× effort in map/chart color
recalibration — deferred.
