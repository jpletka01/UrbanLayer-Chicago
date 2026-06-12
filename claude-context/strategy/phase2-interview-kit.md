# Phase 2 Interview Kit — Customer Validation (2026-06)

Operational companion to `north-star.md` Phase 2. That document owns the strategy (goals, metrics,
kill/validation criteria); this one owns the practice: recruiting, the expanded script, what to
observe, how to log, and the demo-day gotchas verified against production on 2026-06-12.

**The question these interviews answer:** "Who is my customer, what do they need, and will they
pay?" — with evidence, not assumptions. Per the audit's sequencing decision, the address-first
homepage shipped first, so interviewees now enter through the feasibility product being validated,
not the old auth-walled chat.

**Numbers that govern (from north-star, repeated here so the kit is self-contained):**
- 20 conversations: 5 developers, 5 architects, 5 zoning attorneys, 5 commercial brokers/appraisers.
- Success: clear highest-pain segment; 5+ free signups during/after; 2+ unprompted willingness to pay.
- **Kill metric:** after 20 conversations and 6 weeks, nobody has paid → pivot, don't add features.
- **Validation metric:** 3+ unprompted report purchases → double down on that segment.
- Discipline: build nothing during the first 2 weeks; afterwards only what 3+ interviewees requested.

---

## 1. Recruiting

### Channels by segment
| Segment | Where to find them | Angle |
|---|---|---|
| Small developers (2–10 projects/yr) | ULI Chicago events, LinkedIn ("real estate developer Chicago" + infill/multifamily keywords), local RE meetups, past permit applicants (public data — permits list owners/contractors) | "How do you evaluate a site before committing capital?" |
| Architects | AIA Chicago chapter directory/events, firm websites (small firms doing residential/mixed-use — they self-perform zoning checks; big firms have specialists) | "How do you handle zoning compliance research?" |
| Zoning attorneys | Chicago Bar Association Real Property Law committee, firms appearing in ZBA/Plan Commission minutes (public) | "How do you research code questions and incentive eligibility?" |
| Brokers / appraisers | CCIM Chicago chapter, local brokerage firms; appraisers via tax-appeal angle (Cook County appeal season is a predictable annual cycle — north-star opportunity #6) | "How do you assemble property data for an evaluation?" |

### Outreach template (cold, LinkedIn/email — adapt per segment)
> Hi [name] — I'm a Chicago software developer building a site-feasibility tool for [segment]
> professionals, and I'm doing research conversations before going further. I'm NOT selling
> anything. I'd like 30 minutes to hear how you evaluate a [site / project / property] today —
> what you use, what wastes your time. In exchange I'll show you what I've built (instant
> zoning/tax/incentive assessment for any Chicago address) and you can keep using it free.
> Would a 30-minute call [or coffee] in the next two weeks work?

Notes: lead with research, not product. "Keep using it free" is the honest carrot. Warm intros
beat cold outreach — start with anyone Jack already knows in Chicago RE (north-star "fastest path"
step 3: send the URL to 5 acquaintances and watch what they do, before formal interviews).

### Logistics
- 30–40 min, video call with screen share **where the interviewee drives**, or in person on their
  laptop. Their machine, their account state (anonymous) — the funnel is part of what's being tested.
- Aim for 3–4/week; 20 takes 5–6 weeks. Book segment-diverse weeks rather than 5 developers in a row,
  so cross-segment patterns surface early.

---

## 2. Script (expanded from north-star Phase 2)

Timing for a 35-minute call. The north-star 6 questions are the spine; don't skip any.

### Part A — Their world (10 min, product hidden)
1. "Walk me through the last time you evaluated a new site/property. Start to finish."
   - Probe: How long did it take? Which websites/tools? What did you pay for?
2. "What tools do you currently use? What frustrates you about them?"
   - Probe: Chicago Cityscape? (subscriber? lapsed? why?) Assessor site? Zoning map? A paid consultant?
   - Probe: "What's the most recent piece of information that was hard to get?"
3. Segment-specific:
   - **Developer:** "What kills a deal at the due-diligence stage? Have you ever missed something
     (overlay, incentive, tax) that cost you?"
   - **Architect:** "Who does the zoning compliance check on your projects? How long does a code
     question take to resolve? What happens when the code is ambiguous?"
   - **Attorney:** "How do you research a code or incentive-eligibility question today? Do you bill
     that research time? What does a client pay for a feasibility opinion?"
   - **Broker/appraiser:** "What goes into a property evaluation package? Where does the data come
     from? How much of it is copy-paste assembly?"

### Part B — Live session (15 min, watch, don't explain)
4. Share the URL (urbanlayerchicago.com), say only: **"Here's what we built. Type in an address you
   know."** Then be quiet. Use the observation checklist (§3). Resist narrating — every explanation
   contaminates the "zero learning curve" claim.
   - If they stall, the one permitted nudge: "What would you want to know about this property?"
   - Let them hit walls (rate limit, sign-in asks, confusing labels). Walls are data.
5. After ~10 minutes of free exploration: "Would you use this in your work? What would need to
   change?" — then "What's missing that you expected to see?" (the strongest feature-signal question).

### Part C — Money (5–10 min)
6. "If this cost $99/mo, would you pay for it? What about $25 for a single report?"
   - Probe past the polite yes: "What would you have to believe to actually expense this?"
   - "Who else at your firm would use it? Who approves a $99/mo tool?"
   - If they're warm: show the $25 report CTA on the Scorecard and ask "would you buy this for the
     property you just looked up?" — and if yes, **let them**. An actual purchase is the validation
     metric; never comp it preemptively.
7. Close: "Who else should I talk to?" (referral chain) + permission to follow up.

---

## 3. Observation checklist (fill during Part B)

Record behavior, not opinions:
- [ ] First address typed: own property / active deal / curiosity address?
- [ ] Used autocomplete or typed free-text? Hesitated at the hero?
- [ ] Noticed/used the "Try:" chips or persona cards, or went straight to input?
- [ ] First-load wait reaction (cold loads can take 10–20s — see §5): patient / confused / refreshed?
- [ ] First Scorecard card they read; cards they scrolled past without stopping.
- [ ] Did they verify accuracy against what they know? Quote any "that's right" / "that's wrong" verbatim.
- [ ] Clicked Investigate? Which card? Did they understand it opens chat?
- [ ] Used chat at all? Read citations? Clicked a code section?
- [ ] Noticed the $25 report CTA unprompted? Reaction?
- [ ] Hit any wall (429 rate limit, sign-in ask, error)? What did they do next?
- [ ] What they asked YOU to explain (each one is a UX failure to log).
- [ ] The one moment their energy visibly rose (or never did).

---

## 4. Per-interview log (write within 1 hour, while fresh)

```markdown
## [DATE] — [Name], [Segment], [Firm/context]
**Current workflow:** (tools, hours per evaluation, what they pay for today)
**Frustrations (verbatim quotes):**
**Live session:** address(es) tried, path taken, walls hit, accuracy reactions (verbatim)
**Feature asks (their words, not my interpretation):**
**Pricing:** $99/mo reaction / $25 report reaction / what they'd need to believe
**Bought a report or signed up?** yes/no — prompted or unprompted?
**Pain score (1–5):** how acute is the problem for THEM
**Likelihood-to-pay score (1–5):** my honest read, not their politeness
**Referrals:**
**One-sentence takeaway:**
```

Keep logs in a private folder (not this repo — they contain names). Suggested:
`~/urbanlayer-interviews/`. After every 5 interviews, write a rollup: feature-ask tally
(the "3+ requests" build threshold), pain/pay scores by segment, accuracy incidents.

---

## 5. Demo-day operations (verified against prod 2026-06-12)

**Pre-flight (15 min before each call):**
1. `curl -s https://urbanlayerchicago.com/health` → `{"ok":true,"qdrant":true,"db":true}`.
2. Pre-warm the persona/demo addresses (one Scorecard GET each): 4520 N Clark St,
   2400 N Milwaukee Ave, 1425 N Wells St. **Cold loads measured at 12–20s; warm ~2s.** The "in
   seconds" pitch is only true warm. If the interviewee types their own (cold) address, fill the
   wait honestly: "it's assembling the file from 25 live sources."
3. If you plan to demo chat yourself, do it from your admin account (unlimited). The interviewee
   should stay anonymous on their machine.

**Limits the interviewee can hit (by design — observe, don't apologize):**
- Anonymous chat: **3 messages/day per IP** (office NAT shares this across colleagues). The 429
  banner offers sign-in (free tier: 25/day). Watching whether they sign in at the wall is funnel data.
- Scorecard/address lookups: unlimited, no auth. The primary flow can't be rate-limited away.
- Anonymous chat does not persist (by design). If they ask "where did my conversation go" — log it.

**Known data quirks that may surface mid-demo (full detail in `core/known-issues.md`):**
- Cook County GIS is intermittently down → Socrata fallback: Scorecard still works but no parcel
  polygon on the map and building/land sqft may be missing.
- Condo addresses land on an arbitrary unit PIN in the stack (workaround: explicit `?pin=`).
- CCAO returns 400 for some PINs → assessment shows unavailable → no tax estimate.
- Some addresses resolve "approximate" (geocode) rather than parcel-exact — e.g. 2400 N Milwaukee
  Ave and 1425 N Wells St did on 2026-06-12, with complete data regardless; 4520 N Clark St
  resolves authoritative.
- **If they catch a real data error, treat it as a P0 log item.** North-star: a wrong zoning
  classification destroys trust permanently. Verbatim-quote what they said was wrong.

**During the interview period, the admin dashboard observes:** `page_view`, `chat_message_sent`,
`investigate_click` (by card), `report_cta_click` (+ purchases), visitor/return metrics.
Charted but not yet on the dashboard: `scorecard_bridge_click`, `hero_address_submit`,
`hero_librarian_click` are in the backend allowlist; charting them is a small pending task.
Check the dashboard after each interview day — interviewee sessions are a chance to correlate
observed behavior with the events it produces.

---

## 6. Anti-goals (what these interviews are NOT)

- Not sales calls. A purchase is welcome but never pushed; the unprompted purchase is the metric.
- Not feature-collection sessions. Asks get logged, tallied, and only built at 3+ independent requests.
- Not demos. The interviewee drives Part B; a narrated tour measures nothing.
- Not validation of the chatbot. If a session collapses into "playing with the AI," steer back to
  their workflow: "Would you use this on the deal you described earlier?"
- Don't promise timelines, prices, or features mid-interview. "That's exactly the kind of thing I'm
  here to learn" is the universal deflection.
