# PDF Report — Feature Status Tracker

Single source of truth for all planned, shipped, and blocked report features across V4–V6+.

Last updated: 2026-06-10

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
| 3 | V5-1b | Estimated Land Value Range marked Shipped but doesn't render | 5 | S–M | Open |
| 4 | Miss#1 | No cover decision box (6 numbers) | 5 | M | Open |
| 5 | P2 | No comp-implied valuation for the subject lot | 5 | M–L | Open |
| 6 | V5-2a | Parcel + setback-envelope viz absent (GIS-blocked) | 5 | XL | Needs real-data |
| 7 | P1 | No FAR-utilization framing | 4 | S | Open |
| 8 | P8 | No as-of-right unit yield | 4 | S | Open |
| 9 | Exec | Constraints not consolidated into one callout | 4 | S | Open |
| 10 | P4 | 311 "high-risk" alarmism (rodent baiting) | 4 | M | Open |
| 11 | Q9 | Lakefront Protection false positive inland | 4 | M | Needs real-data |
| 12 | Q7/Q8 | Map/table different neighborhoods; comps wrong section `[mock?]` | 4 | S/M | Needs real-data |
| 13 | Miss#6 | No combined site-context map | 4 | L | Open |
| 14 | Q5 | Tax agency rows sum > stated total `[mock?]` | 3 | XS/S | Needs real-data |
| 15 | P7/Q13 | Reassessment drift sold as appreciation opportunity | 3 | XS | Open |
| 16 | Q6 | Effective tax rate vs assessed value; market value hidden | 3 | S | Open |
| 17 | D3 | Maps have no legend / scale / radius ring | 3 | S | Open |
| 18 | D7 | Comps scatter plots absolute price, not $/sf | 3 | S | Open |
| 19 | Q12/P9 | Building class "EX" mislabeled "standard" `[mock?]` | 3 | S | Needs real-data |
| 20 | P5 | Ownership Intelligence lacks the "so what" | 3 | S | Open |
| 21 | D2 | Construction map orphaned across page break | 2 | XS–S | Open |
| 22 | V6-5 | "0.25mi" narrative contradicts "0.5mi" header | 2 | XS | Open |
| 23 | Q10 | CAGR labeled 5yr (2020–2025) but data starts 2021 | 2 | XS | Open |
| 24 | Q14 | "Surplus" undefined; existing sf not shown | 2 | XS | Open |
| 25 | P6/D11 | Crime: no benchmark, buried | 2 | S | Open |
| 26 | P3 | Financial = five "No"s + irrelevant grant | 2 | S | Open |
| 27 | V5-1c | Advisory tier of Next Steps missing | 2 | S | Open |
| 28 | D1 | Blank page 8 (orphaned footnote) | 1 | XS | Open |
| 29 | D4 | Tax + effective rate shown 3× | 1 | XS | Open |
| 30 | D5 | Transit duplicated + rounding mismatch | 1 | XS | Open |
| 31 | D6 | Overlay bracket labels duplicate name verbatim | 1 | XS | Open |
| 32 | D9 | "ZONE TYPE: 4" meaningless | 1 | XS | Open |
| 33 | D10 | Inconsistent distance precision | 1 | XS | Open |
| 34 | Q11 | "Lakeview Historic District" on Lincoln Park property | 1 | XS | Open |
| 35 | D8 | Site Assessment badges mix scales | 1 | S | Open |
| 36 | V6-2 | Year-built / nonconformity absent (CCAO-blocked) | 3 | L | Needs real-data |

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
