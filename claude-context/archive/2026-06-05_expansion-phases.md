# Expansion Phases & Tier 3 Integrations

**Completed**: 2026-06-05
**Status**: Shipped to production

## What Was Built
7 expansion phases (Infrastructure/Regulatory/Property/Incentives/Neighborhood/Frontend/Polish) plus Tier 3 integrations (tax incentive classes, SBIF, NOF, ARO housing, food inspections, vacant buildings). All phases and Tier 3 items complete. PR #1 merged (2026-06-05), all integrations live on production.

## Implementation Details

### Completed Phases

All expansion phases from the original `chicago_expansion_plan.md` are complete:

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1 | Infrastructure + Regulatory Domain | Done — models, routing, domain orchestrators, overlay layers 2-24 |
| Phase 2 | Property Domain | Done — parcels, characteristics, assessments, sales, PTAXSIM tax estimation |
| Phase 3 | Regulatory Domain | Done — overlays, FEMA flood, EPA brownfields |
| Phase 4 | Incentives Domain | Done — TIF boundaries + financials, Enterprise Zones, Opportunity Zones |
| Phase 5 | Neighborhood Domain | Done — demographics, transit proximity, Walk Score API |
| Phase 6 | Frontend Integration | Done — PropertyCard, RegulatoryCard, IncentivesCard, NeighborhoodCard, map overlay/incentive polygons |
| Phase 7 | Polish & Optimization | Done — TTL caching, startup preloading, graceful degradation, workflow_hint, eval expansion (39 queries), overlay/incentive map geometry |

Original Buckets 1-3 also complete: mobile responsiveness, file upload, admin dashboard, LLM-as-judge eval, legal-domain reranker, data source coverage benchmark (29 queries across 29 sub-sources, 83% coverage rate).

### Remaining Opportunities (Tier 3)

| Integration | Value | Difficulty | Notes |
|-------------|-------|------------|-------|
| ~~Cook County Tax Incentive Classes (6b, 7a)~~ | ~~Medium~~ | ~~Low~~ | **Done** — Interprets `class` field from Parcel Universe as incentive classification (6b/6c/7a/7b/7c/8). Enriches IncentivesSummary in assembler. |
| ~~SBIF Projects~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — `grant_programs.py` queries `etqr-sz5x` (2,152 records) by community area name |
| ~~Neighborhood Opportunity Fund~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — Combined with SBIF in `grant_programs.py`. Queries `j7ew-b73u` (large) + `rym7-49n8` (small) |
| ~~ARO Housing Data~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — `aro_housing.py` queries `s6ha-ppgi` (598 records). Enriches RegulatorySummary when regulatory_domain active |
| ~~Food Inspections~~ | ~~Low~~ | ~~Low~~ | **Done** — `food_inspections_api`, pass/fail/risk breakdown, recent inspections |
| ~~Vacant Buildings~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — `vacant_buildings_api`, by-department counts, recent reports with fines |
| Illinois Professional Licenses | Low | Medium | Different Socrata portal (data.illinois.gov). Deferred — low value, different base URL/auth pattern |

### ArcGIS Layer Audit (2026-06-04)

Evaluated the 5 unintegrated Chicago Zoning MapServer layers. None warranted integration:

| Layer | Name | Decision | Reasoning |
|-------|------|----------|-----------|
| 10 | Downtown Area | Skip | Single large polygon, not actionable for property-level queries |
| 14 | TSL Route | Skip | CTA transit routes — redundant with TOD station layers (13, 24) already integrated |
| 18 | Special District SubArea | Skip | Duplicates PMD SubAreas (layer 12) already integrated |
| 19 | Downtown Exclusion Zone | Skip | Narrow regulatory exclusion, very limited use case |
| 21 | Planning Regions | Skip | Administrative boundaries, not actionable for users |

### Tier 3 Design Decisions (2026-06-04)

**Tax Incentive Classes**: The `class` field was already being retrieved from the Parcel Universe dataset in `parcels.py`. Rather than adding a new API call, the assembler now interprets existing class codes (6b/6c/7a/7b/7c/8) as tax incentive classifications. The property class comes from the property domain but the incentive interpretation lives in the assembler since it enriches the IncentivesSummary — a cross-domain concern handled at assembly time rather than in either orchestrator.

**SBIF + NOF combined**: All three datasets (SBIF, NOF Large, NOF Small) share identical schemas and represent the same concept (city grant programs). Combined into a single `grant_programs.py` module that queries all 3 in parallel and tags results by program source. They're wired into the incentives domain orchestrator (not as separate source tags) because they're contextual enrichment for incentive analysis, not standalone data sources worth routing separately.

**ARO Housing as parallel source**: ARO housing runs as a standalone task in `main.py` (parallel with the regulatory domain), not nested inside the regulatory orchestrator. This avoids adding latency — the regulatory orchestrator would need to complete overlay detection before conditionally fetching housing data. Instead, ARO housing always fetches for the community area when regulatory_domain is active, and the assembler attaches it to RegulatorySummary. The dataset is small (598 records) so the unconditional query is cheap.

**Violation categorization hybrid**: Investigated using `violation_code` as the primary categorization key. The codes are heterogeneous alphanumeric strings (CN190019, EV1110, AAG679, BR1010) with no consistent structure — a full code-to-category mapping would require maintaining thousands of entries. Instead, added code-prefix mapping for the two clear prefixes (EV→Elevator, BR→Boiler) and expanded keyword coverage to catch common abbreviations (e.g., "ELEVA" for elevator, "ELECT" for electrical). The keyword approach remains primary.

## Key Decisions

- **Tax incentive class as assembler-level concern**: Property class comes from property domain but incentive interpretation enriches IncentivesSummary — a cross-domain concern handled at assembly time rather than in either orchestrator.
- **SBIF + NOF combined into `grant_programs.py`**: All three datasets share identical schemas and represent the same concept. Combined into one module querying all 3 in parallel, wired into incentives domain orchestrator as contextual enrichment.
- **ARO housing as parallel source (not nested in regulatory orchestrator)**: Runs as standalone task in `main.py` parallel with regulatory domain to avoid added latency. Unconditional query is cheap (598 records).
- **Violation categorization hybrid approach**: Code-prefix mapping for clear prefixes (EV→Elevator, BR→Boiler) + expanded keyword coverage. Full code-to-category mapping impractical due to heterogeneous alphanumeric codes.
- **ArcGIS layers 10/14/18/19/21 skipped**: None actionable for property-level queries. Downtown Area is a single polygon, TSL Route redundant with TOD layers, Special District SubArea duplicates PMD SubAreas.

## Files Changed

- `backend/retrieval/incentives/grant_programs.py` — **New**: SBIF + NOF combined module
- `backend/retrieval/regulatory/aro_housing.py` — **New**: ARO housing data
- `backend/retrieval/food_inspections_api.py` — **New**: Food inspection data
- `backend/retrieval/vacant_buildings_api.py` — **New**: Vacant building reports
- `backend/assembler.py` — Tax incentive class interpretation, grant program attachment, ARO housing attachment
- `backend/main.py` — ARO housing parallel task, food inspections + vacant buildings routing
- `backend/models.py` — New summary models for Tier 3 data sources
- `backend/router.py` — Updated routing for new source tags
