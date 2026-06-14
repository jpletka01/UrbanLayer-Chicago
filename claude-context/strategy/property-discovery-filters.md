# Property Discovery — Search & Filter Expansion

**Status:** ✅ **SHIPPED to production 2026-06-13** (this was the strategy/why; the system is built
+ deployed). For implementation reality + what remains, see
`claude-context/property-discovery/10-implementation-status.md`. **Created:** 2026-06-13.
**Context:** Today the product supports exactly one filter — zoning district. This doc defines
the candidate filter set, an MVP, a prioritization, and a rollout for expanding property
discovery. It also contains a self-critique that separates the *product* answer (what filters
should exist) from the *architecture* answer (how to serve them at scale).

**TL;DR of the critique (read this first):** the filter set, MVP, and prioritization below stand
on their own as a UI/product decision. The "prospecting index" architecture is a real but
*downstream* concern — needed only if/when we support cross-parcel querying at scale. Decide the
filters first; treat the index as a dependency to plan for, not a premise that governs the set.

---

## Part A — Product answer (architecture-independent)

This is the version to drive product decisions from. No indexing, precompute, or backend redesign
assumed — just "what filters should exist and why."

### Candidate filters (grouped by user intent)

- **Property type & physical:** land-use class · lot size · building size · year built / age ·
  units / rooms · improvement ratio (building÷land value, a teardown/underutilization signal) · vacancy
- **Location:** neighborhood / community area · ward / alderman · radius / draw-polygon ·
  transit proximity (TOD) · walk/transit/bike band
- **Zoning & development potential:** zoning district *(existing)* · zoning group
  (Residential/Business/Commercial/Manufacturing/Downtown/PD) · density / FAR band ·
  overlay flags (Planned Development, landmark/historic, pedestrian street, PMD) · ADU-eligible ·
  ARO zone · pending zoning change
- **Financial:** assessed value · last sale price / recency · price per SF · estimated tax band
- **Incentives (structural advantage vs. competitors):** TIF · Opportunity Zone · Enterprise Zone · SBIF/NOF area
- **Environmental / risk:** floodplain · brownfield proximity · crime-density index (YoY-normalized)
- **Condition / red flags:** open violations · 311 red-flags (no-heat, rodent, collapse risk) ·
  vacant-building case · recent permit activity

### MVP — smallest set that makes discovery genuinely useful

1. **Land-use class** — the atom of every search; nothing else is useful without "what kind of property."
2. **Neighborhood / community area** — the dominant way users scope location.
3. **Zoning group + density band** — turns the one cryptic existing filter into intent ("where can I build multifamily").
4. **Incentive eligibility (TIF / OZ / Enterprise Zone)** — a literal item on a developer's shopping list; competitors bury it behind paywalls.
5. **Vacancy** — the core "find me a site" signal.
6. **Lot size band** — the first hard developer constraint after zoning.

**Why these six:** together they answer the canonical query —
*"vacant, multifamily-zoned parcels of a usable size in this neighborhood that qualify for an incentive."*
That is the job property discovery exists to do, and it's impossible in the product today. Each filter
expresses an unambiguous user intent.

### Prioritization (user value × data-sourcing effort)

| Attribute | Customer Value | Effort to source the field |
|---|---|---|
| Land-use class | High | Low |
| Neighborhood | High | Low |
| Zoning group + density | High | Low |
| Incentive (TIF/OZ/EZ) | High | Low |
| Vacancy | High | Low–Med (definitional: vacant land vs. vacant building) |
| Lot size | High | Med |
| Assessed value | High | Med |
| Last sale price / recency | High | Med |
| Improvement ratio (teardown) | High | Med |
| Transit proximity | High | Med |
| Radius / draw-polygon | High | Med |
| Open violations | High | Med |
| Building SF / year built | Medium | Med |
| Ward · overlays · ADU · floodplain | Medium | Low |
| Price per SF · 311 flags · permits | Medium | Med |
| Estimated tax band | High | High |
| Crime index · walk score | Medium | High |
| Brownfield proximity | Low | Med |
| Pending zoning change | High | High |

**Rollout by value (not by architecture):**
- **First:** the six MVP filters (all high-value, low-effort).
- **Next:** broker/valuation layer — assessed value, last sale, price/SF, improvement ratio, transit, radius search.
- **Defer:** volatile / hard-to-source long tail — tax band, crime index, walk score, pending zoning changes — until core demand is proven.

**Product-scoping note:** keep **permits-as-leads** (subcontractors filtering permits by missing trade)
on a separate track. It shares the word "filter" but is a different product for a different persona
(spine = Permits dataset, not parcels). Don't let it bloat the prospecting MVP.

---

## Part B — Architecture note (downstream dependency, do NOT lead with this)

Filtering a *known result set* needs no redesign. **Prospecting** ("show me all parcels where…")
does eventually require a way to query across parcels — you can't run 1.8M per-parcel spatial
queries at request time, which is how the product fetches data today.

If/when prospecting-at-scale is greenlit, the enabling work is a **precomputed PIN-keyed index**
built offline from data already ingested:
- **Spine:** Parcel Universe `pabr-t5kh` (pin, `class`, township, lat/lon) — ~1.8M rows
- **Join by PIN:** Characteristics (`char_land_sf`, `char_bldg_sf`, `char_age`), Assessed Values, Parcel Sales
- **Offline spatial-flag pass:** run each centroid through the preloaded layers once → zoning, TIF,
  Enterprise Zone, Opportunity Zone, floodplain, TOD, ADU, ARO, landmark, PMD flags
- **Per-PIN rollups:** open-violation count, recent 311 red-flags, last-12mo permits, PTAXSIM tax estimate

This is a Phase-2 *engineering* concern that follows the product decision. It is **not** a prerequisite
for deciding which filters should exist.

---

## Part C — Self-critique (why Part B is separated from Part A)

The first draft of this analysis led with the index architecture ("the architectural fact that
governs everything") and framed building it as "Phase 0, prerequisite, not optional." A critical
review found that framing **overextended**:

- **Necessity test:** every system-design claim (per-parcel model can't prospect; build an index;
  filters become cheap scans; Phase-0 foundation; latency column) is required *only for scale*, **not
  for the product/filter decision**. All filters, the MVP, and the prioritization survive intact
  without any of it.
- **Three distortions introduced by leading with architecture:**
  1. **Inverted premise and consequence** — an implementation detail (the index) was promoted to the headline.
  2. **System constraint posing as user value** — the MVP was justified partly by "servable from
     preloaded data with no per-parcel calls," which is an engineering filter, not a user filter.
  3. **High-intent filters demoted for implementation reasons** — comps and tax band are high
     user-value (brokers, underwriting) but were pushed down for precompute cost, not user value.
- **But not pure speculation:** the underlying observation (prospecting at scale needs a cross-parcel
  query path) is true and eventually load-bearing. The error was *altitude and proportion*, not fact.

**Verdict: ⚠️ Mixed signal (useful insight, overextended).** Correct shape = answer the filter
question cleanly first (Part A), then footnote the scale dependency (Part B) — not the reverse.

---

## Competitive anchor

Cityscape's "Property Finder" (bulk-filter parcels by zoning, transit, vacancy, land use) is their
flagship *paid* feature; incentive filtering is buried in their $125/mo tier. The MVP above plus a
natural-language front door is a combination no competitor offers. See `competitive-analysis.md`.
