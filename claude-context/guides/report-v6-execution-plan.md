# Report V6 — Implementation Strategy & Phased Execution Plan

Plan date: 2026-06-10. Status: **strategy only — no implementation started.**

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
| 1 | Report viability (R1, R2, R3) | Real report for subject + taxable control is no longer hollow; zoning/tax/comps each render correct data or a correct labeled state |
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
