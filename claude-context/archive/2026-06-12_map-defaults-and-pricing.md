# Coherence Audit Step 2 — Map Defaults Flip + Pricing-Page Emphasis

**Completed**: 2026-06-12
**Status**: Shipped to production (merge `b0921e9`; feature commit `312106a` on `audit/map-defaults-and-pricing`)

## What Was Built

The second implementation step of the product coherence audit
(`strategy/product-coherence-audit.md` §6 and §8): (1) the chat map's default layers now match the
product thesis — crime/311/permit point clouds OFF by default, transit stations ON, with points
auto-enabling behind explicit query intent; (2) the pricing page leads with the $25 Development
Feasibility Report instead of $99 Pro, and `/pricing` gained its first anonymous-reachable inbound
link (landing footer). Together with step 1 these remove the last two "wrong product" first
impressions (crime-map identity, subscription-first pricing) ahead of Phase 2 customer interviews.

## Implementation Details

### Map defaults (`MapView.tsx`)
- `showPoints` default `true` → `false`; `showTransit` default `false` → `true`
  (zoning/incentives/overlays unchanged at `true`).
- **Intent gate**: new `useEffect` mirrors the existing `hasTransitContext` pattern — when
  `deriveFilterMode(sources)` returns a non-`"overview"` mode (the query's sources resolved to
  exactly one of crime/311/permits, i.e. an explicitly scoped question like "crime near X"),
  `showPoints` auto-enables. Broad multi-source queries ("what's going on near…") keep dots off;
  the source tabs still show counts, one toggle away.
- One-way ratchet, same as transit: a later non-point query doesn't force the toggle back off
  (harmless — its mapData carries no point arrays).
- Transit stations are fetched by the pre-existing `showTransit` effect (module-level cache in
  `api.ts`); mobile (`MobileSidebarSheet`) inherits everything since it renders the same component.

### Pricing page (`PricingPage.tsx`)
- 2-card → **3-card** grid (`max-w-4xl`→`5xl`, `md:grid-cols-2`→`3`): Free / **Development
  Feasibility Report $25** (center, accent `border-2`, "Start here" badge, CTA `Link` →
  `/scorecard`, hint "Open any parcel's free Scorecard, then buy its full report.") / Pro $99
  (plain border, "Recommended" badge removed, secondary-styled upgrade button, new arithmetic
  upsell line "4 reports ≈ a month of Pro — go unlimited.").
- The hardcoded-English a-la-carte footnote paragraph (the audit's "$25 wedge as footnote"
  finding) was deleted — its content is the center card.
- Copy updates: page subtitle now speaks feasibility vocabulary; `billingNote` notes reports are
  one-time purchases; `proFeatures` "PDF zoning reports" → "Unlimited Development Feasibility
  Reports" (step-1 vocabulary rule); `pricing.recommended` i18n key removed (unused).
- Full en/es parity for all new keys (`reportTier`, `perReport`, `perParcelNoSub`, `startHere`,
  `reportFeatures[]`, `getReport`, `scorecardHint`, `proMath`).

### Footer link (`landing/Footer.tsx`)
- "Pricing"/"Precios" link to `/pricing` in the About column — first inbound link reachable
  without sign-in (previously only UserMenu post-auth + UpgradePrompt paywall).

### Drive-by fix
- `es/pages.json` `scorecard.reportCTA` block was entirely untranslated English in production
  (pre-existing parity bug found during exploration) — now translated.

## Key Decisions (Jack, via AskUserQuestion)

- **Intent-gated auto-enable** over a pure flip: an explicit "crime near X" question still shows
  dots immediately; the audit's "behind explicit intent — the SSE pipeline is the natural grain"
  principle, implemented on the existing `hasTransitContext` pattern.
- **3-card layout** over a 2-card + hero band: the wedge becomes a first-class tier, free-tier
  limits stay visible.
- **Footer Pricing link now** rather than deferring all navigation to the homepage redesign:
  cheap, reversible, decoupled.
- Badge says "Start here" (honest with 0 customers), not "Most popular".

## Verification

- `tsc --noEmit` + `npm run build` clean. Playwright against live dev stack, 17/17 checks
  including two real chat queries through the SSE pipeline:
  - "Tell me about the property at 1425 N Wells St" → zoning/overlay polygons + transit stations,
    no dots; Points toggle off, Transit on.
  - "What crimes were reported near 2400 N Milwaukee Ave?" → Points auto-enabled by the intent
    gate; manual toggle-off still works.
  - `/pricing`: 3 cards en + es; free-tier mock sees "Current plan"/proMath/"Get a report" →
    navigates to `/scorecard`; admin/Pro sees "Active". Footer link navigates.
- Live deploy verified by polling the production JS bundle for the new pricing strings.

## Noted For Later (not built)

- **TOD radii** around stations don't exist as a map layer — audit §6 names "transit stations +
  TOD radii" as the default experience; only stations exist today. New feature work.
- `LandingMap`'s crime-dot demo on the homepage is untouched — a homepage-redesign concern.
- `UpgradePrompt.tsx` / `ReportPurchasePrompt.tsx` copy is hardcoded English (not i18n-ified) —
  pre-existing, unchanged.

## Files Changed

- `frontend/src/components/sidebar/MapView.tsx`
- `frontend/src/components/PricingPage.tsx`
- `frontend/src/components/landing/Footer.tsx`
- `frontend/src/locales/{en,es}/{pages,landing}.json`
