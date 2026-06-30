# Design System — UrbanLayer frontend

**Status: COMPLETE on branch `design-system-refactor` (8 commits, HEAD `bf33d70`) — NOT yet
merged/pushed to `main`/prod (2026-06-20).** `tsc` + production build + 51 vitest tests green.
This is the source of truth for type, radius, and shared UI primitives. Read before any
visual/CSS/component-chrome work.

> **⚠️ COLOR is partly SUPERSEDED (2026-06-29) — see `light-dark-theming.md`.** The app is now
> light/dark themeable and the palette was revised to **"Cyanotype on Vellum"** (bright **azure**
> accent on **warm vellum** neutrals; terracotta demoted to a premium-only `highlight`). Tokens are
> CSS-var-backed (class names unchanged). Specifically superseded here: §2's fixed dark neutral hexes
> (now per-theme vars), §6's terracotta accent + "links never blue" rule (links are now azure
> `text-link`), and the static `emerald/rose/amber-400` state colors (now themed `state-*` tokens).
> New: an **action hierarchy** (`action`/`link`/`highlight`) and theme-aware `shadow-card`/`shadow-modal`.
> Type scale, radius, fonts, and the Card/Chip/Modal primitives below are unchanged.

## Why this exists
A UI audit (against the "vibecoded-design-tells" study: the top AI tells are untouched
shadcn/Tailwind defaults, "AI purple," gradients) found the app already had a *deliberate* palette
(warm terracotta accent `#c96442` + a tuned dark ramp) but applied it inconsistently: 4 different
card chrome recipes, 6+ hand-rolled chip variants, ~300 arbitrary `text-[Npx]` sizes, two parallel
neutral systems (token `dark-*` vs raw `white/<opacity>`), a 6-way radius drift, and a rainbow
status-chip row. The fix was discipline, not redesign. Full spec history: this doc is the distilled
decision record; the original per-step specs were authored in-session.

## The decisions (source of truth — `frontend/tailwind.config.js` + `src/index.css`)

### 1. Type scale (10 named steps) — replaces all arbitrary `text-[Npx]`
`display · stat · section · subtitle · lead · title · body · caption · micro · overline`. Each
carries size + line-height + weight (+ tracking) baked into the Tailwind `fontSize` token.
`display/stat/section` use `clamp()` so one token spans mobile→desktop. **Picking a weight = picking
the step** (e.g. body=14/400, title=14/600 — don't override). `overline` pairs with `uppercase`.
Migration map: `text-[8/9/10/11px]`→`micro`; `[12/13px]`/`text-xs`→`caption`; `text-sm`→`body` (or
`title` if a label/heading); `text-base`→`lead`; `text-lg/xl`→`subtitle`; `text-2xl`→`section`;
`text-3xl`→`section`(heading) or `stat`(metric number); `text-4xl/5xl`→`display`.

### 2. Neutral ramp — one system (kills the `white/opacity` fork)
Surfaces `dark.bg #0d0d0d / surface #171717 / elevated #1f1f1f / hover #242424` (hover = NEW,
interactive fill). Borders `dark.border-subtle #1f1f1f / border #2a2a2a / border-strong #383838`
(border-strong = NEW). Text `text.primary #eeeeee / secondary #a3a098 / muted #6b6962 /
on-accent #ffffff` (on-accent = NEW, for text/icons on accent fills). **Retired** `dark.bubble /
bubble-user / drawer / tooltip` (→ accent-muted / surface / border-strong). `white/<n>`→tokens map:
text 90/80→primary, 70/60→secondary, 50/40/30→muted; border 10→border, 5→subtle, 20/30→strong;
`bg-white/x`→`bg-dark-hover`. **Cards/panels are opaque** — no `bg-*/80` + `backdrop-blur` frosting.

### 3. Radius by role (stock Tailwind values, no config change)
card/panel/modal/sheet = `rounded-xl`(12); button/input/control = `rounded-lg`(8); chip/badge/tag =
`rounded-md`(6); inline mono/code = `rounded`(4); avatar/dot/pill-toggle = `rounded-full`. `2xl/3xl`
retired **except** chat bubbles + the chat composer (deliberate "bubble" shape, no spec role) and
Pricing cards (one intentional marketing exception, owner's call).

### 4. Typefaces (`src/index.css` @import + `fontFamily`)
`font-sans` = **Inter** (body/UI). `font-display` = **Space Grotesk** (chosen 2026-06-20 over
Fraunces — modern-utilitarian, less editorial). `font-mono` = **IBM Plex Mono** (PINs/code/data).
**Display face is scoped to the two largest type steps only** — `.text-display` + `.text-section`
get Space Grotesk via an unlayered rule in `index.css`; everything else (incl. card titles
`subtitle`, chat UI) stays Inter. Display weight = **600** (not 700 — §1 table and the typeface
decision were reconciled to 600). Fallbacks: `'Space Grotesk', Inter, system-ui, sans-serif` and
`'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace` (derived; spec only named
Fraunces's).

### 5. Three primitives (`src/components/ui/`)
- **`Card`** — replaces 4 chrome recipes. Props: `surface`(surface|elevated), `padding`
  (none|sm|md|lg), `title`/`icon`/`headerRight`, `divider` (default on for static, off for
  collapsible), `collapsible`/`defaultOpen`, `footer`, `interactive`, `accentEdge`, `onClick`.
  Radius locked `xl`, opaque, no blur, header always the `title` step. `CollapsibleCard` is now a
  thin wrapper over `<Card collapsible>` — so all sidebar data cards inherited unified chrome free.
- **`Chip`** — replaces 6+ hand-rolled chips. Props: `tone`(neutral|accent|positive|negative|
  warning), `selected`, `interactive`, `removable`/`onRemove`/`removeLabel`, `mono`, `size`(sm|md),
  `as`, `title`, `role`/`aria-pressed`/`aria-checked` (ARIA passthroughs added for Discovery's
  radio/toggle filter controls). Radius `md`, text `micro`.
- **`Modal`** — replaces 4 duplicated dialog shells. Overlay `bg-black/60` + blur (legit floating
  layer), centered `rounded-xl` panel on `bg-dark-surface`, ESC + click-outside, optional
  `title`/`description` header + close ×(`showClose`, default = !!title), `size`(sm|md|lg).

### 6. Color discipline (the §6 rule — the "no AI rainbow" guardrail)
Chrome uses **accent + neutral ramp only.** Hue is permitted ONLY for genuine semantic state, via
three reserved tones: `positive`=emerald-400, `negative`=rose-400, `warning`=amber-400. **Banned in
chrome:** blue/indigo/purple/violet/cyan/teal/sky/green/red/yellow as decoration. Categorical labels
(overlays, intents, zone types, domains) are **neutral**, not rainbow-coded. Links are `text-accent`,
never default blue. Off-palette state shades normalized to the canonical three (rose-300→400,
amber/80→amber, green/red/yellow-400→emerald/rose/amber).

## Reasoning frameworks (apply these to future visual work)
- **Rule A — existing color ≠ intended tone.** Tone comes from the §6 rule, not the current class.
  `todEligible`/`SSA #26` were emerald/cyan but are categorical facts → neutral. A score's
  pass/fail/warn IS genuine state → positive/warning/neutral.
- **Over-image exemption.** White / `white/opacity` text is correct and legible over photography and
  is a *distinct surface* from dark-UI chrome — exempt from the neutral-ramp migration. Applies to:
  the splash hero (over `HeroSlideshow`), `StorySection`/`ScrollIndicator`/`HeroEntrance`,
  `PromptSuggestionChip`, `AddressInput` (hero input), `ChatInput` **hero variant**, the splash
  header glass buttons, `LanguageSelector` splash hover. (Same spirit as the data-encoding exemption.)
- **Functional-data-encoding exemption.** Multi-hue that *encodes data* is not chrome decoration and
  stays: `mapColors.ts`, the `DataPill` `[data:X]` citation pills, `discovery/upsideColor.ts`, the
  CTA transit-line brand colors + walk-score quality ramp in `NeighborhoodCard`. Keep these in their
  modules; never let them leak into chrome.
- **Floating-layer blur is allowed (§2).** `backdrop-blur` is fine on genuinely overlapping floating
  layers — modals, drawers, popovers/tooltips, map-overlay controls. It is NOT allowed as decorative
  frosting on standard cards/panels (those are opaque).
- **Bespoke vs. primitive.** Inline affordances with structure the primitive doesn't model stay
  bespoke even if chip-shaped: `CitationPill` (baseline-aligned `[N]` superscript + tooltip) and
  `CrossRefPill` (`§` ref + hover-fetch tooltip) are accent-compliant, NOT migrated to `Chip`, NOT
  the DataPill exemption. The inline-citation family is exactly 3: CitationPill, CrossRefPill,
  DataPill(exempt) — no fourth.
- **Conclusion-first (the Verdict Band pattern, 2026-06-30).** Lead with the conclusion, support it
  with card-linked evidence, commit to ONE next step — never make the user synthesize raw data; say
  what you know, flag what you don't. The Scorecard `VerdictBand` is the canonical bespoke hero element
  of this kind (one tone bar per favorability = genuine state, not rainbow; caveats folded *into* the
  verdict, not a separate banner; methodology disclosed for the attorney persona). A money CTA never
  lives inside the verdict — azure = do work (the verdict's next step), terracotta = costs money (the
  separate `ReportCTACard`). Don't preview the old wall-of-cards; preview the conclusion.
- **Subordinate the secondary door.** A second entry point (a chat door, a "see a real example" link)
  stays **labeled** but visually subordinate to the page's one primary action — smaller, muted, no
  competing CTA (the #5 Home/nav "Ask the analyst" door sits *under* the address box; the #6 Discovery
  seam is quiet, below the ranked list). And **judge a hero element on the live page, not in spec**:
  the #7 "payoff preview" card read fine in spec but was heavier than its value live (parcel jargon to
  a context-less newcomer, crowded the hero) → **reverted.** Green tests confirm shape, not weight.

## What shipped (8 commits on `design-system-refactor`)
1. `f4ee78a` foundation: tokens, type scale, fonts, Card + Chip.
2. `1572f69` Modal primitive + the 4 modals.
3. `6009b8d` UserMenu.
4. `b273b07` chat cluster A — citation/source (ScorePill→Chip, Tooltip/InfoTooltip #333/#444→tokens).
5. `215db3d` chat cluster B — chat shell (HistorySidebar white/opacity→tokens; ChatInput compact).
6. `77fd0d5` chat cluster C — sidebar data cards (px + FoodInspection state colors).
7. `81e0e0d` chat cluster D — map + analytics (px; panels opaque; swatch borders; map overlays kept).
8. `bf33d70` cluster E — last px residual (NeighborhoodCard, SidebarPanel/Header, SourceDetailDrawer).
Pre-2-cluster work (Scorecard/Discovery/Landing/header/Admin/About/Pricing) is in commits 1–3's range
and the earlier in-session edits folded into `f4ee78a`. Net: **zero arbitrary `text-[Npx]` app-wide**
outside the documented exemptions; zero off-palette chrome hue.

## Not done / carry forward
- **Branch is unmerged and unpushed.** Pushing to `main` = deploying (auto-deploy). Needs owner
  approval + a visual QA pass on prod before merge.
- The pre-existing uncommitted doc edits + `vibecoded-design-tells-main.zip` at repo root are
  deliberately left out of the refactor commits.
- Visual QA was code-level (tsc/build/tests) — no human has eyeballed every migrated surface on prod
  yet. Watch the hero (Space Grotesk 600 weight), terracotta user-message bubbles, de-rainbowed
  DepthShowcase row.
