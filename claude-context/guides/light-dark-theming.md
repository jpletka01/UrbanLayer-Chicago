# Light/Dark Theming — Plan

**Status: Phase 1 COMPLETE on branch `feat/light-dark-theming` (2026-06-29) — not merged/pushed.**
Phases 2–4 pending. Design decisions locked (see "Decisions" below). Builds directly on the
shipped design system (`guides/design-system.md`).

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
4. **Light palette = warm off-white** (harmonizes with the terracotta accent).
5. **Toggle = 3-state** (light / dark / system).

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
