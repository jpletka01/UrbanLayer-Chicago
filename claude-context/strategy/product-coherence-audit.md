# Product Coherence Audit — Post-Identity-Unification (2026-06-11)

**Status:** Analysis complete; implementation underway. **Step 1 SHIPPED 2026-06-11** (merge `c3f68c3`,
see `archive/2026-06-11_rename-and-bridge.md`): the "report"→transcript renaming and the chat→Scorecard
bridge. Sections 1 and 3 below are the audit's point-in-time evidence (2026-06-11 pre-implementation) —
the claims "chat→Scorecard bridge does not exist", "chat export titled Chicago Report", and "ReportTeaser
non-clickable" are now resolved; see §10 for the per-item status. All other findings remain open. This
document is the strategic interpretation that implementation work must serve. Read this *with*
`strategy/north-star.md` (the governing strategy doc); this audit extends, sharpens, and in places
challenges it based on what the product actually does as-built.

**Origin:** Two-session founder-level product review conducted immediately after the SelectedParcel
identity unification shipped (2026-06-11, see `archive/2026-06-11_selected-parcel.md`). Session 1 was a
product-level coherence evaluation ("do these pieces form one product?"). Session 2 was an aggressive
first-principles audit ("does the product make sense as a business and a UX?") with a 7-part structure.
All findings below were verified against the live codebase, not assumed from docs.

---

## 0. The Headline Diagnosis

**UrbanLayer is one product whose front door is wired to the wrong room.** The strategy (north-star),
the data architecture (SelectedParcel, PIN-keyed purchases), and the monetization (per-parcel $25
reports) all describe a single coherent product: a **parcel feasibility engine / single-parcel due
diligence automation tool**. But the entry experience still belongs to an earlier product — a
civic-data chatbot — and the connective tissue between surfaces runs in only one direction.

The pieces do NOT form multiple products. They form one product whose funnel stages exist but are
**not connected in order**: the chatbot greets visitors before the assessment can build trust; the free
"report" is offered before the real report is discoverable; the neighborhood data speaks before the
feasibility data. The product was repositioned at the copy level (Phase 0, 2026-06-08) but **not at the
plumbing level** — "repositioned words, unrepositioned plumbing" is the one-line summary.

---

## 1. Verified Ground Truth (codebase evidence)

Every claim in this audit was verified directly. Key evidence, with locations:

### Routing & entry points
- **Homepage hero routes 100% of actions into chat.** `App.tsx:702` — hero `ChatInput onSubmit={sendMessage}`.
  Suggestion chips (`App.tsx:715`) → `sendMessage`. `PersonaScenarios` (`App.tsx:767`) → `sendMessage`.
  There is NO homepage element that leads to the Scorecard, Explorer, or Pricing.
- **The Scorecard is effectively orphaned.** Links to `/scorecard` exist in exactly 3 places app-wide:
  `ExplorePage.tsx:180` and `:326` (parcel click → `/scorecard?pin=`, behind the premium gate),
  `ExplorePage.tsx:207` (nav link, also behind the gate), and `PricingPage.tsx:118` (a footnote link).
  Neither the homepage (`App.tsx` splash) nor the chat workspace contains any link to `/scorecard`.
- **Chat→Scorecard bridge does not exist; Scorecard→chat bridge does** (Investigate buttons via `?q=`,
  see `App.tsx:357` comment). The design-guidelines "hybrid model" was built in only one direction.

### The auth wall (discovered in session 2 — material funnel fact)
- **In production, an anonymous visitor's FIRST action (typing into the hero) hits a Google sign-in
  modal before any value is shown.** `App.tsx:318-319`: `if (authRequired && !isAuthenticated) {
  setShowAuthModal(true); return; }` inside `sendMessage`. `backend/auth.py:339-366`: `auth_required`
  is `true` whenever auth is enabled (GOOGLE_CLIENT_ID set — which it is in production).
- **Meanwhile `/api/scorecard` requires NO auth and NO rate limit** (`rate_limit.py` is applied to
  `/chat` only, per backend/CLAUDE.md; ScorecardPage is not a ProtectedRoute). The product's
  frictionless, zero-API-cost, trust-building surface is hidden; the visible surface demands OAuth
  up front. Anon chat rate limit (if it were reachable) is 3/day (`rate_limit.py:25-26`,
  `RATE_LIMIT_ANON_DAY=3`).

### Vocabulary collisions (the "report" problem)
- **Chat export is a free PDF titled "Chicago Report".** `App.tsx:598-608` `handleExport()` →
  `buildReportData(messages, mapScreenshot, title)` with fallback title "Chicago Report" →
  `ExportReport.tsx` (a styled conversation transcript with Q&A blocks).
- **Landing copy markets the FREE export with the PAID report's value prop.** `locales/en/landing.json:55`:
  "Ask a question in plain English… *Download a professional PDF report you can hand to a client,
  investor, or lender.*" — this sentence describes the chat flow, i.e. the free transcript. Same
  framing at `landing.json:164`.
- **The paid artifact** is "Development Feasibility Report — $25" (`pages.json:71-86`, `ReportCTACard`),
  purchasable only on the Scorecard. PIN-keyed entitlement (db schema v11).
- **Scorecard CSV download** is also called "export" (`csvExport.ts`, `ScorecardPage.tsx:383`).
- Net effect: four artifacts share two words; the free artifact carries the paid artifact's sales pitch.
  **The free export pre-satisfies the perceived need** — users can reasonably believe they already
  obtained the product being sold.

### Report visibility in chat
- The ONLY mention of the paid report inside the chat experience is `sidebar/ReportTeaser.tsx` —
  a **non-clickable**, 10px, muted-gray text fragment rendered inside PropertyCard, ComparablesCard,
  IncentivesCard. It is not a link. A user can hold ten parcel conversations and never learn a
  purchasable report exists.

### Map defaults
- `sidebar/MapView.tsx:170-174`: `showZoning=true`, `showPoints=true` (crime/311/permit dots),
  `showIncentives=true`, `showOverlays=true`, **`showTransit=false`**.
- I.e., the ambient point clouds (crime/311/permits) are ON by default while **transit/TOD — the only
  point layer that is a literal zoning-bonus determinant in Chicago — is the only layer OFF.**
  The defaults are inverted relative to the product thesis.

### Explorer
- Premium-gated before any value shown: `ExplorePage.tsx:110-113` — `if (!isPro) { setShowUpgrade(true); return; }`.
- Filters are only community area + property-class prefix (too crude for professional prospecting,
  as north-star already noted).
- Correctly terminates in `navigate('/scorecard?pin=')` — the architecture already treats discovery
  as the funnel top.

### Pricing page
- `PricingPage.tsx`: leads with $99/mo Pro marked "Recommended"; the $25 a-la-carte report — the
  strategy's actual wedge — is a footnote paragraph (`:113-122`) with the app's only non-Explorer
  link to `/scorecard`. The page itself is nearly orphaned: reachable mainly via UserMenu
  (requires sign-in) and UpgradePrompt (requires hitting a paywall).

### Identity contradiction in the project's own self-description
- Root `CLAUDE.md` still names the killer query as "What's going on near 2400 N Milwaukee Ave?" —
  a resident's neighborhood-exploration question. The stated killer query and the monetized workflow
  belong to two different products.
- Homepage suggestion chips ARE professionally positioned (Phase 0 worked at copy level):
  "Can I build a 6-unit building at 4520 N Clark St?", "What are the setback requirements for B3-2
  zoning?", "Is 2400 N Milwaukee Ave eligible for a Class 6b incentive?", "Tell me about the property
  at 1425 N Wells St" (`landing.json` suggestions). **Three of four are address-anchored
  parcel-assessment intents — written into the front door, then routed to the interface that can't
  assess a parcel or sell anything.**

---

## 2. Part 1 — What UrbanLayer Actually Is (capability-based, not aspirational)

- **Category:** Single-parcel due diligence automation. A machine that turns a Chicago address into a
  capital-decision-grade assessment. The automated midpoint between Cityscape's Address Snapshot and a
  $500 consultant memo.
- **Primary job-to-be-done:** "Before I commit capital to this parcel, tell me what I can build here,
  what it's worth, what it will cost me, and what will bite me — in minutes, not afternoons."
- **Primary customer:** Small Chicago developer (2–10 projects/yr, $500K–$5M at risk) as the hypothesis;
  architects and zoning attorneys adjacent. Still unvalidated (0 paying customers) — but the only
  customer for whom every strong surface is simultaneously relevant.
- **Primary monetization event:** The $25 Development Feasibility Report purchase — the only per-unit
  monetization event that exists, correctly placed at peak conviction (right after the free Scorecard
  proves accuracy). The $99/mo Pro tier is aspirational: it currently sells "unlimited reports + a
  crude Explorer" — a recurrence promise without a recurrence engine.
- **Strongest differentiator:** Cited reasoning over the municipal code (14,535 chunks, section-aware
  RAG, § citations) — the moat. Second: one query → full synthesis in ~2s — the hook.
- **Surfaces that reinforce this identity:** Scorecard, Feasibility Report, Investigate buttons,
  SelectedParcel/PIN identity, zoning/overlay/incentive map layers, Explorer's parcel→Scorecard handoff.
- **Surfaces that dilute it:** the homepage mechanics (auth-walled chat box), chat's catch-all routing
  (9 Socrata domains incl. food inspections — the backend proudly answers neighborhood questions, so
  the product IS partly a neighborhood explorer regardless of landing copy), default-on crime/311/permit
  point clouds, the free "Chicago Report" export, landing analytics/crime demos
  (`LandingAnalytics`/`LandingMap`), and the CLAUDE.md killer query.
- **Diagnosis:** one real product wearing the costume of an earlier one. The civic-data chatbot owns
  the front door, the default map, the vocabulary, and the chat router. The feasibility product owns
  everything that works and everything that charges money.

---

## 3. Part 2 — The Funnel, Mapped Honestly

### Entry points (all of them)
1. `/` homepage — every interactive element calls `sendMessage`
2. `/s/:shareToken` — shared conversations (lands in read-only chat)
3. `/scorecard?pin=` — canonical parcel URLs (shareable since SelectedParcel; excellent, but only
   shared by someone who already found the Scorecard)
4. `/pricing`, `/about` — direct/footer

### The anonymous visitor's actual experience
```
Land on homepage → professional copy, slideshow ✓
→ Type an address question → GOOGLE SIGN-IN MODAL     ← abandonment cliff #1
→ (if OAuth) → chat answers; sidebar: map w/ crime/311/permit dots + property cards
→ ReportTeaser: 10px gray non-clickable text          ← "monetization visibility" (invisible)
→ "Export" → free PDF titled "Chicago Report"          ← user believes they got the product
→ session ends. No Scorecard. No $25 CTA. No pricing link on this path.
```

### Dead ends, enumerated
1. **The auth wall** — first action demands OAuth before any value. The north-star says the Scorecard
   exists precisely to be the free, instant, anonymous trust-builder — and it's the only major surface
   with no auth gate, hidden in a back room with no signage.
2. **Chat terminates in a transcript** — the system resolves the parcel's PIN to render sidebar cards,
   i.e. it KNOWS the user has a parcel-assessment intent, and declines to route them to the assessment
   product.
3. **Explorer's paywall** — pay $99/mo to *begin* the funnel.
4. **Pricing leads with the wrong product** — $99 "Recommended", $25 wedge as footnote, page itself
   nearly unreachable pre-sign-in.

### Value/monetization visibility
- Value demonstrated at: chat answers (good, expensive, unmonetized), Scorecard (fastest/cheapest/best —
  unreachable), the report (only after purchase).
- Monetization visible at: Scorecard's ReportCTACard (excellent, orphaned), pricing footnote,
  ReportTeaser (decorative).

### The 1,000 qualified developers thought experiment
- All 1,000 read correct positioning copy. Several hundred bounce at the OAuth modal (professionals
  don't sign in before seeing one answer from an unknown tool). Those who sign in end up in chat,
  get a good answer, see a crime-dotted map (conclude: crime-data tool), some export the free
  "Chicago Report" and leave believing they received the deliverable.
- **Would they discover the paid product?** Only by accident (avatar → pricing, or external Scorecard
  link). The dominant path contains zero clickable routes to it.
- **Would they understand what the product is?** Partially — copy says feasibility, experience says
  "AI chatbot with a crime map."
- **Would they understand why to pay?** No — worse: the funnel hands out a counterfeit of the product
  (free PDF named and framed as the deliverable).

### Phase 2 contamination warning (important)
If the 20 customer-validation interviewees (north-star Phase 2) enter through the current funnel,
they will validate the chatbot, not the feasibility product. **Funnel shape determines what customer
conversations measure.** Coherence is the precondition for validation data meaning anything.

---

## 4. Part 3 — Chat's Proper Role

**Conceptual answer: chat is the analyst attached to the file, plus a librarian at a second desk.**
Exactly two legitimate roles:

1. **The parcel analyst** — every assessed parcel is a "file" (the Scorecard is the file's face);
   chat is the analyst inside that file who has already read everything and answers "why" and
   "what if" (Why does the ARO apply? What if I wanted 4 stories?). This is where Investigate already
   points, where the code RAG shines, and where chat inherits context instead of demanding it.
2. **The code librarian** — parcel-less municipal-code research ("setbacks for B3-2 adjacent to
   RS-3") for architects/attorneys. A legitimate *secondary* entrance: the moat speaking directly,
   converging naturally on parcels.

What chat should NOT be: the front door, the product's identity, or a catch-all. Today it
simultaneously acts as parcel analyst + code librarian + neighborhood researcher + civic explorer,
because a single text box that accepts anything gets used for everything and the router serves all
nine domains. The capability need not be deleted — **stop soliciting it** (front-door placement is
the solicitation).

**Current routing misaligns on every axis:** destination (100% of traffic → chat), friction (auth
wall), economics (per-query marginal cost vs. zero-cost Scorecard; north-star itself says "push users
toward Scorecard first, Chat second"), and outcome (terminates in a transcript with no bridge to the
assessment product). Deepest tell: three of four homepage chips are address-anchored intents routed
to the one interface that can't assess or sell.

Bridge asymmetry summary: **the analyst can be summoned from the file (Investigate), but the file can
never be opened from the analyst (no chat→Scorecard path).**

---

## 5. Part 4 — Discovery

**The four offered framings (separate product / supporting workflow / subscription layer / top of
funnel) hide a false choice. Discovery is the top of the funnel AND the subscription layer
simultaneously — the same thing viewed from UX and from revenue.**

- **Not a separate product:** discovery's output (a parcel list) has no independent value in this
  business — worthless until each parcel is assessed. The architecture already knows this
  (Explorer's only terminal action is `/scorecard?pin=`). A standalone discovery product would be
  lead generation — explicitly rejected by the manifesto, and Cityscape's home turf.
- **What makes the business recurring:** assessment alone is episodic (per-deal $25, then silence
  for two months) — a transactional tool with no subscription logic, which is why Pro currently has
  nothing real to sell. Criteria search ("vacant lots in an OZ, zoned B3+, near CTA") is a
  *Monday-morning habit*: prospecting is weekly; evaluation is per-deal. Discovery converts
  UrbanLayer from a per-deal expense into a workflow subscription.
- **Multiplies the monetization event:** one shortlist of 12 parcels = 3–5 report purchases or one
  Pro conversion. Every discovery feature's value is denominated in assessments triggered.
- **Relationship to assessment: strictly upstream, strictly feeding.** Conveyor belt, not sibling.
  SelectedParcel already carries the handoff; PIN-keyed purchase puts a discovered parcel two clicks
  from revenue.
- **Pricing geometry that falls out:** assessment monetizes conviction per-unit ($25); discovery
  monetizes appetite via subscription ($99/mo = full criteria search + unlimited reports +
  eventually monitoring). One funnel, two billing motions.
- **Today's inversion:** the expensive unmonetized surface (chat) is the free front door while the
  funnel's entrance (Explorer) is paywalled before it can demonstrate anything. **A discovery teaser
  must be free** — show the 12 parcels, gate the depth. A paywalled funnel-top feeds nothing.
- **Sorting future capabilities** (zoning search, OZ search, TOD search, underutilized parcels,
  incentive filtering, foreclosure screening, permit screening): all pass the one test — "does this
  produce parcels for assessment?" — and belong on the conveyor. **Exception:** "investment lead
  generation" as a standalone deliverable (exported lead lists for sale) fails the test — that's the
  separate-product trap and commoditizes UrbanLayer into Cityscape's shadow.

---

## 6. Part 5 — The Map: Attention Economics

Test for every layer: *during a capital decision about THIS parcel, does this pixel earn its
attention?* Information that doesn't change the decision is decoration; decoration on by default
becomes identity.

- **Default experience (always on)** — layers that are attributes of the parcel decision:
  subject pin + parcel boundary; zoning polygons (subject + adjacent — adjacency drives transition
  rules); overlay districts (binary deal-changers); incentive zone boundaries (TIF/OZ/EZ);
  **transit stations + TOD radii** (currently the only layer OFF — yet TOD proximity is a literal
  zoning-bonus determinant: parking reductions, density bonuses).
- **Behind explicit intent (one toggle/question away, never default):** crime, 311, permit point
  clouds. Ambient environment data, not parcel attributes. Three harms when default-on: dots
  visually outcompete the five polygon layers that matter; the map reads as a crime map (re-anchoring
  the demoted "explore your neighborhood" identity at first impression); false visual equivalence
  (a battery report 400m away renders at the same weight as the TIF boundary that changes the pro
  forma). The SSE pipeline already drives the map per-query — intent-gating is the system's natural
  grain.
- **Only inside reports:** synthesized spatial artifacts — comps map, envelope visualization,
  development-trend context. Conclusions, not exploration surfaces.
- **Only in chat-driven exploration:** businesses, food inspections, vacant buildings, demographics —
  anything serving a question rather than the standing decision.

**Principle:** the default map should look like the inside of a feasibility analyst's head, not the
city's open-data portal. Five polygon layers + a transit radius is what a professional sees when
they look at a lot; eight hundred crime dots is what a data engineer sees when proud of the pipeline.

---

## 7. Part 6 — Product Coherence Scorecard

Criteria: (1) supports core workflow, (2) demonstrates value, (3) reinforces identity,
(4) leads toward monetization, (5) creates confusion.

| Surface | 1 | 2 | 3 | 4 | 5 Confusion | Verdict |
|---|---|---|---|---|---|---|
| **Homepage** | ✗ routes all traffic away from workflow into auth-walled chat | ✗ OAuth before any value | ◐ copy says feasibility; mechanics say chatbot | ✗ no path to Scorecard/report/pricing | **High** — promises "professional PDF report" that is the free transcript | Best copy, worst plumbing |
| **Scorecard** | ✓ IS the workflow's spine | ✓ instant, accurate, free, anonymous | ✓ purely feasibility | ✓ ReportCTACard + sticky CTA at peak conviction | Low | **Strongest surface, effectively unreachable** (3 inbound links: gated Explorer ×2, pricing footnote) |
| **Chat** | ◐ serves workflow via Investigate; bypasses it as entry | ✓ cited code reasoning genuinely differentiated | ✗ answers everything → communicates everything | ✗ terminates in transcripts; ReportTeaser non-clickable; no chat→Scorecard bridge | **High** — 4 roles in one box + free-"report" export | A differentiator deployed as a front door — the one job it's wrong for |
| **Explorer** | ✓ conceptually (→ `/scorecard?pin=`) | ✗ paywalled before value; filters too crude anyway | ✓ parcel-finding on-thesis | ◐ sells Pro but charges admission at the entrance | Low | Right concept, wrong gate, premature filters |
| **Report** | ✓ terminal artifact | ✓ the "$500 consultant memo" moment | ✓ the identity, distilled | ✓ the monetization event itself | **High by collision** — shares the word "report" with a free PDF | Crown jewel, discoverable only by those who already found it |
| **Pricing** | ◐ links to Scorecard | ✗ | ◐ | ✗ leads with $99 "Recommended"; $25 wedge a footnote; page near-orphaned | Medium — subscription-first for a transactionally-proven product | Inverted emphasis on an orphaned page |
| **Map** | ◐ polygons = decision context; point clouds = noise | ◐ impressive ≠ decision support | ✗ in defaults — crime on, TOD off | ✗ | Medium — signals "civic data explorer" at first impression | Instrument panel calibrated for the previous product |

Vertical readings: **column 4 has exactly two checkmarks, both on pages the funnel doesn't reach.**
Column 5's three "High"s share one root cause: the product still speaks its previous identity's
vocabulary.

---

## 8. Part 7 — Future-State Product Architecture (the recommended direction)

### The conceptual model: UrbanLayer is a parcel dossier machine
Every parcel in Chicago can have a **file** opened on it. Opening the file is free and instant.
Interrogating the file is the AI. Buying the file is the business. Finding files worth opening is
the subscription. **Everything in the product is one of four verbs acting on a parcel:
FIND, OPEN, INTERROGATE, BUY.**

### "When a new user lands on UrbanLayer, what should happen next?"
They are asked one question — **"Which property?"** — and within two seconds of answering, they are
looking at a real assessment of a real parcel, with no account, no payment, and no conversation
required. The first interaction is the product *working*, not the product asking for something
(identity, OAuth, a well-formed question). Everything else is downstream of this moment.

### Primary flow (the spine)
Address in → **parcel file opens** (the Scorecard is the file's face: identity strip, zoning,
overlays, incentives, financials, map context) → the file **invites interrogation** (Investigate →
the analyst) → the file **advertises its own completion**: a visible preview of the full dossier —
"here's what the complete Development Feasibility Report contains" — purchasable at $25 from the
first second. Free assessment builds trust; the report monetizes conviction; both inside the same
file, so discovery of the paid product is structural, not lucky.

### Secondary flows
- **Find** — discovery search: free at teaser depth (run any criteria query, see resulting parcels
  on the map), Pro at working depth (full results, saved searches, results-into-files). Every result
  is a file waiting to open.
- **The librarian** — parcel-less code-research entrance for architects/attorneys; clearly its own
  room; converges on parcels ("check this against an actual lot").
- **Shared artifacts** — shared parcel files and shared reports as the viral loop. Shared *files*
  are the marketing (each lands a stranger inside a working file, one step from the spine); shared
  conversations matter less.

### Roles
- **Chat:** the analyst inside every file + the librarian at the second desk. Never the homepage.
  Never a catch-all — answers about *this parcel* or *the code*; ambient civic curiosity remains
  possible but unsolicited. Economics align: tokens are spent on users already inside an assessment
  (the qualified ones).
- **Discovery:** the funnel's top and the subscription's reason to exist. Free at the mouth, paid
  at depth.
- **Reports:** the terminal artifact and **the only thing in the product called a "report."**
  Chat export becomes a *transcript*; CSV stays an *export*; the word "report" is reserved
  product-wide for the thing being sold. The report is also the brand's traveling salesman (every
  purchased PDF travels to a lender/partner/attorney).
- **Maps:** the file's window, not a destination. Default = the analyst's mental model (parcel,
  zoning, overlays, incentives, TOD radii); ambient layers summoned by question or toggle;
  synthesized spatial artifacts live in the report.

### Monetization structure
- **$25 per dossier** — the transactional spine, purchasable as-anonymously-as-possible at the
  moment of conviction, advertised inside every free file.
- **$99/mo Pro** — unlimited dossiers + full discovery + (later) monitoring of watched files.
  Sells *recurrence* (prospecting + portfolio), not just bulk discount.
- **Auth moves to where identity is needed** — saving, purchasing, deep chat — never the front door.
- Pricing page leads with the $25 report (the proven motion) and upsells Pro via arithmetic
  ("4 reports = a month of Pro").

### The universal test
For every future feature, screen, and sentence of copy: **does it find, open, interrogate, or sell
a parcel file?** If yes → it belongs on the spine. If no → available behind intent, off the
homepage, out of the vocabulary — or not built.

### Why this coheres
Every surface becomes a verb on the same noun. The homepage opens files. Discovery finds them.
Chat interrogates them. The map contextualizes them. The report sells them. Pro multiplies them.
Nothing needs deletion — crime/311/demographics/chat-router all remain as depth inside the file or
answers to explicit questions — but only one noun ever holds the spotlight.

---

## 9. Earlier Session-1 Outputs (kept for completeness)

Session 1 produced a structured product definition that session 2 refined but did not contradict:

- **Product Definition:** UrbanLayer is a parcel feasibility engine for Chicago that turns any
  address — typed, asked about, or discovered by search — into a decision-grade assessment of what
  can be built, what it's worth, and what it will cost, culminating in a purchasable professional
  report.
- **Primary User:** A Chicago real-estate professional (small developer first; architect and zoning
  attorney adjacent) evaluating a specific parcel before committing capital.
- **Core Workflow:** Select a parcel → instant free Scorecard assessment → interrogate via chat with
  cited municipal code → purchase the Development Feasibility Report.
- **Supporting Workflows:** Discovery (Explorer/criteria search feeding the core workflow);
  code research (parcel-less municipal-code Q&A); sharing (conversations + reports as viral channel);
  monitoring (future — watched parcels/alerts re-entering the core workflow).
- **Features That Strengthen:** Scorecard; SelectedParcel/PIN identity; municipal code RAG with
  citations; Investigate buttons; $25 a-la-carte report with PIN-bound purchase; incentives/tax/comps
  substance; Explorer's `→ /scorecard?pin=` handoff; zoning/overlay/incentive map defaults.
- **Features That Dilute:** homepage→chat routing; free chat export titled/marketed as a "report";
  default-on crime/311/permit point clouds + landing analytics/crime demos; the absent chat→Scorecard
  bridge; Explorer's paywall placement; business licenses/food inspections/vacant buildings in any
  prominent position; Spanish expansion as default feature work (north-star already flags these last
  two — still true).
- Session 1's discovery verdict (criteria search = core stage of the same funnel, answer "A") was
  upheld and deepened by session 2's "top-of-funnel AND subscription-layer simultaneously" framing.

---

## 10. Implementation Status / Open Questions

### Done (Step 1, shipped 2026-06-11 — merge `c3f68c3`, details in `archive/2026-06-11_rename-and-bridge.md`)
- **Renaming executed.** "Report" is reserved for the paid Development Feasibility Report. Chat export:
  button "Export", PDF "UrbanLayer Conversation Transcript", filename `*_transcript.pdf`. Landing copy
  no longer counterfeits — the professional-PDF sentence now points at the $25 report itself (en + es).
- **Chat→Scorecard bridge built.** `ScorecardBridgeCard` pinned at top of the Data sidebar when the
  active message resolves a parcel (`/scorecard?pin=`, `?address=` fallback); ReportTeaser fragments
  clickable in the chat sidebar; new `scorecard_bridge_click` analytics event (in backend allowlist;
  not yet charted on the admin dashboard).

### Still open (each requires fresh approval before implementation)
- **No decision on what exactly the new homepage IS** (address-input hero? combined search? where
  the librarian entrance lives?). The conceptual answer is "ask 'Which property?' and open a file in
  2 seconds" — the concrete surface design is unresolved.
- **No decision on auth placement specifics** (purchase-time? save-time? Nth chat message?).
  Direction: defer auth past the first demonstrated value.
- **No decision on Explorer free-teaser depth** (how many results free? which filters free?).
- **Map defaults unchanged** (crime/311/permit dots on, transit/TOD off — still inverted per §6).
- **Pricing page unchanged** ($99 "Recommended" lead, $25 wedge a footnote, page near-orphaned).
- **Phase 2 (customer validation) interaction:** the audit's strongest practical claim is that the
  current funnel would contaminate validation — interviewees would validate the chatbot. Step 1
  removed the counterfeit-report confusion and gave chat a route to the assessment product, but the
  homepage→auth-walled-chat entry is untouched; whether to fix the rest of the funnel BEFORE running
  the 20 interviews is a sequencing decision Jack has not made.
- **Tension with north-star to reconcile if accepted:** north-star says "hero action: a single
  address input field → Scorecard" (already aligned with this audit) but also tolerates the current
  chat-first homepage as shipped Phase 0. This audit says the Phase-0 repositioning was copy-only
  and the mechanics contradict it. If this audit's direction is accepted, north-star §4 (Product
  Narrative) should be updated, and the CLAUDE.md "killer query" line should change to an
  address-assessment example.

---

## 11. Methodology Note (for trust calibration)

All structural claims were verified by direct code inspection on 2026-06-11 (post-SelectedParcel,
main @ 292aef3): grep for all `/scorecard` links app-wide; reading `App.tsx` splash/hero/sendMessage/
handleExport; `MapView.tsx` default useState values; `ExplorePage.tsx` gating; `PricingPage.tsx`
full read; `ReportTeaser.tsx` full read; `rate_limit.py` tier limits; `auth.py` `handle_me()`
auth_required logic; en locale JSONs for landing/pages strings. Strategy context from
`strategy/north-star.md` (read in full) and `strategy/design-guidelines.md` (read in full).
Numbers like "several hundred bounce at OAuth" in the 1,000-developer thought experiment are
reasoned estimates, not measurements — there is no traffic data yet.
