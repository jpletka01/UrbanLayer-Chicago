# DotMatrix — LED dot-grid halftone system (hero skyline + reusable renderer)

**Status: built 2026-07-02 on `feat/bento-pro`** (commits `7a9b8ea` → `178d292`), the hero
variant Jack picked after rejecting pure-texture procedural backdrops. **`skyline` is the
HeroBackdrop DEFAULT** (flipped 2026-07-02 at Jack's request); the old variants (`plat`,
`bloom`, `contour`, `geo`, `curtain`) remain reachable via `?bg=` for comparison. Read this
before touching the hero backdrop, or when reusing DotMatrix on any other surface — Jack
expects this component to travel.

## What it is

A two-layer system that turns **any image** into an LED-billboard dot halftone, drawn on a
uniform grid where dot size + alpha encode sampled luminance:

- `frontend/src/components/landing/dotGrid.ts` — **pure** sampling/layout logic (no DOM):
  `computeDots`, `coverCrop`, `luminanceAt`, `pickAccentDot`, `DOT_DEFAULTS`. Unit-tested
  (`dotGrid.test.ts`, 17 tests) — all tuning behaviors are pinned here.
- `frontend/src/components/landing/DotMatrix.tsx` — canvas renderer. Loads `src`, downsamples
  to **one source pixel per grid cell** via `drawImage` (area-averaging melts source detail
  into local luminance), draws dots in the element's resolved `currentColor` (theme-aware),
  DPR-capped at 2, redraws via ResizeObserver.
- Source asset: `frontend/src/assets/skyline-night.jpg` (512×333, ~90 KB) — cropped/downscaled
  with `sips` from Jack's AI-generated reference (CRT frame + caption trimmed).

Hero wiring: `HeroBackdrop.tsx` → `SkylineVariant` (`SKYLINE_PARAMS` + `SKYLINE_MASK`).

## Why this shape (decision record)

1. **Figure beats texture.** First attempt was a procedural curtain-wall facade
   (`facade.ts`/`CurtainWall.tsx`, still wired as `?bg=curtain`): architecturally disciplined
   line-work + clustered lit windows. Jack's verdict: *"a bunch of random squares."* Texture
   with no macro figure doesn't read. The skyline works because the dots encode a
   *recognizable picture* — that's the load-bearing idea, keep it when reusing.
2. **Masks must not amputate the figure.** The line-work variants void the content zone
   (translucent surfaces over line-work = noise). Applying that mask to the skyline cut the
   Hancock out of the scene. Figures instead get: an **alpha ceiling** (`maxAlpha` keeps
   merged-bright clusters below text contrast) + a mask that dims **only the left text
   column** (`SKYLINE_MASK`); the preview card occludes on its own.
3. **Measure, don't guess.** Every tuning round that worked started with an in-browser pixel
   probe (see "Probe workflow"). The two structural features (silhouette, spires) were both
   invisible to threshold-tuning and only fell out of measured data.

## Silhouette mode (the Chicago-recognition machinery)

Night photos have **no luminance separation between sky and dark tower bodies** — measured
medians 0.035–0.051 (sky) vs 0.043 (Hancock body). No threshold can find the skyline. So the
figure is built structurally per column (`silhouette` param):

- **Roofline detection**: topmost cell with lum > `threshold` (0.4 — calibrated: sampled sky
  maxes at ~0.35, roof/crown lights hit 0.4–1.0).
- **Spire rule** (the Hancock's twin antenna masts): thin masts downsample to 0.15–0.35,
  under `threshold` — so a roofline also starts at a cell > `spireTop` (0.18) heading a
  contiguous vertical run of `spireRun` (3) cells > `spireCut` (0.12). Discriminator:
  antennas have **vertical continuity**; the source's own sky dots alias into *isolated*
  bright cells on periodic rows and are rejected.
- **Above roofline** = sky → perfectly uniform lattice dot (`floorRadius` at `skyAlpha`) —
  quantization kills sampling noise so the field reads as a regular LED grid.
- **Below roofline** = building → cells > `lightCut` (0.08) render as lit windows with a
  **higher alpha floor** (0.5 + 0.5·shaped, vs sky 0.38) so figure separates from field even
  at equal dot size; dark body cells render **nothing** (true black voids). The tower reads
  as a negative silhouette cut out of the lattice — same mechanism as Jack's reference image.

Hero calibration (`SKYLINE_PARAMS`): `gamma 0.95` (γ>1.5 crushed midtone buildings to the
sub-pixel floor — the "invisible skyline" failure), `maxAlpha 0.85`, `floorRadius 0.2`,
`skyAlpha 0.38`, `silhouette {threshold 0.4, lightCut 0.08}`.

## Geometry / layout truths (hard-won)

- **`coverCrop` anchors the vertical crop to the image BOTTOM** — skylines sit on their base;
  excess always trims from the sky. (A 0.75 "bias" left a constant dark strip; and a
  `shiftDown=6` band-trim was actively cutting the brightest street band — the probe showed
  the asset is bright to its literal last row.)
- **Row count uses `ceil`**, not `round` — a rounded-down grid leaves a sub-cell unpainted
  strip at the bottom.
- **The "gap at the bottom of the hero" was never the image.** Hero pulls itself up under the
  floating nav; the pull-up must equal the nav's **flow height** (`h-14` = 56px → `-mt-14`).
  `sticky top-3` moves the *stuck* position, not the flow slot. The old `-mt-[4.75rem]` left
  the hero 20px short of the fold at every window height. Probe-verified 0 unpainted px at
  700/900/1100 viewport heights.
- `DotMatrix` still has a `shiftDown` prop (translate image down N cells; vacated top rows
  render as synthesized sky lattice) — unused by the hero, available for band presets.

## Reuse recipes (why this doc exists)

`<DotMatrix src={...} cols={150} params={...} style={mask} />` is surface-agnostic. Planned/
plausible uses: **StorySection photos** as on-brand dot art, a **pre-footer horizon band**
(shorter container, `cols` ~180, no mask), **empty states / 404**, light-mode surfaces (dots
draw in `currentColor` — on white they invert to a print-halftone look; the hero never
exercises this because it's a dark-locked island). For non-skyline photos skip `silhouette`
and set `skyLevel` (~0.2) instead — it quantizes flat regions to the uniform lattice without
roofline logic. The one orange `accent` dot (brightest window in a zone — "found parcel")
exists in the API but is **off** in the hero: a lone unexplained orange dot read as noise.

## Probe workflow (the debugging tool — reuse this)

All real diagnosis came from throwaway Playwright scripts in `frontend/` that run **in the
page context** and measure, rather than eyeballing screenshots:

1. `._probe.mjs` pattern: load the asset in-browser, downsample on an offscreen canvas
   exactly as the component does, then print luminance **histograms**, **region patches**
   (min/p25/med/p75/max), per-row **max/mean** sweeps, or ASCII **luminance maps**
   (`# + . ` glyphs) of a suspect region — the antenna calibration came straight off one.
2. Geometry probes: compare `canvas.getBoundingClientRect()` vs hero rect vs **lowest painted
   buffer row** (scan `getImageData` alpha from the bottom) across several viewport sizes —
   this is what separated "image content" from "layout constant" for the fold gap.
3. Visual pass stays Playwright screenshots per `bento-pro-redesign.md` (dark+light, desktop+
   390px, `waitForTimeout ~2200` for the canvas draw), incl. `clip:` close-ups of a region.
4. Clean up: `rm ._probe.mjs ._shot.mjs ._*.png` before committing.

## Gotchas

- **Case-insensitive filename collision (macOS/APFS):** `dotmatrix.ts` next to
  `DotMatrix.tsx` hijacks the `./DotMatrix` import (Vite tries `.ts` first and the FS serves
  `dotmatrix.ts`) → black page, "does not provide an export named". Hence the pure module is
  `dotGrid.ts`. Also: **restart Vite after renames** — its resolution cache survives HMR.
- The asset regeneration path: original reference in `~/Downloads` (Gemini-generated) →
  `sips -c <h> <w>` center-crop (trim CRT frame; caption sits in the bottom band — verify by
  Reading the output jpg) → `sips --resampleWidth 512 -s format jpeg -s formatOptions 70`.
- Stat legibility over the full-strength field: local radial **halo divs** behind each hero
  stat (App.tsx), not orange text — orange = action only (§ color discipline).
- `params` prop must be a module-level const (new object identity per render would re-run the
  draw effect).

## Light mode (2026-07-06) — SEPARATE asset, not an inversion

The hero used to be a **dark-locked island** (`data-theme="dark"` on the wrapper), so a
light-mode visitor still got the white-on-black night skyline. It's now **theme-aware**:
`HeroBackdrop`'s `SkylineVariant` reads `useThemeContext().resolvedTheme` and swaps both the
asset and the params.

**Why two assets, not one inverted.** The night photo is a *dark-mode* artifact — its
recognizability comes from bright window-glow on a black field. Every attempt to reuse it for
light failed (recorded so we don't retry):
1. **Naive color invert** (dark dots on paper): the building *voids* become paper-white — the
   lightest value — against a near-white sky, so the towers vanish. The negative-silhouette
   trick only reads when the void is the *darkest* value.
2. **Positive silhouette** (ink the tower mass; briefly lived in `dotGrid` as a `positive`
   param, since removed): fixed contrast but flattened the window/tonal detail, so it read as
   "random vertical bars," not Chicago. Recognizability lived in the detail it destroyed.
3. **Hand-authored vector skyline / vector Bean**: recognizable-ish but read as a crude
   cartoon — same lesson as the curtain-wall predecessor ("figure beats texture," and a
   *drawing* isn't enough).

**What shipped:** a purpose-built **daytime photo** asset, `frontend/src/assets/cloudgate-day.jpg`
— a grayscale Unsplash **Cloud Gate** photo, pre-processed to a **NEGATIVE** (PIL:
`ImageOps.autocontrast` → `ImageOps.invert`) so it feeds the *existing* halftone ramp as an ink
print: originally-dark steel → bright → big ink dots; originally-bright sky → dark → faint
lattice. Under the light theme wrapper the dots resolve to `#1a1a1a` ink on warm paper. Light
params (`SKYLINE_PARAMS_LIGHT` in `HeroBackdrop.tsx`) are a **plain halftone** (no silhouette
mode — the photo has real sky/subject luminance separation): `gamma 1.5, maxRadius 0.5, cut 0,
skyLevel 0.1, skyAlpha 0.2`. The night photo stays the dark figure.

**Compose the source for the layout, cover-crop can't.** `coverCrop` centers horizontally, so a
subject centered in the source lands under the Scorecard card. Compose the intended framing INTO
the asset (crop/pad), and put denser content at the image *bottom* — `coverCrop` bottom-anchors,
so a light plaza at the base reads as "the image doesn't reach the bottom" (it does; the content
is just faint there). Full-scene edge-to-edge = full-bleed; a small subject on a black-padded
canvas = a small floating image (black pad → faint lattice, reads empty).

**Legibility scrim (light only).** A full-bleed halftone competes with text. `App.tsx` adds a
light-only radial **paper scrim** (`rgb(var(--bg)/…)` fading to transparent) behind the left
text column so grey text isn't sitting on grey dots — the light analog of dark mode's DotMatrix
mask + headline drop-shadows. Left column legible, dots stay full-strength in the periphery.

**Search bar = primary action, must not hide.** On paper a white field (`bg-dark-surface`) with
a hairline border vanishes. `AddressInput` `page` + `hero` variants now: (a) a persistent
**orange submit button** (`bg-accent/15 text-accent`, solid on typing), and (b) a gentle idle
**`animate-search-pulse`** that breathes `box-shadow` from the resting shadow (`--shadow-card`)
to the accent glow (`--glow-accent`) — the *same* shadow the field holds on hover, so hover/focus
settles onto the identical orange. `motion-reduce:animate-none` guard; `hover:animate-none` stops
the pulse. Both `--shadow-card` and `--glow-accent` are 2-layer theme-aware shadows so the
`var()` endpoints interpolate smoothly.

- **⚠️ Tailwind config gotcha (cost a debugging round):** adding `keyframes`/`animation` to
  `tailwind.config.js` requires a **dev-server restart** — Vite HMR does NOT re-scan the config,
  so the `animate-*` class applies with *no CSS behind it* (`animationName: none`, no
  `@keyframes`), which looks exactly like "the animation is broken." Verify via
  `getComputedStyle(el).animationName` + checking the built CSS; the production `npm run build`
  picks it up correctly (the issue is dev-only).
