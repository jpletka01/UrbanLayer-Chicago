# PDF Report — Feature Status Tracker

Single source of truth for all planned, shipped, and blocked report features across V4–V6+.

Last updated: 2026-06-11 (Report V6 Phase 3 + credibility pass + **Tier-0/Tier-1 SHIPPED & DEPLOYED** + prod memory validated (no OOM history, backend <1 GB); **Tier-2 D3 now SHIPPED** — scale bar + distance reference ring added to the three always-rendering maps (zoning/cover, construction, comps). Scope note: legends already existed, so D3 reduced to scale+ring. Verified visually on both QA-parcel PDFs; 542 unit tests pass (+10 in `test_report_d3_maps.py`). **Not yet deployed.**)

## Shipped Features

### V3 (baseline)
- Table of contents
- Glossary with hyperlinked terms
- Construction/demolition map (Mapbox basemap + matplotlib overlay)
- Comparable sales scatter chart
- Page numbering, spacing, layout polish

### V4 (shipped 2026-06-09)
| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Nearby development detail table | Shipped | Type, address, description, cost, date, distance. Enriched from raw permit data |
| 2 | Parcel geometry map with dimensions | Shipped (partial) | Dimensions grid works. Map renders only when real GIS geometry available — see Blocked section |
| 3 | Ownership intelligence | Shipped | Long-term hold, owner-occupied, rapid turnover, non-arm's-length signals from sales/tax data |
| 4 | Surface existing unsurfaced data | Shipped | Systematic audit done — building characteristics, assessment trend, tax breakdown all added |
| 5 | Additional building characteristics | Shipped | Exterior wall, roof, basement, garage, A/C from CCAO |
| 6 | Assessment trend analysis | Shipped | Total change %, CAGR, 5-year trend |
| 7 | Tax breakdown by agency | Shipped | Top 5 taxing agencies with rates and amounts |
| 8 | Opportunities & constraints synthesis | Superseded by V5 | V4 deferred this; V5 implemented it fully |

### V5 (shipped 2026-06-10)
| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1a | Opportunities & constraints synthesis | Shipped | ~29 deterministic rules across 7 categories. Max 4+4 displayed |
| 1b | Estimated land value range | Shipped | P25–P75 from comps, with sample size and disclaimer |
| 1c | Promoted next steps section | Shipped | Immediate (blocking) + due diligence + advisory tiers |
| 1d | Incentive stacking narrative | Shipped | Template paragraphs for TIF+OZ, TIF+EZ, OZ+QCT, etc. |
| 1e | Development trend narrative | Shipped | Deterministic summary from nearby permit data |
| 1f | Crime condensed to 3-line summary | Shipped | Total incidents, trend, arrest rate. Community-area table removed |
| 1g | Development envelope summary (text) | Shipped | Max buildable, surplus, lot coverage in one block |
| 2a | Development envelope visualization | Shipped | Parcel polygon with setback zones, buildable footprint. Requires real GIS geometry |
| 2b | Regulatory approval pathway | Shipped | SIMPLE/MODERATE/COMPLEX with timeline. PD, landmark, historic, special use decision tree |
| 3a | Condensed glossary | Shipped | ~12 terms, inline footnotes for FAR/setback/lot coverage |
| 3b | Condensed data sources | Shipped | Grouped by category |
| 3c | Removed duplicate development potential box | Shipped | Shows once in exec summary |
| 3d | Adjacent zoning transition zone notes | Shipped | Title 17-2-0303 flags for residential/commercial interface |
| 3e | Due diligence checklist | Shipped | Two-column: completed in report vs action required |

### V6 (shipped 2026-06-10, same session as V5)
| # | Feature | Status | Notes |
|---|---------|--------|-------|
| 1 | Historic district / National Register conflict fix | Shipped | Overlay type labels, National Register row in status grid, synthesis/approval/next-steps updated |
| 3 | 311 open-focused display | Shipped | Open count leads in red, total as footnote |
| 5 | Construction radius expanded to 0.5mi | Shipped | Separate config (0.00725 deg), zoom-14 basemap |
| 6 | Regulatory overlay boundaries on zoning map | Shipped | Dashed boundaries for 7 overlay layers (PD, landmark, historic, national register, special, SSA, landmark building) |
| 8a | Transit station detail | Shipped | CTA rail + Metra with station name, lines served, distance — in regulatory section AND market context |
| 8b | Comparable sales map | Shipped | Cyan diamond markers on basemap between chart and table |

## V6 Audit Findings — Resolution Tracker

Source: `guides/report-v6-audit.md` (rejection audit of `report_v6g.pdf`, 2026-06-10). IDs and rankings defined there.
**Caveat:** audited PDF was `mock=true`. Items tagged `[mock?]` may be fixture-only — **regenerate a real-data report before fixing** to confirm they exist in the real path.

Status values: `Open` · `In progress` · `Fixed` · `Needs real-data` · `Won't fix`

| Rank | ID | Finding (short) | Impact | Effort | Status |
|------|----|-----------------|--------|--------|--------|
| 1 | Q3/Q4 | Zoning self-contradiction: RM-6 label (FAR 4.4) vs FAR 2.2 table + commercial uses `[mock?]` | 5 | XS/S | Needs real-data |
| 2 | Q1/Q2 | Lot size "N/A" hero + 3 conflicting lot sizes | 5 | S | Open |
| 3 | V5-1b | Estimated Land Value Range marked Shipped but doesn't render | 5 | S–M | **Fixed (Phase 3)** — root cause was missing comp land-area (condo market), not the comp query. Comp merge now keeps the most complete chars row; land range renders when ≥3 land-bearing comps, else honest "Valuation Indicators" fallback on median comp **sale price** |
| 4 | Miss#1 | No cover decision box (6 numbers) | 5 | M | **Fixed (Phase 3)** — page-1 "Development Snapshot": lot · zone · max buildable · value · key constraint · approval path, with honest "n/a" |
| 5 | P2 | No comp-implied valuation for the subject lot | 5 | M–L | **Fixed (Phase 3)** — `_compute_comp_valuation`: median comp sale (reliable anchor) + land value range + $/buildable-sf when land-bearing comps exist; flags the data limit otherwise |
| 6 | V5-2a | Parcel + setback-envelope viz absent (GIS-blocked) | 5 | XL | Needs real-data |
| 7 | P1 | No FAR-utilization framing | 4 | S | **Fixed (Phase 3)** — `_compute_far_utilization`: "existing X sf uses Y% of FAR-allowed Z sf" line in exec Dev Potential block (vacant-lot variant too) |
| 8 | P8 | No as-of-right unit yield | 4 | S | **Fixed (Phase 3)** — `_compute_unit_yield` from authoritative min-lot-area-per-unit (Title 17-2-0303-A table added to zoning_definitions); R districts only, method note shown |
| 9 | Exec | Constraints not consolidated into one callout | 4 | S | **Fixed (Phase 3)** — decision box surfaces the single most deal-shaping constraint on page 1 (binding-priority order); also gated the ARO constraint to lots that can actually reach 10+ units (was a false positive on small lots) |
| 10 | P4 | 311 "high-risk" alarmism (rodent baiting) | 4 | M | **Fixed (Phase 2)** — severity taxonomy: rodent/rat → routine_service_flags, structural only stays high-risk |
| 11 | Q9 | Lakefront Protection false positive inland | 4 | M | **Won't fix — verified TRUE positive (Phase 2)**; only the lead label changed |
| 12 | Q7/Q8 | Map/table different neighborhoods; comps wrong section `[mock?]` | 4 | S/M | Needs real-data |
| 13 | Miss#6 | No combined site-context map | 4 | L | Open |
| 14 | Q5 | Tax agency rows sum > stated total `[mock?]` | 3 | XS/S | Needs real-data |
| 15 | P7/Q13 | Reassessment drift sold as appreciation opportunity | 3 | XS | **Fixed (Phase 2)** — synthesis signal reframed as reassessment trend + tax-burden, not "appreciation opportunity" |
| 16 | Q6 | Effective tax rate vs assessed value; market value hidden | 3 | S | **Fixed (Tier-1)** — `market_value` persisted on `ReportData` + rendered as "Est. Market Value" between Assessed Value and Est. Annual Tax; effective rate labeled "(of market value)" so 1.9% can't be misread as ~19% of assessed. Verified on real control: $146,001 assessed → $1,460,010 market → $28,141 tax → 1.9% |
| 17 | D3 | Maps have no legend / scale / radius ring | 3 | S | **Fixed (Tier-2)** — legends already existed; added a bottom-left **scale bar** (auto round distance) + a dashed **distance reference ring** (zoning/comps 0.25 mi, construction 0.5 mi) to all three always-rendering maps, both derived from the basemap's actual Web Mercator m/px (`_rendered_m_per_px`, with the `@2x` ÷2 factor) so they can't misstate distance. Verified visually on both QA PDFs |
| 18 | D7 | Comps scatter plots absolute price, not $/sf | 3 | S | Open |
| 19 | Q12/P9 | Building class "EX" mislabeled "standard" `[mock?]` | 3 | S | **Fixed (Phase 2)** — EX → property_tax_class "exempt", consistent with R2c callout |
| 20 | P5 | Ownership Intelligence lacks the "so what" | 3 | S | **Fixed (Phase 3)** — `_ownership_interpretation` renders a "What this means for a buyer" deal read (off-market / basis / non-arm's-length) under Ownership Intelligence |
| 21 | D2 | Construction map orphaned across page break | 2 | XS–S | **Fixed (Phase 2)** — `<figure page-break-inside:avoid>` + caption binds map together |
| 22 | V6-5 | "0.25mi" narrative contradicts "0.5mi" header | 2 | XS | Fixed (Phase 1, R4) |
| 23 | Q10 | CAGR labeled 5yr (2020–2025) but data starts 2021 | 2 | XS | **Fixed (Phase 2)** — period already derived from real oldest/newest year + disclaimer; regression-tested |
| 24 | Q14 | "Surplus" undefined; existing sf not shown | 2 | XS | Open |
| 25 | P6/D11 | Crime: no benchmark, buried | 2 | S | Open |
| 26 | P3 | Financial = five "No"s + irrelevant grant | 2 | S | Open |
| 27 | V5-1c | Advisory tier of Next Steps missing | 2 | S | **Fixed (Phase 3)** — Advisory (Optimization) tier now always renders (appraisal, validate unit yield w/ zoning attorney, broker comps + market study) plus the conditional incentive items |
| 28 | D1 | Blank page 8 (orphaned footnote) | 1 | XS | **Won't fix — not reproducible (Phase 2)**; real reports (15/18pp) have no blank page (was mock-only) |
| 29 | D4 | Tax + effective rate shown 3× | 1 | XS | **Fixed (Tier-1, with Q6)** — effective-rate **value** now renders exactly once (property section); the orphan exec-summary block and the duplicate financial-section "Effective Rate" dt were removed. The traffic-light "high effective tax rate" pill is a separate conditional risk signal, not a value display, and is intentionally kept |
| 30 | D5 | Transit duplicated + rounding mismatch | 1 | XS | **Fixed (Phase 2)** — single canonical transit block in Market Context; regulatory dup removed |
| 31 | D6 | Overlay bracket labels duplicate name verbatim | 1 | XS | **Fixed (Phase 2)** — `[desc]` rendered only when it differs from name |
| 32 | D9 | "ZONE TYPE: 4" meaningless | 1 | XS | **Fixed (Phase 2)** — redundant numeric Zone Type row removed (Zone Class already labels it) |
| 33 | D10 | Inconsistent distance precision | 1 | XS | **Fixed (Phase 2)** — transit narrative standardized to 1 decimal (tables keep 2-dec for comp separation) |
| 34 | Q11 | "Lakeview Historic District" on Lincoln Park property | 1 | XS | **Won't fix — verified correct (Phase 2)**; real NR district spans Wrightwood, name is authoritative |
| 35 | D8 | Site Assessment badges mix scales | 1 | S | Open |
| 36 | V6-2 | Year-built / nonconformity absent (CCAO-blocked) | 3 | L | Needs real-data |

### Phase 4 — RE-PRIORITIZED (planning only, 2026-06-11)

Full rationale, rankings, assumptions, risks, dependencies, QA strategy, and acceptance criteria:
**`report-v6-execution-plan.md` → "Phase 4 — RE-PRIORITIZED" section** (that is the source of truth;
this is a pointer). Not yet implemented.

The original Phase 4 plan (D3 → D7 → Miss#6 → V5-2a → D8 → P6) was re-prioritized after three Phase 1–3
findings: (1) `$/land-sqft` is data-blocked (condo market) → **D7 dropped as specified**; (2) the
GIS-dependent maps (Miss#6, V5-2a) are not just blocked but **reliability-risky** — report generation
exited mid-render twice after a GIS lookup failure (root cause unconfirmed: GIS hang vs OOM); (3) the real
remaining leverage is **comp comparability**, not map cosmetics.

Re-prioritized order:
1. **Tier 0 — GIS / report-gen reliability — ✅ SHIPPED (2026-06-11).** Root cause was
   **CONFIRMED** (investigation, read-only): render-memory + event-loop serialization, **not** GIS. Measured:
   each report holds ~375 MB of render data (map rasters + `write_pdf`); `write_pdf()` ran **synchronously and
   blocked `/health` for 6.4 s** at report completion; **3 concurrent reports all timed out** (single worker
   saturates). GIS-as-cause **disproven** as a direct crash path (blackholed GIS still returned via Socrata
   fallback, no exception; GIS only adds ~12 s latency and currently returns **no geometry**). (Local 48 GB
   macOS compresses instead of OOM-killing → timeout cascade; prod 8 GB Linux → the SIGKILL.)
   **Fix shipped (all 3 items):** (1) `_REPORT_SEM = asyncio.Semaphore(report_concurrency=2)` wraps the heavy
   span `_fetch_report_data`…`write_pdf` in `report()`; (2) `write_pdf()` offloaded to `run_in_executor` so it
   no longer blocks the loop; (3) `_lookup_parcel_gis` now passes an explicit 8 s per-request timeout and makes
   a single attempt (retry 2→1). **Files:** `backend/config.py` (`report_concurrency`, env `REPORT_CONCURRENCY`),
   `backend/main.py` (`_REPORT_SEM` + `async with` span + executor offload), `backend/retrieval/property/parcels.py`
   (`_GIS_TIMEOUT_S=8.0`, single attempt). **Tests:** `backend/tests/test_report_tier0.py` (+4: semaphore
   serialization, concurrency bound, harness-concurrency sanity, degraded-data completion) and 2 new parcels
   tests (single-attempt, explicit-timeout). 524 unit tests pass (integration GIS tests fail = GIS down,
   environmental). Full evidence/rationale: `report-v6-execution-plan.md` → "Tier-0 investigation" /
   "Tier-0 implementation plan".
2. **Tier 1 — comps-section consolidation — ✅ SHIPPED (2026-06-11).** Removed the legacy "Comparable Sales
   Summary" stat block (and its always-empty `Median $/Land Sq Ft` tile); consolidated on the "Comparable
   Market Activity" callout. $/bldg-sf preserved: median surfaced in the callout, per-row column switched from
   `$/Land SF` → `$/Bldg SF`. **New finding:** the surviving $/bldg-sf is *also* frequently empty — on the
   real control run, **0 of 6 comps carried building sq ft** (same missing-CCAO-characteristics root cause as
   land area). The consolidation is still correct (one presentation, no contradictory `—` tiles); the metric
   renders only when data exists.
3. **Tier 1 — Q6 tax clarity — ✅ SHIPPED (2026-06-11).** `market_value` persisted on `ReportData` + rendered
   as "Est. Market Value"; market/assessed/effective-rate now read coherently; effective-rate **value**
   collapsed to one render (**closes D4**); assessment-history fallback fills estimated annual tax when the
   ptaxsim bill is missing. Verified on the real control PDF.
4. **Tier 2 — D3 map scale bar + radius ring — ✅ SHIPPED (2026-06-11).** Legends already existed, so D3
   reduced to a scale bar + distance reference ring on the three always-rendering maps. `_rendered_m_per_px`
   (pure, tested) + `_draw_scale_and_ring` (best-effort, swallows failure) in `backend/main.py`; called from
   `_generate_zoning_map` (0.25 mi), `_generate_construction_map` (0.5 mi = its real search radius), and
   `_generate_comps_map` (0.25 mi reference — comps search starts ~0.28 mi and may widen, so it's labeled a
   *reference* not a boundary). Verified visually on both QA-parcel PDFs. **Not yet deployed.**
5. **Tier 2 — P5 ownership-coverage validation** + **D8/Q14 cosmetic batch** — **next up.**
6. **Optional — P6 crime benchmark.**
**Defer:** Miss#6, V5-2a (until Tier 0 + geometry caching), V6-2 (CCAO-blocked), P3. **Resolved in passing
by Phase 3 / mock-only (drop):** Q14, Q1/Q2 hero, Q3/Q4, Q7/Q8, Q5. **D4 reclassified:** *not* moot — it is
the live 3× effective-rate render; now folded into the Tier-1 Q6 fix (see execution plan verification pass).

> **Verification pass (2026-06-11):** a read-only code review before Phase 4 implementation resolved 2 of 4
> open questions (Q6 root cause; comps already compute $/bldg-sf) and reclassified D4. Ordering unchanged;
> Tier-1 effort lower than estimated. Detail: `report-v6-execution-plan.md` → "Verification pass (2026-06-11)".

### Tier-1 (comps consolidation + Q6 tax clarity) SHIPPED — 2026-06-11

Both Tier-1 items landed and were verified on the **real** taxable control PDF (`14331030110000`,
19pp). 532 backend unit tests pass (`-m "not integration"`); +8 regression tests in
`test_report_tier1_fixes.py` (3 comps, 5 Q6) including a render of the real Jinja template.

**Comps consolidation.** The legacy "Comparable Sales Summary" `stats-box` (Median Sale Price · the
always-empty `Median $/Land Sq Ft` tile · Median $/Bldg Sq Ft) and the standalone price-range line were
removed. The section now leads with a neutral `Comparable Sales (N arm's-length transactions)` heading
and consolidates on the existing "Comparable Market Activity" / "Valuation Indicators" callout (`comp_valuation`).
$/bldg-sf is **preserved**: `_compute_comp_valuation` now carries `median_price_per_bldg_sqft`, surfaced as a
"Median price per building sq ft" line in the callout, and the per-row comps table column switched from
`$/Land SF` (mostly `—` in this market) to `$/Bldg SF`.

**New finding — $/bldg-sf coverage is also thin.** On the control run, **0 of 6** returned comps carried a
building sq ft (all rows `LAND SF —, BLDG SF —, $/BLDG SF —`), so the median $/bldg-sf line did not render.
Same root cause as the missing land area (CCAO characteristics frequently null for class-2xx sales in this
dense market). The consolidation is correct regardless — one presentation, no contradictory empty tiles —
but the surviving $/bldg-sf metric is *not* reliably populated. This answers the execution plan's open
"how often does `char_bldg_sf` exist" question: **rarely, on these QA parcels.**

**Q6 tax clarity.** `ReportData.market_value` is now persisted (was a throwaway local) and rendered as
"Est. Market Value (assessed ÷ 10% residential level)" between Assessed Value and Est. Annual Tax; the
effective-rate row is labeled "(of market value)". On the real control this reads coherently —
**$146,001 assessed → $1,460,010 market → $28,141 tax → 1.9% (of market value)** — where before the lone
1.9% sat next to $146,001 and looked like it should be ~19%. The effective-rate **value** now renders
**exactly once** (the orphan exec-summary block + the duplicate financial-section "Effective Rate" dt were
deleted) → **closes D4**; the conditional traffic-light "high effective tax rate" pill is a separate risk
signal and is kept. An **assessment-history annual-tax fallback** (`_resolve_market_value_and_tax`, rate
`config.report_fallback_tax_rate=0.021`) fills `estimated_annual_tax` from assessed value when the ptaxsim
bill is missing, flags it (`PropertySummary.tax_estimate_is_fallback` → "estimated from assessed value"
label), and intentionally leaves the effective rate `None` to avoid circularly echoing the assumed rate.

**Files (Tier-1):** `backend/main.py` (`_resolve_market_value_and_tax` helper extracted from Step-4 inline
logic; `median_price_per_bldg_sqft` added to `_compute_comp_valuation`; `market_value` wired into `ReportData`
+ mock path), `backend/models.py` (`ReportData.market_value`, `PropertySummary.tax_estimate_is_fallback`),
`backend/config.py` (`report_fallback_tax_rate`), `backend/templates/zoning_report.html` (comps block +
table column; tax grid; removed exec-summary + financial-section effective-rate dups),
`backend/tests/test_report_tier1_fixes.py` (+8). **Next: Tier-2 — D3 map legends/scale/radius ring.**

### Tier-2 (D3 — map scale bar + radius ring) SHIPPED — 2026-06-11

**Scope correction (stale-assumption finding):** the plan listed D3 as "legends + scale bar + radius ring,"
but **all three always-rendering maps already built styled `ax.legend(...)`**. So D3 reduced to the two
missing pieces — a **scale bar** and a **distance reference ring** — on `_generate_zoning_map`,
`_generate_construction_map`, and `_generate_comps_map`. The parcel/envelope maps stay untouched (GIS
returns no geometry → they don't render; "absent maps don't error" is satisfied by leaving them alone).

**What landed.** Two helpers in `backend/main.py`:
- `_rendered_m_per_px(lat, zoom)` — pure, unit-tested: `156543.03·cos(lat)/2**zoom / 2`. The `/2` encodes
  the `@2x` retina factor baked into `_latlon_to_px` (its trailing `* 2`), so the scale overlays match the
  exact projection used to place every marker — no independent constant that could drift.
- `_draw_scale_and_ring(ax, lat, zoom, img_w, img_h, ring_mi)` — best-effort (swallows its own exceptions so
  a map always still renders): a dashed reference ring around the subject pin (only drawn if it fits the
  frame) + a bottom-left scale bar that auto-picks the largest round distance (0.05/0.1/0.25/0.5/1/2 mi)
  under ~¼ of the frame width, with end ticks and a `"<d> mi"` label.

Ring radii by map: **zoning/cover 0.25 mi**, **construction 0.5 mi** (= the real nearby-construction search
radius, config `0.00725 deg`), **comps 0.25 mi** (a *distance reference*, not a claimed boundary — the comp
search starts at ~0.28 mi and may widen, so labeling it a boundary would be false; comps appearing outside
the ring honestly show the widening).

**Verified** by regenerating both real (non-mock) PDFs and extracting the embedded map PNGs: all three maps
on the control + the comps/construction maps on the EX subject show the dashed ring (with `mi` label), the
bottom-left scale bar, and the pre-existing legend. No render warnings in the server log. **542 unit tests
pass** (+10 in `backend/tests/test_report_d3_maps.py`: m/px math, helper adds ring+scalebar, round-distance
pick, no-raise on degenerate lat, and an end-to-end smoke render of each of the three maps).

**Files (Tier-2 D3):** `backend/main.py` (`_rendered_m_per_px`, `_draw_scale_and_ring`, `_SCALE_BAR_MILES`,
+3 call sites), `backend/tests/test_report_d3_maps.py` (+10). No model/template/config changes.
**Not yet deployed** (per workflow rules). **Next: Tier-2 — P5 ownership-coverage validation + D8/Q14 batch.**

### Phase 3 credibility pass — 2026-06-11

Post-Phase-3 decision-quality audit → targeted "don't imply certainty beyond the data" fixes.
Verified on regenerated real PDFs for both parcels; 60 report tests pass (+5 in `test_report_phase3_fixes.py`).

- **Valuation:** decision-box value field no longer implies a subject valuation. Tax-exempt/institutional
  parcels → "Tax Status: Exempt (institutional) — verify availability" (not a residential comp number).
  Otherwise "Nearby Sales (median) · n=N" at n≥3, or "Nearby Sales: $lo–$hi · N sales" at n<3 (no "median").
  Section heading is "Valuation Indicators" only when a real land-value range exists, else "Comparable
  Market Activity." n<3 prints "Too few sales for a reliable central estimate — treat as directional only."
  Disclosure now states the comps are nearby whole-property sales **not size-/condition-matched** to the
  subject (their lot/bldg size are unreported), not just that land area is missing.
- **Unit yield:** "As-of-right unit yield" → "Indicative unit capacity (screening estimate) … total,
  assuming redevelopment … **not a zoning determination** — limited by minimum lot area, rear-yard open
  space, FAR, height, parking, unit mix." Math unchanged.
- **Constraint language:** decision-box default "None identified" → "No major constraints flagged."
- **General:** "Max Buildable (as-of-right)" → "Max Buildable (FAR-based, gross)"; FAR-util "X sq ft unused"
  → "X sq ft below the FAR cap, typically realized through addition or redevelopment."

Intentionally unchanged: exec Site-Assessment traffic-light badges (CLEAR/CAUTION/RISK are backed by actual
data queries and are a recognized summary convention); the comp section still renders for exempt parcels
(market context with the stronger disclosure) rather than being suppressed. **Files:** `backend/main.py`
(`_build_decision_box`), `backend/templates/zoning_report.html`, `tests/test_report_phase3_fixes.py`.

### Phase 3 (decision quality) SHIPPED — 2026-06-10

Miss#1, V5-1b, P2, P1, P8, Exec, P5, V5-1c all **Fixed**. Verified on real PDFs for both
parcels (EX subject 16pp / RM-5 control 19pp) + a template-render smoke test for every block.
19 regression tests in `test_report_phase3_fixes.py`; 555 backend unit tests pass (10 live-API
integration failures are environmental — Cook County GIS / Socrata were down during the run).

**Page-1 decision box** ("Development Snapshot"): lot · zone · max buildable · value · key
constraint · approval path. Control renders 6/6; EX renders 4/6 with honest "n/a" for
lot/buildable (institutional parcel genuinely has no land-area record in assessor data).

**Key data finding (supersedes the plan's assumption that R3 unblocked land value):** comparable
sales in dense Lincoln Park are condo-dominated (class 299) and carry **no land area** in the
assessor characteristics file; even SFR `char_land_sf` is frequently null. After a best-row merge
fix, only ~1 sold parcel within 0.25mi/3yr has land area — so a land-value **range** (needs ≥3)
is data-blocked here. The honest design: median comparable **sale price** is the reliable value
anchor; the lot-normalized land value + $/buildable-sf render only when ≥3 land-bearing comps
exist, otherwise a labeled "Valuation Indicators" fallback explains the limitation. Not fabricated.

**Bonus credibility fix:** ARO ("affordable housing at 10+ units") was wrongly flagged as the key
constraint on a ~2-unit lot. Now gated on estimated as-of-right unit capacity (min-lot-area-per-unit,
else ~1,000 sf/unit) ≥ ~10 units.

**Files changed (Phase 3):** `backend/retrieval/zoning_definitions.py` (Title 17-2-0303-A MLA
table + `min_lot_area_per_unit()`), `backend/retrieval/property/sales.py` (best-row chars merge),
`backend/main.py` (`_compute_far_utilization`, `_compute_unit_yield`, `_compute_comp_valuation`,
`_ownership_interpretation`, `_build_decision_box`, ARO gating, wiring in real + mock paths),
`backend/models.py` (5 ReportData fields), `backend/templates/zoning_report.html` (decision box +
CSS, FAR/yield lines, Valuation Indicators block, ownership "so what", always-on Advisory tier),
`backend/tests/test_report_phase3_fixes.py` (+19).
**Next: Phase 4 (UX & visualization)** — map legends/scale/radius ring, $/sf comps chart, combined
site-context map (GIS-blocked), badge vocabulary, crime benchmark.

### Phase 2 (credibility) SHIPPED — 2026-06-10

P4, Q12/P9, D6, D5, D9, D10, D2, Q10, P7 **Fixed**; Q9 + Q11 **investigated → not bugs** (authoritative
City GIS confirmed via ArcGIS intersect + shapely PIP); D1 **not reproducible** on real data. Verified on
real PDFs for both parcels (EX 14pp / control 18pp). 8 regression tests in `test_report_phase2_fixes.py`.
Key finding: the audit's Q9 "1.5mi inland false positive" was a mock-era mis-estimate — the parcel is
genuinely in the Lakefront Protection District (~0.2mi W of Lake Shore Dr) and the flag is a real
constraint. Detail + per-item table: `guides/report-v6-execution-plan.md` (Phase 2 status).
**Next: Phase 3 (decision quality)** — cover decision box, land-value range, FAR utilization, unit yield.

### Phase 1 (viability) SHIPPED — 2026-06-10, commit f0c1996

R1, R2, R3, R4 all **Fixed** and verified on real PDFs for the EX subject + taxable control (table below).
Full plan, per-fix detail, and verification evidence: `guides/report-v6-execution-plan.md`.
Also fixed two latent general bugs (PIN→coords `latitude/longitude` resolver; `standards.max_far`→`far`).
**Next: Phase 2 (credibility)** — Q9 Lakefront false positive, P4 311 alarmism, Q12/P9 "EX called standard"
(now contradicts the new Tax-Exempt callout), plus the D5/D6/D9/Q11/V6-5 dedup/label batch.

### Real-data regeneration done (2026-06-10) — reclassification

Regenerated real (non-mock) report for the same parcel → `/tmp/report_v6_real.pdf` (14 pp). Full analysis in `report-v6-audit.md`. The real report for the flagship address is **largely hollow** — mock=true was masking it.

**NEW critical real findings (top of the real backlog):**

**Verification parcels (use both after every change; mock=true banned from data QA):**
- **Subject / failure-path:** PIN `14283190070000` (443 W Wrightwood Ave) — class **EX, tax-exempt institutional**, RM-6. Exercises R1/R2/R3 + exemption labeling.
- **Taxable control / happy-path:** PIN `14331030110000` (Lincoln Park, ~0.3mi, RM-5 — same RM family). 2024 tax $23,024 / AV $114,600, non-zero assessment history, yrblt 1888 (→ nonconformity), 2023 sale $1.207M, abundant class-2 comps. See `report-v6-execution-plan.md` + memory `project_report_verification_parcels`.

| ID | Finding | Impact | Effort | Status |
|----|---------|--------|--------|--------|
| R1 | Structured zoning extraction fails for RM-6 → dumps Chapter 17-5 **Manufacturing** code into a residential report; no Bulk table / setbacks / uses / dev potential. Fall back to deterministic zone-definitions table (has RM-6 FAR 4.4) | 5 | M | **Fixed (Phase 1)** — `standards_from_definitions()` synthesizes ZoningStandards from the Title 17 table when AI extraction is None/low-conf; raw-dump only for PD/unknown |
| R2 | Tax & assessment missing — diagnosed as 3 stacked bugs: (a) assessment query ordered by non-existent `tax_year` col (→`year`); (b) ptaxsim queried year today-1=2025 but DB max 2024 (→clamp to latest ≤ requested); (c) subject PIN genuinely class EX/$0 | 5 | M | **Fixed (Phase 1)** — a+b fix all taxable reports; c renders a "Tax-Exempt (Class EX)" callout. Also fixed stale char cols (char_apts/char_air/derived age) |
| R3 | No comparable sales — root cause was `class_prefix=bldg_class[0]`="E" for EX subject. Now derive comp class from zoning when non-marketable + progressive widening | 5 | M–L | **Fixed (Phase 1)** — `_comp_class_prefix()` (EX/RM→"2"); `nearby_comparable_sales` widens radius→window with a labeled basis. EX subject now returns 9 comps |
| R4 | Nearby-dev formatting: "$3987K" (should ~$4.0M) and "within 0.25mi" vs "0.5mi" header | 2 | XS | **Fixed (Phase 1)** — `_fmt_money()` ($K/$M) + radius label derived from config |

**Reclassified — CONFIRMED REAL (fix):** Q9, Q11, D6, P4, D9, D5, V6-5, Q12/P9.
**Reclassified — MOCK-ONLY (drop from fix list):** Q3/Q4 (real fails via R1 instead), Q7/Q8, Q1/Q2 (hero absent in real), Q5/Q6 (no tax section in real → R2), Q10, Q14, P7. Justifies a decoupling/fallback guard, not per-symptom fixes.

**Revised execution order:** (1) **R1 zoning fallback** ✅ → (2) **R3 comps fallback** ✅ + **R2 tax/assessment source** ✅ → (3) confirmed-real cleanups (D6, P4, D9, D5, V6-5, **R4 ✅**, Q12) ← **Phase 2 starts here** → (4) Q9 Lakefront overlay validation → (5) cover decision box + land-value range (depends on R1/R3) → (6) big-bet maps.

**Original execution order (pre-regen, from audit):** (1) coherent-mock + Quick-Wins pass → (2) cover decision box + land-value range → (3) 311/overlay validation → (4) real-data regen + decoupling guards → (5) big-bet maps.

## Blocked / Data-Dependent

| Feature | Blocker | Research Needed |
|---------|---------|----------------|
| **Parcel boundary map** | Requires real vertex coordinates from Cook County GIS. GIS is intermittently down. Fabricated rectangles are misleading — removed. | Can Socrata Parcel Universe (`pabr-t5kh`) return geometry? Can we cache/pre-fetch polygons? Alternative geometry sources? |
| **Year built / nonconformity analysis** | Code shipped, but CCAO Characteristics API returns 400 for some PINs (e.g., 14283190070000). When year_built is null, nonconformity analysis doesn't trigger. | Why does CCAO fail for some PINs? Alternative year_built sources? Should we fall back to bldg_age? |
| **Envelope visualization** | Depends on parcel_geometry (same GIS blocker as parcel map). When geometry unavailable, section doesn't render. | Same as parcel map — needs reliable geometry source |
| **Comps map** | Code shipped with mock data. Needs validation that real comps queries return non-zero lat/lon from Parcel Universe. | Test with real (non-mock) report generation |

## Confirmed Limitations (No Fix Possible)

| Feature | Why | Workaround |
|---------|-----|------------|
| Property ownership (owner name) | Cook County doesn't expose taxpayer names in open data. Assessor website is dynamic/CAPTCHA-protected. | "Ownership Intelligence" section derives signals from sales/tax data. Disclaimer explains limitation. |
| Rental market indicators | ACS median rent is 2-year lagged and not unit-type specific. | Deferred per V5 decision — only build if multifamily developers become primary customer |
| Pending zoning changes | Requires PDF parsing from Chicago Legistar. High maintenance. | Deferred to Phase 4+ per North Star |

## Explicitly Not Building

From V5 planning — features evaluated and rejected with rationale.

| Feature | Rationale |
|---------|-----------|
| Development scenario verdicts ("PERMITTED") | Crosses into entitlement interpretation. Wrong verdicts destroy trust. Envelope approach is safer. |
| Full automated pro forma (IRR/NPV) | Too many assumptions. Provide inputs, not projections. |
| Soil/geotechnical analysis | USDA SSURGO too coarse for urban lots. Always requires borings. |
| Wetlands/endangered species | Irrelevant for Chicago urban infill |
| Topography/elevation | Chicago is flat |
| School performance ratings | Property report, not feasibility |
| Noise contour mapping | Complex integration, marginal value |
| Construction cost estimation from permits | Reported costs notoriously under-reported |
| Full subdivision cost estimation | 50+ line items varying wildly by project |
| Property photos / street view | No free API available |

## Future Ideas (Deferred to V7+ / Customer Validation)

| Idea | Trigger to Build |
|------|-----------------|
| IL EPA environmental risk (LUST/SRP/RCRA) | Customer interview reveals missed environmental flag |
| Rental market indicators (vacancy, rent-to-income) | Multifamily developers become primary customer |
| Pro forma inputs table | Customers repeatedly ask for it |
| Frontage adequacy check | Envelope visualization ships with proven edge classification |
| Alley access detection | Customer asks about it |
| Utility infrastructure flags | Customer reveals utility access as pain point |
| Comprehensive plan alignment | Attorneys/planners become a customer segment |
| Traffic/ADT counts | Commercial developers request it |
| Year-built in comparable sales table | Low effort, add when CCAO data pipeline is more reliable |
