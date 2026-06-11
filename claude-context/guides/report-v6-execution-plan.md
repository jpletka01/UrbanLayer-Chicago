# Report V6 — Implementation Strategy & Phased Execution Plan

Plan date: 2026-06-10.

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
