# UrbanLayer North Star Product Plan

## Context

This document replaces the previous strategic analysis. It is not a code change plan -- it is a product direction document that should be committed to `claude-context/strategy/north-star.md` if accepted.

The inputs: a detailed competitive analysis of Chicago Cityscape (22K+ users, $342K ARR, 11 years of data, 160+ sources), a feature-by-feature product audit of UrbanLayer (live ~1 week, 0 paying customers, 15+ data sources, AI-powered chat + scorecard + reports), a strategic review, and a red-team challenge of that review. The user's hypothesis is that small land developers may be the ideal first customer. This document treats that as a hypothesis to validate, not a conclusion.

---

## 1. Product Manifesto

### What is UrbanLayer?

UrbanLayer is an AI-powered site feasibility tool for Chicago real estate professionals. It answers the question every developer, architect, and attorney asks before committing capital: **"What can I build here, and should I?"**

Type an address. In two seconds, get a complete property assessment: zoning classification and what it allows, regulatory overlays, tax projections, incentive eligibility, comparable sales, permit history, environmental flags, and neighborhood context. Ask follow-up questions in plain English -- the AI searches 14,000+ sections of Chicago's municipal code and synthesizes the answer with citations. Download a professional development feasibility report.

### What is UrbanLayer not?

- **Not a data portal.** We don't dump 160 data sources into a searchable table. We synthesize a smaller number of high-quality sources into actionable analysis.
- **Not a neighborhood guide.** We don't help residents decide where to live. We help professionals decide where to invest.
- **Not a lead generation tool.** We don't sell contractor lists or permit feeds. We help people evaluate sites.
- **Not a general-purpose AI chatbot.** UrbanLayer answers questions about Chicago real estate. That's it.
- **Not a cheaper Cityscape.** We are a different kind of tool. They show you data. We give you understanding.

### What problem does it solve?

Evaluating a Chicago development site requires assembling information from 5-10 separate sources: the Chicago Zoning MapServer, the Cook County Assessor, the municipal code, the city data portal, FEMA, the EPA, the Census Bureau, Walk Score, and more. A professional spends 2-6 hours per site manually toggling between government websites, reading legal text, and cross-referencing regulatory overlays. Many of these sources are confusing, poorly designed, or broken.

UrbanLayer consolidates this into a single query. The structured Scorecard delivers the facts in under 2 seconds with zero AI cost. The chat copilot delivers the analysis -- interpreting zoning rules, explaining regulatory implications, and answering questions that require reasoning over legal text. The PDF report packages it into a professional deliverable.

### Who is the ideal customer?

**Primary hypothesis: Small-to-mid-size Chicago land developers.**

These are firms or individuals doing 2-10 projects per year: infill development, teardown-and-rebuild, rehab-and-conversion, small multifamily, mixed-use. They have real capital at risk ($500K-$5M per project), make site selection decisions frequently, and currently cobble together their due diligence from multiple sources. They're pragmatic, results-oriented, and make purchasing decisions quickly.

**Why this is a hypothesis, not a conclusion:** We have zero customers and zero data on who actually converts. The adjacent segments -- architects doing zoning compliance, zoning attorneys doing code research, and commercial brokers doing property evaluation -- are equally plausible first customers. The ideal customer will be determined by who uses the product and is willing to pay for it, not by competitive analysis.

**What all viable segments share:** They evaluate specific Chicago properties for professional purposes, they need zoning and regulatory information, and they currently spend meaningful time assembling data from multiple sources.

### What outcome does the customer receive?

A complete site feasibility assessment for any Chicago address, delivered in seconds, with the ability to ask follow-up questions and download a professional report. The outcome is confidence: the professional knows what the zoning allows, what overlays apply, what incentives are available, what the tax implications are, and what risks exist -- without spending hours on manual research.

### Why would they choose UrbanLayer instead of Chicago Cityscape?

Three reasons, in order of importance:

1. **AI-powered interpretation.** Cityscape shows you the zoning class. UrbanLayer explains what the zoning class allows, what setbacks apply, whether your intended use is permitted, and what municipal code sections govern the answer -- with citations. This is the difference between seeing "RT-4" on a map and understanding what RT-4 means for your project.

2. **Instant synthesis.** Cityscape requires you to navigate to different pages for zoning, property data, incentives, and permits. UrbanLayer delivers all of it for a single address in one request, synthesized into a coherent picture.

3. **Zero learning curve.** Cityscape requires a 30-minute onboarding session because the filter interface is complex. UrbanLayer works like asking a colleague a question.

What UrbanLayer does NOT have that Cityscape does: property ownership data, pending zoning change tracking, 200K+ company profiles, 11 years of historical data accumulation, 160+ data sources, curated newsletters. The bet is that AI-powered interpretation of fewer sources is more valuable to certain professionals than a broader but raw data catalog.

---

## 2. Core Product Thesis

### The Wedge

**The development feasibility report, sold per-unit.**

This is the smallest possible version of UrbanLayer that creates undeniable value. Not a category. Not a vision. A workflow:

```
User enters an address
    → Scorecard loads instantly (free, no auth required)
    → User sees zoning, property data, incentives, tax projection, regulatory overlays
    → User sees: "Download Development Feasibility Report — $25"
    → User pays $25 via Stripe
    → User receives a professional PDF:
        zoning analysis + AI-extracted bulk standards
        comparable sales + assessment history
        incentive eligibility (TIF, OZ, EZ, tax classifications)
        PTAXSIM tax projection
        regulatory overlays + risk flags
        recommended next steps
```

Why the report and not the chat, scorecard, or explorer:

1. **It's a tangible artifact with obvious dollar value.** "I would have paid a consultant $500-1,000 for this." A chat conversation doesn't feel like a product. A scorecard feels like a free tool. A PDF report feels like a deliverable.
2. **It can be priced per-unit ($25-35).** No subscription commitment. The decision is "is this worth $25 for this specific property right now?" -- a much lower threshold than "$99/mo forever."
3. **It demonstrates the full product in one shot.** One report proves the value of every underlying system: zoning data, municipal code RAG, property data, incentives, tax projections, regulatory overlays.
4. **It naturally upsells.** After 4-5 reports at $25, the user sees: "Go Pro -- unlimited reports for $99/mo." The math makes itself obvious.
5. **It's the marketing.** A developer sends the report to a partner, lender, or attorney. They see "Generated by UrbanLayer" on the cover and visit the site.

The Scorecard is the hook (free preview of what the report contains). The chat is the engine (powers the AI analysis in the report and answers follow-ups). The Explorer feeds addresses into this workflow (find parcels → evaluate them via report). But the report is the wedge -- the thing someone pays for.

### The Two Workflows (Evaluate + Discover)

The product serves two complementary workflows, in this priority order:

**Workflow 1: Evaluate (today's wedge)**
"I found a property. Should I develop it?"
→ Scorecard + Chat + Report
→ Monetized via per-unit reports ($25) and Pro subscription ($99/mo)

**Workflow 2: Discover (tomorrow's power feature)**
"Find me properties I should evaluate."
→ Site Explorer with meaningful filters (zoning, incentive zones, lot size, vacancy, transit proximity)
→ Each discovered parcel flows into Workflow 1

The current Site Explorer (community area + property class) is too crude for professional prospecting. But the underlying data supports much richer filtering: zoning classification, incentive zone membership (OZ, TIF, EZ), assessment values, lot size from assessor data, and transit proximity from GTFS data. A version of Explorer that can answer "Show me vacant lots in an Opportunity Zone, zoned B3 or higher, within a quarter mile of a CTA station" would be genuinely unique -- Cityscape can do some of this with their Property Finder, but not with the AI-powered follow-up that UrbanLayer provides.

Discovery is not today's wedge because it requires significant filter engineering. But it should not be mentally written off. It belongs in Phase 2-3, positioned as the product's second act: first you prove people will pay for evaluation, then you build the tool that feeds the evaluation pipeline.

### If a User Only Used One Feature

**The Scorecard.**

The Scorecard is the hook. It's instant, it's free (3/day), it costs zero in API fees, and it demonstrates the product's data breadth in 2 seconds. A professional types an address they know well and sees: correct zoning classification, accurate assessment history, real TIF/OZ/EZ eligibility, actual Walk Score, real PTAXSIM tax projection. They think: "This is right. And I didn't have to visit 6 websites to get it."

The Scorecard alone doesn't convert. But it earns the right for the user to try the chat (via Investigate buttons) and consider the report (via the Download CTA). The Scorecard is the free taste. The report is the product.

### The "Holy Shit" Moment

Two moments, depending on entry point:

**For the evaluation user:** They download a $25 report for a property they're actively evaluating. The report contains AI-extracted zoning bulk standards (FAR, height, setbacks) with cited municipal code sections, comparable sales they hadn't found, an incentive program they didn't know about, and a PTAXSIM tax projection they would have had to calculate manually. Their reaction: "This would have taken me 4 hours. It cost me $25."

**For the discovery user (future):** They ask the Explorer to show vacant parcels in Logan Square with B3+ zoning in an Opportunity Zone near CTA. It returns 12 parcels they didn't know about. They click one, see the Scorecard, and download a report. Their reaction: "I just found my next project."

Both moments depend on accuracy. A wrong zoning classification or incorrect incentive eligibility destroys trust permanently. Municipal code RAG accuracy is the single highest-priority engineering investment.

---

## 3. Feature Audit

### Core (These ARE the product)

| Feature | Why Core |
|---------|----------|
| **Scorecard** | The hook. Instant, free, zero API cost. Demonstrates the product's value in 2 seconds. Every user journey should start or pass through here. |
| **Chat / AI Copilot** | The differentiator. This is what Cityscape cannot do. Reasoning over municipal code, cross-referencing regulatory overlays, answering "can I build X here?" in plain English. Without this, UrbanLayer is just a worse Cityscape with fewer data sources. |
| **Municipal Code RAG** | The moat. 14,535 chunks from 8,615 sections of Chicago's municipal code, searchable via natural language with citations. Nobody else has this. If this breaks, the product has no reason to exist. |
| **Zoning Data** | The foundation. Zoning classification, overlays, TOD, landmark, historic district, PMD -- all 14+ layers. This is what every target persona needs first. |
| **Incentives** | The money question. TIF, OZ, EZ, SBIF, NOF, tax incentive classifications. Developers and attorneys need this for every deal. UrbanLayer currently covers ~10 programs; expanding to 20-25 is high-leverage. |
| **Property Data** | The comps. Assessments, sales history, building characteristics, PTAXSIM tax projections. Essential for financial feasibility. Comparable sales should be more prominent. |
| **PDF Reports** | The conversion mechanism. The moment a professional needs to produce a deliverable (for a client, investor, or lender), they need the PDF. This is where free users become paying users. |

### Supporting (Enhance the core but don't lead)

| Feature | Why Supporting | Recommendation |
|---------|---------------|----------------|
| **Maps** | Provide spatial context. A map showing where the property is, what's zoned around it, and where nearby permits/violations/crime occurred adds understanding. But the map is not the product -- it's context for the analysis. | Keep. Maps are expected. Don't invest in making them the hero. |
| **Regulatory Overlays** | FEMA flood, EPA brownfields, ARO, pedestrian streets, lakefront protection -- all important for compliance. But they're binary flags (present/absent) that should be summarized on the Scorecard, not explored interactively. | Keep. Already integrated well as status badges on the Scorecard. |
| **Permit Data** | Useful context: what's been built nearby, who the contractors are, what the construction costs were. Helps developers understand the development trajectory of an area. | Keep, but don't feature as primary. It's background intelligence. |
| **Investigate Buttons** | The bridge between structured data and AI reasoning. This is a novel UX pattern that makes the chat feel like a natural extension of the dashboard, not a separate feature. | Keep. This is the mechanism that converts Scorecard users into Chat users. |
| **Shared Links** | Viral distribution. When a developer shares a conversation link with a colleague, that colleague sees UrbanLayer in action. The "Try UrbanLayer" CTA on shared views is the best possible marketing. | Keep. Polish the shared view to be professional and branded. |
| **Conversation Persistence** | Expected by any chat-based tool. Users need to revisit past research. | Keep. Already works. |
| **Auth / Payments / Rate Limiting** | Infrastructure. Required for revenue. | Keep. Already works. |

### Future (Build when customer demand validates)

| Feature | When to Build | Signal to Watch |
|---------|--------------|-----------------|
| ~~**Incentives Expansion**~~ | **DONE (2026-06-10).** ~14 programs: Class 6b/6c/7a/7b/7c/8, QCT, NMTC, TIF, EZ, OZ, SBIF, NOF. Further expansion paused until customer demand. | Shipped. |
| **Property Tracker Alerts** | Phase 3-4. Watch addresses for new violations/permits/assessment changes. Email notifications. | Users returning daily to check the same properties. |
| **Comparable Sales Enhancement** | Phase 1-2. Already partially in PDF v3. Surface comps on the Scorecard as a visible section, not just buried in the report. | Users asking about nearby sales or property values. |
| **Contractor Intelligence** | Phase 4+. Parse permit contacts to identify projects missing specific trades. | Subcontractor interest in the product (different persona). |
| **Pending Zoning Changes** | Phase 4+. LLM PDF extraction from Legistar. High effort, high value. | Attorneys or developers asking about pending applications. |
| **Site Explorer Enhancement** | Phase 2-3. Add filters: zoning classification, incentive zones (OZ/TIF/EZ), lot size, assessment value, vacancy, transit proximity. Transform from demo feature into genuine prospecting tool. The query "Show me vacant lots in an OZ, zoned B3+, near CTA" would be unique in the market. | Developers asking "can I search for parcels with [specific criteria]?" This is the product's second wedge after per-unit reports are proven. |
| **Zoning Alert Monitoring** | Phase 4+. Cron-diff the municipal code HTML. | Users asking "will the zoning change?" Municipal code changes are infrequent (~2-3 times/year on relevant topics). Don't build this early; it fires too rarely to justify the investment. |
| **API Access** | Phase 4+. REST API for power users and firms. | Multiple users asking for programmatic access. |
| **Team Accounts / Enterprise** | Phase 4+. Shared billing, admin controls. | A firm with 3+ people wanting to use the product. |
| ~~**A La Carte Report Sales**~~ | ~~Phase 0-1.~~ **DONE (2026-06-09).** $25 one-time Stripe checkout. See `archive/2026-06-09_a-la-carte-reports.md`. | Shipped. |
| **One-Time Scorecard Purchase** | Phase 2. Pay $5-10 for a single premium Scorecard (comps, full assessment, tax projection) without subscribing. | Users who hit the 3/day free limit but don't want monthly commitment. |

### Distraction (Confuses the narrative or serves the wrong market)

| Feature | Why It's a Distraction | Recommendation |
|---------|----------------------|----------------|
| **Crime Data as a primary feature** | Crime analytics (MoM trends, arrest rates, crime density) serve the resident/neighborhood-explorer use case, not the development feasibility use case. A developer cares about crime insofar as it affects property values and insurance costs, but they don't need interactive crime type filtering, arrest rate charts, or date range sliders. | **Demote.** Keep crime data flowing through the Scorecard as a summary (YoY totals, high-level safety context) and available via chat. Remove crime as a landing-page feature. Don't feature crime analytics prominently on the Scorecard. |
| **311 Data as a primary feature** | Same issue. 311 data is useful as a property health signal (address-level complaints = due diligence red flag), but interactive 311 analytics (department breakdown, status filters, trend tables) serve neighborhood exploration, not site feasibility. | **Demote.** Keep address-level 311 as a property health flag on the Scorecard. Remove 311 from the landing page narrative. |
| **Business Licenses** | "What businesses are nearby?" is a neighborhood exploration question, not a development feasibility question. A developer evaluating a site doesn't care about the nearby restaurant's license status. | **Demote.** Keep in the chat pipeline (the AI can reference it when relevant), but remove from Scorecard and landing page. |
| **Food Inspections** | A food inspection database has nothing to do with site feasibility. This is a leftover from the "know your neighborhood" positioning. | **Demote.** Keep in chat pipeline, remove from any prominent position. |
| **Vacant Buildings** | Marginally relevant (a vacant building next door is a risk signal). But it's a niche dataset that doesn't drive purchasing decisions. | **Demote.** Keep in chat pipeline. |
| **Site Explorer (in current form)** | The concept is right (find candidate sites) and the long-term potential is high -- "find underutilized parcels with favorable zoning and incentive eligibility" could become the product's most valuable workflow. But the current implementation (community area + property class only) is too crude for professional prospecting. It needs zoning filters, incentive zone filters, lot size, vacancy, and transit proximity before it becomes a genuine prospecting tool. | **Keep and plan to invest.** Don't feature as a primary selling point today. Do position it as a Phase 2-3 power feature. The underlying data (Parcel Universe, zoning overlays, incentive boundaries, GTFS stations) already exists in the backend -- the gap is filter UI and query composition. This is the product's "second act" after evaluation is proven. |
| **Spanish Language** | Chicago has a large Spanish-speaking population, including bilingual contractors, developers, and property owners. The current translations are functional and cost nothing to keep running. However, maintaining and expanding translations for every new feature adds friction to development velocity. | **Maintain, don't expand.** Keep what's built. Don't add new translated strings as a default part of feature work. Don't remove the language selector. If Spanish-speaking users emerge as a meaningful segment during customer validation, revisit and invest. This is a low-confidence call either direction -- watch for signal. |
| **"The Resident" Persona** | The landing page currently targets "The Investor, The Business Owner, The Resident." The Resident is a consumer, not a professional. Consumers don't pay $99/mo. Including them dilutes the B2B positioning and confuses the message. | **Remove from landing page.** UrbanLayer can still answer neighborhood questions via chat -- but don't market to residents. |

### Remove (Actively hurts the product's coherence)

Nothing currently built needs to be deleted from the codebase. Everything that exists works and doesn't cost anything to keep running. The issue is not features that exist -- it's features that are prominently positioned despite not serving the core thesis.

"Remove" means: **remove from the product narrative, landing page, and primary navigation.** Not from the codebase.

---

## 4. Product Narrative

> **SHIPPED (2026-06-12, coherence-audit step 3).** The homepage now matches this section: hero is a
> single address-autocomplete input ("Site feasibility for any Chicago address. In seconds.") that
> opens `/scorecard?address=` — no account, no payment, no conversation required. The code-research
> chat (the "librarian") is a secondary entrance behind a quiet link that swaps the hero input.
> Persona cards route by intent (Developer/Attorney → Scorecard, Architect → librarian chat).
> The auth wall is off the front door: anonymous chat works at 3/day (IP), with sign-in asked at
> save/share/purchase/rate-limit. See `product-coherence-audit.md` §10 for details.

### What the Homepage Should Communicate (60 seconds)

**Headline:** "Site feasibility for any Chicago address. In seconds."

**Subheadline:** "Zoning, tax projections, incentives, regulatory overlays, comparable sales, and municipal code analysis -- all from one search."

**Hero action:** A single address input field. Type an address, hit enter, see the Scorecard. **(Shipped.)**

**Social proof section (when available):** "Used by X developers and architects for site due diligence."

**Three value props:**
1. **"Know what you can build."** Instant zoning classification with AI-powered code interpretation. Ask what's allowed, what the setbacks are, what FAR applies -- get cited answers from 14,000+ municipal code sections.
2. **"Know what it's worth."** Assessment history, comparable sales, PTAXSIM tax projections, and incentive eligibility. The financial picture for any address.
3. **"Know what to watch for."** Regulatory overlays, environmental flags, building violations, and permit history. The risks and opportunities you need to see before committing capital.

**Persona scenarios (replace current three):**
1. **"The Developer"** — "Can I build a 6-unit residential building at 4520 N Clark St?" → Returns: zoning analysis, bulk standards, overlay compliance, incentive eligibility, tax projection, comparable sales, development feasibility report.
2. **"The Architect"** — "What are the setback requirements for a mixed-use building in B3-2 adjacent to an RS-3 district?" → Returns: cited municipal code answer with specific dimensions, transition zone rules, parking requirements.
3. **"The Attorney"** — "Is the property at 2400 N Milwaukee Ave eligible for a Class 6b tax incentive?" → Returns: property class analysis, incentive eligibility check, TIF district status, applicable programs.

All three personas click the scenario and see a real answer. Each scenario leads into the product.

**Below the fold:** How it works (3 steps: Ask → See → Download). Data sources. Pricing. Footer.

### What a Product Demo Should Communicate

A 5-minute demo should follow this script:

1. **(0:00-0:30)** Type a real Chicago address. Scorecard loads instantly. "This is everything you'd spend an hour assembling from 6 different websites."
2. **(0:30-1:30)** Walk through the Scorecard: zoning, overlays, property data, tax projection, incentives, crime summary, violations. "All real-time data. No AI cost. Loads in under 2 seconds."
3. **(1:30-3:00)** Click "Investigate" on the zoning label. Chat opens with a pre-populated question. AI responds with cited municipal code sections explaining the zoning rules. "This is what nobody else can do. The AI has read the entire municipal code and can explain it in plain English."
4. **(3:00-4:00)** Ask a follow-up: "What if I wanted to build a 4-story mixed-use building here?" AI responds with FAR analysis, height limits, and parking requirements with code citations.
5. **(4:00-5:00)** Download the PDF report. "This is a professional deliverable you can hand to a client or include in a pitch deck. $99/mo for unlimited reports, or $25 for a single report."

### What the First Successful User Experience Should Be

The user types an address they know well -- their own property, a project they're evaluating, a building they drive past every day. The Scorecard loads and shows them something they already know to be true (correct zoning, correct assessment). This builds trust. Then they see something they didn't know (a TIF district they weren't aware of, an incentive they hadn't checked, a violation on an adjacent property). This creates value. Then they click "Investigate" and the AI explains the zoning in a way that would have taken them 20 minutes to look up manually. This creates conversion intent.

The first successful experience is: **"This is right, and it told me something I didn't know."**

---

## 5. Development Phases

### Phase 0: Product Focus + First Wedge (1-2 weeks)

**Goal:** Align the product with site feasibility positioning AND ship the revenue wedge (a la carte report sales).

**Build:**
- ~~**A la carte report purchase.**~~ **DONE (2026-06-09).** Stripe one-time $25 checkout, `report_purchases` table, Scorecard shows "Download Report — $25" for free users, auto-download after purchase. See `archive/2026-06-09_a-la-carte-reports.md`.
- ~~**Landing page repositioning.**~~ **DONE (2026-06-08).** Rewrote hero subtitle, value props (Build/Worth/Watch), personas (Developer/Architect/Attorney), story sections, intelligence stack (reordered, "Safety" → "Due Diligence Signals"), suggestion chips. Removed NeighborhoodExplorer from landing page. Added ValueProps section. Hero slideshow tint matched to story sections.
- ~~**Elevate comparable sales, incentives, and tax projections on the Scorecard.**~~ **DONE (2026-06-09).** `ComparablesCard` (median price, $/sqft, sales volume, expandable recent sales table), expanded `IncentivesCard` (TIF financials + grant programs), `FinancialSnapshotStrip` above card grid (assessed value, annual tax, median comp sale, TIF balance, active incentive zone count). `ReportTeaser` nudges embedded in PropertyCard, ComparablesCard, and IncentivesCard.
- ~~**Make the "Download Report" CTA unmissable on the Scorecard.**~~ **DONE (2026-06-09).** `ReportCTACard` with feature checklist placed prominently above the card grid, sticky bottom CTA bar that appears when main CTA scrolls out of view, "$25" buy button for free users with purchase modal flow.

**Ignore:**
- New data sources
- New backend features beyond a la carte payments
- Spanish language updates
- Site Explorer improvements
- Zoning alerts

**Success Metrics:**
- A la carte report purchase flow works end-to-end (Stripe → PDF download)
- Landing page clearly communicates "site feasibility for Chicago professionals" within 5 seconds
- A developer friend or acquaintance can describe what UrbanLayer does after visiting the homepage
- The Scorecard → Report flow has zero friction

**Phase 0 Status: COMPLETE (2026-06-09).** All build items shipped. Exit criteria met: a la carte $25 report purchase works end-to-end, landing page communicates site feasibility positioning, Scorecard prominently surfaces comps/incentives/tax projections with unmissable report CTA.

### Phase 1: Demoable Product — COMPLETE (2026-06-10)

All build items shipped. RAG at 100% A/B. Incentives at ~14 programs (Class 6b/6c/7a/7b/7c/8, QCT, NMTC, TIF, EZ, OZ, SBIF, NOF). Report V5 shipped with synthesis intelligence, envelope visualization, and approval pathway. Comps on Scorecard, a la carte reports, landing page — all done.

### Phase 1.5: Observation Infrastructure (NEW — 2026-06-10)

**Goal:** Before customer conversations, instrument the product so engagement data flows. Without this, customer validation (Phase 2) is qualitative-only.

**Build:**
- ~~**Usage analytics (4 events).**~~ **DONE (2026-06-10).** `page_view`, `investigate_click`, `report_cta_click`, `chat_message_sent`. Schema v10, fire-and-forget ingestion, admin dashboard with engagement section.
- **Title 14A re-ingestion.** Parser regex already fixed. Run `python -m ingestion.update` to add ~500+ building code sections to the index. ~30 minutes.

**Exit Criteria:** Events flowing in production, admin dashboard shows engagement metrics, Title 14A sections indexed.

### Phase 2: Customer Validation (4-6 weeks)

**Goal:** Determine who the actual first customers are and whether they'll pay.

**Sequencing decision (2026-06-12):** the homepage/auth fix (coherence-audit step 3) lands BEFORE
these interviews. The audit's claim was that the old entry (auth-walled chat) would make
interviewees validate the chatbot rather than the feasibility product; with the address-first
homepage shipped, interviewees now enter through the product being validated.

**Build:**
- Nothing new at the start. Spend the first 2 weeks on customer conversations, not engineering.
- After 10+ conversations, build the 1-2 features most frequently requested. These might be:
  - More incentive programs
  - Better comparable sales
  - Property ownership data (consider a per-lookup scraping approach if the use case is strong)
  - Specific zoning comparison queries
  - Something you haven't anticipated
- ~~**Analytics.**~~ **DONE (2026-06-10).** Moved to Phase 1.5 and shipped: 4 events, admin dashboard, hypothesis-driven design. See Phase 1.5.

**Conversations to Have:**
- 5 small developers (find via LinkedIn, local RE meetups, ULI Chicago)
- 5 architects (AIA Chicago chapter, architecture firms' websites)
- 5 zoning attorneys (Chicago Bar Association Real Property committee)
- 5 commercial brokers or appraisers (CCIM, local brokerage firms)

**Script for Each Conversation:**
1. "Walk me through how you evaluate a new site/property."
2. "What tools do you currently use? What frustrates you about them?"
3. [Show them UrbanLayer] "Here's what we built. Type in an address you know."
4. [Watch, don't explain] Note what they click, what they ignore, what they ask about.
5. "Would you use this in your work? What would need to change?"
6. "If this cost $99/mo, would you pay for it? What about $25 per report?"

**Ignore:**
- Any feature that isn't directly requested by 3+ interviewees
- Scaling infrastructure
- Geographic expansion
- Enterprise features

**Success Metrics:**
- 20 customer conversations completed
- Clear pattern in which segment has the highest pain and shortest decision cycle
- At least 5 people signing up for free accounts during or after conversations
- At least 2 people expressing unprompted willingness to pay

**Exit Criteria:** You can answer: "Who is my customer, what do they need, and will they pay?" with evidence, not assumptions.

### Phase 3: First Paying Customers (4-8 weeks)

**Goal:** 10 paying users (reports + subscriptions). $1K+ MRR. Prove the business model works.

**Build:**
- The features validated in Phase 2 conversations
- Conversion optimization: analyze where free users drop off, what triggers upgrades, what the a la carte vs. subscription split looks like
- Content marketing: create 3-5 pieces of content (blog posts or video demos) analyzing specific Chicago properties or zoning scenarios using UrbanLayer. Demo videos are high-leverage -- the product demos beautifully.
- Referral mechanism: when a user shares a conversation link or a report, the recipient sees UrbanLayer branding + "Generate your own" CTA

**Ignore:**
- Features for personas that didn't validate in Phase 2
- Geographic expansion
- Enterprise/team features
- Infrastructure optimization

**Success Metrics:**
- 10+ paying customers (reports + subscriptions combined)
- Number of a la carte reports sold (proxy for "undeniable value per use")
- Conversion rate from report buyer to subscriber (proxy for "recurring value")
- At least 3 customers who independently describe UrbanLayer as "essential" or "saves me hours"

**Exit Criteria:** The product generates revenue from customers who would be upset if it disappeared. You can articulate: "My customer is [X], they pay for [Y], and the value is [Z]" based on evidence.

### Phase 4: Product Expansion (3-6 months)

**Goal:** 50+ paying users. $5K+ MRR. Expand the product based on validated demand.

**Build (based on Phase 3 signals):**
- **Site Explorer enhancement** (the second wedge): Add zoning filters, incentive zone filters, lot size, vacancy, transit proximity. Transform Explorer from a demo into a genuine prospecting tool. The goal: "Find me parcels that match [criteria]" → each result flows into the evaluate-and-report workflow. This could become the product's most valuable feature.
- Incentives expansion to 25-30 programs
- Property tracker alerts (retention feature: watch properties, get email notifications)
- Contractor intelligence (if subcontractor interest materialized)
- Pending zoning changes (if attorneys are a significant customer segment)
- Team accounts (if firms are requesting shared access)

**Evaluate:**
- Pricing: is $99/mo right, or should it be $149 or $199?
- Hiring: is it time for a part-time sales/marketing person?
- Fundraising: is this a venture-scale opportunity or a profitable lifestyle business?

**Success Metrics:**
- $5K+ MRR
- Net revenue retention >100% (existing customers spending more over time)
- Product is mentioned in at least one Chicago real estate community (Crain's, RE meetup, bar association)

**Exit Criteria:** Sustainable business with clear growth trajectory and product-market fit.

---

## 6. Customer Validation Plan

### When is the product mature enough to show customers?

**Now.** The product is already live at urbanlayerchicago.com. It has a Scorecard, Chat, PDF Reports, maps, and auth/payments. It works. The question is not "is it ready?" -- it's "will anyone pay for it?"

What should happen before showing it:
- ~~Phase 0 (landing page repositioning)~~ **DONE.** Landing page repositioned for site feasibility. Scorecard elevated with comps, incentives, financial snapshot, and report CTA.
- ~~Municipal Code RAG accuracy spot-check~~ **DONE (2026-06-09).** 28-query retrieval benchmark at 100% A/B. Pipeline v5 with synonym expansion + keyword-aware dedup.

### What should exist before conducting interviews?

- A working Scorecard with accurate zoning, property, and incentive data
- A chat that correctly answers common zoning questions with citations
- A PDF report that looks professional
- A clear landing page that communicates the value prop
- The ability to create a free account and use the product

All of this exists today.

### What should exist before asking for money?

- Stripe payment flow (already exists)
- ~~A la carte report purchase option~~ **DONE (2026-06-09)**
- ~~Confidence that the municipal code RAG is accurate enough for professional use (eval at 95%+)~~ **DONE (2026-06-09).** 100% A/B on 28-query benchmark.
- A pricing page that makes the value clear (already exists)

### What should exist before launching publicly?

- 10+ paying customers who validate the product
- A clear understanding of which persona converts
- Content (blog posts, demo videos) that can drive organic traffic
- ~~Basic usage analytics~~ **DONE (2026-06-10).** 4-event analytics system with admin dashboard.
- Confidence in the infrastructure under moderate load

---

## 7. Founder Reality Check

### The Biggest Risks

1. **Building in a vacuum.** The product has been live for a week with zero paying customers. Every strategic decision so far is based on competitive analysis and feature logic, not customer behavior. The risk is spending months perfecting features that nobody asked for. **Mitigation: Start customer conversations in the next 7 days.**

2. ~~**Municipal Code RAG accuracy.**~~ **MITIGATED (2026-06-09).** Retrieval benchmark improved from 75% to 100% A/B (28 queries). Pipeline v5 with synonym expansion, keyword-aware dedup, incremental update infra. Title 14A building code parser fixed (re-ingestion pending). Remaining risk: queries outside the benchmark may still fail — continue expanding benchmark coverage.

3. **Cityscape adds AI.** Adding a Claude/GPT wrapper to an existing data platform with 160+ sources is trivially easy. If Cityscape ships an "Ask AI" button, UrbanLayer's primary differentiator weakens dramatically -- they'd have AI PLUS 11 years of data. **Mitigation: Build depth, not just breadth. Your advantage isn't "we have AI" -- it's "our AI deeply understands Chicago's municipal code in a way a wrapper over raw data can't." The 14,535 chunks, section-aware chunking, cross-reference expansion, and blended reranking create search quality that a naive RAG-over-Cityscape-data can't match. But this is a wasting advantage -- they will close the gap eventually.**

4. **The market is smaller than it looks.** "Chicago real estate professionals who evaluate sites" is a finite market. If it's 2,000 people and 5% convert at $99/mo, that's $120K ARR. Enough for a lifestyle business, not enough for a venture-scale outcome. **Mitigation: This is fine. Not everything needs to be venture-scale. A $120K-$300K ARR business run by one person is an excellent outcome. Size the ambition to the market.**

5. **Token costs eat margins.** Every chat query costs $0.02-0.10 in Anthropic API fees. At 3 free queries/day for anonymous users, the costs can add up quickly. **Mitigation: The Scorecard is zero API cost. Push users toward Scorecard first, Chat second. Monitor token costs per user closely.**

### The Biggest Distractions

1. **Feature engineering before customer validation.** The temptation is to build zoning alerts, contractor intelligence, incentives expansion, and pending zoning changes before anyone has asked for them. Resist. Talk to 20 potential customers first. Build what they ask for, not what competitive analysis suggests.

2. **Geographic expansion.** The entire pipeline is Chicago-specific. Every conversation about "when do we expand to other cities?" is a distraction from making Chicago work. There is no second city until Chicago has $30K+ MRR.

3. **Enterprise sales.** Team accounts, custom pricing, onboarding sessions, API access -- all premature. Get individual users paying before building for teams.

4. **Perfecting features nobody uses.** Crime analytics with arrest filters, date range sliders, and trend tables are impressive engineering. But if the target customer is a developer evaluating a site, they need a 3-line crime summary, not an interactive dashboard. Don't polish what should be demoted.

5. **Spanish language maintenance.** Every new feature means updating 7 JSON translation files. For zero paying Spanish-speaking customers. Stop.

### The Biggest Opportunities

1. **A la carte report sales as the first wedge.** Selling individual PDF reports for $25-35 is the fastest path to first revenue AND the fastest way to validate product-market fit. Every report sold is a signal: someone valued the analysis enough to pay for it. It requires no subscription commitment, it's easy to market ("Get a development feasibility report for any Chicago address for $25"), and it naturally upsells to Pro ($99/mo for unlimited).

2. **Site Explorer as the second wedge.** Discovery workflows ("find me properties to evaluate") are potentially more valuable than evaluation workflows ("evaluate this property I found"). If Explorer can be enhanced with zoning, incentive zone, lot size, and transit proximity filters, it becomes a unique prospecting tool that feeds the report workflow. This is Phase 2-3, not Phase 0-1, but it should be on the mental roadmap as the product's second act.

3. **Demo-driven marketing.** The product demos beautifully. A 2-minute video of someone typing an address and getting a complete feasibility assessment -- with AI explaining the zoning code -- would be the most compelling marketing asset possible. This is cheaper and more effective than any other marketing channel.

4. **The architect segment.** The red-team review identified architects as potentially the best first customer: they check zoning compliance on every project, they're more tech-forward than attorneys, they adopt tools faster, and they have a clear daily workflow UrbanLayer serves. The AIA Chicago chapter is a direct acquisition channel. This segment deserves dedicated attention in customer validation.

5. **Municipal Code expertise as positioning.** "The only tool that can search Chicago's 14,000+ municipal code sections in natural language" is a concrete, defensible, and compelling claim. This is the technical moat. Even if Cityscape adds AI, a naive wrapper over their data won't match section-aware chunking with cross-reference expansion and blended reranking.

6. **Appraisers during tax appeal season.** Cook County property tax appeals are a massive industry with a predictable annual cycle. Appraisers need comparable sales, assessment history, and tax projections -- exactly what the Scorecard provides. Worth investigating during customer validation.

### The Fastest Path to Proving the Product Has Value

1. ~~**This week:** Spot-check 10 common zoning questions against the municipal code RAG.~~ **DONE (2026-06-09).** 28-query benchmark at 100% A/B.
2. ~~**This week:** Ship a la carte report purchase ($25-35 via Stripe).~~ **DONE (2026-06-09).**
3. **Next week:** Send the product to 5 people you know in Chicago real estate (developers, architects, attorneys, brokers). Don't explain it. Give them the URL and watch what they do. Ask: "Would you pay $25 for this report?"
4. ~~**Next 2 weeks:** Rewrite the landing page per Phase 0.~~ **DONE (2026-06-08).**
5. **Next 4 weeks:** Have 15-20 conversations with potential customers per the Phase 2 script.
6. **By week 6:** You should know whether this product has commercial potential, who the customer is, and what they'll pay for.

**The kill metric:** If, after 20 conversations and 6 weeks, nobody has paid for a report or subscribed to Pro, the hypothesis is wrong and you need to pivot. Not add features -- pivot. More features on a product nobody will pay for is the most common way startups die.

**The validation metric:** If 3+ people independently buy a report without being prompted, the product has value. Double down on whatever segment those buyers came from.

### Uncomfortable Truths

~~**The current landing page tells three different stories.**~~ **RESOLVED (2026-06-08).** Landing page repositioned with Developer/Architect/Attorney personas, site feasibility value props (Build/Worth/Watch), and professional narrative. NeighborhoodExplorer removed from landing page.

**Crime and 311 analytics are the wrong lead.** The interactive crime and 311 dashboards (date sliders, arrest filters, trend tables, pie charts) are the most visually impressive features -- and the least relevant to the paying customer. They say "explore your neighborhood" when the product should say "evaluate your next investment." These features aren't bad. They're just in the wrong position in the product hierarchy.

**The product is broader than it needs to be.** 96 frontend TypeScript files, 7 i18n translation namespaces, a landing page with 14 components, admin dashboard, about page, pricing page, scorecard, explorer, chat, shared views, mobile bottom sheet -- this is a LOT of surface area for a product with zero customers. Every additional feature is additional maintenance burden, additional things that can break, and additional cognitive load for the user. The answer is not to delete things, but to ruthlessly prioritize which features are in the spotlight.

**You don't know who your customer is yet.** This is the most important truth. "Small land developers" is a plausible hypothesis. So is "architects." So is "zoning attorneys." So is "commercial brokers." So is "nobody -- the product is a solution looking for a problem." The only way to find out is to put it in front of people and observe. Not ask them what they think. Observe what they do.

---

*This document should be committed to `claude-context/strategy/north-star.md` if accepted. The existing `product-roadmap.md` and `competitive-analysis.md` should be updated to reflect these decisions. The first action item is Phase 0: rewrite the landing page.*
