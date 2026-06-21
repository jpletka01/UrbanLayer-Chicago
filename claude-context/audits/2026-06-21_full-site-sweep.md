# Full-Site Sweep & UX Audit — UrbanLayer Chicago

**Date:** 2026-06-21 · **Auditor:** Claude (read-only) · **Branch/HEAD at audit:** `main` @ `f28d02a`
**Method:** Expert heuristic review + live probing of **local** (qdrant + backend :8001 + frontend build) and **prod** (`https://urbanlayerchicago.com`). **Zero users / no telemetry** — every UX/discoverability conclusion is heuristic, flagged where assumed. No code was changed.

Ground-truth parcels used: `2400 N Milwaukee Ave` (flagship), `481 W Deming Pl`, `642 W Belden Ave` (PIN `14331030110000`).

---

## 1. Executive Summary — top 5 findings (ranked by impact)

| # | Sev | Finding | One-line evidence |
|---|-----|---------|-------------------|
| 1 | **P1** | **The flagship address does not resolve an authoritative PIN.** Two PIN-resolution paths disagree: the property orchestrator returns `property.pin14`, but the scorecard's top-level `resolved_pin` is `null`/`approximate`. The UI then shows "Unconfirmed", **hides the "Ask about this property" chat handoff**, and degrades report keying. Reproduces **local + prod**. **⚠️ UPDATE (see `2026-06-21_resolver-investigation.md`): the `null` is CORRECT — the orchestrator's `pin14` is a *neighbor* parcel in both disputed cases (Milwaukee→across-street 2401/2403; Deming→470 not 481). Do NOT promote `pin14`. Real issue = the orchestrator silently serving neighbor-parcel data + a dense-area bbox-truncation bug.** | `2400 N Milwaukee`: `property.pin14=13253220380000` (=2401/2403, across street) but `resolved_pin=None`. `481 W Deming`: `pin14=14283180160000` (=470 W Deming, ≠ true EX parcel `14283190070000`). `642 W Belden` round-trips → authoritative. |
| 2 | **P1** | **Chat router-seam breaks on any deictic follow-up after a Scorecard handoff.** A free-typed "What can I build here?" with a known `parcel_pin` routes to `clarification_needed` and asks for an address we already hold. The whole "interrogate the parcel" pitch is one off-script question away from a dead-end. | Live prod: `{"message":"What can I build here?","parcel_pin":"14331030110000"}` → `intent=clarification_needed, location.type=none, sources=[]`. Code: `main.py:1018` `_apply_parcel_hint` only rescues `location.type=="address"`. |
| 3 | **P2** | **Discovery's default/empty state leads with garbage.** Default sort is `assessed_value` ascending, so the first rows (even inside a real neighborhood filter) are all `$1` tax-exempt parcels with unresolved `~` approximate addresses and null community area. First impression of the workbench is ten $1 parcels. | `neighborhood:22` (Logan Square) → total 19,564, but top 10 all `assessed_value=1.0`, `~`-prefixed addresses, `community_area=null`. |
| 4 | **P2** | **Chat & default-Discovery latency is high on prod.** Router alone is ~3.4 s before retrieval starts; a simple code question is 9.3 s end-to-end. Unfiltered Discovery search is ~9.8 s and the default map (`/search/pins`) is ~10.4 s. | `done` timings: `router:3436, retrieval:564, first_token:5479, total:9322`. Pins no-filter `[200 10.4s]`. |
| 5 | **P2** | **Chat is undiscoverable from the top-level UI.** Nav is only Scorecard / Discovery / Pricing — "Analyst" was deliberately removed. A first-time visitor who wants code research must scroll the marketing homepage to the persona cards or type a non-address into the Scorecard box. A headline capability is hidden by design. | `PageHeader.tsx:9-17` (`NAV_ITEMS` = scorecard, pricing; Discovery injected). Chat reached only via `PersonaScenarios` `/?q=` + Investigate buttons. |

**Overall verdict:** The suite is **more coherent than it is discoverable, and more correct than it is fast.** The "address → Scorecard → Report" spine is genuinely good (the $25 PDF is a real deliverable; the Scorecard is dense-but-useful; chat answers are accurate and cited). The cracks are at the *seams between tools* — PIN identity dropping between resolver paths (#1), chat losing the parcel on a free-typed turn (#2), and Discovery's default sort exposing junk (#3). For a pre-launch hardening pass, fix the seams before adding surface.

---

## 2. Workstream findings

### Workstream 1 — Code health

| Sev | Finding | Evidence | Local vs prod | Recommended fix |
|-----|---------|----------|---------------|-----------------|
| P1 | **Divergent PIN-resolution paths.** `property.pin14` and top-level `resolved_pin` can disagree; the scorecard surfaces the latter. Architecture smell: two address→parcel resolvers with no reconciliation. | `main.py:1530` `/api/scorecard`; `property.pin14=13253220380000` vs `resolved_pin=None` for the flagship. | Identical both envs | When `resolved_pin` is null/approximate but `property.pin14` is present, reconcile (promote it, or downgrade confidence rather than dropping identity). |
| P2 | **Router-seam fragility (documented, still live).** `_apply_parcel_hint` only overrides `address`-typed plans; deictic questions classified `none`/`clarification_needed` never receive the held pin. Mirrors the 3 bugs in the grounding archive — same root cause. | `main.py:1018-1031`; live deictic test (#2 above). | Prod-confirmed | The deferred "conversation-pinned-to-parcel" track is the right fix; interim: have `_apply_parcel_hint` also rescue `none`/`clarification_needed` when a pin is held. |
| P2 | **`frontend/CLAUDE.md` is stale in 3 places** — describes UI that no longer exists, which will mislead future work. | (a) `HeroEntrance` doc claims "address mode ⇄ chat mode swapped by a quiet link" + `chatPrefill` prop — actual `HeroEntrance.tsx` is address-only, `chatPrefill` returns **zero** grep hits. (b) `PageHeader` doc lists nav "Analyst/Scorecard/Discovery/Pricing/About" + `/?analyst=1` — actual `NAV_ITEMS` is scorecard+pricing(+discovery). (c) Routing line says Discovery "25 CAs" — registry coverage is **all 77** (`asOf 2026-06-15`). | Docs only | Update the three rows to match the shipped 2026-06-15 coherence pass. |
| P3 | **`mock=true` is a prod-reachable fabricated-data flag.** Gated behind `require_auth` + purchase (✅ not a payment bypass), but an entitled caller can pass `?mock=true` and receive a report with `_apply_mock_overrides` synthetic values. | `main.py:report(... mock: bool=False ...)` ~4377; `if mock: report_data=_apply_mock_overrides(...)` after the purchase check. Prod anon → `401`. | Prod-confirmed gated | Restrict `mock` to non-prod (env check) or a dev/admin tier, so a paying user can't silently get fake data. |
| ✅ | **Clean TODO/dead-code hygiene.** Zero real `TODO/FIXME/XXX/HACK` in `backend/` + `frontend/src` (one false positive on a PIN format docstring). Sampled components (`HeroSlideshow`, `UpgradePrompt`, `DisclaimerBanner`, `ThinkingTrace`) all referenced. | `grep -rnE "TODO\|FIXME..."` → 1 false positive. | — | None. |

### Workstream 2 — Persona journeys (executed live)

Four realistic personas drawn from `strategy/north-star.md` + `product-roadmap.md`. Each was run against the live app with real addresses.

**A. Small developer / value-add investor (the wedge).** Goal: "is this lot worth pursuing?"
Journey: type `642 W Belden` → Scorecard (3.8 s prod, clean authoritative PIN, ✓ Exact badge) → "Ask about this property" → grounded chat → buy $25 Report.
- **Works well:** Belden resolves authoritative; report is excellent (development surplus 4,750 sq ft, ~8-unit screen, grandfathered-1888 flag, risk badges, full bulk/density + setback prose). This is the product's strongest path.
- **Breaks:** Run the *same* journey with the **flagship `2400 N Milwaukee`** and it degrades immediately — "Unconfirmed" badge, **no "Ask about this property" button** (hidden when `pin` is null, `ScorecardPage.tsx:569`), report falls back to address-keying. Finding #1.

**B. Residential broker / acquisitions analyst.** Goal: comps + neighborhood read for a listing.
Journey: Scorecard → ComparablesCard → "What are recent comparable sales near…" (Investigate).
- **Breaks:** Belden report shows "Nearby sales $605K–$605K · 1 sale" / "Thin comparable sales market (1 transaction)." Honest, but a single comp is thin for a broker's decision. The Scorecard surfaces `comparables.sales: 1`. This is a **data-density** limit, not a bug — but the persona's core need (a comp set) is under-served on in-fill blocks.

**C. Zoning attorney / architect (code research).** Goal: "max height in RM-5?", overlay interactions.
Journey: …there is no front-door for this. Must either (a) scroll the homepage to persona cards, or (b) type a question into the **Scorecard** box and rely on the failure-recovery redirect.
- **Works well once reached:** chat answer was accurate (RM-5 45/47 ft by frontage, no-limit for nonresidential, Near North historic overlay exception), cited `[1]`/`[5]`, proper disclaimer. Genuinely strong.
- **Breaks:** discoverability (Finding #5) + any deictic follow-up (Finding #2).

**D. Land prospector / site selector.** Goal: "find me undervalued multifamily / teardown candidates."
Journey: `/discovery` → pick a recipe / neighborhood → scan list → map → export.
- **Works:** recipes show live counts (`teardown:1191`, `vacant_mf_transit:1418`); filtered neighborhood search is fast (1.4 s).
- **Breaks:** the default/empty workbench leads with `$1` junk (Finding #3); the unfiltered map is a ~10 s load (Finding #4); export is premium-gated (correct, but the free user hits a wall after investing in filters).

**Synthesis — one product or a bag of tools?** It **reads as one product** at the conceptual level (the "parcel dossier machine" framing has clearly landed — shared vocabulary, shared `SelectedParcel`, consistent dark design system, the Scorecard↔chat↔report bridges exist). But it **behaves like loosely-coupled tools at the seams**: identity silently drops between the resolver and the property domain (#1), chat forgets the parcel on a natural-language turn (#2), and Discovery doesn't hand off *into* a Scorecard for a found parcel as smoothly as the homepage does. The connective tissue is the weak point, not the tools themselves.

### Workstream 3 — Discoverability

| Tool | Entry points (verified) | Rating | Concrete fix |
|------|------------------------|--------|--------------|
| **Scorecard** | Homepage hero (address box, default), nav "Scorecard", chat→ScorecardBridgeCard. | **Strong** | None needed — this is the front door and it's clear. |
| **Report ($25)** | Only *inside* a Scorecard (CTA card + sticky bar) and `/pricing` lead card. | **Good** | Acceptable — the report should be earned from a parcel. Keep. |
| **Discovery** | Nav (self-activates when index has data), `/explore` redirect. Not on the homepage hero or in any value-prop section I could find. | **Medium** | Add one homepage signpost ("Prospect across all 77 community areas →") — right now a visitor only finds it if they read the nav. |
| **Chat / Analyst** | `PersonaScenarios` cards (mid-homepage, `/?q=`), Scorecard Investigate buttons, Scorecard address-box failure redirect. **Not in nav** (removed by design). | **Weak (by design)** | Heuristic, no telemetry: the focus argument is defensible, but code-research + neighborhood Q&A is a headline capability per `CLAUDE.md` and is currently invisible above the fold. Consider a single restrained "Ask the analyst" entry (e.g. in the hero's secondary line) — the coherence pass deferred exactly this ("cold-start chat"). |
| **code-research** | Same as Chat (it *is* chat). | **Weak** | Same as above. |

Hidden/under-signposted: **Chat** (worst), then **Discovery**. Scorecard and Report are well-signposted.

### Workstream 4 — Per-tool utility & information density

| Tool | Verdict | Detail (live) | Highest-leverage change |
|------|---------|---------------|--------------------------|
| **Scorecard** | **Right-to-slightly-dense** | ~9 cards (zoning, property, comps, incentives, regulatory, violations, crime YoY, 311, neighborhood) in a 2-col multicol flow, with a facts-only verdict line up top and one Investigate link per card. Hierarchy is good: identity band → verdict → report CTA → financial strip → cards. Prod latency 1–4 s — feels fast. The density is justified for a due-diligence audience. | Make the **verdict line do more triage** — it currently restates flags already in cards; lead it with the 1–2 facts that decide "pursue/skip" (zone + development surplus). And fix #1 so the identity band shows ✓ Exact for the flagship. |
| **Chat** | **Genuinely useful, too slow to start** | Accurate, cited, disclaimed answers (RM-5 test). Grounded handoff works when the address is embedded. But router is 3.4 s of dead air before anything streams, and the deictic seam (#2) is a cliff. | Cut router latency / stream a "thinking" affordance earlier, and close the deictic seam. |
| **Discovery** | **Capable, intimidating default** | 32 filters, 6 recipes with honest live counts, deck.gl map, premium CSV. The recipe shelf is the right on-ramp. But the *empty* state sorts `$1` exempt parcels to the top and the unfiltered map is a 10 s load. | Change the default sort (or default to a recipe) so the first screen shows real, valued parcels — never lead with `$1`/`~` rows. |
| **Report** | **Underwhelming-to-buyer-only-because-it's-unseen; the artifact itself is strong** | 18-page PDF: cover snapshot, zoning map w/ parcel pin, exec summary with CLEAR/RISK/FAVORABLE/COMPLEX badges, development potential (FAR utilization, indicative units), opportunities/constraints, full bulk/density table + setback notes, glossary, sources. Clearly worth $25. | The **value is legible only after purchase.** Strengthen the pre-purchase teaser (the sample report exists — make sure the CTA shows 2–3 real bullets from *this* parcel). Minor: the **Setbacks table renders headers with no rows** (data is in prose below) — looks like a gap; either populate or drop the empty table. |

---

## 3. Live-probe log (reproducible)

CSRF bootstrap for POST endpoints: `curl -c cookies.txt https://urbanlayerchicago.com/api/auth/me` → use `csrf_token` cookie as `X-CSRF-Token` + `-b cookies.txt`.

| # | Command (abbrev) | Result |
|---|------------------|--------|
| 1 | `GET /api/scorecard?address=2400 N Milwaukee Ave` (prod ×3) | `200` 0.8–2.1 s · `resolved_pin=None, conf=approximate` **every time** · but `property.pin14=13253220380000`, comps=1, in_tif=true |
| 2 | same, **local** :8001 | `200` 2.9 s · `resolved_pin=None`, `property.pin14=13253220380000` — **identical to prod** |
| 3 | `GET /api/scorecard?address=481 W Deming Pl` (prod) | `200`, cold spike **12.0 s** then 0.8 s warm · `resolved_pin=None` · `property.pin14=14283180160000` (note: ≠ documented ground-truth `14283190070000` — possible neighbor resolution) |
| 4 | `GET /api/scorecard?address=642 W Belden Ave` (prod) | `200` 3.75 s · `resolved_pin=14331030110000, conf=authoritative` · `property.pin14` **matches** ✓ |
| 5 | `POST /api/discovery/search` `{}` (no filter, prod) | `200` **9.8 s** · `result.total=948991, gated=true` · top row `~2967 N MANNHEIM RD, assessed_value=1.0, CA=null` |
| 6 | `POST /api/discovery/search` `neighborhood:22` (Logan Sq) | `200` 1.4 s · `total=19564` · top 10 all `assessed_value=1.0`, `~` addresses, `CA=null` |
| 7 | `POST /api/discovery/search/pins` `{}` (no filter) | `200` **10.4 s** · `total=948991, points=5000, truncated=true` |
| 8 | `POST /chat` "max height in RM-5?" (prod) | `200` 9.3 s · timings `router:3436, retrieval:564, first_token:5479, total:9322` · accurate, cited `[1][5]`, disclaimer |
| 9 | `POST /chat` "What can I build here?" + `parcel_pin` (prod) | `200` · `intent=clarification_needed, location.type=none, sources=[]` — **pin ignored**, asks for address |
| 10 | `POST /chat` "…RM-5 at 642 W Belden?" + `parcel_pin` (prod) | `200` · `intent=legal_question, location.type=address, location.pin=14331030110000` — **grounding applied**, parcel-specific answer |
| 11 | `GET /api/report?pin=14331030110000…` **local** dev cookie | `200` **8.2 s**, 1.21 MB, 18-page PDF, renders fully |
| 12 | `GET /api/report?...` prod anon / `mock=true` prod anon | `401` both (`Authentication required`) — gate holds, mock not a bypass |
| 13 | `GET /autocomplete?q=2400 N Milw` / `…Milwaukee` | `[]` for partial street; full street → 1 whole-value suggestion in ~1 s (Census geocoder, no prefix match) |

**Local-vs-prod discrepancies:** **No data discrepancies** — zoning (`C1-2`, FAR 2.2 for Milwaukee), `property.pin14`, and resolution confidence are byte-identical between local and prod. Differences are **latency only**: prod shows cold spikes (Deming 12 s, Belden 3.75 s) and the slow unfiltered Discovery/pins paths (~10 s) that local serves faster from a warm cache. The PIN-path divergence (#1) and router seam (#2) reproduce on **both** — they are architectural, not infra.

> Note on a false start: an early probe reported `zone_definition: None` locally — that was a **parsing error in my probe** (I read `.code` instead of `.code_section`); `zone_definition` is in fact populated locally and matches prod. No finding there.

---

## 4. Prioritized backlog

**If I had a day** (stop-the-bleeding on the flagship demo):
1. Fix #1 — reconcile `property.pin14` into `resolved_pin` when the top-level resolver returns approximate/null. This single fix restores the ✓ Exact badge, the "Ask about this property" button, and PIN-keyed reports for the flagship and Deming.
2. Fix #3 — change Discovery's default sort (or auto-apply a recipe) so the empty/default state never leads with `$1`/`~` rows.
3. Fix the stale `frontend/CLAUDE.md` rows (3 edits) so they stop misleading.

**If I had a week** (close the seams):
4. Fix #2 — extend `_apply_parcel_hint` (or ship the deferred conversation-pinned-to-parcel model) so a held pin survives deictic follow-ups. This is the highest-value reliability fix for the "interrogate the parcel" pitch.
5. Attack chat router latency (3.4 s) — cache/trim the router prompt or stream a status token before retrieval; target sub-1 s to first feedback.
6. Speed up or defer the unfiltered Discovery map (10 s) — don't fetch 5000 pins until a filter narrows the set, or paginate the map.
7. Report pre-purchase teaser — surface 2–3 real per-parcel bullets before the $25 wall; drop or populate the empty Setbacks table.

**If I had a month** (discoverability + depth):
8. Decide chat's front-door story (Finding #5) — either commit to "chat is contextual-only" and remove the residual "Ask the analyst" copy, or give it one restrained, above-the-fold entry. Right now it's half-hidden, which is the worst of both. (Heuristic — revisit once there's telemetry.)
9. Discovery → Scorecard handoff polish: clicking a found parcel should open its Scorecard as smoothly as the homepage does.
10. Comp-density for in-fill blocks (Persona B) — widen the comp search radius or surface the thin-comps caveat earlier in the Scorecard, not just the report.

---

*Read-only audit. No files other than this report were created or modified.*
