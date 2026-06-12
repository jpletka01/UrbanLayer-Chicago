# Coherence Audit Step 1 — Report→Transcript Renaming + Chat→Scorecard Bridge

**Completed**: 2026-06-11
**Status**: Shipped to production (merge `c3f68c3`; commits `e5aa766` renaming, `4d305ac` bridge)

## What Was Built

The first implementation step of the product coherence audit
(`strategy/product-coherence-audit.md`): (1) the word "report" is now reserved product-wide for
the paid $25 Development Feasibility Report — the free chat PDF export became a "transcript";
(2) the missing chat→Scorecard bridge was built, so chat conversations that resolve a parcel now
link to the assessment product. Both were prerequisites for Phase 2 customer interviews measuring
the feasibility product instead of the chatbot.

## Implementation Details

### Renaming (`e5aa766`)
- Chat export button: "Report" → "Export" (`common.json` key `report` → `export`; only used in
  `App.tsx` header).
- Export PDF: fallback title "Chicago Report" → "Chicago Transcript" (`App.tsx`,
  `reportBuilder.ts`); heading "UrbanLayer Site Report" → "UrbanLayer Conversation Transcript"
  (`data.json` `report.siteReport`); modal "Report Preview" → "Transcript Preview"; filename
  `*_report.pdf` → `*_transcript.pdf` (`ExportReport.tsx`).
- Landing copy (`landing.json`): `story.reportSubtitle` previously sold the FREE export with the
  paid report's value prop ("Download a professional PDF report you can hand to a client, investor,
  or lender") — the audit's "counterfeit" finding. Now it points at the real artifact: "…then get
  the full Development Feasibility Report, a professional PDF you can hand to a client, investor,
  or lender. $25 per parcel." This is the homepage's first mention of the paid product.
  How-it-works step now says "Export your research as a PDF transcript anytime."
- All changes mirrored in Spanish locales.
- **Deliberately not renamed**: internal identifiers (`buildReportData`, `ReportData`,
  `ExportReport.tsx`, `reportBuilder.ts`) — user-facing vocabulary only; a mechanical internal
  rename can follow separately. The ~70 generic PDF field labels under `data.json` `report.*`
  also unchanged. Paid-report strings (`pages.json` `scorecard.reportCTA.*`, `ReportCTACard`,
  `ReportPurchasePrompt`) untouched by design.

### Chat→Scorecard bridge (`4d305ac`)
- New `frontend/src/components/sidebar/ScorecardBridgeCard.tsx`: compact non-collapsing card
  pinned at the top of `DataView`'s card stack whenever the active message's context resolves a
  parcel. Shows resolved address + PIN + "View Scorecard →". Exports `buildScorecardHref(pin,
  address)`: PIN → `/scorecard?pin=` (digits-only, same normalization as the Explorer handoff),
  else address → `/scorecard?address=` (ScorecardPage param precedence handles both and
  canonicalizes the URL).
- PIN source: `context.property.pin14`; address source: `context.resolved_address` (fallback
  `context.property.address`). Both arrive in the existing context SSE event — no backend
  pipeline change.
- `ReportTeaser` gained an optional `href` prop: with it (chat sidebar via `PropertyCard` and
  `IncentivesCard`, which now take an optional `scorecardHref` threaded from `DataView`) it
  renders as a react-router `Link`, 11px, accent hover, trailing "→"; without it (ScorecardPage's
  `ComparablesCard`) it renders exactly as before.
- New analytics event `scorecard_bridge_click` (`source: "bridge_card" | "teaser"`, plus
  pin/address on the card), added to `_VALID_EVENT_NAMES` in `backend/main.py`. **Not yet charted
  on the admin dashboard** — stored and queryable in the `events` table.
- New i18n keys: `sidebar.json` `bridge.viewScorecard`, `bridge.pin` (en + es).

## Key Decisions

- Bridge prominence: Jack chose "sidebar bridge card + clickable teaser" over teaser-only
  (audit had judged the teaser "invisible") and over an additional per-message footer CTA
  (rejected as repetitive).
- Landing sentence: Jack chose redirecting the value prop to the paid report over describing the
  transcript honestly-but-quietly — stops the counterfeit AND puts the first paid-product mention
  on the homepage without waiting for the homepage redesign.
- Export button label is the action verb "Export" (next to "Share"); the artifact itself is the
  "transcript". Both audit-compliant: neither is "report".

## Verification

- `tsc --noEmit` clean; 577 backend unit tests pass; all 8 edited locale JSONs valid.
- Live end-to-end (dev stack): chat query "Tell me about the property at 642 W Belden Ave" → context
  event carried `pin14: 14331030120000` + `resolved_address` → `/api/scorecard?pin=14331030120000`
  resolved `authoritative` with full property context → posted `scorecard_bridge_click` event landed
  in the `events` table.
- Side observation: chat resolved 642 W Belden to PIN `…120000` while the V6 QA notes list the
  taxable control as `…110000` — likely the same class of QA-labeling discrepancy as the previously
  investigated (and dismissed) Address Points "bug", not re-investigated.

## Files Changed

- `frontend/src/components/sidebar/ScorecardBridgeCard.tsx` (new)
- `frontend/src/components/sidebar/{DataView,ReportTeaser,PropertyCard,IncentivesCard}.tsx`
- `frontend/src/{App.tsx, lib/reportBuilder.ts, components/ExportReport.tsx}`
- `frontend/src/locales/{en,es}/{common,data,landing,sidebar}.json`
- `backend/main.py` (event allowlist, one line)
