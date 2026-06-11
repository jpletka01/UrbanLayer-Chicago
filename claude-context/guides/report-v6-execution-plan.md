# Report V6 — Implementation Strategy & Phased Execution Plan

Plan date: 2026-06-10.

## STATUS — R5 parcel-resolution bug FIXED (2026-06-11, commit 2c12286)

**Found while validating P5 (Tier-2, "next up").** Validating "does ownership render?" exposed a far more
serious, un-backlogged bug: **the Socrata parcel bounding-box fallback resolved the subject to the wrong
neighbor whenever Cook County GIS is down — which is currently always.**

- **Mechanism:** `_lookup_parcel_socrata` fetched only `limit_ccao_parcels=20` rows from a ~220m box (no
  `$order`) then picked closest. Dense residential boxes hold ~500-600 parcels, so the arbitrary 20 usually
  **excluded the true parcel** → report rendered a neighbor's class/year/assessments/sales/tax/ownership.
- **Reproduced:** control `14331030110000` (class 205, 2023 sale $1.207M) → resolved `14331090140000`
  (class 211, 0 sales); 557 parcels in box, true PIN not in the fetched 20. P5 ("ownership renders on
  neither QA parcel") was a *symptom*: the wrong neighbor had no sales.
- **Fix:** cap → 2000 so closest is computed over the whole bbox; warn on cap-hit (condos stay
  coord-ambiguous). **Verified:** control now resolves class 205 + 2023 sale + Ownership Intelligence
  ("What this means for a buyer"); EX subject still class EX (`match=True`). 543 unit tests + regression test.
- **Implication for this whole document:** several "verified on real data" claims were produced while GIS
  was down and may describe a neighbor parcel, not the named PIN. The deterministic numbers tied to a
  *specific* PIN (e.g. R2 "$114,600 assessed", "1888 year built") should be re-spot-checked post-fix;
  coords-based sections (regulatory overlays, comps, transit, crime) are unaffected.
- **Re-ranking consequence:** R5 outranked the entire remaining Phase-4 backlog (it is data-correctness, not
  polish) and is now fixed. **DEPLOYED 2026-06-11** (with D3; live image built 19:05 UTC, git `2fdf465`,
  verified inside the running prod container). Remaining backlog is low-leverage cosmetics or GIS-blocked —
  see "Re-prioritized ranking" below (updated).

---

## STATUS — Tier 2 D3 SHIPPED (2026-06-11)

**D3 (map scale bar + radius ring) is implemented and verified on both real QA-parcel PDFs.** Tier-0/Tier-1
shipped and are **deployed**; prod memory was validated afterward (no OOM history, no restarts, backend
<1 GB, `mem_limit` still UNLIMITED — the deferred infra backstop — but not needed at current load; the
original OOM concern was overstated). GIS still returns no geometry, so parcel/envelope maps remain absent
and the GIS-blocked viz items (Miss#6, V5-2a) stay deferred.

**Stale-assumption finding (changes D3 scope):** the plan framed D3 as "legends + scale bar + radius ring,"
but **legends already existed** in all three always-rendering maps. D3 therefore reduced to the **scale bar +
distance reference ring** only. Effort came in below the plan's "S."

| Piece | Resolution |
|-------|-----------|
| Scale math | `_rendered_m_per_px(lat, zoom) = 156543.03·cos(lat)/2**zoom / 2` (pure, unit-tested). The `/2` encodes the `@2x` retina factor from `_latlon_to_px`'s trailing `* 2`, so overlays match the projection markers use |
| Scale bar | `_draw_scale_and_ring`: bottom-left bar auto-picking the largest round distance (0.05/0.1/0.25/0.5/1/2 mi) under ~¼ frame width, with end ticks + `"<d> mi"` label |
| Radius ring | dashed reference ring around the subject pin, drawn only if it fits the frame. Zoning/cover **0.25 mi**, construction **0.5 mi** (= real search radius, config `0.00725 deg`), comps **0.25 mi** *reference* (search starts ~0.28 mi and widens — labeled a reference, not a boundary; comps outside it honestly show widening) |

**Verified:** regenerated both real PDFs, extracted embedded map PNGs — all three control maps + the EX
comps/construction maps show ring + scale bar + legend; no render warnings in the log. **542 unit tests pass**
(+10 in `test_report_d3_maps.py`). **Files:** `backend/main.py` (`_rendered_m_per_px`, `_draw_scale_and_ring`,
`_SCALE_BAR_MILES`, +3 call sites), `backend/tests/test_report_d3_maps.py`. No model/template/config changes.
**DEPLOYED 2026-06-11.** **Next: Tier-2 P5 ownership-coverage validation + D8/Q14 batch.**

---

## STATUS — Tier 1 SHIPPED (2026-06-11)

**Both Tier-1 items (comps-section consolidation + Q6 tax clarity) are implemented and verified on the
real taxable control PDF `14331030110000` and the real EX subject `14283190070000`.** Tier-0 shipped
earlier in commit d5c165c. 532 backend unit tests pass (`-m "not integration"`); +8 regression tests in
`test_report_tier1_fixes.py`.

| Item | Resolution | Verified on real data |
|------|-----------|------------------------|
| Comps consolidation | Removed the legacy "Comparable Sales Summary" `stats-box` (+ the always-empty `Median $/Land Sq Ft` tile + standalone price-range line). Section now leads with a neutral `Comparable Sales (N …)` heading and consolidates on the "Comparable Market Activity"/"Valuation Indicators" callout (`comp_valuation`). $/bldg-sf preserved: median in the callout + per-row table column `$/Land SF`→`$/Bldg SF` | Control: single "Comparable Sales (6 …)" + "Comparable Market Activity", no legacy block; EX: "Comparable Sales (4 …)" |
| Q6 tax clarity | `ReportData.market_value` persisted + rendered "Est. Market Value" between Assessed and Est. Annual Tax; effective rate labeled "(of market value)"; effective-rate **value** collapsed to **one** render (closes **D4**); `_resolve_market_value_and_tax` adds an assessment-history annual-tax fallback (`config.report_fallback_tax_rate=0.021`, `PropertySummary.tax_estimate_is_fallback` → "estimated from assessed value", effective rate left None) | Control (post-R5, pin-only): **$114,600 assessed → $1,146,000 market → $23,024 tax → 2.0% (of market value)**, one effective-rate value row; EX: market value + effective rate correctly suppressed, Tax-Exempt callout kept |

**New data finding (answers an open question below):** the surviving $/bldg-sf metric is *also* thinly
populated — on the control run **0 of 6** returned comps carried a building sq ft (all rows `—`), same
missing-CCAO-characteristics root cause as land area. Consolidation is still correct (one presentation, no
contradictory `—` tiles); the metric simply renders only when data exists.

**Files (Tier-1):** `backend/main.py` (`_resolve_market_value_and_tax` extracted from inline Step-4 logic;
`median_price_per_bldg_sqft` added to `_compute_comp_valuation`; `market_value` wired into `ReportData` +
mock path), `backend/models.py` (`ReportData.market_value`, `PropertySummary.tax_estimate_is_fallback`),
`backend/config.py` (`report_fallback_tax_rate`), `backend/templates/zoning_report.html` (comps block + table
column; tax grid; removed the exec-summary orphan + financial-section effective-rate dups),
`backend/tests/test_report_tier1_fixes.py` (+8).

**Not done / deferred:** condo (class 299) vs non-condo comp tagging (optional in the plan — skipped to stay
low-risk; the consolidation made it unnecessary for the contradiction fix). **Deploy still pending** (per
workflow rules). **Next: Tier 2 — D3 map legends / scale / radius ring.** ✅ **D3 now SHIPPED — see the
Tier-2 status block at the top of this file.**

---

## STATUS — Phase 3 SHIPPED (2026-06-10)

**Phase 3 (decision quality) complete, verified on real PDFs for both parcels.** All 8 items
landed: cover decision box (Miss#1), land-value/comp valuation (V5-1b/P2), FAR utilization (P1),
as-of-right unit yield (P8), consolidated key-constraint on page 1 (Exec), ownership "so what" (P5),
always-on Advisory tier (V5-1c).

| Item | Resolution | Verified |
|------|-----------|----------|
| Miss#1 decision box | Page-1 "Development Snapshot" — lot · zone · max buildable · value · key constraint · approval path; honest "n/a" | Control 6/6; EX 4/6 (lot/buildable genuinely n/a — institutional parcel, no land-area record) |
| V5-1b land value | Was data-blocked, not a query bug: comps are condo-dominated (class 299) with **no land area**; even SFR `char_land_sf` often null. Best-row chars merge added; range renders only with ≥3 land-bearing comps | Both: honest "Valuation Indicators" fallback on median **sale price** (range needs ≥3 land comps; ~1 available here) |
| P2 comp valuation | `_compute_comp_valuation`: median comp sale anchor + land range + $/buildable-sf when land comps exist; flags limit otherwise | Both: median comp sale + basis + limitation note |
| P1 FAR utilization | "existing X sf uses Y% of FAR-allowed Z sf" (vacant variant) | Control: "2,992 sf uses 48% of 6,250 sf" |
| P8 unit yield | From authoritative MLA-per-unit (Title 17-2-0303-A table → `min_lot_area_per_unit`); R districts only | Control RM-5: "~7 units (3,125 ÷ 400)" |
| Exec consolidate | Decision box surfaces the single most deal-shaping constraint (binding-priority); **ARO gated** to lots that can reach 10+ units (was a false positive on a ~2-unit lot) | Control: ARO correctly suppressed; EX: "National Register district" surfaced |
| P5 ownership | "What this means for a buyer" deal read (off-market / basis / non-arm's-length) | Template render confirmed (off-market line) |
| V5-1c advisory | Advisory tier always renders (appraisal, validate yield w/ zoning attorney, broker comps) + conditional incentive items | Both |

**Files changed (Phase 3):** `backend/retrieval/zoning_definitions.py`, `backend/retrieval/property/sales.py`,
`backend/main.py`, `backend/models.py`, `backend/templates/zoning_report.html`, `tests/test_report_phase3_fixes.py` (+19).
555 unit tests pass (10 live-API integration failures environmental — GIS/Socrata down during run).

Remaining: Phase 4 (UX/viz) — not started.

### Credibility pass (2026-06-11) — applied after a post-Phase-3 decision-quality audit

Goal: the report must not imply certainty beyond the data. Highest-leverage item was the decision
box's value field (most-read, least-qualified). Changes, verified on both real PDFs:
- **Valuation** never implies a subject value: exempt parcels show tax status, not a comp number;
  "Nearby Sales" framing (median only at n≥3, range + "directional only" at n<3); disclosure says
  comps are nearby whole-property sales **not size-/condition-matched**. Heading downgrades to
  "Comparable Market Activity" when no real land-value range exists.
- **Unit yield** reframed "as-of-right yield" → "Indicative unit capacity (screening estimate) …
  not a zoning determination" with min-lot-area/open-space/redevelopment caveats (math unchanged).
- **Constraints** "None identified" → "No major constraints flagged."
- **Labels** "Max Buildable (as-of-right)" → "(FAR-based, gross)"; FAR "unused" → "below the FAR cap."
Left unchanged on purpose: traffic-light badges (query-backed); comp section still renders for exempt
parcels (now with a stronger disclosure). Detail: `report-status.md` (Phase 3 credibility pass).

---

## STATUS — Phase 2 SHIPPED (2026-06-10)

**Phase 2 (credibility) complete, verified on real PDFs for both parcels.** Two audit items
(**Q9 Lakefront, Q11 Lakeview NR**) were **investigated and found NOT to be bugs** — the City GIS
data is authoritative and correct; the original audit ran on a mock and mis-estimated geography.

| Item | Resolution | Verified on |
|------|-----------|-------------|
| P4 311 rodent alarmism | Severity taxonomy: `_STRUCTURAL_RISK_TYPES` vs `_ROUTINE_SERVICE_TYPES`; rodent/rat → `routine_service_flags`, no longer a structural high-risk constraint | EX cover badge downgraded RISK→CAUTION (real open violations); routine note renders |
| Q12/P9 EX "standard" | Assembler labels exempt class → `property_tax_class="exempt"`, consistent with R2c callout | EX shows "Tax Incentive Class: exempt…"; control 205 still "standard" |
| Q9 Lakefront | **TRUE positive** — parcel is genuinely in the LPO (≈0.2mi W of Lake Shore Dr; confirmed by ArcGIS intersect + shapely PIP; inland controls excluded). Only the misleading lead label fixed | EX: "Lakefront Protection District [Private Lakefront]" |
| Q11 Lakeview NR | **CORRECT** — real National Register "Lakeview Historic District" spans Wrightwood per its ADDRESS field; NR names are independent of community area. No code change | EX shows authoritative name, kept |
| D6 dup brackets | `[desc]` shown only when it differs from name (case-insensitive) | EX: "ADU Eligible Areas" / "ARO Zones" — no dup |
| D5/D10 transit | Removed regulatory dup; single canonical block in Market Context at 1-decimal | both: one "Transit Access" |
| D9 ZONE TYPE | Removed redundant numeric row (no published domain; Zone Class already labels it) | both: no Zone Type row |
| D2 construction map | `<figure page-break-inside:avoid>` + caption binds map together | template |
| Q10 CAGR | Already derived from real oldest/newest year + reassessment disclaimer; regression-tested | control: "over 3 years (2022–2025)…" |
| P7 appreciation | Synthesis signal reframed reassessment-trend + tax-burden, not "appreciation opportunity" | code (CAGR>5 not present on either parcel) |
| D1 blank page | **Not reproducible** on real data (15/18pp, no blank page) — was mock-only | both |

**Files changed (Phase 2):** `backend/retrieval/three11.py` (severity taxonomy), `backend/models.py`
(`Address311Summary.routine_service_flags`), `backend/assembler.py` (exempt tax-class branch + 311 passthrough),
`backend/retrieval/regulatory/__init__.py` (lakefront lead label), `backend/main.py` (P7 reframe),
`backend/templates/zoning_report.html` (D6/D9/D5/D2/P4 display), tests (`test_report_phase2_fixes.py` +8).
539 tests pass (8 pre-existing live-API integration failures unrelated).

Remaining: Phase 3 (decision quality), Phase 4 (UX/viz) — not started.

---

## STATUS — Phase 1 SHIPPED (2026-06-10, commit f0c1996)

**Phase 1 (viability: R1, R2, R3, R4) is complete, verified, committed, and pushed to `main`.**

Phase 1 verified end-to-end by regenerating real (non-mock) PDFs for both parcels and extracting text:

| Fix | Subject EX `14283190070000` | Control `14331030110000` |
|-----|------------------------------|--------------------------|
| R1 zoning fallback | "RM-6 — Residential Multi-Unit (FAR 4.4)" bulk table; **no manufacturing text** | RM-5 FAR 2.0, max buildable 6,700 sf |
| R2a assessment column | exempt (correct) | assessed **$114,600** + history + trend |
| R2b ptaxsim year clamp | $0 exempt (correct) | est. tax **$23,024** (2024 clamped from 2025) |
| R2c exempt label + char drift | "Tax-Exempt (Class EX)" callout | Year Built **1888** → nonconformity flagged |
| R3 comp class + widening | **6 comps** (was 0), basis labeled | 4 comps, basis labeled |
| R4 money/radius format | "$4.0M" (was $3987K), "0.5mi" matches header | — |

**Files changed (Phase 1):** `backend/zoning_extract.py` (`standards_from_definitions`), `backend/main.py`
(`_comp_class_prefix`, `_fmt_money`, fallback wiring, `max_far`→`far`, lat/lon resolver), `backend/models.py`
(`ZoningStandards.extraction_confidence="definitions"`, `PropertySummary.tax_exempt`, `ComparablesSummary.comp_basis`),
`backend/retrieval/property/{__init__,assessments,sales,tax_estimate}.py`, `backend/templates/zoning_report.html`,
tests (`test_report_phase1_fixes.py` +8, updated `test_property_orchestrator.py` to real schema). 489 tests green.

**Bonus general bugs fixed in Phase 1:** PIN→coords resolver used non-existent `latitude/longitude` columns
(broke pin-only report lookups); constraints synthesizer referenced `standards.max_far` (field is `far`).

**Phase 2 entry point:** Q9 (Lakefront false positive), P4 (311 rodent alarmism), and **Q12/P9** — the
subject still prints *"Tax Incentive Class: standard — class EX is a standard classification,"* which now
directly contradicts the new Tax-Exempt callout. See "Phase 2" section below.

---

Original plan date: 2026-06-10. Status when written: **strategy only — no implementation started.**

Sources of truth: `report-status.md`, `report-v6-audit.md`, `report-v6-improvements.md`.
Subject parcel for all diagnostics: **PIN 14283190070000** (443 W Wrightwood Ave, Lincoln Park / Lake View township, **class EX**).

This plan is sequential and verifiable: after each phase, regenerate a real (non-mock) report for the
subject PIN (and one taxable control PIN) and re-audit against the acceptance criteria before moving on.

```bash
# Standard verification command per phase (real data, not mock):
curl -o /tmp/report_phaseN.pdf "http://localhost:8001/api/report?pin=14283190070000&address=443+W+Wrightwood+Ave" -H "Cookie: session=dev"
# Plus a taxable control parcel (chosen in Phase 1, see R2):
curl -o /tmp/report_control.pdf  "http://localhost:8001/api/report?pin=<TAXABLE_PIN>" -H "Cookie: session=dev"
```

---

## Root-cause findings (verified against live data, not inferred)

The audit attributed R1/R2/R3 to a single bad PIN. Investigation shows each is a **stack** of a
general pipeline bug plus a property-specific reality. This distinction drives the whole plan: the
general bugs must be fixed (they silently degrade *every* report), and the property-specific realities
must be *labeled*, not hidden.

### R1 — Structured zoning extraction fails for RM-6 (CRITICAL)

**Root cause (verified):**
- `backend/zoning_extract.py::extract_zoning_standards()` runs 5 vector searches → Haiku JSON
  extraction. For RM-6 it returns `None` (vector search surfaces wrong-chapter chunks — Chapter 17-5
  **Manufacturing Districts** — and/or Haiku emits null/unparseable JSON).
- When `standards is None`, `dev_potential` is never computed (`main.py:1987` guards on `standards`),
  and the template (`templates/zoning_report.html:647`) falls through to the
  `{% elif report.bulk_standards_text %}` branch, printing *"Structured extraction unavailable…"* then
  dumping `bulk_standards_text`. That text is built by a **separate generic** semantic search at
  `main.py:2024` (`f"{zone_class} bulk standards floor area ratio…"`) which retrieved the manufacturing
  ordinance — so a residential report displays manufacturing code.
- **The correct data already exists, unused:** `retrieval/zoning_definitions.py:96` defines
  `RM-6 → FAR 4.40, 70 ft, 60% coverage, §17-2-0104, _RM_USES`. `get_zone_definition()` has a robust
  fallback chain (exact → prefix → PD/PMD → unknown).

**Affected files:** `backend/zoning_extract.py`, `backend/main.py` (~1985–2035 orchestration, dev-potential
guard, bulk-text branch), `backend/retrieval/zoning_definitions.py` (numeric parsing of `max_height`/
`lot_coverage` strings), `backend/models.py` (`ZoningStandards` needs a provenance marker), 
`backend/templates/zoning_report.html` (standards branches at 569/635/647).

**Dependencies:** none external. `DevelopmentPotential` calc (`calculate_development_potential`) already
consumes a `ZoningStandards` — the fallback just needs to *produce* one.

**Risks:**
- `ZoneDefinition` stores `max_height`/`lot_coverage` as display strings ("70 ft", "60%"); converting to
  `ZoningStandards.max_height_ft:int` / `lot_coverage_pct:float` needs careful parsing (PD/unknown rows
  have `far=None`).
- Definitions table FAR is *base* district only — must keep the existing "Reflects base district
  standards only; overlays/PD/transition may alter" disclaimer and not over-claim setbacks/parking the
  table doesn't have (those fields stay null → template already hides them).

**Fallback strategy:** when AI extraction returns `None` (or low confidence), synthesize a
`ZoningStandards` from `get_zone_definition(zone_class)` with `extraction_confidence="definitions"` (new
provenance value) and a note "Standards from deterministic zone-class table (Title 17), not site-specific
extraction." **Never** dump raw `bulk_standards_text` when a definitions row exists; reserve that branch
for truly unknown zones (PD without ordinance). Definitions fallback feeds `calculate_development_potential`
so max-buildable/FAR returns.

**Verification:** regenerate real report → zoning section shows an RM-6 Bulk & Density table (FAR 4.4,
70 ft, 60%), residential permitted uses, Development Potential block with max buildable, and **no**
manufacturing text. Add a unit test asserting `extract_zoning_standards`→`None` yields a definitions-sourced
`ZoningStandards` for RM-6 with `far==4.4`.

**Regression risk:** zones where AI extraction *succeeds* must still win over the table (table is fallback
only). PD/PMD/unknown must still degrade gracefully (no fabricated FAR). Verify a B3-2 / RT-4 control
still renders extracted (not table) standards when extraction succeeds.

### R2 — Tax & assessment data missing (CRITICAL)

**Root cause — three independent layers (all verified):**
1. **Assessment query column bug (general — breaks every report).**
   `retrieval/property/assessments.py:34` sets `"$order": "tax_year DESC"`, but dataset `uzyt-m557` has
   **no `tax_year` column** — it is `year`. Live query returns:
   `query.soql.no-such-column; No such column: tax_year`. The exception is swallowed → `[]` for *all*
   PINs. `_build_summary` (`property/__init__.py:175`) also reads `row.get("tax_year")` (also wrong → `year`).
2. **ptaxsim year off-by-one (general — breaks every 2026 report).**
   `property/__init__.py:57` uses `tax_year = datetime.date.today().year - 1` = **2025**, but the local
   ptaxsim DB max year is **2024** (verified: `SELECT MAX(year) FROM pin` → 2024). `estimate_tax(2025,…)`
   finds no row → returns `None` → tax gap for every report run in 2026.
3. **Subject PIN is genuinely tax-exempt (property-specific).**
   Parcel Universe shows `class="EX"`; ptaxsim shows `tax_bill_total=0.0, av_clerk=0` for 2020–2024;
   CCAO assessments show `mailed_tot=0.0` for 2024–2026. This is a real exempt institutional parcel —
   there is no tax/assessed value to display even after (1) and (2) are fixed.

**Affected files:** `backend/retrieval/property/assessments.py` (order + nothing else there reads year),
`backend/retrieval/property/__init__.py` (tax-year clamp; read `year`; detect EX/zero → exemption flag),
`backend/retrieval/property/tax_estimate.py` (treat `tax_bill_total==0` for EX distinctly from "not found"),
`backend/models.py` (`PropertySummary`: add `tax_exempt: bool` / `exempt_class` marker),
`backend/main.py` (effective-rate calc ~2004; pass exemption to template),
`backend/templates/zoning_report.html` (render "Tax-exempt parcel (Class EX)" block instead of a silent gap),
`backend/config.py` (optional `ptaxsim_max_year` setting instead of `today-1`).

**Dependencies:** ptaxsim.db is present (9.4 GB, years ≤2024). CCAO assessment/sales datasets are live
Socrata. No new data sources required for the general fixes.

**Risks:**
- Clamping `tax_year` to `min(today-1, ptaxsim_max_year)` must not silently show a stale year as current —
  label the tax year explicitly ("2024 tax bill estimate").
- EX detection must not mislabel partially-exempt or class-transition parcels; key off `class` startswith
  "EX" *and* zero assessed value, and word it as "currently exempt — verify status."

**Fallback strategy:** layered. (a) Fix column + year so taxable parcels populate. (b) If assessed value
present but ptaxsim row missing, still show assessment history + effective-rate "n/a (tax estimate
unavailable)". (c) If `class==EX`/zero, show an explicit **Tax-Exempt Parcel** callout (this is
decision-relevant — signals institutional ownership / possible disposition complexity), not "data
unavailable." (d) **Pick a taxable control PIN** for the flagship demo so the happy path is provable;
keep the EX parcel as the exemption-handling test case.

**Verification:** taxable control PIN renders assessed value, assessment history (correct years, no 400),
estimated annual tax (2024), and effective rate next to **market** value. Subject EX PIN renders a clean
"Tax-Exempt (Class EX)" block. Add unit tests: assessment query uses `year`; tax-year clamp ≤ ptaxsim max;
EX → `tax_exempt=True`.

**Regression risk:** the assessment-history-driven `effective_tax_rate` fallback (`main.py:1999`) and the
assessment-trend / CAGR sections depend on populated history — once the column bug is fixed, history that
was *always empty* will start rendering, surfacing the Q10 CAGR-label and P7 "appreciation" issues (Phase 2)
on real data for the first time. Expect those to light up and fix in Phase 2.

### R3 — Comparable sales retrieval fails (CRITICAL)

**Root cause (verified):** `main.py:1952` sets `class_prefix = ctx.property.bldg_class[0]`. For the EX
subject that is `"E"`. `nearby_comparable_sales` (`sales.py:104`) filters Parcel Universe by
`class LIKE 'E%'` → only exempt parcels, which essentially never sell arm's-length → 0 comps → no table,
chart, map, median, or land value. Verified nearby inventory within 0.25 mi (radius_deg 0.004):
**5,538 residential (class 2) parcels**, with multiple arm's-length sales 2023–2025 ($120k–$350k, class 299).
The comps engine works; it is pointed at the wrong class.

**Affected files:** `backend/main.py` (class-prefix derivation ~1952), `backend/retrieval/property/sales.py`
(`nearby_comparable_sales` — class mapping + progressive widening), `backend/config.py` (radius/years/limits),
`backend/templates/zoning_report.html` (comp-basis provenance line).

**Dependencies:** R1 (zoning class) is the better signal for *redevelopment* comps than the current exempt
class — sequence R3 after R1 so RM→residential mapping is available. Land-value range (Phase 3) consumes R3.

**Risks:**
- Broadening class changes comp semantics ("what could be built here" vs "what this exempt parcel is").
  Must label the basis ("Comparable residential sales within 0.25 mi" with class + count).
- Progressive widening (radius → years → class) can pull in non-comparable sales; cap widening and show
  the actual radius/window used, plus sample size, so the reader can judge.

**Fallback strategy:** (a) if subject class is non-marketable (EX / exempt / vacant-institutional), derive
comp class from **zoning** (RM* → residential prefix "2"; B/C → commercial), else from subject class.
(b) Progressive widening with provenance: same-class @0.25mi/3yr → widen radius (0.5mi) → extend window
(5yr) → relax to land/all-residential, stopping at first non-empty tier; always emit the tier used.
(c) If still empty, show "No qualifying comparables — see nearby development activity" (don't fabricate).

**Verification:** subject EX report shows a residential comps table/chart/map with ≥3 sales, a stated basis
line, and a derived median $/sf. Add a unit test: EX subject + RM zoning → comp class "2", non-empty comps
from mocked Socrata.

**Regression risk:** taxable residential subjects already on the happy path must keep using their own
class (don't force zoning-derived class when subject class is already marketable). The comps *map* and
*scatter chart* (V6-8b, D7) will now render with real coords for the first time — validate marker coords
are non-zero (the `report-v6-improvements.md` open item).

---

## Phasing overview

| Phase | Theme | Gate to exit |
|-------|-------|--------------|
| 1 ✅ SHIPPED | Report viability (R1, R2, R3) | DONE — real report for subject + taxable control no longer hollow; zoning/tax/comps each render correct data or a correct labeled state |
| 2 | Credibility (false positives, dupes, mislabels, formatting) | No factual contradiction or false risk signal survives a re-audit |
| 3 | Decision quality (decision box, land value, FAR util, yield, constraints) | A reader gets the go/no-go answer in <60s on page 1 |
| 4 | UX & visualization (legends, combined map, layout) | Maps are self-explanatory; no orphaned/blank pages |

Effort key: XS (<1h) · S (few h) · M (~1 day) · L (multi-day) · XL (blocked on external data/infra).
Data-availability risk: Low / Med / High.

---

## Phase 1 — Report viability fixes (R1, R2, R3)

Goal: a real report for the subject parcel stops being hollow. These gate everything else — land value
(Phase 3) depends on R3; FAR utilization/yield depend on R1; tax credibility items (Phase 2) depend on R2.

### 1.1 — R1 zoning definitions fallback
- **User impact:** 5 — restores the core of a feasibility report (standards, uses, FAR, max buildable);
  removes the trust-destroying manufacturing-code dump.
- **Effort:** M.
- **Data-availability risk:** Low — definitions table is local and already populated for RM-6.
- **Order:** 1 (unblocks R3 class mapping + Phase 3 FAR/yield).
- **Acceptance criteria:** RM-6 real report shows Bulk & Density (FAR 4.4 / 70 ft / 60%), residential uses,
  Development Potential with max-buildable; zero manufacturing text; provenance note present; B3-2 control
  still uses AI-extracted standards when extraction succeeds.

### 1.2 — R2a assessment column fix (`tax_year` → `year`)
- **User impact:** 5 — unbreaks assessed value + assessment history for *every* taxable property.
- **Effort:** XS.
- **Data-availability risk:** Low — verified `year` column returns rows.
- **Order:** 2.
- **Acceptance criteria:** taxable control PIN shows assessment history with correct years and no 400 in logs.

### 1.3 — R2b ptaxsim tax-year clamp
- **User impact:** 5 — unbreaks tax estimate for all 2026 reports.
- **Effort:** XS.
- **Data-availability risk:** Low.
- **Order:** 3.
- **Acceptance criteria:** taxable control PIN shows a 2024 estimated annual tax + agency breakdown; tax
  year is labeled; no off-by-one None.

### 1.4 — R2c tax-exempt labeling + taxable control PIN
- **User impact:** 4 — converts a hollow gap into a decision-relevant fact (institutional/exempt site).
- **Effort:** S.
- **Data-availability risk:** Low.
- **Order:** 4.
- **Acceptance criteria:** subject EX report shows "Tax-Exempt Parcel (Class EX)" instead of blank; a
  chosen taxable PIN is documented in `report-status.md` as the demo happy-path parcel.

### 1.5 — R3 comp-class derivation + progressive widening
- **User impact:** 5 — restores comps table/chart/map/median and the basis for land value.
- **Effort:** M–L.
- **Data-availability risk:** Low (residential comps verified abundant); Med for the widening provenance UX.
- **Order:** 5 (after R1 so zoning-derived class is available).
- **Acceptance criteria:** subject report shows ≥3 residential comps with a stated basis line + sample size;
  taxable residential control still uses its own class; comp map markers have non-zero coords.

### 1.6 — R4 nearby-dev formatting/radius label (carried into Phase 1 as a freebie)
- **User impact:** 2 — "$3987K"→"$4.0M"; "within 0.25mi" vs "0.5mi" header reconciliation.
- **Effort:** XS.
- **Data-availability risk:** Low.
- **Order:** 6.
- **Acceptance criteria:** currency formatted in $M with one decimal; radius text matches the section header.

**Phase 1 exit gate:** regenerate subject + control reports. Zoning, tax, and comps each render correct
data or a correct *labeled* state. No section silently empty. Re-audit confirms R1/R2/R3 closed.

---

## Phase 2 — Credibility fixes

Confirmed-real items from the audit (`report-v6-audit.md` reclassification). Several only become visible
on real data **after** Phase 1 populates assessment history and comps. Batch the XS cleanups in one pass.

| ID | Item | User impact | Effort | Data risk | Order | Acceptance criteria |
|----|------|-------------|--------|-----------|-------|---------------------|
| Q9 | Lakefront Protection false positive ~1.5 mi inland | 4 | M | Med (overlay geometry) | 1 | Inland parcel no longer flagged "Private Lakefront"; overlay point-in-polygon validated against a known inland + known lakefront control |
| P4 | 311 rodent-baiting framed as structural/site risk | 4 | M | Low | 2 | Routine City abatement (rodent/baiting) no longer in "high-risk"; severity taxonomy documented |
| Q12/P9 | Class "EX" called "standard" | 3 | S | Low | 3 | EX shown as "Exempt", not "standard"; consistent with R2c labeling |
| Q11 | "Lakeview Historic District" on a Lincoln Park parcel | 1 | XS | Low | 4 | Overlay name matches actual district; community-area naming consistent |
| D6 | Overlay bracket labels duplicate name ("ARO Zones [ARO Zones]") | 1 | XS | Low | 5 | `[type]` appended only when it differs from display name |
| D5 | Transit duplicated (p5 + p7), 0.63 vs 0.6 mi | 1 | XS | Low | 6 | One canonical transit block; one distance precision |
| D9 | "ZONE TYPE: 4" meaningless | 1 | XS | Low | 7 | Removed or labeled |
| V6-5 | "within 0.25mi" narrative vs "0.5mi" header | 2 | XS | Low | 8 | Narrative radius matches config/header (overlaps R4) |
| Q10 | CAGR labeled 5yr (2020–2025) but data starts 2021 | 2 | XS | Low (newly visible post-R2a) | 9 | CAGR period derived from actual first/last assessment year |
| P7/Q13 | Reassessment drift sold as "appreciation opportunity" | 3 | XS | Low (newly visible post-R2a) | 10 | Drift framed as reassessment, not market appreciation; consistent with section disclaimer |
| Q6 | Effective rate shown next to assessed (reads 21.9%); market value hidden | 3 | S | Low | 11 | Show market value + assessed + effective rate together |
| D2/D1 | Construction map orphaned across page break / blank page | 2/1 | XS–S | Low | 12 | `page-break-inside: avoid` binds map+caption+table; no blank page |
| D10 | Inconsistent distance precision | 1 | XS | Low | 13 | One decimal throughout |

**Phase 2 exit gate:** re-audit finds no factual contradiction, no false risk signal, no duplicated/mislabeled
block. Trust-blocking clutter cleared.

---

## Phase 3 — Decision-quality improvements

These raise *altitude* — the audit's meta-finding ("30 data sections, little synthesis"). Each depends on
Phase 1 data being real.

| ID | Item | User impact | Effort | Data risk | Order | Acceptance criteria |
|----|------|-------------|--------|-----------|-------|---------------------|
| Miss#1 | Cover decision box (lot / zone / max buildable / land value / key constraint / timeline) | 5 | M | Low (post P1) | 1 | Page-1 box with 6 populated numbers (or honest "n/a"); no map-as-hero |
| V5-1b | Estimated Land Value Range actually renders | 5 | S–M | Low (post R3) | 2 | P25–P75 land value from comps with sample size + disclaimer renders on real data |
| P2 | Comp-implied valuation for the subject lot | 5 | M–L | Med | 3 | $/buildable-sf or land-residual tied to subject FAR/lot, with confidence band |
| P1 | FAR-utilization framing ("existing ≈ X% of allowable") | 4 | S | Low (post R1) | 4 | One line: existing sf vs FAR-allowed sf as a % |
| P8 | As-of-right unit yield estimate | 4 | S | Low (post R1) | 5 | Estimated unit count from FAR/min-lot-area with method note |
| Exec | Consolidate deal-shaping constraints into one callout | 4 | S | Low | 6 | Single "Key Constraints" callout (violations, NR/Section 106, ARO threshold, transition setbacks) |
| P5 | Ownership Intelligence "so what" | 3 | S | Low | 7 | Off-market / limited-leverage interpretation line |
| V5-1c | Advisory tier of Next Steps renders | 2 | S | Low | 8 | All three tiers (immediate / due diligence / advisory) present |

**Phase 3 exit gate:** a reader gets lot, zone, what-can-I-build, what-it's-worth, and the binding
constraint within 60 seconds on page 1.

---

## Phase 4 — UX & visualization improvements

| ID | Item | User impact | Effort | Data risk | Order | Acceptance criteria |
|----|------|-------------|--------|-----------|-------|---------------------|
| D3 | Map legends + scale bar + radius ring (cover, comps, construction) | 3 | S | Low | 1 | Every map has a legend strip, scale, and radius ring |
| D7 | Comps scatter plots $/land-sf with trend line | 3 | S | Low (post R3) | 2 | Y-axis $/sf, trend line, median reference |
| Miss#6 | Combined site-context map (parcel + envelope + comps/permits) | 4 | L | High (GIS-blocked) | 3 | One basemap with parcel + 0.25mi comp/permit points; gated on geometry availability |
| V5-2a/V4-2 | Parcel + setback-envelope visualization | 5 | XL | High (GIS-blocked) | 4 | Renders when real vertex geometry available; otherwise dimensions-only (no fabricated rectangle) |
| D8 | Site Assessment badge vocabulary consistency | 1 | S | Low | 5 | One scale across all badges |
| P6/D11 | Crime benchmark + placement | 2 | S | Low | 6 | Benchmarked vs city/CA; moved to Market Context or dropped |

**Phase 4 exit gate:** maps are self-explanatory; no orphaned/blank pages; geometry-blocked items degrade
gracefully (never fabricate).

**Explicitly deferred (data/infra-blocked, per `report-status.md`):** reliable parcel geometry caching,
CCAO year-built/nonconformity for EX/400 PINs, owner names. Do not spend Phase 1–4 effort here.

---

## Phase 4 — RE-PRIORITIZED after the Phase 1–3 handoff review (2026-06-11)

> This supersedes the ordering in the original Phase 4 table above. The table above is kept for
> history; **use this section to choose work.** A future conversation should be able to read this
> section alone and understand exactly why the priorities are what they are.

### What Phases 1–3 changed about Phase 4

Three findings from implementation invalidate parts of the original Phase 4 plan:

1. **`$/land-sqft` is data-blocked, not "Low (post R3)" as the plan assumed.** Comparable sales in
   dense, condo-dominated areas (class 299) carry **no land area** in CCAO characteristics, and even SFR
   `char_land_sf` is frequently null (best-row merge recovers ~1 land-bearing comp within 0.25mi/3yr).
   → **D7 as written ("scatter $/land-sf with trend line") cannot be built** — there is no $/land-sf to
   plot, and typical n (2–3) makes a "trend line" statistically meaningless. D7 must be descoped or dropped.
2. **The marquee Phase 4 maps are GIS-blocked AND now look reliability-risky.** During Phase 3
   regeneration the report-generation process **exited mid-render twice** right after a `GIS parcel
   lookup failed` log line (empty HTTP reply, worker down, leaked-semaphore warning) — while the same
   PIN succeeded on other runs and the live-API/GIS integration tests were simultaneously failing. Root
   cause is **unconfirmed** (Cook County GIS hang vs local OOM under embed+reranker+matplotlib+weasyprint).
   Miss#6 (combined site-context map) and V5-2a (parcel/envelope viz) both add *more* GIS-dependent
   rendering, so if the crash is GIS-related they amplify a production reliability risk on the live site.
3. **The weakest analytical area is comparable-sales comparability, not map cosmetics.** Comps render
   with unknown size/type (`LAND SF —, BLDG SF —`), and a legacy "Comparable Sales Summary" stat block
   (showing `MEDIAN $/LAND SQ FT —`) now co-exists with the new "Comparable Market Activity" block — a
   redundant/contradictory presentation. Improving comp *quality and presentation* delivers more decision
   value than any planned Phase 4 viz item.

Also resolved-in-passing by Phase 3 (so dropped from the Phase 4 backlog): Q14 (existing sf now shown via
FAR-utilization), Q1/Q2 hero (replaced by the decision box), Q3/Q4 + Q7/Q8 + Q5 (mock-only; real path uses
the deterministic fallbacks). D4 ("tax shown 3×") is effectively moot — on the real taxable control the
effective rate / market value / estimated annual tax now render **0×** (see Q6 below), so over-display is
not the problem; under-display is.

### Re-prioritized ranking (all remaining items, 1 = lowest, 5 = highest)

| Item | User value | Decision value | Effort | Data risk | Regression risk | Verdict |
|------|-----------|----------------|--------|-----------|-----------------|---------|
| **R5 — parcel bbox fallback resolves WRONG parcel when GIS down** (NEW, found 2026-06-11) | 5 | 5 (whole property section can be the wrong building) | XS (one-line cap + warn) | n/a | Low | **✅ FIXED (commit 2c12286) — outranked everything; this is correctness, not polish** |
| **GIS / report-gen reliability spike** (NEW) | 5 | 4 (a crashed report = no decision) | S–M (investigate) | n/a | n/a (read-only spike) | **Tier 0 — ✅ SHIPPED & DEPLOYED** |
| **Comp comparability + comps-section consolidation** (NEW, absorbs D7) | 4 | 5 | **S** (was S–M; $/bldg-sf already computed+rendered — see verification pass) | Med | Med (touches comps render) | **Tier 1** |
| **Q6 — market value + assessed + effective rate together** | 3 | 4 | S | Low | Low | **Tier 1** (verified: market value computed at `main.py:2038` but never stored; effective rate renders 3× = latent D4; gated on `annual_tax>0`. Fix = store market value, collapse to one render, add annual-tax fallback) |
| **D3 — map legends + scale + radius ring** | 3 | 2 | S | Low | Low (render-only) | **Tier 2** (the safe, valuable viz item) |
| **P5 ownership-coverage validation** (NEW) | 2 | 3 | XS | Low | Low | **Tier 2** (de-risk a shipped feature: it renders on neither QA parcel) |
| **P6/D11 — crime benchmark + placement** | 2 | 2 | S | Low | Low | **Tier 3 (optional)** |
| **D8 badge vocabulary + Q14 "Surplus" label** | 1 | 1 | XS | Low | Low | **Tier 3 (cosmetic batch)** |
| **Miss#6 — combined site-context map** | 4 | 3 | L | High (GIS) | High (GIS crash) | **Defer** until Tier 0 + geometry caching resolved |
| **V5-2a — parcel + setback-envelope viz** | 5 | 4 | XL | High (GIS) | High | **Defer** (XL, GIS-blocked) |
| **V6-2 — year-built / nonconformity** | 3 | 3 | L | High (CCAO 400) | Med | **Defer** (data-blocked) |
| **P3 — financial section rework** | 2 | 2 | S | Low | Low | **Defer** (low leverage) |
| **D7 (original) — $/land-sf scatter + trend line** | 3 | 2 | S | **Blocked** | — | **Drop** (no $/land-sf; n too small for a trend) |

### Proposed implementation order + rationale

1. **GIS / report-gen reliability spike (Tier 0).** Reproduce the mid-render worker exit, determine GIS-hang
   vs OOM, add a hard timeout + graceful-degrade around the parcel GIS call so a slow/failing GIS never
   crashes a report. This *gates* any further GIS map work and protects the live site. ~½ day, read-only
   until the fix.
2. **Comp comparability + comps-section consolidation (Tier 1).** Verified to be a *consolidation* task, not
   new computation: `price_per_bldg_sqft`/`median_price_per_bldg_sqft` are already computed (`sales.py:246,
   266`) and rendered (template 1009/1073). Kill/merge the legacy "Comparable Sales Summary" stat block
   (`zoning_report.html:997`, with the `MEDIAN $/LAND SQ FT —` tile) that co-exists with the new "Comparable
   Market Activity" block (`:1023`); optionally tag condo (299) vs non-condo. Highest decision-value lever.
3. **Q6 tax clarity (Tier 1).** Verified root cause: market value computed at `main.py:2038` but never stored
   on the report; effective rate already renders in 3 template spots (latent D4). Fix = add `market_value`
   to the report and render it once next to assessed + effective rate, collapse the 3 effective-rate renders
   to one, and add an assessment-history fallback for `estimated_annual_tax` so the row isn't all-or-nothing
   when ptaxsim misses. Small, real clarity win; closes D4 in passing.
4. **D3 map legends (Tier 2).** ✅ **SHIPPED 2026-06-11.** Legends already existed → delivered the scale bar +
   distance reference ring on the three maps that already render (cover zoning, comps, construction).
   Render-only, low regression risk, verified visually on both QA PDFs. See the Tier-2 status block at top.
5. **P5 ownership-coverage validation (Tier 2).** ✅ **DONE 2026-06-11.** Validation exposed **R5** (see the
   R5 status block at top) — the ownership read was never broken, it just never received sales data because
   the report resolved the wrong parcel when GIS is down. R5 fixed in commit 2c12286; P5 now renders on the
   control. **This is the model case for "validate, don't assume": the next-up task was cosmetic; validating
   it surfaced a critical correctness bug underneath.**
6. **D8/Q14 cosmetic batch (Tier 2/3).** ← **now next.** One-pass badge-vocabulary + "Surplus" label cleanup.
   Low leverage; render-only.
7. **(Optional) P6 crime benchmark.** Only if time allows.
8. **Deploy the shipped-but-undeployed fixes (D3 + R5).** Highest *user-facing* value remaining — the fixes
   exist on `main` but the live site hasn't pulled them. Requires deploy confirmation (workflow rule).
   **Defer Miss#6 and V5-2a** until the Tier-0 spike clears GIS reliability *and* parcel-geometry caching
   exists; otherwise they cannot land reliably and raise crash exposure.

Rationale in one line: Phase 4 was framed as "UX/visualization," but the implementation reality is that
the high-ceiling viz items are GIS-blocked and now reliability-risky, while the real remaining leverage is
**(a) not crashing, (b) trustworthy comps, (c) legible tax** — so the re-prioritization elevates a
reliability spike + two analytical/clarity fixes above map polish, keeps the one safe viz item (D3), and
defers/drops the rest.

### Assumptions
- The two QA parcels remain the regression baseline: EX subject `14283190070000` (exercises empty/exempt
  states) + taxable control `14331030110000` (exercises populated states). Pass the control with **pin only**
  (an `address` param overrides the pin in `_resolve_location`).
- Comp building size (`char_bldg_sf`) is more often present than land size; the comparability fix relies on
  that asymmetry. **Unverified at scale** — confirm during Tier 1.
- The live production site uses the same report path; a local report-gen crash is therefore assumed
  production-relevant until the Tier-0 spike proves it is local-only (OOM) and not GIS.

### Verification pass (2026-06-11) — two open questions resolved by code inspection

A read-only code review (no regen) before Phase 4 implementation resolved two of the four unresolved
questions below and sharpened two ranking rows. **Net effect: the ordering holds, but Tier-1 effort drops
and the Q6 root cause is now known.**

- **Q6 is a display-wiring gap, not dead logic — and it carries a latent D4.** `effective_tax_rate` *is*
  computed (`main.py:2026–2039`) and *is* rendered — in **three** template locations (`zoning_report.html`
  440–442, 894, 1218). So the old D4 ("tax shown 3×") is still live and should be collapsed *in the same
  edit*. The genuine "hidden" value is **market value**: it is computed as a throwaway local
  (`main.py:2038 market_value = assessed / 0.10`) and **never stored on `ReportData`/`PropertySummary` nor
  passed to the template**. The "renders 0× on the control" symptom is gated by `annual_tax > 0`
  (`main.py:2036`): when `estimated_annual_tax` is null on a run (ptaxsim miss), effective rate is `None`
  and nothing renders despite a real AV in history. → **Q6 work = (a) surface `market_value` once next to
  assessed + effective rate; (b) collapse the 3 effective-rate renders to one (closes D4); (c) add an
  assessment-history annual-tax fallback so the row isn't all-or-nothing.** All display-layer, low risk.
  Effort confirmed **S**.
- **Tier-1 comps is consolidation, not new computation — effort drops S–M → S.** `price_per_bldg_sqft`
  *and* `median_price_per_bldg_sqft` are **already computed** (`sales.py:246, 266`) and **already rendered**
  (`zoning_report.html` 1009 median tile, 1073 per-row). The defect is that the **legacy "Comparable Sales
  Summary" stat block** (`zoning_report.html:997`, with the `MEDIAN $/LAND SQ FT —` tile at 1005) still
  co-exists with the **new "Comparable Market Activity" block** (`:1023`). → **Tier-1 comps work = kill/merge
  the legacy 997 block (and its `—` $/land-sf tile), keep the new block, optionally tag condo (299) vs
  non-condo.** No new query, no new field. The $/bldg-sf coverage question (below) still governs how useful
  the surviving $/bldg-sf column is.

### Unresolved questions
- Is the mid-render worker exit caused by Cook County GIS (hang/native crash) or local memory pressure?
  (Determines whether the GIS maps are merely blocked or actively dangerous.) **Still open — needs the
  Tier-0 spike (requires running report-gen, out of scope for the read-only verification pass).**
- How often does `char_bldg_sf` exist for the returned comps in real runs? (Determines whether the surviving
  $/bldg-sf column has enough coverage to be worth keeping prominent.) **RESOLVED (Tier-1 verification):
  rarely — on the control run 0 of 6 comps carried a building sq ft (all rows `—`), so the median $/bldg-sf
  line did not render. Same missing-CCAO-characteristics root cause as land area. Implication: the $/bldg-sf
  column/metric is correct to keep (renders when present) but should NOT be relied on as a primary signal;
  the median comparable *sale price* remains the only reliably-populated anchor. Do not invest further in
  $/bldg-sf prominence; if Tier-2+ wants a size-normalized signal it is data-blocked, not presentation-blocked.**
- ~~Does the effective-rate / market-value display logic still execute for taxable parcels?~~ **RESOLVED:
  effective rate executes and renders 3×; market value is computed but never stored. See verification pass.**
- Should the comps section exclude condos (299) from the basis for development-oriented subjects, or just
  label them? (Comparability vs sample size trade-off.) **Decided in Tier 1: neither yet — keep all comps,
  no class tagging.** The consolidation already fixes the contradiction (one presentation, honest "not
  size-/condition-matched" disclosure on the callout), and on these QA parcels n is too thin (2–6) to afford
  excluding. Optional condo (299) vs non-condo *labelling* was deliberately skipped to stay low-risk; revisit
  only if a future subject returns a comp set large enough that filtering wouldn't collapse n.

### Technical risks
- **Report-gen can OOM-kill the single worker at `write_pdf`** (Tier 0) — highest risk; takes down the whole
  backend (chat + health), not just maps. *Corrected by the Tier-0 spike: the trigger is render-time memory,
  not GIS; GIS only widens the window. See "Tier-0 investigation".*
- Comps-section edits touch a render path with run-to-run data variance (n flips 2↔3) — snapshot tests must
  tolerate variable n; assert on *structure/labels*, not exact comp counts.
- Any matplotlib legend work must degrade when a map is absent (EX parcel has no parcel/envelope map).
- Adding sections grows an already-long report (EX 16pp / control 19pp); prefer consolidation over addition.

### Known data limitations (carry forward)
- No reliable per-parcel land area for comps → no land-value range in condo markets (use sale price + honest
  disclosure; already shipped Phase 3).
- Cook County GIS intermittent/down → parcel & envelope geometry unavailable. **Not directly crash-inducing**
  (Tier-0 spike: GIS failures are fully swallowed; the mid-render worker exit is an OOM at `write_pdf`, not
  GIS). GIS only adds ~30 s latency that widens the OOM window. See "Tier-0 investigation".
- CCAO characteristics 400 for some PINs (incl. the EX subject) → no year-built / land area for those.
- Owner names not in open data.
- Comps have no size/type for many parcels → comparability is structurally limited even after Tier 1.

### Dependencies
- Miss#6, V5-2a **depend on** the Tier-0 GIS spike + parcel-geometry caching (neither exists yet).
- Q6 depends on the assessment/tax pipeline (Phase 1 R2) — already fixed; this is display-only.
- Comp comparability depends only on the existing 3-hop comps query (no new data source).

### QA strategy
- Regenerate **both** real PDFs (no `mock=true` for data sign-off) after each Tier; use `mock=true` only for
  template-layout smoke tests. A template-render smoke script (build a `ReportData`, render the Jinja
  template, grep the text) is the fast, GIS-independent check used in Phase 3 — reuse it.
- For the Tier-0 spike: add an integration-style test that simulates a slow/failing GIS call and asserts the
  report still returns (degraded), proving no crash path.
- Snapshot assertions on comps must key off labels/structure, not exact n (data varies run-to-run).
- Each viz change must be verified against the EX parcel (empty-state) as well as the control (populated).

### Acceptance criteria (Phase 4, re-prioritized)
- **Tier 0:** a simulated GIS timeout/failure yields a complete report (geometry sections degrade, no worker
  exit); a hard timeout caps the GIS call. Both QA reports still generate end-to-end.
- **Tier 1 comps:** exactly one comparable-sales presentation (no legacy `—` $/sf tiles alongside the new
  block); comp building size / $/bldg-sf shown where data exists; basis discloses comparability limits.
- **Tier 1 Q6:** taxable control shows market value + assessed value + effective rate together, once, legibly.
- **Tier 2 D3:** every rendered map has a legend, scale indication, and radius ring; absent maps don't error.
- **Tier 2 P5:** ownership "so what" verified to render with correct wording on a parcel with real signals.
- **Exit gate (unchanged):** maps are self-explanatory; no orphaned/blank pages; geometry-blocked items
  degrade gracefully and never fabricate.

---

## Tier-0 investigation — GIS / report-gen reliability (2026-06-11)

> ### ✅ Tier-0 FIX SHIPPED (2026-06-11)
> The fix described in "Tier-0 implementation plan" below is **implemented and verified**. All three items
> landed exactly as specified:
> 1. **Render concurrency cap** — `report_concurrency: int = 2` in `config.py` (env `REPORT_CONCURRENCY`);
>    `_REPORT_SEM = asyncio.Semaphore(get_settings().report_concurrency)` at `main.py` module level;
>    `async with _REPORT_SEM:` wraps the heavy span (`_fetch_report_data` → `write_pdf`) in `report()`. Auth /
>    `_resolve_location` / purchase-gate stay **outside** the semaphore (cheap, shouldn't hold the cap).
> 2. **`write_pdf` offload** — now `await loop.run_in_executor(None, lambda: HTML(string=html_content).write_pdf())`,
>    so the synchronous cairo/pango rasterization no longer blocks the event loop.
> 3. **GIS timeout/retry trim** — `_lookup_parcel_gis` passes an explicit `httpx.Timeout(8.0)` per request
>    (`_GIS_TIMEOUT_S=8.0`) even with a shared client, and makes a **single** attempt (retry 2→1; the
>    `asyncio.sleep(0.5)` and the now-unused `asyncio` import were removed).
>
> **Tests:** `backend/tests/test_report_tier0.py` (4 endpoint tests via `httpx.ASGITransport` with the heavy
> internals faked: semaphore-of-1 serialization, concurrency bounded by sem value, harness-observes-true-
> concurrency sanity, degraded-data still returns 200+PDF) and 2 new `test_property_parcels.py` tests
> (single-attempt, explicit-timeout). **524 unit tests pass** (`-m "not integration"`); the 2 integration GIS
> tests fail only because Cook County GIS is down (environmental, pre-existing).
>
> **Not done (optional, deferred):** item 5 infra backstop (`mem_limit` + `restart: unless-stopped` in
> `docker-compose.prod.yml`; freeing base64 map strings post-embed) — safe to add but not required for the fix.
> **Deploy still pending** (per workflow rules, requires confirmation) — the fix is committed-ready but not
> yet on the live server.

Status: **investigation complete + hypothesis EMPIRICALLY VALIDATED; FIX SHIPPED (2026-06-11).**
Headline finding: **the mid-render worker exit is not caused by GIS, and GIS cannot by itself abort a
report.** The crash is an out-of-memory (OOM) kill of the single uvicorn worker driven by per-report render
memory + a synchronous PDF render that serializes the event loop; the "GIS lookup failed" log line right
before it is a co-symptom of the same load window, not the cause. **The concrete implementation plan is at
the end of this section ("Tier-0 implementation plan").**

### Tier-0 VALIDATION — empirical evidence (2026-06-11)

Ran live experiments against the local running server (pid 26923) + standalone microbenchmarks. **Caveat:
the local box has 48 GB RAM and macOS memory compression, so a literal SIGKILL/OOM cannot reproduce locally
— under pressure macOS compresses pages (RSS collapses) and requests time out instead of the worker being
killed. On the 8 GB prod Linux container with no compressor, the same contention produces the OOM-kill.**
Same root cause, different surface symptom.

| Experiment | Result | What it proves |
|-----------|--------|----------------|
| **Single mock report + `/health` polling** | Report 94 s, 200. A `/health` check **at report completion took 6.44 s** (vs 0.06 s avg); RSS peaked ~904 MB vs ~620 MB idle (**+284 MB**). | `write_pdf()` runs synchronously and **blocks the event loop ~6 s at the end of every report** — health/chat/other reports stall. Confirms the loop-blocking mechanism. |
| **3 concurrent mock reports** | **All 3 timed out at 240 s (none completed)**; RSS peaked 986 MB then **collapsed to ~42–70 MB while the pid stayed alive** (macOS compressor). | The single worker **serializes catastrophically under concurrency**. On 8 GB Linux this is the OOM-kill; here the compressor masks it as a timeout cascade. |
| **`write_pdf` microbench, realistic 1200×800 basemaps** | Holding 6 map images ≈ **+236 MB**; `write_pdf` ≈ **+139 MB** on top → **~375 MB/report render footprint**; `write_pdf` blocked 0.8 s (synthetic) / 6.4 s (real template). | Attributes the spike: **large embedded map rasters + `write_pdf` rasterization**, both held in one process. Scales with image size/count. |
| **GIS blackholed (unreachable URL)** | Returned a PIN via **Socrata fallback in 11 s, no exception**. | GIS fully down → graceful degradation, **no crash**. (Claim 3 confirmed.) |
| **Real `lookup_parcel` timing** | 12.66 s, returned PIN but **`geometry=none`** (GIS currently failing → Socrata fallback). | GIS adds ~12 s latency/report **and is currently not returning geometry at all** — so parcel/envelope maps are already silently absent. |
| **GIS helper forced to `raise`** | Propagated out of `lookup_parcel` (the `await _lookup_parcel_gis(...)` call at `parcels.py:60` is **not** wrapped) — BUT the report's retrieve-level `gather(return_exceptions=True)` (`main.py:1219/1223`, `1989/2002`) maps it to `property=None`. | A raise *can* escape `lookup_parcel`, but **the report orchestration contains it** → still no endpoint crash. Earlier "GIS can never raise" was too strong; corrected — containment is at the gather, not inside `lookup_parcel`. |

**Arithmetic for prod (8 GB container):** resident embed + reranker ≈ 1–1.5 GB; each in-flight report holds
~375 MB (maps + render) and one report is in `write_pdf` at a time (serialized on the loop). 3–4 concurrent
reports → models + ~1.1–1.5 GB of report data + write_pdf working set can exceed available RAM → OOM-kill.
Single sequential reports stay well under budget (consistent with "same PIN succeeded on other runs"; the
crash hit twice during overlapping Phase-3 regen).

### Confidence assessment

**Confidence: HIGH** that the failure is render-memory + event-loop serialization (not GIS). Demonstrated:
the per-report render footprint (~375 MB), the synchronous `write_pdf` loop-block (6.4 s real), the
concurrency saturation (3 reports → total stall), and GIS graceful degradation. The one un-reproduced link
is the literal SIGKILL (impossible on a 48 GB macOS box) — inferred from the signature + the prod arithmetic.

**Alternative explanations that still fit (and how they're handled):**
- *A1 — timeout/health-check cascade rather than literal OOM.* In prod a failed `/health` (blocked by
  `write_pdf`) could trigger a container restart that looks like "worker down." **Same fix** (concurrency cap
  + offload). The "leaked semaphore" line still points to SIGKILL/OOM specifically.
- *A2 — the map rasters, not `write_pdf`, are the bigger memory share* (microbench: +236 MB vs +139 MB).
  True; the concurrency cap bounds the aggregate either way, and freeing base64 strings earlier is a cheap
  add-on.
- *A3 — GIS native hang leaking threads/semaphores.* **Weakened** — GIS is pure-async `httpx`, times out
  cleanly, demonstrated no crash. Low likelihood.

**Verdict: hypothesis CONFIRMED (render-memory/serialization), with the GIS-as-cause theory DISPROVEN as a
direct crash path and reduced to a latency amplifier.**

### 1. Exact failure path (traced in code)

The report endpoint is `report()` (`backend/main.py:4074`). Flow:
`_resolve_location` → `_fetch_report_data` (`:1923`) → Jinja render → **`HTML(string=html_content).write_pdf()`
(`:4161`)** → `Response`.

Two structural facts dominate:

1. **`write_pdf()` runs synchronously on the event loop** (`main.py:4161` — *not* in `run_in_executor`,
   unlike every matplotlib call). WeasyPrint re-rasterizes all embedded base64 map/chart PNGs and lays out a
   16–19-page document. This is a transient **memory spike** and a **full event-loop block** for its whole
   duration.
2. **One uvicorn worker, no `--workers`** (`backend/Dockerfile:58`), with the embedding model **and** the
   torch reranker resident (`RERANKER_ENABLED=true` in prod), and `_RETRIEVAL_SEM = Semaphore(8)` allowing 8
   concurrent retrieval tasks. So peak memory = resident models + up to 6 in-RAM matplotlib PNGs held on
   `report_data` + the WeasyPrint layout buffers, all in one process on an 8 GB box.

When peak memory exceeds available, the Linux OOM killer **SIGKILLs** the worker. SIGKILL → the
`multiprocessing.resource_tracker` prints **"leaked semaphore objects"** (torch/OpenBLAS), the container's
single worker dies ("worker down"), and in-flight HTTP returns nothing ("empty reply"). That is exactly the
reported signature — and it is an OOM signature, **not** a Python exception (a caught exception would log a
traceback and return a 500; an uncaught one would return a 500 with a stack trace, not kill the process).

### 2. Where failures originate — GIS retrieval vs geometry vs rendering vs memory

| Stage | Can it crash the report? | Evidence |
|-------|--------------------------|----------|
| GIS retrieval (`parcels.py`) | **No** | `_lookup_parcel_gis` and `_lookup_parcel_socrata` both wrap everything in `try/except → return None` (`:122`, `:174`). Failure = `None`, never raises. |
| Property orchestrator (`property/__init__.py`) | **No** | `lookup_parcel` returning `None` → `return None` (`:41-43`); sub-queries use `asyncio.gather(return_exceptions=True)` (`:60`). |
| Geometry processing | **No** | Parcel/envelope sections are gated `if ctx.property and ctx.property.parcel_geometry` (`main.py:2204`, `:2297`); when GIS is down `parcel_geometry is None` → sections **skip**, no error. |
| Map rendering (6 matplotlib fns) | **No** | Every render is individually `try/except` with `log.warning(exc_info=True)` (`:2106, 2161, 2176, 2188, 2230, 2308`) and offloaded via `run_in_executor`. |
| **PDF render (`write_pdf`) + memory** | **YES (OOM)** | Synchronous on the loop (`:4161`), no concurrency cap, stacked on resident torch models. This is the only stage whose failure mode matches "worker down / leaked semaphore". |

**Conclusion:** the failure originates in **rendering/memory (WeasyPrint + matplotlib + resident torch)**,
not in GIS retrieval or geometry. The GIS timeout merely *widens the overlap window*: the property
orchestrator owns an `httpx` client with `timeout=15.0` (`property/__init__.py:38`) and passes it to
`_lookup_parcel_gis`, so the GIS call uses **15 s** (its own 10 s only applies when it owns the client) ×
**2 attempts** + 0.5 s ≈ **~30 s worst-case stall** before the Socrata fallback. That stall holds the report
request open longer, increasing the chance it overlaps a second heavy request during the OOM window. (The
known-issues "60 s+" figure predates this 15 s client.)

### 3. Can report generation fail *entirely* because of GIS issues? 

**No — not via an exception.** GIS fully down → the report still generates, **degraded**: no parcel map, no
envelope map, no dimensions, comp class derived from zoning (Phase-1 R3). The *only* first-order GIS effect
is up to ~30 s added latency. GIS contributes to the crash **only indirectly**, by lengthening the request
and thus the memory-pressure overlap window. So "GIS reliability" is real but is a **latency/availability
amplifier**, not the crash's root cause.

### 4. Which Phase 4 items depend on GIS reliability

- **Miss#6 (combined site-context map)** and **V5-2a (parcel + setback-envelope viz)** — both consume
  `ctx.property.parcel_geometry`; both add *more* synchronous matplotlib rendering to the same OOM-prone path.
  **Remain deferred** behind Tier-0 **and** parcel-geometry caching.
- **D3 (legends/scale/radius)** — only enhances maps that *already* render; degrades fine when a map is
  absent. **Not GIS-blocked.**
- **Tier-1 comps + Q6** — touch no GIS path. **Independent of this spike.**

### 5. Smallest safe mitigation (recommended)

In priority order; (a) is the keystone:

- **(a) Cap heavy-render concurrency.** Add a dedicated `asyncio.Semaphore(1)` (or 2) around the
  map-generation block + the `write_pdf()` call so two reports can't OOM the box simultaneously. **XS–S,
  low risk, highest leverage.** Directly addresses the OOM.
- **(b) Offload `write_pdf()` to `run_in_executor`.** Stops the PDF step from blocking the event loop, so
  health checks / chat / a second report don't see "empty reply" during a render. **XS.** (Reduces
  head-of-line blocking; does not by itself reduce peak memory — pair with (a).)
- **(c) Bound + unify the GIS timeout.** Make `_lookup_parcel_gis` pass an explicit per-request
  `timeout≈8 s` even when handed a shared client, so a GIS hang can't add ~30 s. **XS.** (Latency only —
  it already degrades correctly.)
- **(d) Backstop (infra, optional).** Add a container `mem_limit` + `restart: unless-stopped` so an OOM
  recycles fast instead of wedging; consider freeing matplotlib base64 strings once embedded. **XS.**

### Is a hard timeout + graceful-degradation path *sufficient*?

**Partially — and the distinction matters.**
- For **GIS safety**: yes, and it is **~90 % already implemented** — a GIS failure already degrades
  gracefully (returns `None`, geometry sections skip). (c) just bounds the latency.
- For the **actual crash (OOM at `write_pdf`)**: **No.** A GIS timeout does not reduce render-time memory.
  The worker exit requires the **concurrency cap (a) + executor offload (b)**. Stating it plainly: *a hard
  GIS timeout makes GIS safe but does not fix the mid-render worker exit; that exit is a memory/concurrency
  problem at the WeasyPrint step.*

### Reproduction steps (EXECUTED 2026-06-11 — see "Tier-0 VALIDATION" above)

- **Concurrency reproduction (done):** fired 3 concurrent `/api/report?...&mock=true` requests → **all timed
  out at 240 s**; RSS peaked 986 MB then collapsed (macOS compressor). On 8 GB Linux this is the OOM-kill /
  `resource_tracker: ... leaked semaphore objects`. Single sequential report succeeds (~90 s).
- **Loop-block reproduction (done):** single report + `/health` polling → health stalled **6.44 s at report
  completion** = synchronous `write_pdf`.
- **GIS-not-the-crash (done):** blackholed `PARCEL_QUERY_URL` → report path still returns a parcel via Socrata
  fallback, no exception. To re-confirm end-to-end on prod, block egress to `gis.cookcountyil.gov` and
  generate one report — it must complete degraded. (This remains the Tier-0 acceptance test.)

### Impact assessment

- **Severity: high (site-wide).** One worker → an OOM during a report takes down chat **and** health until
  Docker restarts. This is an availability risk, not just a report-quality issue — it validates the plan's
  "Tier-0 protects the live site."
- **Frequency: intermittent, load-dependent** (concurrency × report weight). Single-user sequential use is
  unaffected, which is why it surfaced only twice during Phase-3 regen.

### Updated Phase 4 ordering (post-spike)

Sequence **unchanged**, but Tier-0 is now precisely scoped: it is a **render-concurrency cap + event-loop
offload (+ a GIS-timeout tightening freebie)** — *not* a GIS-retry rewrite. Estimated effort **S (~½ day)**:
items (a)+(b)+(c) + the degradation test. Miss#6 / V5-2a stay deferred behind Tier-0 **and** geometry
caching. Nothing in the spike changes the Tier-1/Tier-2 ranking.

### Assumptions & open items (carry forward)

- **OOM is now validated by arithmetic + behavior, not just inference** — but the literal SIGKILL is still
  un-reproduced locally (48 GB macOS compresses instead of killing). Optionally confirm on a memory-capped
  container (`docker run --memory=1g`) before shipping, or just ship the cap (it's safe regardless).
- Resident model footprint measured locally at **~620 MB idle** (embed; reranker lazy). On prod with
  `RERANKER_ENABLED=true` resident, budget ~1–1.5 GB. Choose `_REPORT_SEM` size after a quick `docker stats`
  during a report; **default 2, drop to 1 if headroom is tight.**
- GIS is **currently returning no geometry** (Socrata fallback) — parcel/envelope maps are already absent in
  practice, so the GIS-dependent Phase-4 viz items have no live data to render even if built.

### Tier-0 implementation plan (concrete — ready to execute next session)

Effort: **S (~½ day)** total. Items (1)+(2) are the keystone (the OOM + loop-block); (3) is a cheap latency
add-on. All changes are in `backend/main.py` + `parcels.py` + config; no new deps, no data changes.

1. **Report/render concurrency limit (keystone).**
   - Add `_REPORT_SEM = asyncio.Semaphore(get_settings().report_concurrency)` at module level in `main.py`
     (alongside `_RETRIEVAL_SEM`, `:72`); add `report_concurrency: int = 2` to `config.py` (env
     `REPORT_CONCURRENCY`).
   - In `report()` (`main.py:4074`), wrap the heavy span — from `_fetch_report_data` (`:4102`) through the
     `write_pdf` call (`:4161`) — in `async with _REPORT_SEM:`. This bounds the number of reports
     simultaneously holding ~375 MB of render data + doing `write_pdf`.
   - Acceptance: 3 concurrent report requests all return 200 (serialized), none time out; peak RSS stays
     bounded (≈ models + `report_concurrency` × ~375 MB).

2. **Offload `write_pdf()` off the event loop.**
   - Replace `pdf_bytes = HTML(string=html_content).write_pdf()` (`:4161`) with
     `pdf_bytes = await asyncio.get_running_loop().run_in_executor(None, lambda: HTML(string=html_content).write_pdf())`.
   - WeasyPrint is mostly C (cairo/pango) so a thread genuinely unblocks the loop. Combined with (1), at most
     `report_concurrency` PDF threads run at once.
   - Acceptance: during a report, `/health` latency stays < 1 s (was 6.4 s); chat/health no longer stall at
     report completion.

3. **Bound + unify the GIS timeout (latency).**
   - In `_lookup_parcel_gis` (`parcels.py:93`), pass an explicit per-request timeout so a shared client can't
     impose 15 s: `await client.get(PARCEL_QUERY_URL, params=params, timeout=httpx.Timeout(8.0))`; and reduce
     the retry loop from 2 attempts to 1 for the point query (the retry rarely helps a broken index).
   - Net: GIS stall capped at ~8 s (was ~12–30 s), shrinking the request duration and the contention window.
   - Acceptance: a blackholed GIS lookup returns within ~8 s (measured 11–12 s today).

4. **Tests (per QA strategy).**
   - Degradation test: monkeypatch `lookup_parcel` to raise/hang → assert `/api/report` still returns a
     (degraded) report, proving no crash path. (Mostly true today; lock it in.)
   - Concurrency test: fire 2–3 concurrent report requests (mock, fast) → assert all return 200 within a
     bound. Without the semaphore this currently times out; with it they serialize and complete.
   - Re-measure the single-report `/health` stall (< 1 s) after (2).

5. **(Optional) Infra backstop** in `docker-compose.prod.yml`: `mem_limit` + `restart: unless-stopped` so any
   residual OOM recycles fast instead of wedging the single worker; consider dropping the 6 base64 map
   strings from `report_data` once embedded in the HTML.

**Is a hard GIS timeout + graceful degradation sufficient?** Confirmed empirically: **sufficient for GIS
safety (already ~90 % implemented — GIS down degrades cleanly), NOT sufficient for the worker exit.** The
worker exit needs (1) + (2). Ship all three; (1)+(2) are the fix, (3) is hygiene.

### Updated implementation order (post-validation)

**Unchanged sequence; Tier-0 now CONFIRMED and concretely specified.** Tier-0 (items 1–3 above) ships first
and is re-scoped definitively as *render-concurrency cap + event-loop offload + GIS-timeout trim* — not a
GIS-retry rewrite. After Tier-0 lands, Miss#6 / V5-2a remain deferred: they are safer behind the semaphore
but still **geometry-blocked** (GIS returns no geometry today), so there is nothing for them to render.
Tier-1 (comps consolidation, Q6) and Tier-2 (D3, P5) are unaffected by this spike.

---

## If we stopped after only 5 changes — maximum-leverage list

Ranked by improvement-in-usefulness per unit effort, respecting dependencies. These five take the real
report from "hollow / reject on sight" to "credible, decision-useful draft."

1. **R1 — Zoning definitions fallback (1.1).** Single biggest restoration: brings back standards, uses,
   FAR, and max-buildable, and stops the manufacturing-code dump. Unblocks FAR utilization, unit yield,
   and the decision box. *Effort M, impact 5.*
2. **R3 — Comp-class derivation + widening (1.5).** Restores comps table/chart/map/median and the entire
   valuation basis. *Effort M–L, impact 5.*
3. **R2a+R2b — Assessment column fix + ptaxsim year clamp (1.2 + 1.3).** Two tiny fixes that unbreak
   tax + assessment for *every* taxable report (not just this PIN). Highest leverage per hour. *Effort XS×2,
   impact 5.*
4. **Cover decision box + render land-value range (Phase 3 #1 + #2).** Converts restored data into the
   answer a developer opens the report for — surfaced on page 1. Depends on 1–3. *Effort M+S, impact 5.*
5. **Credibility batch: Q9 Lakefront false positive + P4 311 alarmism + the XS dedup/label cleanups
   (Phase 2 #1, #2, and the D5/D6/D9/Q11/V6-5 batch).** Kills the two false *risk* signals that could
   wrongly scare a buyer off, plus the cheap contradictions that erode trust. *Effort M+M+ (batched XS),
   impact 4.*

Rationale: #1–#3 make the report *exist* (viability); #4 makes it *answer the question* (altitude); #5
makes it *trustworthy* (no false alarms, no contradictions). Items deliberately **not** in the top 5:
parcel/envelope viz and combined site-context map (XL, GIS-blocked — high ceiling but can't land reliably
yet) and the long tail of cosmetic Phase-2 fill-ins (batch them, but they're not the leverage).

---

## Execution & verification protocol

1. Work strictly phase-by-phase; within a phase, follow the per-item order.
2. After each phase, regenerate **two** real reports (subject EX PIN + taxable control PIN) and re-audit
   against that phase's acceptance criteria and exit gate.
3. Keep `mock=true` out of QA from here on — the audit proved an incoherent mock masks real bugs. Use mock
   only for template-layout smoke tests, never for data-correctness sign-off.
4. Add a regression test alongside each R-fix (R1 definitions fallback, R2a column, R2b year clamp,
   R2c EX flag, R3 class mapping) so the pipeline bugs can't silently return.
5. Update `report-status.md` Resolution Tracker statuses (`Open`→`Fixed`) as each item lands; archive per
   `claude-context/README.md` when a phase ships.
