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
