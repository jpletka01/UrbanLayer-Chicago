# Expansion Roadmap — UrbanLayer

## Completed Phases

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

## Remaining Opportunities (Tier 3)

These were identified as "nice to have" and not yet implemented:

| Integration | Value | Difficulty | Notes |
|-------------|-------|------------|-------|
| ~~Cook County Tax Incentive Classes (6b, 7a)~~ | ~~Medium~~ | ~~Low~~ | **Done** — Interprets `class` field from Parcel Universe as incentive classification (6b/6c/7a/7b/7c/8). Enriches IncentivesSummary in assembler. |
| ~~SBIF Projects~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — `grant_programs.py` queries `etqr-sz5x` (2,152 records) by community area name |
| ~~Neighborhood Opportunity Fund~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — Combined with SBIF in `grant_programs.py`. Queries `j7ew-b73u` (large) + `rym7-49n8` (small) |
| ~~ARO Housing Data~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — `aro_housing.py` queries `s6ha-ppgi` (598 records). Enriches RegulatorySummary when regulatory_domain active |
| ~~Food Inspections~~ | ~~Low~~ | ~~Low~~ | **Done** — `food_inspections_api`, pass/fail/risk breakdown, recent inspections |
| ~~Vacant Buildings~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — `vacant_buildings_api`, by-department counts, recent reports with fines |
| Illinois Professional Licenses | Low | Medium | Different Socrata portal (data.illinois.gov). Deferred — low value, different base URL/auth pattern |

## ArcGIS Layer Audit (2026-06-04)

Evaluated the 5 unintegrated Chicago Zoning MapServer layers. None warranted integration:

| Layer | Name | Decision | Reasoning |
|-------|------|----------|-----------|
| 10 | Downtown Area | Skip | Single large polygon, not actionable for property-level queries |
| 14 | TSL Route | Skip | CTA transit routes — redundant with TOD station layers (13, 24) already integrated |
| 18 | Special District SubArea | Skip | Duplicates PMD SubAreas (layer 12) already integrated |
| 19 | Downtown Exclusion Zone | Skip | Narrow regulatory exclusion, very limited use case |
| 21 | Planning Regions | Skip | Administrative boundaries, not actionable for users |

## Tier 3 Design Decisions (2026-06-04)

**Tax Incentive Classes**: The `class` field was already being retrieved from the Parcel Universe dataset in `parcels.py`. Rather than adding a new API call, the assembler now interprets existing class codes (6b/6c/7a/7b/7c/8) as tax incentive classifications. The property class comes from the property domain but the incentive interpretation lives in the assembler since it enriches the IncentivesSummary — a cross-domain concern handled at assembly time rather than in either orchestrator.

**SBIF + NOF combined**: All three datasets (SBIF, NOF Large, NOF Small) share identical schemas and represent the same concept (city grant programs). Combined into a single `grant_programs.py` module that queries all 3 in parallel and tags results by program source. They're wired into the incentives domain orchestrator (not as separate source tags) because they're contextual enrichment for incentive analysis, not standalone data sources worth routing separately.

**ARO Housing as parallel source**: ARO housing runs as a standalone task in `main.py` (parallel with the regulatory domain), not nested inside the regulatory orchestrator. This avoids adding latency — the regulatory orchestrator would need to complete overlay detection before conditionally fetching housing data. Instead, ARO housing always fetches for the community area when regulatory_domain is active, and the assembler attaches it to RegulatorySummary. The dataset is small (598 records) so the unconditional query is cheap.

**Violation categorization hybrid**: Investigated using `violation_code` as the primary categorization key. The codes are heterogeneous alphanumeric strings (CN190019, EV1110, AAG679, BR1010) with no consistent structure — a full code-to-category mapping would require maintaining thousands of entries. Instead, added code-prefix mapping for the two clear prefixes (EV→Elevator, BR→Boiler) and expanded keyword coverage to catch common abbreviations (e.g., "ELEVA" for elevator, "ELECT" for electrical). The keyword approach remains primary.

## Production Readiness

| Item | Status |
|------|--------|
| Docker Compose (Qdrant + backend + frontend) | Done |
| Dockerfile (FastAPI backend) | Done — multi-stage, CPU-only PyTorch, baked HF models, non-root user |
| Dockerfile (Frontend) | Done — multi-stage Vite build + nginx, `NGINX_CONF` build arg for dev/prod |
| Production nginx config | Done — `nginx.prod.conf` with HTTPS (Cloudflare Origin Cert), security headers, gzip, CSP for Mapbox |
| Production compose override | Done — `docker-compose.prod.yml` layers port 443 + SSL volume on base config |
| Server deployment (HTTP) | Done — all 3 services running at `http://178.105.184.66` |
| DNS + HTTPS (Cloudflare) | Done — Full (Strict) + Origin Certificate, security headers verified |
| Qdrant data transfer | Done — 14,535 vectors snapshot-transferred |
| Google OAuth setup | Done — OAuth client configured, auth active on server |
| CI pipeline (tests + type check) | Done — `.github/workflows/ci.yml`, auto-deploy on push to main |
| CI/CD deploy secrets | Done — `SERVER_SSH_KEY` + `SERVER_HOST` configured in GitHub repo secrets |
| Monitoring / alerting | Done — UptimeRobot active, Sentry active (EU region DSNs configured) |
| AI code review on PRs | Done — `.github/workflows/code-review.yml`, `anthropics/claude-code-action@v1`, Claude Code GitHub App installed |
| Tier 3 production deploy | Done — PR #1 merged (2026-06-05), all integrations live on production |
| CI fixes | Done — `anthropic_api_key` default, Walk Score test mocking, `id-token: write` permission, `ANTHROPIC_API_KEY` secret |
| CI deploy key | Done — passphrase-free ed25519 key, verified end-to-end (2026-06-05) |
