# Bento Pro Frontend Redesign — Handoff

**Status:** in progress on branch `feat/bento-pro` (NOT merged, NOT pushed).
**Started:** 2026-06-30 · **Last updated:** 2026-07-01 (evening — Scorecard restructure + Discovery pass 1 done; see `bento-pro-phase3-app-surfaces.md`).
**⚠️ Pushing `feat/bento-pro` → `main` deploys to prod.** Do not push without Jack's OK. Commit freely on the branch.

Full-site visual overhaul from the old "Cyanotype on Vellum" system (azure-on-vellum, Space
Grotesk) to **"Bento Pro"**: dark-first near-black canvas, warm **orange** brand accent, editorial
Inter Tight type, bento card language, and a unified floating nav. Driven by an external "Bento Pro"
design spec + iterative founder feedback (the landing storytelling went through many rounds).

## How to resume

```bash
git checkout feat/bento-pro
cd frontend && npm run dev           # localhost:5173 (frontend only; backend not needed for chrome)
kill $(lsof -ti:5173) 2>/dev/null; cd frontend && npm run dev   # restart
```
- **CI-parity gate (run before ANY push):** `cd frontend && npm run build` (`tsc -b` + vite build). A
  build failure silently skips the prod deploy. `tsc --noEmit` is weaker — don't rely on it.
- Tests: `npx vitest run` (88 incl. i18n parity + Discovery + verdict). Always run
  `src/i18n.parity.test.ts` after locale edits.
- **Visual verification via Playwright** (installed): write a throwaway `._shot.mjs` in `frontend/`,
  `node ._shot.mjs`, Read the PNG. Set theme via `addInitScript(()=>localStorage.setItem('urbanlayer-theme','dark'|'light'))`.
  Wait ~1.5s after load; for scroll-triggered sections wait ~3s. **Gotcha:** the Bash tool's cwd resets
  to repo root between calls — always `cd /Users/jack/projects/chicago/frontend` first (Playwright is in
  frontend/node_modules).

## Locked decisions (from Jack)

1. **Keep light/dark toggle** — reskin both. Dark = Bento Pro; light = clean warm-neutral.
2. **Orange `#F9A474`** is the single brand/CTA accent (replaces azure). **Same orange in BOTH modes**
   (2026-07-01) — light-mode brand/fills use the bright dark-mode peach with a dark label; only small
   orange *link text* stays deeper (`#c2410c`) for legibility on white.
3. **Violet `#c3a3ff`** = the "costs money / paid report" premium signal (moved off terracotta, which
   collided with orange). Dual-accent meaning: **orange = do the work, violet = costs money.**
4. **One floating nav** across the whole app incl. the chat workspace.
5. **Show, don't tell** on the landing — visualize the *problem* (fragmented, slow diligence), not a
   product demo. Cut generic card grids and stock-photo banners.

## Design system (the Bento Pro token layer)

Token layer is CSS-var-backed in `frontend/src/index.css` (`:root`/`[data-theme=dark]` + `[data-theme=light]`)
→ mapped in `tailwind.config.js` as `rgb(var(--x) / <alpha-value>)`. **Components consume semantic
classes** (`bg-dark-surface`, `text-text-primary`, `text-accent`, `bg-action`, `text-highlight`, …) so
recoloring is re-pointing vars, not editing components.

- **Canvas:** dark `#0a0a0a` bg; surfaces step up in tiny increments, borders (`border-dark-border` ~10%
  white, `-strong` ~20%) do the separation. Light = near-white warm neutral.
- **Fonts:** `font-sans` Inter · `font-display` **Inter Tight** (scoped to `.text-display`/`.text-section`
  via index.css) · `font-mono` **JetBrains Mono**.
- **Radius:** `rounded-bento` (28px) + `rounded-bento-sm` (20px) for cards/modals; controls stay `rounded-lg`.
- **Glow/shadow:** `shadow-glow` (accent halo), `shadow-card`/`shadow-modal` (theme-aware).
- **Brand gradient:** `bg-brand-gradient` (orange CTA blend, dark label).
- **Primitives** (`src/components/ui/`): `Card`, `Chip` (pill), `Modal` — Bento anatomy (bento radius,
  hover glow+lift on interactive cards). Use these; don't hand-roll chrome.
- **Ambient:** `body::before` renders two faint orange/violet corner blooms site-wide.

### External-spec adaptation rule (IMPORTANT)
The external "Bento Pro" / component prompts are written in **generic Tailwind** (`bg-white dark:bg-gray-950`,
`text-gray-500`, raw green). This project does **NOT** use Tailwind's `dark:` variant — it flips via
CSS-var tokens. **Always translate generic Tailwind → this project's tokens** (`text-text-muted`,
`state-positive`, `accent`, etc.) so both themes stay correct. Use `motion/react` (already a dep) for
animation rather than adding global CSS keyframes.

## What's DONE (`git log main..HEAD` for the full list)

**Phase 0 — Foundation** (`f076e34`): repointed all tokens to Bento (both themes); Inter Tight +
JetBrains Mono; 28px radius, glow, brand gradient; reworked Card/Chip/Modal.

**Phase 1 — Unified nav** (`f9c4e82`, `fe616de`, `c1661f3`, `51eb448`): `FloatingNav.tsx` — one nav for
every surface (floating rounded pill; over-image variant on the hero; sticky, persists on scroll). 3-zone
layout (brand left / **nav centered** / utilities right). Workspace controls (history, export, share,
new-chat, admin, sign-in) preserved via `contextLeft`/`contextRight`/`signInSlot` slots — handlers stay in
`App.tsx`. `PageHeader.tsx` is now a thin wrapper over FloatingNav (keeps `navItemsFor` + the 4 page
consumers + `PageHeader.nav.test.ts` working).

**Phase 2 — Home/landing** (many commits). Current top-to-bottom flow:
1. **Hero** — split layout: value-statement headline + `AddressInput` (left), `HeroScorecardPreview`
   (right, a compact verdict-first mock Scorecard). Mode-locked **dark island** (`data-theme="dark"`) so it
   stays dramatic in light mode. `HeroBackdrop` = clean abstract bloom + faint grid (a real Chicago map was
   tried and rejected — labels fought the type).
2. **ChaosToVerdict** — the flagship problem-visual: a dense, blurred, overlapping stack of raw municipal
   source docs (Assessor block, zoning table, `§ 17-2-0300` code) → animated orange data-flow → one crisp
   verdict card (green ✓ Buildable, Zoning B3-2). i18n'd (`landing.chaos.*` + `heroPreview.*`); the mock
   document text is intentionally hardcoded (represents raw untranslated records).
3. **ValueProps** — slimmed to a compact inline triad (icon + one-line claim), not cards.
4. **StorySection** (Cloud Gate cityscape) — split photo + text.
5. **PersonaScenarios** — Developer/Architect/Attorney cards.
6. **StorySection** (construction site) — split photo + text.
7. **HowItWorks** — 3 steps; each visual now sits in a fixed-height slot so titles/descriptions align.
8. **Footer** — Bento near-black band + orange bloom.

Landing additions (2026-07-01): **HeroBackdrop** rebuilt — achromatic **plat-map** drawing
(street grid, staggered lots, diagonal avenue, orange found-parcel) in `currentColor` under
`text-text-primary` so it inverts with the theme; periphery-masked (voided over the content
zone — line-work under translucent surfaces read as noise). Variants `?bg=bloom|contour|geo`
remain for comparison; hero is still a dark-locked island (unlock = pending Jack's pick).
**`?bg=curtain` added (2026-07-01, `e2d7df1`)** — procedural curtain-wall facade, the city in
*elevation* (Concept B of the background exploration). Pure seeded
generator `landing/facade.ts` + `CurtainWall.tsx`: abutting towers with per-building modules
(floors misalign at party walls), dialects miesian / chicagoSchool (1:2:1 Chicago-window
mullions, spandrel bands) / braced (one full-width X-brace tower), line-weight hierarchy
(party 0.20 > braces 0.13 > columns 0.12 > floors 0.09 > mullions 0.06), lit windows placed
in clustered runs/stacks (~4% ratio, fill 0.15), one orange found-parcel pane at left
periphery (mask-fade-aware placement). Batched to ~8 SVG path nodes; 35 generator tests
(`facade.test.ts`). **Jack's verdict: reads as "random squares"** — abstract texture with no
macro figure. Lesson: figure beats texture for this hero.
**`?bg=skyline` added (2026-07-01)** — the pivot Jack asked for, from a reference image he
supplied (LED dot-matrix halftone of the night skyline, "unit-grid feed" look): a uniform
dot lattice whose dot size + alpha encode sampled luminance, so the *recognizable skyline
figure* emerges from the dots. `landing/dotmatrix.ts` (pure: computeDots/coverCrop/
pickAccentDot, unit-tested) + `DotMatrix.tsx` (canvas renderer: downsamples a bundled
`assets/skyline-night.jpg` — cropped/downscaled from Jack's reference — one source px per
grid cell, dots in resolved currentColor). The DotMatrix component is the site-wide system:
any photo (e.g. StorySection images) can be run through it for on-brand dot art.
Revision after Jack's review (`b6d6b97`): the lone orange accent dot REMOVED (read as noise
without the found-parcel context) and **silhouette mode** added — measured luminance can't
separate night sky from dark tower bodies (both ~0.04), so the figure is built structurally:
per-column roofline detection, uniform bright lattice above (skyAlpha 0.38), black void below
with only lit windows rendered (alpha floor 0.5) — the Hancock reads as a negative silhouette
with its lit crown band. Mask dims only the left text column.
**AccentRails** — faint orange plat-grid rails (16% alpha) along the below-hero margins.

Also done: orange/violet across app surfaces (inherited via tokens); readability pass (contrast, spacing);
light-mode orange = dark-mode orange (2026-07-01); How-it-works balance fix.

**Cut along the way:** DepthShowcase, IntelligenceStack, ProductShowcase, ProblemPivot, TimeCompression
(a dual-track gantt — looked homemade, leaned on invented numbers, doubled ChaosToVerdict), the
`staticMap.ts` Mapbox helper, and stock-photo banner sections. Orphaned i18n keys (`showcase.*`,
`intelligence.*`, most of `depth.*`) were removed; en/es kept in parity.

## What's LEFT (prioritized)

1. **Placeholder data to confirm:** ChaosToVerdict + HeroScorecardPreview use illustrative values
   (1601 N Milwaukee Ave, $8,420, B3-2, walk/transit scores). Fine as mocks, but confirm they're
   acceptable / swap for real defensible figures.
2. **Personas** — optional light touch: flatten the nested quote boxes (card-in-card). Section otherwise
   earns its place (answers *who it's for*).
3. **Phase 3 — App surfaces** (biggest remaining chunk): **Scorecard + Discovery are now a full
   information-design overhaul, not a reskin — spec/plan/status live in
   `bento-pro-phase3-app-surfaces.md` (the working doc for this phase).** Still simple reskins:
   **Pricing**, **About** (also still name-drops the old fonts in its copy — update), **chat
   workspace** (MessageBubble, ChatInput, sidebar cards).
4. **Phase 4 — Cleanup & docs:** sweep remaining ad-hoc chrome (`grep -rn "white/\|text-\[" src`).
   Docs DONE 2026-07-01: `frontend/CLAUDE.md` tokens/rows rewritten for Bento Pro;
   `design-system.md` + `light-dark-theming.md` marked HISTORICAL (mechanics still valid, values retired).
5. **Redundancy watch:** three "scorecard result" mini-cards now exist (hero preview, ChaosToVerdict
   verdict, How-it-works step 3). Acceptable, but keep an eye on it.
6. **Ship:** when Jack approves — merge/push `feat/bento-pro` to `main` (= deploy). Run `npm run build`
   first; verify live via the served bundle, not just git HEAD.

## Exempt from the recolor (do NOT touch)
Functional data encoding: `lib/mapColors.ts`, `components/DataPill.tsx`, `discovery/upsideColor.ts`, and
Mapbox/deck.gl map layers. `state-*` tokens stay semantic (only hues retuned for the new canvas).

## Gotchas / lessons
- **cwd resets to repo root** between Bash calls → `cd frontend` before npm/node.
- **`npm run build` is the gate**, not `tsc --noEmit`; an unused import passes `--noEmit` but fails the
  build and silently skips deploy.
- **Playwright fullPage + sticky nav** renders the nav at an odd mid-page position (artifact, not a bug).
- **Light-mode orange text tradeoff:** brand/fills are bright `#F9A474`; small orange *link text* is kept
  deeper (`#c2410c`) for AA on white. If Jack wants it identical, it's a one-line change (accepting low contrast).
- **i18n:** landing copy lives in `src/locales/{en,es}/landing.json`; `i18n.parity.test.ts` guards en/es
  key + placeholder parity. New landing sections' framing copy should be i18n'd; mock/data strings can stay
  hardcoded.
```
