# Report V6 — Rejection Audit & Prioritized Findings

Audit date: 2026-06-10. Subject artifact: `/tmp/report_v6g.pdf` (18 pages, WeasyPrint), generated for **443 W Wrightwood Ave** with **`mock=true`**. Adversarial review — goal was to find everything wrong, not to validate.

## CRITICAL FRAMING — read first

The audited PDF was generated with **`mock=true`**. This matters for every finding below:

- The worst contradictions (N/A lot, FAR mismatch, commercial uses on a residential zone, Logan Square addresses on a Lincoln Park map, tax rows exceeding the tax total) are **incoherent mock fixtures**, not confirmed real-data behavior.
- But this is also the exact PDF used as the V6 launch-QA artifact, and a second class of problems are **structural template/logic defects that hit real reports too** (blank page, map/table page breaks, missing legends, tax-rate-vs-assessed-value display, redundant sections).
- **An incoherent mock is worse than no mock** — it masks real bugs behind fake-data bugs and can't be used for demos.
- **Highest-priority next action:** regenerate against a **real (non-mock) address** and re-audit. ~1/3 of the worst findings can't be confirmed as real vs mock-only until then.

**Meta-finding:** the report's core problem is **altitude, not features**. It produces ~30 data sections but little synthesis. It never answers the question a developer opens it for: *"What can I build, what will fight me, and is it worth pursuing?"* The Approval Pathway section (MODERATE / 2–4 months / why) is the one section that does this well — it's the template for everything else.

---

## Real-data regeneration results (2026-06-10)

Regenerated the **same parcel** without mock: `GET /api/report?pin=14283190070000&address=443+W+Wrightwood+Ave` → `/tmp/report_v6_real.pdf` (14 pages vs the mock's 18). This decisively reclassifies every `[mock?]` item — and reveals that **the real report for the flagship demo address is largely hollow**, with worse defects than the mock's fabricated data. `mock=true` was masking this.

### NEW critical real findings (invisible in the mock; these are what real users actually get)

| ID | Finding | Impact | Effort | Evidence |
|----|---------|--------|--------|----------|
| **R1** | **Structured zoning extraction FAILS for RM-6.** Report prints "⚠ Structured extraction unavailable for this zone class. Raw code sections shown below" then dumps **Chapter 17-5 MANUFACTURING DISTRICTS** bulk/density ordinance into an RM-6 *residential* report. No Bulk & Density table, no setbacks, no parking, no permitted uses, **no development potential / max buildable** — the core of a feasibility report is absent and replaced with wrong-chapter code. The deterministic zone-definitions table *does* have RM-6 (FAR 4.4) and could be the fallback. | 5 | M | p3–4 of real PDF |
| **R2** | **Tax & assessment entirely missing.** Property section shows only PIN + "BUILDING CLASS EX" + "Parcel geometry unavailable." No assessed value, no tax estimate, no effective rate, no agency breakdown, no assessment history. Consistent with the known CCAO 400 for this PIN. A real user gets zero valuation/tax data. | 5 | L (CCAO-blocked) | p6 of real PDF |
| **R3** | **No comparable sales.** "No comparable sales found within 0.25 miles in the last 3 years." → no comps table, chart, map, median prices, or land value. Market Context collapses to walk/transit/bike scores + nearby permits. No valuation basis exists. | 5 | M–L | p7 of real PDF |
| **R4** | Nearby-dev formatting/logic: "Average project investment: **$3987K**" (should be ~$4.0M) and "$35.9M … **within 0.25mi**" while the header says **0.5mi**. | 2 | XS | p7 of real PDF |

### Reclassification of audited findings

**CONFIRMED REAL (persist in real data — fix these):**
- **Q9** Lakefront Protection District false positive — still shows "Private Lakefront" ~1.5 mi inland. ✔ real.
- **Q11** "Lakeview Historic District" on a Lincoln Park property — still present. ✔ real.
- **D6** redundant bracket labels ("ADU Eligible Areas [ADU Eligible Areas]", "ARO Zones [ARO Zones]") — still present. ✔ real.
- **P4** 311 rat-complaint alarmism — still present verbatim. ✔ real.
- **D9** "ZONE TYPE: 4" — still present. ✔ real.
- **D5** transit duplicated (p5 + p7) with 0.63 vs 0.6 mi mismatch — still present. ✔ real.
- **V6-5** "within 0.25mi" narrative vs "0.5mi" header — still present. ✔ real.
- **Q12/P9** Building class "EX" called "standard" — still present. ✔ real.

**MOCK-ONLY (real path is correct or doesn't render the section — do NOT spend effort here):**
- **Q3/Q4** zoning FAR-4.4-vs-2.2 + commercial uses — mock fixture only; real path instead fails via **R1** (worse, but different).
- **Q7/Q8** map/table neighborhood mismatch + wrong-section comps — mock only; real nearby-dev correctly shows Wrightwood/Lehmann/Clark addresses.
- **Q1/Q2** "N/A sq ft" hero — the hero sentence is **absent** in real data (no dev potential computed because of R1); the underlying "no lot size / no buildable" issue is real via R1/R2.
- **Q5/Q6** tax sum + effective-rate display — mock only; real has **no tax section at all** (see R2).
- **Q10** CAGR mislabel, **Q14** undefined surplus, transition-zone setback flag, **P7** appreciation "opportunity" — all mock only (real lacks assessment history; real neighbors are RM-5/RM-6 residential, not B3-2).

**Net effect on priorities:** the top of the real backlog is now **R1 (zoning extraction) → R2 (tax/assessment) → R3 (comps) → Q9 (Lakefront) → the cheap confirmed-real cleanups (D6, P4, D9, D5, V6-5, Q12)**. The mock-only contradictions drop off the fix list but justify a **decoupling/fallback guard** (when structured extraction is unavailable, fall back to the deterministic zone-definitions table instead of dumping raw wrong-chapter code).

---

## Scoring legend

- **Impact** = effect on a real user's decision quality. 5 = changes go/no-go or core valuation; 4 = materially affects valuation/risk read; 3 = improves understanding/trust; 2 = polish; 1 = cosmetic.
- **Effort** = XS (<1 hr template tweak) · S (a few hrs) · M (~1 day) · L (multi-day) · XL (blocked on external data/infra).
- **Scope** = Real (degrades a real delivered report) · Mock (only visible in the mock QA artifact; real-path impact unconfirmed).

---

## Master ranking (impact desc, then effort asc)

| Rank | ID | Finding | Impact | Effort | Scope |
|---|---|---|---|---|---|
| 1 | Q3/Q4 | Zoning self-contradicts: "RM-6 (FAR 4.4)" label vs FAR 2.2 table + commercial uses (Retail/Tavern/Gas Station) on a residential zone | 5 | XS mock / S real guard | Mock + decoupling risk |
| 2 | Q1/Q2 | Lot size "N/A" in cover hero + 3 conflicting lot sizes (N/A vs 3,125 vs implied 5,000) | 5 | S | Real (null land_sqft) |
| 3 | V5-1b | Estimated Land Value Range marked "Shipped" but does not render | 5 | S–M (code exists) | Real |
| 4 | Miss#1 | No cover decision box (lot/zone/buildable/value/constraint/timeline) | 5 | M | Real |
| 5 | P2/Miss#10 | No comp-implied valuation for the subject lot | 5 | M–L | Real |
| 6 | V5-2a/V4-2 | Parcel + setback-envelope visualization absent (most decision-relevant map) | 5 | XL (GIS-blocked) | Real |
| 7 | P1 | No FAR-utilization framing ("existing uses ~29% of allowable") | 4 | S | Real |
| 8 | P8 | No as-of-right unit yield estimate | 4 | S | Real |
| 9 | Exec | Deal-shaping constraints not consolidated into one callout | 4 | S | Real |
| 10 | P4 | 311 "high-risk" alarmism (rat/rodent-baiting complaint framed as structural risk) | 4 | M | Real |
| 11 | Q9 | Lakefront Protection District false positive ~1.5 mi inland | 4 | M | Real |
| 12 | Q7/Q8 | Map basemap and its table describe different neighborhoods; comps from wrong section (14-30 vs subject 14-28) | 4 | S mock / M real check | Mock + decoupling risk |
| 13 | Miss#6 | No combined site-context map (parcel + envelope + comps/permits on one basemap) | 4 | L | Real |
| 14 | Q5 | Tax agency rows sum > stated annual tax ($10,680 visible vs $8,720 total) | 3 | XS mock / S real | Mock + real reconciliation |
| 15 | P7/Q13 | Reassessment drift sold as "appreciation opportunity" — contradicts section's own disclaimer | 3 | XS | Real |
| 16 | Q6 | Effective tax rate 2.2% shown next to assessed $39,900 (reads as 21.9%); market value hidden | 3 | S | Real |
| 17 | D3/V6-6/V6-8b | Maps have no legend / scale bar / radius ring (cover, comps, construction) | 3 | S | Real |
| 18 | D7 | Comps scatter plots absolute price vs date, not $/sf; no trend line | 3 | S | Real |
| 19 | Q12/P9 | Building class "EX" mislabeled "standard" (EX usually = exempt) | 3 | S | Real |
| 20 | P5 | Ownership Intelligence lacks the "so what" (off-market / limited-leverage read) | 3 | S | Real |
| 21 | D2 | Construction map orphaned across the page-10/11 break, headerless atop Financial section | 2 | XS–S | Real |
| 22 | V6-5 | "within 0.25mi" narrative contradicts the "0.5mi" section header | 2 | XS | Real |
| 23 | Q10 | CAGR labeled "5 yrs (2020–2025)" but assessment data starts 2021 | 2 | XS | Real |
| 24 | Q14 | "Surplus 7,800 sf" undefined; existing building sf not shown on that page | 2 | XS | Real |
| 25 | P6/D11 | Crime: no benchmark, buried at p13 in a site report | 2 | S | Real |
| 26 | P3 | Financial section = five "No"s + irrelevant SBIF grant (Chicago Ballet) | 2 | S | Real |
| 27 | V5-1c | Advisory tier of Recommended Next Steps missing (only 2 of 3 tiers render) | 2 | S | Real |
| 28 | D1 | Blank page 8 (single orphaned footnote) | 1 | XS | Real |
| 29 | D4 | Tax + effective rate shown 3× (p3, p6, p12) | 1 | XS | Real |
| 30 | D5 | Transit Access duplicated (p5 + p9) with 0.63 vs 0.6 mi rounding mismatch | 1 | XS | Real |
| 31 | D6 | Overlay bracket labels duplicate the name verbatim ("ARO Zones [ARO Zones]") | 1 | XS | Real |
| 32 | D9 | "ZONE TYPE: 4" meaningless to any reader | 1 | XS | Real |
| 33 | D10 | Inconsistent distance precision throughout | 1 | XS | Real |
| 34 | Q11 | "Lakeview Historic District" on a property labeled Lincoln Park community area | 1 | XS | Real |
| 35 | D8 | Site Assessment badges mix scales (CLEAR/RISK vs NEUTRAL/MODERATE) | 1 | S | Real |
| 36 | V6-2 | Year-built / nonconformity analysis absent (CCAO 400 for this PIN) | 3 | L (data-blocked) | Real |

---

## Two-axis quadrant

**Quick Wins — high impact, low effort (DO FIRST):**
Q3/Q4 zoning contradiction · Q1/Q2 lot size · V5-1b land value range · P1 FAR-utilization · P8 unit yield · Exec constraints callout · Q5 tax sum · P7 reframe drift · Q6 tax-rate context · D3 map legends · D7 better comps chart

**Big Bets — high impact, high effort (PLAN/RESOURCE):**
Miss#1 cover decision box · P2 comp valuation · V5-2a parcel/envelope viz (GIS-blocked) · Miss#6 site-context map · P4 311 reclassification · Q9 Lakefront false-positive validation

**Fill-ins — low impact, low effort (BATCH IN ONE PASS):**
D1 blank page · D2 map orphan · V6-5 radius narrative · Q10 CAGR label · Q14 surplus def · D4/D5/D6/D9/D10/Q11 dedup & label cleanups · V5-1c advisory tier

**Deprioritize — low impact / high effort (DEFER):**
V6-2 year-built (data-blocked) · P6 crime benchmarking · D8 badge vocabulary · P3 financial-section rework

---

## Recommended execution order

1. **Coherent-mock + Quick-Wins pass** (ranks 1–3, 7–9, 14–18, 22–24 + all Fill-ins): ~1 day of template/rule work clears the credibility-killers and trust-erosion clutter. Moves the report from "reject on sight" to "credible draft."
2. **Cover decision box + ship land-value range** (ranks 3, 4): the two changes that most raise decision quality — surface the answer fast, state what the site is worth.
3. **311 / overlay validation** (ranks 10, 11): kill false risk signals that could wrongly scare a buyer off.
4. **Real-data regeneration + decoupling guards** (ranks 1, 12, 14): confirm the zoning/comp/tax contradictions are mock-only, not lurking in the real path. Turns "potential 5s" into confirmed 5s or non-issues.
5. **Big-bet maps** (ranks 5, 6, 13): invest once cached GIS geometry is solved.

---

## Verified root causes (in `backend/main.py`)

- **Q1/Q2 (lot size):** cover hero uses `prop.land_sqft` (null in mock → "N/A"); `_apply_mock_overrides()` dev-potential falls back to hardcoded `land_sqft=5000`; parcel-geometry mock uses 25×125=3,125. Three independent sources, never reconciled. Real path also renders "N/A" when `land_sqft` is null.
- **Q3/Q4 (zoning):** `_apply_mock_overrides()` injects a **B3-2 commercial `ZoningStandards`** fixture (FAR 2.2, retail/tavern/gas-station uses) while leaving the real RM-6 zone class. The per-property standards and the zone-class label are **decoupled** and can silently disagree — a risk that survives into real data if AI extraction returns a FAR different from the zone-class lookup table.
- **Q5 (tax):** hardcoded `TaxLineItem` mock amounts (8 agencies ~$12,150 total; top-5 visible ~$10,680) don't sum to the hardcoded `estimated_annual_tax=8720`.
- **Q6 (effective rate):** real path computes `effective_tax_rate = annual_tax / market_value` (~line 2007), but the template displays it adjacent to **assessed** value with market value never shown → 2.2% looks like it should be 21.9%.
- **Q7/Q8 (neighborhood mismatch):** nearby-development and comps fixtures were written for the "2400 N Milwaukee" demo and reused for Wrightwood without updating addresses/PINs; only lat/lon are recomputed from the real coords, so markers sit near Wrightwood while labels read Logan Square.

---

## Full audit detail (for reference)

### Design issues
- D1 blank page 8 (orphaned footnote) — bind caption to its block with `page-break-inside: avoid`.
- D2 construction map orphaned across page break — keep map+table+heading together; add caption.
- D3 maps lack legends/scale/radius — render explicit legend strip under each map.
- D4 effective tax rate + annual tax shown 3× — show once in Financial.
- D5 transit duplicated (p5 + p9), 0.63 vs 0.6 mi — pick one home, standardize precision.
- D6 overlay bracket labels duplicate name verbatim — only append `[type]` when it differs from display name.
- D7 comps scatter plots absolute price — plot $/land-sf with a trend line.
- D8 exec Site Assessment mixes risk vocabularies — one consistent scale.
- D9 "ZONE TYPE: 4" meaningless — remove or label.
- D10 inconsistent distance precision — standardize to one decimal.
- D11 crime buried at bottom of p13 — move to Market Context or drop.

### Product issues
- P1 no buildable verdict / FAR-utilization framing.
- P2 no price-per-buildable-foot or land residual tied to the subject.
- P3 financial section is five "No"s + irrelevant ballet grant.
- P4 "high-risk 311" framing alarmist (rodent baiting is routine City abatement, not site risk).
- P5 Ownership Intelligence thin — missing the off-market / limited-leverage interpretation.
- P6 crime stat (1,012/90 days) has no benchmark.
- P7 assessment trend sold as "appreciation opportunity" while disclaimed as not market value.
- P8 no as-of-right unit yield.
- P9 building class "EX" called "standard" while showing a homeowner exemption + tax — contradictory.

### Data quality issues
- Q1 "N/A sq ft" in cover hero.
- Q2 three incompatible lot sizes.
- Q3 FAR 4.4 label vs 2.2 table vs 4.4 definitions.
- Q4 commercial permitted uses on RM-6.
- Q5 tax components exceed total.
- Q6 effective rate vs assessed value, market value hidden.
- Q7 construction table (Logan Sq) on Wrightwood basemap.
- Q8 comps PINs from a different section.
- Q9 Lakefront Protection false positive inland.
- Q10 CAGR period mislabeled (2020–2025 vs data from 2021).
- Q11 Lakeview vs Lincoln Park naming.
- Q12 "EX" class = "standard" likely wrong.
- Q13 appreciation "opportunity" contradicts disclaimer.
- Q14 "surplus" undefined; existing sf not shown.

### Map audit summary
- Cover zoning map: legend illegibly small, no scale/radius, hard-to-find subject pin.
- Comps map: no legend, no price labels, no radius ring.
- Construction map: markers unexplained (new vs demo), orphaned from table; mock markers can't match table addresses.
- Parcel/envelope map: ABSENT (GIS-blocked) — the most decision-relevant map.
- Missing the single best map: a combined site-context map (parcel + setback envelope + 0.25mi comp/permit points).

### Executive summary audit
- 30 s: reader hits "N/A sq ft lot" + illegible map legend → trust damaged before p3.
- 2 min: exec p3 is the best page, but undermined by drift-as-appreciation, rat alarmism, and a dev-potential built on a contradicted FAR.
- 5 min: the genuinely important constraints (open violation, NR/Section 106, ARO 10-unit threshold, transition setbacks) are scattered across p3/p5/p12/p13, never consolidated.
- Fix: replace the cover zoning map with a 6-number decision box.

### Plan vs implementation — notable gaps
- **V5-1b Estimated Land Value Range:** marked Shipped, does NOT render. (Regression/Missing — highest-value omission.)
- **V5-1c Next Steps tiers:** only Immediate + Due Diligence render; Advisory tier missing. (Partial.)
- **V6-5 Construction radius 0.5mi:** header updated, narrative still says 0.25mi. (Partial/Regressed.)
- **V6-6 / V6-8b map overlays/comps map:** render but legends missing/illegible. (Partial.)
- **V5-2a envelope viz / V4-2 parcel map / V6-2 year-built:** absent as warned (data-blocked).

### Missing features (by value ÷ effort)
High value / low effort: cover decision box; ship land-value range; FAR-utilization %; as-of-right unit yield; map legends + scale bars.
High value / medium effort: combined site-context map; 311/violation severity re-classification; tax (market+assessed+rate together).
High value / high effort (data-blocked): parcel + envelope visualization; comp-implied valuation with confidence band.
Correctly deferred: pro-forma IRR/NPV, soil/geotech, "PERMITTED" verdicts, photos.
