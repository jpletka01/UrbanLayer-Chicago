# PDF Report V5: Feasibility Intelligence Upgrade

**Status:** Shipped (2026-06-10) — all 3 phases implemented
**Prereq:** Report V4 items 1-7 shipped; item 8 (Opportunities & Constraints) deferred to V5
**Reference:** NAHB Land Development Checklist (`claude-context/guides/subcontractor-info.pdf`)
**Prior plan:** `claude-context/guides/report-v4-plan.md`

## 1. Executive Summary

This document captures the complete planning effort for Report V5 — a gap analysis of the current report against professional land development due diligence standards (NAHB Land Development Checklist), pressure-testing of initial recommendations, and a final prioritized implementation roadmap.

**Core insight:** The biggest gap in the current report is not missing data — it is missing *answers*. The report provides all the raw materials (FAR, height, setbacks, comps, incentives) but never assembles them into the conclusions a developer is paying $25 to receive:

1. What can I build here? → Development Envelope Summary + Visualization
2. What will it cost to get approved? → Regulatory Approval Pathway
3. What is the land worth? → Estimated Land Value Range
4. What opportunities am I missing? → Opportunities & Constraints Synthesis
5. What do I need to do next? → Promoted Next Steps

All five additions are achievable with existing data. No new API integrations. No new data sources. The transformation is from "organized data" to "synthesized intelligence."

**Design philosophy:** Optimize for the developer's screening decision (go / maybe / kill), not for information completeness. The Executive Summary should answer the screening question in 90 seconds. Everything after that is supporting evidence.

---

## 2. Gap Analysis: NAHB Checklist vs. Current Report

### What the NAHB Checklist Covers

The NAHB Land Development Checklist is organized around the developer's decision journey across 6 stages:

**Stage 1 — Site Constraints & Opportunities** (25+ items): gross vs. net developable area, easements/covenants, ROW dedications, utility availability, encroachments, surrounding land use, highest-and-best-use, ALTA survey, topography/slopes/drainage, environmental exposures (soils, hazmat, noise), natural resource inventory (wetlands, floodplains, species), cultural/historic resources, ingress/egress, frontage/depth.

**Stage 2 — Government Constraints** (15+ items): development review procedures, local political attitude, comprehensive plan alignment, all applicable codes, overlay analysis, inclusionary zoning, traffic impact study needs, archaeological/endangered species study needs, net buildable area → unit count → profit, land dedication requirements.

**Stage 3 — Project Financing** (12+ items): cash flow projection, lot pricing/pace/timing, LTV ratios, AD&C/gap/permanent financing, performance guarantees, municipal financing (TIF), market analysis, feasibility study.

**Stage 4 — Approval Process** (flowchart): federal environmental review, rezoning/variance/special exception path, subdivision process, permitting sequence, impact fees.

**Stage 5 — Subdivision Costs** (50+ line items): engineering, surveying, grading, drainage, utilities, streets, sidewalks, landscaping, permits, fees, bonds, interest, overhead.

**Stage 6 — Site Plan** (10+ items): zoning change/variance needs, design review boards, conceptual layouts, community outreach.

### Current Report Inventory (V4)

| Section | Pages | Strengths | Gaps |
|---------|-------|-----------|------|
| Cover | 1 | Zoning map, development headline, PIN link | No key financial metrics strip |
| Executive Summary | 0.7 | Traffic lights are the best feature — instant red/yellow/green on 5 dimensions | No financial summary; no opportunities/constraints synthesis |
| Zoning & Development | 1.5 | Bulk standards, setbacks, uses, parking, adjacent zoning | No transition zone analysis; no "what can I build" envelope; no development envelope visualization |
| Regulatory & Environmental | 0.7 | Overlays, flood, brownfields, ARO | No approval pathway; no IL EPA databases beyond brownfields |
| Property & Physical | 2.0 | Parcel map, dimensions, ownership signals, assessment trend | No site constraints (frontage adequacy, alley, utilities) |
| Market Context & Comps | 2.0 | Stats box, comp table, demographics, transit, walk score | No rental market data; no development trend narrative; no estimated land value |
| Financial & Incentives | 1.5 | TIF/OZ/EZ/QCT/NMTC, financials, grants, tax breakdown | No estimated land value; no incentive stacking narrative |
| Site Condition & History | 1.5 | Violations, 311, permits, crime | Crime over-weighted (0.5 pages community-area stats); no due diligence checklist |
| Glossary | 1.5 | Good cross-references | Could condense |
| Zone Definitions | 0.5-1 | Valuable reference | Fine |
| Data Sources & Disclaimers | 1.5 | Thorough | Next Steps buried here — deserve promotion |

### Key Report Weaknesses (Honest Assessment)

1. **No consolidated financial picture.** Financial data scattered across 4 sections. A developer wants ONE view of the money story.
2. **No "what can I build" answer.** Gives FAR, height, setbacks — the raw inputs — but never assembles the development envelope.
3. **Crime section misaligned with product thesis.** Community-area crime counts serve neighborhood exploration, not site feasibility. North Star doc explicitly says to demote crime.
4. **No regulatory approval pathway.** Flags PD/landmark/historic risk but never tells user what approvals they need or how long they take.
5. **No site constraints beyond zoning.** Easements, utility access, frontage adequacy — none present.
6. **Adjacent zoning has no impact analysis.** Shows "South: RS-3" without explaining transition zone implications.
7. **Recommended Next Steps buried on the last page** inside Data Sources & Disclaimers — the highest-action content positioned as an afterthought.

---

## 3. Planning Review: Key Lessons & Decision Changes

### 3a. Information Completeness vs. Decision-Making Speed

The initial analysis optimized for information completeness — adding more data to be thorough. The pressure test revealed that a developer screening a site has a simple decision tree (go / maybe / kill) and needs the answer in the first 2 pages. Additions that don't directly feed the screening decision are interesting but not essential.

**Decision-enabling additions** (directly changes go/maybe/kill):
- Opportunities & Constraints synthesis
- Regulatory Approval Pathway
- Estimated Land Value Range
- Promoted Next Steps

**Interesting but not decision-enabling** (defer or keep minimal):
- Rental Market Indicators, Adjacent Zoning Impact, Environmental Risk beyond brownfields, Site Constraints Checklist, School districts, Noise flags

### 3b. Development Scenario Analysis → Development Envelope (Major Reframe)

**Original proposal:** 2-3 development scenarios with verdicts ("4-unit residential: PERMITTED; 6-unit: REQUIRES VARIANCE").

**Problem identified:** This crosses the line from feasibility analysis into entitlement/legal interpretation. If we say "6-unit residential: PERMITTED" and the developer later discovers a PD amendment, transition zone setback, or overlay requirement we didn't catch, trust is destroyed permanently.

**The line is:**
- **Safe:** "The base zoning (C1-2) permits residential above ground floor. FAR of 2.2 on this 3,576 sqft lot yields a maximum buildable area of 7,867 sqft."
- **Risky:** "You can build a 6-unit residential building here."
- **Dangerous:** "A 6-unit building is permitted and no special approvals are needed."

**Revised approach — two complementary features:**
1. **Development Envelope Summary (text):** Assemble in one paragraph all the parameters a developer needs to reason about scenarios: max buildable sqft, max stories/height, buildable footprint after setbacks, permitted uses, parking per unit, ARO threshold. States what the code says without making scenario-specific claims.
2. **Development Envelope Visualization (2D):** Parcel map with setback lines drawn inward, showing the actual buildable footprint. Visual communication avoids the claim-making risk of text-based verdicts.

**Why this is better:** The developer gets everything they need to evaluate their specific scenario, without us making the specific claim. The visual envelope is more memorable, more differentiating, and lower risk than scenario verdicts.

### 3c. Envelope Visualization vs. Scenario Analysis (Priority Swap)

**Original ranking:** Scenario Analysis > Envelope Visualization.

**Revised ranking:** Envelope Visualization > Scenario Analysis. Reasons:
- Visual comprehension is instant (2 seconds vs. 2 minutes)
- Lower risk of misinterpretation (shows constraints, doesn't make claims)
- More differentiating (no competitor renders buildable footprint automatically)
- More memorable (the feature developers screenshot and share)

### 3d. Nearby Development Activity (Undervalued)

Initial analysis treated nearby development as "already handled by V4." The pressure test revealed that what other developers are building nearby is arguably the strongest market signal in the entire report — stronger than many proposed regulatory or environmental additions.

The V4 table is good. What's missing is the **narrative synthesis** — a 2-3 sentence deterministic summary that tells the story: "Active teardown-rebuild cycle — 7 new construction permits totaling $4.2M within 0.25mi."

**Decision:** Development Trend Narrative promoted to top of Phase 1.

### 3e. Competitive Moat Analysis

Features were re-evaluated for competitive defensibility:

**Genuine moat** (leverages multi-domain data assembly only UrbanLayer has):
- Opportunities & Constraints synthesis (requires zoning + property + incentives + regulatory cross-reference)
- Development Envelope on parcel geometry (requires GIS polygon + zoning code setbacks)
- Incentive Stacking Narrative (requires understanding 6+ programs)
- Regulatory Approval Pathway (requires encoding Chicago-specific approval process)

**Easily copied** (basic data or math): Estimated Land Value Range, crime reduction, rental market indicators

**Decision:** Prioritize moat-building features. Features that are easily copied should only be built when they're also very low effort.

### 3f. Feasibility Report vs. Property Report Drift

The initial V5 proposal included school districts, noise flags, soil data, and wetlands — all drifting toward a generalized property report. The pressure test identified these as off-thesis:

**Core to feasibility thesis:** What can I build? What will it cost? What are the risks? What do I do next?
**Off-thesis (cut):** School districts, noise/nuisance, soil/geotech, wetlands, wildlife, topography

---

## 4. Final Design Principles

1. **Optimize for the screening decision.** The Executive Summary should answer go/maybe/kill in 90 seconds.
2. **Synthesize, don't accumulate.** Cross-reference existing data into conclusions rather than adding more raw data.
3. **Show constraints, don't make claims.** Present the development envelope and regulatory requirements; let the developer evaluate their specific scenario.
4. **Every section answers one of four questions:** What can I build? What will it cost? What are the risks? What do I do next?
5. **No new data sources in V5.** All improvements derive from data already in the pipeline. New APIs belong in V6+.
6. **Page budget discipline.** Add ~3 pages of high-value content, save ~1 page from condensing. Target: 16-17 pages.
7. **Deterministic over generative.** All synthesis is rule-based Python. No LLM calls in the report pipeline. Every statement maps to an objective data condition.

---

## 5. Final Implementation Roadmap

### Phase 1: "Make It Think" (Low effort, highest impact)
*Transform the report from organized data to synthesized intelligence. No new data sources. No new visualizations. Pure logic and restructuring.*

**Estimated effort:** ~1 day total

#### 1a. Opportunities & Constraints Synthesis → Executive Summary

**Purpose:** Cross-reference data from all report sections to surface actionable insights that the developer would miss by reading sections independently.

**Why highest priority:** This is the purest expression of UrbanLayer's competitive moat — it requires combining zoning + property + incentives + regulatory + market data in ways no piecemeal tool can replicate. It also has the best ROI (very high value, very low effort).

**Implementation:**
- New function: `_synthesize_opportunities_constraints(report_data: ReportData) -> tuple[list[dict], list[dict]]`
- Each rule returns `{signal: str, detail: str, category: str}` where category is "incentive", "zoning", "market", "regulatory", "financial", "site_condition"
- ~15-20 deterministic `if` rules (see Section 11 for complete rule set and examples)
- Called in `_fetch_report_data` after all data is assembled
- Template: bullet lists with ⬆/⬇ indicators in Executive Summary after traffic lights
- Volume cap: display at most 4 opportunities + 4 constraints (sort by category priority)

**Model changes:** Add `opportunities: list[dict]` and `constraints: list[dict]` to `ReportData` (default_factory=list)

**Risk:** Low — each rule maps to an objective data condition. Tone must be factual, never predictive.

#### 1b. Estimated Land Value Range → Market Context

**Purpose:** Compute a defensible value range from existing comparable sales data. Answers the first question every investor asks.

**Implementation:**
- From `ComparablesSummary`: compute `percentile_25` and `percentile_75` of `price_per_land_sqft` across comp sales
- Multiply by subject `land_sqft` to get range
- Display: "Estimated Land Value: $180K–$240K ($50–$67/land sqft) based on {{ sales_volume }} arm's-length sales within 0.25mi / 3yr"
- Include sample size and "This is not an appraisal" disclaimer

**Model changes:** Add `estimated_land_value: dict | None = None` to `ReportData` with keys: `low`, `high`, `low_per_sqft`, `high_per_sqft`, `sample_size`

**Risk:** Low-Medium. The range format communicates uncertainty. Disclaimer is essential. Do not present as a point estimate.

#### 1c. Promote Next Steps → Own Section (Position 9)

**Purpose:** Move existing conditional next steps from buried-in-disclaimers to a prominent, visually distinct section.

**Implementation:** Template restructure only. Organize into three tiers:
- **Immediate** (blocking issues): resolve violations, obtain PD amendment, commission Phase I ESA
- **Due Diligence** (standard process): title search, ALTA survey, utility verification, Legistar check
- **Advisory** (optimization): TIF administrator contact, OZ tax advisor, LIHTC structuring

**Risk:** None. Same content, better positioning.

#### 1d. Incentive Stacking Narrative → Financial Section

**Purpose:** When 2+ incentive programs apply, generate a paragraph explaining how they combine.

**Implementation:**
- Pre-written template paragraphs for common combinations: TIF+OZ, TIF+EZ, OZ+QCT, TIF+OZ+QCT, NMTC+TIF, EZ+OZ
- Deterministic selection based on which incentive flags are true
- Place after the incentive eligibility grid, before TIF financials

**Risk:** Low. Program interactions are well-documented. Avoid quantifying savings ("20-35% reduction") — instead describe the mechanism.

#### 1e. Development Trend Narrative → Market Context

**Purpose:** Synthesize nearby development permit data into a 2-3 sentence narrative.

**Implementation:**
- Compute from `nearby_development.recent_projects`: total investment, new/demo ratio, dominant project type (by cost), average project cost, max single project cost
- Deterministic paragraph templates:
  - Active redevelopment: "{{ n }} new construction permits totaling ${{ total }}M within 0.25mi in the last 12 months. Average project investment: ${{ avg }}K. This corridor shows active development momentum."
  - Demolition-heavy: "{{ n }} demolition permits vs {{ m }} new construction permits suggest a teardown-rebuild cycle in early stages."
  - Quiet: "Limited development activity within 0.25mi — {{ n }} permit(s) in 12 months."

**Risk:** Low. Derived directly from permit data.

#### 1f. Reduce Crime to 3-Line Summary

**Purpose:** Replace the 8-row YoY category table with a concise summary aligned with the feasibility thesis.

**Implementation:**
- Keep: total incidents, overall YoY trend direction, any extreme flag (>50% increase in violent crime categories)
- Remove: per-category breakdown table
- Template change only, no backend changes
- Saves ~0.4 pages

**Risk:** None. Aligns with North Star recommendation to demote crime.

#### 1g. Development Envelope Summary (Text) → Zoning Section

**Purpose:** Assemble all development parameters into one readable block so the developer can reason about scenarios without doing mental math across 3 subsections.

**Implementation:**
- Template-only — assembles existing data: "On this {{ land_sqft }} sq ft lot, {{ zone_class }} allows up to {{ max_buildable }} sq ft across {{ max_stories }} stories / {{ max_height }} ft. Buildable footprint after setbacks: approximately {{ computed }} sq ft. Permitted uses include: {{ permitted_uses[:3] }}. Parking: {{ parking_residential }} per residential unit. ARO threshold: 10 units."
- Place after the bulk standards table, before adjacent zoning
- Add caveat: "Reflects base district standards only. Overlays, planned developments, transition zones, and site-specific conditions may alter these parameters."

**Risk:** Low — states facts from the code, makes no claims about specific projects.

### Phase 2: "Make It See" (Medium effort, high impact)
*The visual differentiator. Features no competitor offers.*

**Estimated effort:** ~1-2 days total

#### 2a. Development Envelope Visualization → Zoning Section

**Purpose:** Render parcel polygon with setback lines drawn inward, showing the actual buildable footprint. This is the report's signature visual — the "holy shit" moment.

**Why this over scenario analysis:** Visual envelope shows constraints without making claims. A developer overlays their own design mentally. Lower risk, higher memorability, more differentiating than text-based scenario verdicts.

**Implementation:**
- Input: `parcel_geometry` (GeoJSON Polygon) + `front_setback_ft`, `side_setback_ft`, `rear_setback_ft` from ZoningStandards
- Edge classification heuristic:
  1. Compute bearing of each polygon edge
  2. Identify "front" as the shortest edge(s) facing a street (bearing roughly parallel to street grid — Chicago's grid is ~N/S and E/W ±33°)
  3. "Rear" = edge roughly opposite and parallel to front
  4. "Sides" = remaining edges
  5. Fallback: if classification is ambiguous, use uniform setback (conservative)
- Polygon inset: for each edge, offset inward by the classified setback distance. Compute intersection of offset lines to get inner buildable polygon.
- Rendering (matplotlib, same pattern as `_generate_zoning_map`):
  - Parcel outline: solid dark gray
  - Setback zones: light gray hatching
  - Buildable footprint: blue fill with dimensions annotated
  - Label each setback zone with distance (e.g., "30 ft rear")
  - Compute and display buildable footprint area in sq ft
- Output: base64 PNG, stored in `ReportData.envelope_map_b64`
- Place after the text-based Development Envelope Summary
- Graceful degradation: when `parcel_geometry` is None (GIS down), section simply doesn't render

**Model changes:** Add `envelope_map_b64: str | None = None` and `buildable_footprint_sqft: float | None = None` to `ReportData`

**Technical risk:** Medium. Edge classification is the hard part — Chicago's street grid makes it tractable (most lots are rectangular, aligned to the grid), but irregular lots (corner lots, flag lots, triangular parcels) need fallback handling.

**Accuracy caveat in template:** "Setback zones shown are base district standards. Actual buildable area may differ due to transition zone requirements, overlay modifications, easements, and utility encumbrances. Confirm with a licensed architect or the Chicago Zoning Division."

#### 2b. Regulatory Approval Pathway → Executive Summary (6th traffic light) + Regulatory Section (detail)

**Purpose:** Tell the developer what approvals they need, estimated timeline, and process complexity.

**Implementation — decision tree:**

```
if in_planned_development:
    complexity = "COMPLEX"
    detail = "Planned Development amendment required: City Council approval, public hearing, aldermanic support"
    timeline = "6-18 months"
elif in_landmark_district or in_historic_district:
    complexity = "COMPLEX"
    detail = "Commission on Chicago Landmarks review required for exterior modifications"
    timeline = "3-6 months for permit review"
elif special_uses and not permitted_uses:
    complexity = "MODERATE"
    detail = "Zoning Board of Appeals hearing required for special use approval"
    timeline = "3-6 months"
elif special_uses and permitted_uses:
    complexity = "MODERATE"
    detail = "Permitted uses available; special use approval needed for some use types"
    timeline = "4-8 weeks (permitted) / 3-6 months (special use)"
else:
    complexity = "SIMPLE"
    detail = "Standard building permit application under base zoning"
    timeline = "4-8 weeks"
```

Modifiers (append to detail):
- `if open_violations > 5`: "+ Violation clearance required before new permits"
- `if in_special_flood_hazard`: "+ FEMA floodplain compliance review"
- `if aro_zone and max_units >= 10`: "+ ARO affordable housing compliance"

**Display:**
- Executive Summary: 6th traffic light — "Approval Complexity: SIMPLE/MODERATE/COMPLEX" with color coding
- Regulatory section: new "Approval Pathway" subsection with the detail and timeline

**Model changes:** Add `approval_pathway: dict | None = None` to `ReportData` with keys: `complexity`, `detail`, `timeline`, `modifiers`

**Risk:** Low-Medium. The framework (PD vs landmark vs base zoning) is reliable. Timelines are approximate — label as "estimated" and note they vary by project specifics and political context.

### Phase 3: "Make It Tight" (Low effort, polish)
*Structural improvements that sharpen focus.*

**Estimated effort:** ~0.5 days total

#### 3a. Condense Glossary
- Move FAR, setback, lot coverage to inline footnotes in Zoning section
- Keep ~10 terms in glossary proper: TIF, OZ, EZ, QCT, NMTC, PD, ARO, SSA, SFHA, PIN, TOD, ADU, arm's-length
- Target: 0.75 pages (down from 1.5)

#### 3b. Condense Data Sources
- Group related sources (e.g., "Cook County Assessor: characteristics, assessments, sales, tax" = 1 row instead of 4)
- Target: ~12-15 rows (down from 22)

#### 3c. Remove Duplicate Development Potential Box
- Currently appears in both Executive Summary AND Property section
- Show once in Executive Summary. Remove from Property — reference it: "See Development Potential in Executive Summary."

#### 3d. Adjacent Zoning Impact Notes
- For each adjacent zone, check if a transition zone trigger exists
- Lookup table of zone-type pairs that trigger Title 17-2-0303 (residential adjacent to commercial/manufacturing)
- If triggered: "Transition zone setback may apply (Title 17-2-0303) — verify with zoning review"
- Template-only change

#### 3e. Due Diligence Checklist
- Compact two-column checklist at end of Site Condition section
- Column 1 — ✓ Completed in this report: zoning verification, overlay check, flood zone, brownfields, tax analysis, comparable sales, permit history, violation audit
- Column 2 — ☐ Action required: title search, ALTA survey, Phase I ESA (conditional on brownfield), utility verification (DWM/ComEd), soil/geotech (if applicable), insurance quotes (if SFHA)

---

## 6. Features Considered and Deprioritized

### Deprioritized During Initial Analysis

| Feature | Why Deprioritized | Revisit When |
|---------|-------------------|-------------|
| Full automated pro forma (IRR/NPV/cash-on-cash) | Too many assumptions; one wrong input destroys credibility | Never — provide inputs, not projections |
| Soil/geotechnical analysis | USDA SSURGO too coarse for urban lots; always requires borings | Never for Chicago urban |
| Wetlands/endangered species | Irrelevant for 99%+ Chicago urban parcels | Never for Chicago urban |
| Owner name lookup | Requires paid data license (Regrid/CoreLogic) | When revenue justifies $1K+/mo data cost |
| Pending zoning changes | Requires PDF parsing from Legistar; high maintenance | Phase 4+ per North Star |
| Full subdivision cost estimation | 50+ line items varying wildly by project | Never — too speculative |
| Property photos / street view | Mapbox doesn't offer; Google charges per-image + copyright | When free/affordable API exists |
| Topography/elevation | Chicago is flat (<10ft change across neighborhoods) | Never for Chicago |
| Noise contour mapping | Complex FAA/IDOT datasets for marginal value | Only if customers request |

### Deprioritized During Pressure Testing

| Feature | Initial Tier | Final Decision | Reasoning |
|---------|-------------|---------------|-----------|
| Development Scenario Verdicts | Tier 1 | **Replaced** by Development Envelope Summary + Visualization | Too high risk of overconfidence. "PERMITTED" verdict that turns out wrong destroys trust permanently. The envelope approach gives the same information without making claims. |
| Rental Market Indicators | Tier 3 | **Deferred** | Median rent already in demographics. Don't expand unless multifamily developers emerge as primary customer segment. |
| Environmental Risk (IL EPA LUST/SRP) | Tier 3 | **Deferred** | Marginal incremental value over existing brownfield + flood coverage for Chicago urban sites. Build only if customer interviews surface it. |
| Pro Forma Inputs (construction cost/sqft from permits) | Tier 3 | **Deferred** | Construction costs from permits are notoriously unreliable (under-reported). Risk of providing misleading inputs outweighs value. |
| School District data | Tier 3 | **Cut** | Property report territory, not feasibility. Off-thesis. |
| Noise/Nuisance flags | Tier 3 | **Cut** | Never changes a go/no-go decision in practice for Chicago urban. |
| Adjacent Zoning Impact (full analysis) | Tier 2 | **Reduced** to Phase 3 one-line notes | Full analysis requires deep Title 17 transition zone encoding. A flag ("transition zone setback may apply") provides 80% of the value at 20% of the effort. |
| Site Constraints Checklist (automated checks) | Tier 2 | **Reduced** to Phase 3 Due Diligence Checklist | Frontage adequacy and alley access detection are useful but complex to implement correctly. A manual checklist ("verify these items") provides immediate value. |

---

## 7. Risks, Assumptions, and Guardrails

### Assumptions
1. V4 items 1-7 are shipped (nearby dev table, parcel map, ownership signals, assessment trend, tax breakdown, building characteristics, zone definitions). Verify before starting V5.
2. `parcel_geometry` is available when Cook County GIS is up — development envelope visualization degrades gracefully when it's null.
3. Developers are the primary report buyer (per North Star hypothesis). If architects or attorneys emerge as primary, the priorities may shift.
4. The current 14-page report is not too long. Adding 2-3 pages of high-value content is acceptable if low-value content is condensed.

### Risks
1. **Opportunities & Constraints tone risk:** Statements must be factual, not predictive. "This parcel qualifies for TIF funding" ≠ "You will receive TIF funding." Every statement must describe an objective condition, not an outcome.
2. **Development Envelope edge classification:** The heuristic for identifying front/side/rear edges may fail on irregular lots. Mitigation: conservative fallback (uniform setback).
3. **Land value range on thin markets:** With <3 comps, the range may be misleading. Mitigation: don't show range when `sales_volume < 3`; show "Insufficient comparable sales for automated valuation" instead.
4. **Regulatory Approval Pathway timelines:** Actual timelines vary by aldermanic politics, project complexity, and community opposition. Mitigation: label as "estimated" with disclaimer.
5. **Scope creep:** V5 is scoped as synthesis-over-existing-data. Any proposal requiring new API integrations should be deferred to V6.

### Guardrails
- No LLM calls in any V5 feature. All synthesis is deterministic Python.
- Every Opportunities & Constraints statement has an explicit triggering condition documented in code comments.
- All financial estimates (land value, tax) include sample size, methodology note, and "not an appraisal / not financial advice" disclaimer.
- Development Envelope Visualization includes "Confirm with licensed architect or Chicago Zoning Division" disclaimer.
- Regulatory Approval Pathway includes "Timelines are estimates and vary by project" disclaimer.
- Volume cap on opportunities/constraints: max 4+4 displayed to avoid overwhelming.

---

## 8. Opportunities & Constraints: Complete Rule Set

### Triggering Conditions and Example Output

Each rule is a Python `if` condition on fields already in `ReportData` or `ContextObject`. All are deterministic. No LLM. Organized by category.

### Incentive Stacking (8 rules)

```python
# Rule: TIF + OZ double stack
if inc.in_tif_district and inc.in_opportunity_zone:
    opportunities.append({
        "signal": "TIF + Opportunity Zone",
        "detail": "TIF can subsidize infrastructure and remediation; OZ structuring provides investors with tax-advantaged entry.",
        "category": "incentive"
    })

# Rule: TIF + OZ + QCT triple stack
if inc.in_tif_district and inc.in_opportunity_zone and inc.in_qct:
    # Override the double-stack with the triple
    opportunities.append({
        "signal": "Triple incentive stack: TIF + OZ + QCT",
        "detail": "TIF funds site improvements, OZ defers investor capital gains, QCT provides 130% LIHTC basis boost for affordable housing.",
        "category": "incentive"
    })

# Rule: TIF + EZ
if inc.in_tif_district and inc.in_enterprise_zone:
    opportunities.append({
        "signal": "TIF + Enterprise Zone",
        "detail": "TIF provides direct project funding; EZ provides sales tax exemption on building materials and investment tax credits.",
        "category": "incentive"
    })

# Rule: OZ + QCT
if inc.in_opportunity_zone and inc.in_qct:
    opportunities.append({
        "signal": "OZ + Qualified Census Tract",
        "detail": "OZ investors receive capital gains deferral; QCT provides 130% basis boost for LIHTC projects.",
        "category": "incentive"
    })

# Rule: NMTC severely distressed
if inc.in_nmtc and inc.nmtc_severe_distress:
    opportunities.append({
        "signal": "NMTC with Severe Distress designation",
        "detail": "Severely Distressed tracts receive priority in CDFI allocation rounds for the 39% NMTC credit.",
        "category": "incentive"
    })

# Rule: OZ + vacant lot
if inc.in_opportunity_zone and (prop.bldg_sqft or 0) == 0:
    opportunities.append({
        "signal": "Vacant lot in Opportunity Zone",
        "detail": "Ground-up construction on vacant land is the cleanest Qualified Opportunity Fund investment — no substantial improvement test needed.",
        "category": "incentive"
    })

# Rule: Grant programs active
if inc.grant_programs and inc.grant_programs.total_funding and inc.grant_programs.total_funding > 500000:
    opportunities.append({
        "signal": f"Active grant funding in area",
        "detail": f"${inc.grant_programs.total_funding:,.0f} in SBIF/NOF grants awarded in this community area — established pipeline for applications.",
        "category": "incentive"
    })

# Rule: TIF expiring soon (opportunity to apply NOW)
if inc.in_tif_district and inc.tif_end_year:
    years_left = inc.tif_end_year - current_year
    if 0 < years_left <= 3:
        constraints.append({
            "signal": f"TIF district expires in {years_left} year{'s' if years_left > 1 else ''}",
            "detail": f"{inc.tif_name} expires {inc.tif_end_year}. Apply for TIF funding before expiration — remaining balance may be allocated to pending projects.",
            "category": "incentive"
        })
```

### TOD & Transit (3 rules)

```python
# Rule: TOD parking reduction
if nbr and nbr.transit and nbr.transit.tod_eligible and standards and standards.parking_residential:
    opportunities.append({
        "signal": "TOD parking reduction eligible",
        "detail": "Chicago TOD ordinance allows reduced parking near transit — could free buildable area otherwise consumed by parking.",
        "category": "zoning"
    })

# Rule: High transit + high walk score
if nbr and nbr.walkscore and nbr.walkscore.walk_score and nbr.walkscore.walk_score >= 80 and nbr.transit and nbr.transit.tod_eligible:
    opportunities.append({
        "signal": f"Walkable transit corridor (Walk Score {nbr.walkscore.walk_score})",
        "detail": "High walkability + transit access supports reduced-parking or car-free residential development.",
        "category": "market"
    })

# Rule: ADU eligible
if reg and any(o.layer_type == "adu" for o in (reg.overlays or [])):
    opportunities.append({
        "signal": "ADU-eligible area",
        "detail": "Accessory dwelling unit (coach house, basement apartment, rear cottage) is permitted — adds rental income potential without rezoning.",
        "category": "zoning"
    })
```

### Development Potential (4 rules)

```python
# Rule: Vacant lot with full buildable
if (prop.bldg_sqft or 0) == 0 and dev and dev.development_surplus_sqft and dev.development_surplus_sqft > 0:
    opportunities.append({
        "signal": "Vacant lot with full development capacity",
        "detail": f"{prop.land_sqft:,} sq ft lot allows up to {dev.max_buildable_sqft:,} sq ft with no existing structure.",
        "category": "zoning"
    })

# Rule: Significantly under-improved
if prop.bldg_sqft and dev and dev.development_surplus_sqft and dev.max_buildable_sqft:
    utilization = prop.bldg_sqft / dev.max_buildable_sqft
    if utilization < 0.3:
        opportunities.append({
            "signal": f"Under-improved property ({utilization:.0%} of allowed density)",
            "detail": f"Existing {prop.bldg_sqft:,} sq ft uses {utilization:.0%} of the {dev.max_buildable_sqft:,} sq ft allowed. Significant expansion or teardown-rebuild potential.",
            "category": "zoning"
        })

# Rule: At or over FAR (constraint)
if prop.bldg_sqft and dev and dev.development_surplus_sqft is not None and dev.development_surplus_sqft <= 0:
    constraints.append({
        "signal": "At FAR limit — no development surplus",
        "detail": f"Existing {prop.bldg_sqft:,} sq ft structure is at or near the maximum allowed. Additional floor area requires a variance or rezoning.",
        "category": "zoning"
    })

# Rule: Building age qualifies for historic credits
if prop.bldg_age and prop.bldg_age >= 50 and prop.bldg_sqft and prop.bldg_sqft > 0:
    opportunities.append({
        "signal": f"Building age ({prop.bldg_age} years) may qualify for historic tax credits",
        "detail": "Federal 20% and Illinois 25% historic tax credits available for certified historic structures. Verify individual listing eligibility with Illinois SHPO.",
        "category": "financial"
    })
```

### Regulatory (5 rules)

```python
# Rule: Planned Development
if reg and reg.in_planned_development:
    constraints.append({
        "signal": "Planned Development — discretionary approval required",
        "detail": "Any modification to the approved PD plan requires City Council approval, public hearing, and aldermanic support (typically 6-18 months).",
        "category": "regulatory"
    })

# Rule: Landmark district
if reg and reg.in_landmark_district:
    constraints.append({
        "signal": "Landmark district — design review required",
        "detail": "Commission on Chicago Landmarks must review exterior modifications. Demolition is unlikely to be approved.",
        "category": "regulatory"
    })

# Rule: ARO threshold
if reg and reg.in_aro_zone and dev and dev.max_buildable_sqft:
    constraints.append({
        "signal": "ARO zone — affordable housing requirement at 10+ units",
        "detail": "Projects of 10+ units must set aside units as affordable or pay in-lieu fee (~$175K/required unit). Factor into project economics.",
        "category": "regulatory"
    })

# Rule: Pedestrian street (mixed)
if reg and any(o.layer_type == "pedestrian_street" for o in (reg.overlays or [])):
    opportunities.append({
        "signal": "Pedestrian street overlay",
        "detail": "Requires 60% ground-floor transparency and active uses — constrains design but signals walkable commercial corridor with higher foot traffic.",
        "category": "regulatory"
    })

# Rule: SSA additional tax
if reg and reg.in_ssa:
    constraints.append({
        "signal": f"Special Service Area levy",
        "detail": f"SSA {reg.ssa_name or ''} imposes additional property tax (typically 0.5-2.0% of EAV) beyond base property tax.",
        "category": "financial"
    })
```

### Financial (3 rules)

```python
# Rule: High effective tax rate
if report.effective_tax_rate and report.effective_tax_rate > 0.035:
    constraints.append({
        "signal": f"High effective tax rate ({report.effective_tax_rate:.1%})",
        "detail": "Above Cook County median (~2.1%). Reduces NOI and may impair debt service coverage. Investigate Class 6b/7a/7b/8 incentive eligibility.",
        "category": "financial"
    })

# Rule: Assessment trend up (market appreciation signal)
if report.assessment_trend and report.assessment_trend.get("cagr_pct", 0) > 5:
    opportunities.append({
        "signal": f"Strong assessment appreciation ({report.assessment_trend['cagr_pct']:.1f}% CAGR)",
        "detail": f"Assessed values increased {report.assessment_trend['total_change_pct']:.0f}% over {report.assessment_trend['years']} years — reflects Cook County reassessment cycle and area market trends.",
        "category": "market"
    })

# Rule: Low comp volume (valuation uncertainty)
if comps and comps.sales_volume and comps.sales_volume < 3:
    constraints.append({
        "signal": f"Thin comparable sales market ({comps.sales_volume} transactions)",
        "detail": "Land valuation carries higher uncertainty with limited arm's-length sales nearby. Consider wider search radius or independent appraisal.",
        "category": "market"
    })
```

### Site Condition (4 rules)

```python
# Rule: Many open violations
if report.address_violations:
    open_v = [v for v in report.address_violations if v.get("violation_status") == "OPEN"]
    if len(open_v) > 10:
        constraints.append({
            "signal": f"{len(open_v)} open building code violations",
            "detail": "Outstanding violations can block new permit issuance. Budget for remediation and factor violation clearance into closing timeline.",
            "category": "site_condition"
        })
    elif len(open_v) > 0:
        # Moderate violations — potential acquisition leverage
        opportunities.append({
            "signal": f"Open violations ({len(open_v)}) as acquisition leverage",
            "detail": "Owner faces compliance costs. Open violations may create negotiating leverage on purchase price.",
            "category": "site_condition"
        })

# Rule: High-risk 311 flags
if ctx.address_311 and ctx.address_311.high_risk_flags:
    constraints.append({
        "signal": "High-risk 311 complaints on file",
        "detail": f"Flags: {', '.join(ctx.address_311.high_risk_flags)}. May indicate structural, mechanical, or habitability issues requiring immediate assessment.",
        "category": "site_condition"
    })

# Rule: Active nearby construction (market confidence)
if report.nearby_development:
    nc = report.nearby_development.new_construction_count or 0
    if nc >= 5:
        opportunities.append({
            "signal": f"Active development corridor ({nc} new construction permits nearby)",
            "detail": "High nearby construction activity indicates market confidence, established contractor availability, and favorable zoning precedent.",
            "category": "market"
        })
    elif nc == 0 and (report.nearby_development.demolition_count or 0) == 0:
        constraints.append({
            "signal": "No nearby development activity (12 months)",
            "detail": "Limited construction within 0.25mi may indicate weak demand, regulatory barriers, or infrastructure constraints.",
            "category": "market"
        })

# Rule: Violations + long-term hold (mixed signal)
if report.ownership_signals:
    long_hold = any(s.get("signal") == "Long-term hold" for s in report.ownership_signals)
    if long_hold and report.address_violations:
        open_count = len([v for v in report.address_violations if v.get("violation_status") == "OPEN"])
        if open_count > 5:
            opportunities.append({
                "signal": "Long-held property with deferred maintenance",
                "detail": f"{open_count} open violations on a long-held property — owner faces mounting compliance costs and may be motivated to sell.",
                "category": "site_condition"
            })
```

### Environmental (2 rules)

```python
# Rule: SFHA flood zone
if reg and reg.in_special_flood_hazard:
    constraints.append({
        "signal": f"FEMA Special Flood Hazard Area (Zone {reg.flood_zone})",
        "detail": "Flood insurance mandatory for federally-backed mortgages. Construction costs typically increase 10-20% for SFHA compliance.",
        "category": "environmental"
    })

# Rule: Brownfield + TIF (mixed — remediation funding available)
if reg and reg.brownfield_sites and inc and inc.in_tif_district:
    opportunities.append({
        "signal": "TIF funding available for brownfield remediation",
        "detail": f"{len(reg.brownfield_sites)} brownfield site(s) nearby. TIF districts routinely fund environmental remediation as an eligible expense.",
        "category": "environmental"
    })
```

**Total: ~29 rules, producing 4-8 statements for a typical parcel.**

---

## 9. Development Envelope: Implementation Notes

### Edge Classification Algorithm

Chicago's street grid runs approximately N-S / E-W with a ~33° rotation (north is 33° east of grid-north). Most lots are rectangular and grid-aligned.

```
1. Compute bearing of each polygon edge (atan2 of dx, dy)
2. Normalize bearings to 0-180° (edges are undirected)
3. Group edges by bearing (±15° tolerance) into 2 groups for rectangular lots
4. "Front" = the group whose representative bearing is roughly perpendicular to the nearest street
   - Heuristic: front edges are typically shorter (lot width < lot depth)
   - Refinement: if address geocode is closer to one edge, that edge is front
5. "Rear" = the group parallel to front (same ±15° bearing band), on the opposite side
6. "Side" = all other edges
7. Fallback: if lot has >6 edges or groups don't resolve cleanly, use uniform minimum setback
```

### Polygon Inset Computation

For each edge, create a parallel line offset inward by the classified setback distance. Compute the intersection of adjacent offset lines to form the inner polygon vertices.

Library: shapely `parallel_offset` per edge segment, then intersection. Or manual: for each edge, compute the inward normal vector, offset by setback_ft × cos(lat) / 364567.2 (feet to degrees), intersect adjacent offset lines.

### Rendering

Follow the pattern of `_generate_zoning_map()` — matplotlib figure with Mapbox basemap tile.

- Parcel outline: 2px solid #374151
- Setback zones: #e5e7eb fill with diagonal hatching
- Buildable footprint: #2563eb fill at 20% opacity, solid border
- Dimension annotations: small text labels on each setback zone with distance in feet
- Buildable area annotation: centered text "~X,XXX sq ft buildable"
- Output: 400×400px PNG, base64 encoded

---

## 10. Regulatory Approval Pathway: Implementation Notes

### Decision Tree (Complete)

```
PRIMARY PATH:
  in_planned_development → COMPLEX (6-18 months)
  in_landmark_district OR in_historic_district → COMPLEX (3-6 months)
  special_uses AND NOT permitted_uses → MODERATE (3-6 months)
  special_uses AND permitted_uses → MODERATE (variable by use type)
  base zoning only → SIMPLE (4-8 weeks)

MODIFIERS (append to any path):
  open_violations > 5 → "+Violation clearance required before new permits"
  in_special_flood_hazard → "+FEMA floodplain compliance review"
  in_aro_zone AND estimated_units >= 10 → "+ARO affordable housing compliance"
  in_landmark_district AND bldg_age < 50 → "+Non-contributing structure — demolition may be permitted"
  in_pedestrian_street → "+Ground-floor design must meet pedestrian street standards"
```

### Traffic Light Integration

Add as 6th item in the Executive Summary traffic lights:
- SIMPLE → green pill: "SIMPLE — Standard building permit (4-8 weeks)"
- MODERATE → yellow pill: "MODERATE — Special use or overlay review required"
- COMPLEX → red pill: "COMPLEX — Discretionary approval process (6-18 months)"

---

## 11. Explicit "Do Not Build" List

| Feature | Rationale |
|---------|-----------|
| Development Scenario Verdicts ("PERMITTED / NOT PERMITTED") | Crosses from feasibility into entitlement interpretation. Wrong verdicts destroy trust. Development Envelope Summary + Visualization achieves the same goal safely. |
| Full automated pro forma (IRR, NPV, CoC) | Too many assumptions. One wrong construction cost or vacancy rate produces a misleading projection. Provide inputs, not projections. |
| Owner name lookup | Requires paid data license. Can't automate with public data. Flag as "not available via open data" in ownership intelligence section. |
| Soil/geotechnical analysis | USDA SSURGO too coarse for urban lots. Always requires actual borings. Flag as "verify" in due diligence checklist. |
| Wetlands/endangered species/wildlife | Irrelevant for Chicago urban infill. Don't clutter the report. |
| Topography/elevation | Chicago is flat. Not worth the API integration. |
| School performance ratings | Property report territory, not feasibility. Off-thesis per design principles. |
| Noise contour mapping | Complex data integration for marginal value. Cut. |
| Pending zoning changes | Requires PDF parsing from Legistar. Separate initiative per North Star (Phase 4+). |
| Property photos / street view | No free API available. Copyright issues with Google. |
| Full subdivision cost estimation | 50+ line items varying wildly. Too speculative. |
| Automated rental income projection | ACS median rent ≠ achievable rent for new construction. Too many assumptions. |
| Construction cost estimation from permits | Reported costs in permits are notoriously under-reported. Misleading input. |

---

## 12. Future Ideas (Intentionally Deferred)

These ideas have merit but are deferred to V6+ pending customer validation:

| Idea | Rationale for Deferral | Trigger to Build |
|------|----------------------|-----------------|
| Environmental Risk (IL EPA LUST/SRP/RCRA) | Marginal over existing brownfield/flood coverage | Customer interview reveals missed environmental flag |
| Rental Market Indicators (vacancy rate, rent-to-income) | Median rent already in demographics | Multifamily developers emerge as primary customer |
| Pro Forma Inputs table | Accuracy concerns with construction costs | Customer repeatedly asks "what would a pro forma look like?" |
| Automated frontage adequacy check | Requires reliable edge classification | Development Envelope ships and edge classification is proven |
| Alley access detection | Requires GIS alley dataset or heuristic | Customer asks "does this lot have alley access?" |
| Utility infrastructure flags | DWM/ComEd data may not be accessible via API | Customer interview reveals utility access as a pain point |
| Comprehensive plan alignment | Requires locating and parsing Chicago's community plans | Attorneys or planners become a customer segment |
| Traffic/ADT counts | IDOT data exists but integration is complex | Commercial developers request it |

---

## 13. Page Budget

| Section | Current | V5 Target | Change |
|---------|---------|-----------|--------|
| Cover | 1 | 1 | — |
| Executive Summary | 0.7 | 1.2 | +0.5 (opps/constraints, approval traffic light) |
| Zoning & Development | 1.5 | 2.2 | +0.7 (envelope summary + visualization) |
| Regulatory & Environmental | 0.7 | 0.9 | +0.2 (approval pathway detail) |
| Property & Physical | 2.0 | 2.0 | — |
| Market Context & Comps | 2.0 | 2.3 | +0.3 (land value range, trend narrative) |
| Financial & Incentives | 1.5 | 1.7 | +0.2 (stacking narrative) |
| Site Condition & History | 1.5 | 1.0 | -0.5 (crime condensed, due diligence checklist added) |
| Next Steps (NEW position) | 0 | 0.5 | +0.5 (promoted from Data Sources) |
| Glossary | 1.5 | 0.75 | -0.75 (condensed) |
| Zone Definitions | 0.5-1 | 0.5-1 | — |
| Data Sources & Disclaimers | 1.5 | 1.0 | -0.5 (condensed, next steps removed) |
| **Total** | **~14** | **~16** | **+2 net** |

---

## 14. Verification Plan

After each phase:
1. `python -m pytest backend/tests/ -q` — no regressions
2. Generate mock report: `curl -o /tmp/report-v5.pdf "http://localhost:8001/api/report?address=2400+N+Milwaukee+Ave&mock=true" -H "Cookie: session=dev"`
3. Generate mock for different parcel types:
   - Vacant lot in OZ+TIF: verify incentive stacking opportunities
   - PD-designated site: verify COMPLEX approval pathway
   - Landmark district: verify constraints
   - High-violation property: verify site condition constraints
   - Thin comp market: verify low-volume constraint
4. Visual inspection of development envelope rendering on rectangular, corner, and irregular lots
5. Verify opportunities/constraints volume cap (max 4+4)
6. Verify all disclaimers render correctly
7. Compare page count against budget (~16 target)

---

## 15. Critical Files

| File | Changes |
|------|---------|
| `backend/main.py` | `_synthesize_opportunities_constraints()`, `_compute_land_value_range()`, `_compute_approval_pathway()`, `_generate_envelope_map()`, `_compute_development_trend()`, mock overrides |
| `backend/templates/zoning_report.html` | Opps/constraints in exec summary, envelope summary + map in zoning, approval pathway in regulatory, land value + trend narrative in market, stacking narrative in financial, crime condensed, next steps promoted, glossary condensed, data sources condensed |
| `backend/models.py` | New fields on ReportData: `opportunities`, `constraints`, `estimated_land_value`, `approval_pathway`, `envelope_map_b64`, `buildable_footprint_sqft`, `development_trend` |

No new files. No new dependencies. No new API integrations.
