# Page design: how a UrbanLayer page shows information

> **Two UIs during the front-end rewrite (2026-11-07):** new UI work (`frontend/src/ui-next/`, behind `?ui=next`) follows `guides/frontend-redesign-vision.md` and decisions Items 73+ (`decisions/2026-11_frontend-rewrite.md`): SnowUI frame, Coastal charts, black for this lot, **no satellite map**. This document describes today's live UI only; don't carry its colors, components or map choices into the new UI.


**Status: living, canonical (2026-11-02).** The Property Profile was rebuilt around these rules in decision Items 46-54 (`decisions/2026-10_build-queue.md`), shipped by #162, #163, #174, #175 and #177; Items 55-58 (one analysis map, the phone layout, Discovery's dot preview and rows) follow in the next release PR. Every other app page follow them as they are touched. The checklist form is the project skill **`page-design-rules`** (`.claude/skills/page-design-rules/SKILL.md`); load it before any UI change. This guide holds the reasons, the evidence and the file map.

Supersedes the layout parts of `guides/scorecard-dashboard-model.md` (July 2026). Sits on top of the Bento Pro tokens (`guides/bento-pro-redesign.md`), which still own the palette, type and radius. Does not change the truth rules (`guides/source-confidence.md`); it changes only where their words go.

## Why this exists

On 2026-10-31 Jack called the Profile "terrible": about 3,000 words, ~540 figures, ~30 caveat sentences and ~50 small-print notes, all at the same weight. "You never know what to look at." On 2026-11-02, after the first-screen rebuild, he said an opened section still "bores me... I don't know where to look since there's so much text."

The cause was **additive honesty with no page owner**. Every workstream added correct, reviewed text one card at a time: confidence captions, "couldn't check" lines, code vintages, disclaimers, map keys with counts, method notes. Each passed review alone, and nobody measured the page as a whole. An AI collaborator that adds one honest caveat per edge case makes this worse. The fix is structural: rules for *where* text goes, plus a test that stops the total from growing.

Research behind the rules: `plans/reports/Fixing an overgrown data page.md` (local-only; NN/g progressive disclosure, the inverted pyramid, Few's dashboard rules, Carbon/Atlassian/Primer token and status systems, WCAG 1.4.1/1.4.11/1.4.13, alarm fatigue). The measured case study and the plan: `plans/2026-11-01_profile-discovery-redesign-plan.md` (local-only).

## The rules

### 1. One answer first; two levels only
- The first screen answers **what can I build, what's in the way, what's it worth**. On the Profile: the address, a neutral verdict label, **one deterministic sentence** (`frontend/src/lib/answerSentence.ts`, templates per verdict state, no LLM), three panels (Build · In the way · Value & cost, ≤ 8 figures), the place map.
- Everything else is **one level down**: a section opened from its one-line summary (`ProfileModule` `open`/`onToggle`), or a popover on one figure. Never a disclosure inside a disclosure; dialogs (the Sources sheet) are fine.
- **Say it once.** The verdict label joins the sticky band only after the answer scrolls away; the phone hides the hero Ask because its bottom bar is the Ask.

### 2. A block prints a headline, its key figures and its status labels; evidence goes behind tools
- **Human headline**, stating the finding ("Minimum lot area per dwelling unit for RS-3", "10 N State St"). Never an ID as a headline: no Clerk record numbers, PINs or section numbers.
- **1-3 key figures**, with their units. **No bare numbers or code words**: "Today: parking can be cut by up to 100%", not "today 100"; "coach houses not allowed", not `not_allowed` (backend `legislation/impacts._shown` holds the units and words).
- **Status labels** (rule 5).
- **Evidence behind the tool tray**: dates, code sections, record numbers, official titles, definitions, method notes, disclaimers, arithmetic, links.

### 3. The tool tray: one Lucide icon per meaning, same order everywhere
`frontend/src/components/ui/ToolTray.tsx` (`DateLine` for date rows). Icons come from **`lucide-react` only** (pinned 1.59.0): never Unicode glyphs (they render differently per font) and never emoji (Jack).

| Order | Tool | Lucide | Holds |
|---|---|---|---|
| 1 | Dates | `Calendar` (never a clock) | every date for the item, each with its plain meaning: "City Council last acted", "We read the ordinance text", "We checked the Clerk's list" |
| 2 | Code | `Scale` | the Municipal Code section(s); on the Zoning card it opens the code text |
| 3 | Official record | `SquareArrowOutUpRight` | the Clerk / Assessor / City record; record number + official title in its tooltip |
| 4 | Explain | `Info` | what it means, the method, the disclaimer, in two sentences |
| 5 | Ask | `MessageCircleQuestion` | opens the analyst on this item |
| — | More / expand | `ChevronDown` | |

- **Behavior** (`ui/Toggletip.tsx`): on a mouse, hovering previews the popover and moving into it keeps it open; a click pins it; on touch a tap opens it (pointer type `touch` ignores hover). Escape (focus returns to the trigger), a second click or a click outside closes it. Satisfies WCAG 1.4.13 (hoverable, persistent, dismissible). Never hover-only.
- Icons are neutral gray and turn orange on hover/focus. Each tool is a real button or link with a descriptive accessible name ("Dates: Minimum lot area per unit"); a scripted check on 2026-11-02 found all 81 Profile controls named.
- A year that changes the decision may stay visible beside the calendar (`datesVisible`, e.g. the tax year).
- **Links that open a page open in a new tab** (`target="_blank" rel="noopener noreferrer"`); `frontend/src/components/linksOpenNewTab.test.ts` fails on a new one without it. Exceptions: `mailto:`/`tel:`, router `<Link>`s for in-app navigation, and sign-in / Stripe checkout redirects (they must return to the same tab).

### 4. Color is a role, never a hue
Role tokens over Bento Pro (`tailwind.config.js`, `src/index.css`): `status-{success,warning,danger,info,neutral}` (DEFAULT = text/icon, `-subtle` = tinted fill), `premium` (violet), `action`/`link` (orange), `text-disabled`.

| Color | Means | Budget |
|---|---|---|
| Neutral weight and size | importance | — |
| Orange | **clickable only** | ≤ 1 **solid** orange element per viewport (the dock launcher on desktop, the bottom-bar Ask on phones) |
| Violet | **costs money only** | none on the first screen while purchases are off |
| Amber | check this / act on this | ≤ 3 on the first screen, **shared** by In-the-way rows, "Low confidence" labels and the approximate-match label (`AnswerPanels` `MAX_AMBER`, `amberElsewhere`) |
| Red | a blocker | rare |

- A verdict category is **neutral**, never amber (Q6).
- A note that fires on every parcel is neutral, not amber (the citywide "283 filings couldn't be placed"): amber that always fires teaches readers to ignore amber.
- `frontend/src/components/scorecard/palette.test.ts` fails on raw palette classes (`text-amber-400`) in Profile code.

### 5. Buttons and status labels never look alike
- **`ui/Button`**: 8 px radius, 36-40 px, hover/pressed/focus ring, pointer. `primary` = the one solid orange (`data-solid-action`). `secondary` = **orange outline + orange text** (`border-link text-link`, ~9:1 on dark, ~5:1 on light). Never a dark outline on a dark surface: that was the 2026-11-02 complaint. The module "Ask about…" chips (`InvestigateButton` `chip`) use the same style plus the ask icon.
- **`ui/StatusLabel`**: ≤ 22 px, 3 px radius, tint + Lucide icon (`TriangleAlert`, `OctagonAlert`, `CircleCheck`, `Info`; neutral has none), not focusable, no pointer. `ui/foundation.test.tsx` pins 5 differences between the two.
- **`ui/ConfidenceState`**: the five visible states: Estimate (`EqualApproximately`), Low confidence (same icon, amber), Not checked (`CircleDashed`), None found (`CircleCheck`), Withheld (`CircleSlash`; the value shows "—" + a reason ≤ 8 words), N/A (`CircleMinus`). A verified figure has no label. `confidenceStateFor(entry)` reads the backend's state and never recomputes it. **These states never move behind a tool**; only their explanation does.

### 6. The page has an owner: a ratcheting budget (Profile and Discovery)
`frontend/e2e/profile-budget.spec.ts` + `profile-budget.baseline.json`, run by `npm run test:mobile` (once, in the "Pixel 3" project, opening its own desktop and phone contexts). Not in CI: CI has no backend or live data to render a Profile.
- **What it checks**, on four reference parcels: 2541 N Spaulding (two-flat), 1601 N Milwaukee (commercial, landmark district), 233 S Wacker (downtown) and PIN 14-28-319-102-0000 (the $1 parcel).
  - First screen, desktop 1440×900 and phone 390×844: words ≤ 120 / 90; amber ≤ 3; solid orange ≤ 1; default page ≤ 4 desktop screens; no heading twice; no figure with two confidence states.
  - The opened "What you can build" section: words ≤ 500.
- **Ratchet**: words, orange and page height may only go down. Words get an **8-word allowance for live state rows**: a source outage adds an honest "Not checked" row, as FEMA's did on 2026-11-02. Amber is held to the cap only, because it follows live states. `BUDGET_UPDATE=1` lowers a baseline and never raises one; raising one is a hand edit with its reason in the PR and the decision log (Item 54 raised `milwaukee/build` 348 → 359 for the clearer parking wording).
- The measurement fails on an empty section rather than recording 0 (that bug once wrote a 0 baseline).
- **Discovery** (Item 57): `e2e/discovery-budget.spec.ts` + `discovery-budget.baseline.json` hold the first screen of the Start panel and of a recipe's results (desktop and phone), and the dot preview's words, to the same ratchet.
- **Ad-hoc measuring**: `plans/2026-11-01_redesign-assets/firstscreen.cjs <base> <label>` (local-only; run from `frontend/`).

## Measured effect (production before → after)

| | Before | After |
|---|---|---|
| Profile first screen, desktop words | 150-185 | 93-118 |
| Profile first screen, phone words | 96-132 | 65-71 |
| First-screen amber items | 3-6 | 0-3 |
| Default page height (desktop screens) | 9-11 | 1.6-1.7 |
| Opened "What you can build", 1601 N Milwaukee / PIN 25-04-400-090 | 1,085 / 919 words | 359 / 237 |
| "Pending zoning-code changes" card | 542-627 words | 45-49 |
| Opened Costs / Neighborhood | 195-264 / ~225 | 170-192 / ~196 |

Nothing was deleted: everything is one click away.

## Where things live (frontend)
- **Primitives** (`src/components/ui/`): `Button`, `StatusLabel`, `ConfidenceState`, `Toggletip`, `ToolTray` (+ `DateLine`).
- **Profile**:
  - first screen: `ScorecardPage.tsx` (derivations), `scorecard/ProfileHeader.tsx`, `AnswerPanels.tsx`, `SectionBand.tsx`, `lib/answerSentence.ts`;
  - sections: `scorecard/ProfileModule.tsx` (collapsible), `SourcesSheet.tsx` + `lib/sourceScopes.ts`;
  - cards with tool trays: `PendingTextImpactsCard`, `UpcomingZoningCard`, `ScorecardZoningCard`, `WhatIfCard`, `ScorecardRegulatoryCard`, `CapacityMap`, `ScorecardPropertyCard` (appeals, permits), `RentBlock`.
- **Build section** (Item 55): `scorecard/AnalysisMap.tsx` (one map, a layer switch; `analysisLayers.ts`), `CapacityMap` (a layer), `WhatIfCard` (an inline compare row). **Phone** (Item 56): `lib/useIsPhone.ts` (one open section at a time), `scorecard/PlaceMapStrip.tsx`.
- **Discovery** (Item 57): `discovery/DotPreview.tsx`, `rowFigures.ts` (row title and figures, "Nominal"), the results header's tool tray in `DiscoveryPage.tsx`; `GET /api/discovery/parcel`.
- **Guards**: `ui/foundation.test.tsx`, `scorecard/palette.test.ts`, `components/linksOpenNewTab.test.ts`, `components/siblingKeys.test.ts`, `e2e/profile-budget.spec.ts`, `e2e/discovery-budget.spec.ts` (both count with `e2e/budgetMeasure.ts`).

## Lessons worth keeping
1. **Per-PR review cannot see the page.** Only a whole-page, ratcheting measurement stops accretion.
2. **Text glyphs are not icons.** They render differently per font; use one icon library.
3. **Measure with live data, not just local.** Local had no Clerk snapshot (`python -m backend.legislation.sync` builds one in ~8 min, no credits) and no FEMA outage; production surfaced both.
4. **Reset per-entity UI state on the entity's identity, not on the response object.** A second response for the same parcel snapped opened sections shut (Item 54).
5. **Tailwind config changes need a dev-server restart.** New tokens rendered untinted until it restarted.
6. **A test that pins a printed string pins the clutter.** When a fact moves behind a tool, the test opens the tool and checks the same guarantee. Never delete the guarantee.

## Not done (as of 2026-11-02)
- Compact phone panel rows (plan §6g). They would let the place-map strip move above the panels (Item 56).
- The exact zoning class in Discovery's dot preview (it shows the family and FAR until the index carries the class).
- The tool-tray pass on the chat rail cards and the $25 report.
- About page story for the redesign.
- Native Mexican-Spanish read of every new string; no real-user tests of the icon set.
