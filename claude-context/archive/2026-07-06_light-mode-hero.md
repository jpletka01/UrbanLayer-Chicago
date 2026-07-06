# Light-mode hero — Cloud Gate halftone + legibility pass (2026-07-06)

**Status: SHIPPED to `main` (deploys on push).** Homepage hero (`/`) got a real light-mode
treatment; dark mode is untouched. Pointer doc — details + reusable lessons below, mechanics in
`guides/dot-matrix.md` (the "Light mode (2026-07-06)" section).

## What changed
The hero was a **dark-locked island** (`data-theme="dark"`), so light-mode visitors saw the
white-on-black night skyline regardless of theme. Now theme-aware end to end:
- **Backdrop** (`HeroBackdrop.tsx`): light mode uses a NEW purpose-built daytime asset
  `frontend/src/assets/cloudgate-day.jpg` — a grayscale Unsplash **Cloud Gate** photo processed
  to a NEGATIVE (`ImageOps.autocontrast`→`invert`) so it runs the existing halftone ramp as an
  ink print on warm paper. Dark mode keeps `skyline-night.jpg`. Two theme-switched assets +
  `SKYLINE_PARAMS_LIGHT` (plain halftone, no silhouette mode).
- **Hero content** (`App.tsx`, `HeroEntrance.tsx`, `HeroScorecardPreview.tsx`,
  `PromptSuggestionChip.tsx`): headline/badge/subline/chips/stats made theme-aware via tokens;
  the Scorecard preview stays a dark "product screenshot" floating on paper (deliberate — a
  common premium pattern, and the page's focal anchor).
- **Paper scrim** (`App.tsx`, light only): radial `--bg` wash behind the left text column so
  grey text isn't sitting on grey dots. The light analog of dark mode's mask + drop-shadows.
- **Search bar** (`AddressInput.tsx`, both `page` + `hero` variants): persistent orange submit
  button + idle **`animate-search-pulse`** (breathes to the accent glow, holds that same orange
  on hover) so the primary action doesn't vanish on paper. New keyframe in `tailwind.config.js`.

## Lessons (the reusable part)
1. **A night photo is a dark-mode artifact; don't invert it for light.** Naive color-invert
   makes building voids paper-white (they vanish); inking the mass flattens the detail that made
   it recognizable ("random bars"). The fix is a SEPARATE daytime asset. Full decision chain in
   `guides/dot-matrix.md`.
2. **`coverCrop` centers horizontally and bottom-anchors** — it can't place a subject for you.
   Compose the framing INTO the asset; put dense content at the bottom or it reads as "not
   reaching the bottom" (it does; the base content is just faint).
3. **Full-bleed vs floating:** black padding around a small subject → faint lattice → reads as a
   small floating image, not a background. Fill the source edge-to-edge for full-bleed.
4. **Full-bleed imagery fights text** — add a paper scrim behind content (light) the way dark
   mode dims its text zone. Balance = recede the background, don't just recolor text.
5. **On a light page a white input with a hairline border disappears** — the primary action
   needs elevation + an accent cue. Shadow-card in light is only 4–6% black (too weak for a
   hero CTA); use a real drop shadow / glow.
6. **⚠️ Tailwind `keyframes`/`animation` config changes need a DEV-SERVER RESTART.** Vite HMR
   doesn't re-scan `tailwind.config.js`, so the `animate-*` class applies with no `@keyframes`
   behind it (`animationName: none`) — looks identical to "animation broken." `npm run build`
   picks it up fine; it's dev-only. Diagnose via `getComputedStyle(el).animationName`.

## Process notes
- Extensive iteration was screenshot-driven (Playwright `._*.mjs` throwaways, light+dark). Also
  used a `getComputedStyle`/box-shadow-sampling probe to prove the pulse interpolates and to
  catch the stale-config bug. Clean up `._*` scratch before committing.
- Dead code from the exploration was removed in the same arc: the abandoned vector `skyline-day.png`
  asset and a `positive` silhouette mode (added then removed from `dotGrid.ts`/tests — net zero).
- `cloudgate-day` shipped as JPEG (125 kB) not PNG (185 kB) — it's downsampled to 150 cols at
  render, so quality is moot.
