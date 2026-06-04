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

Original Buckets 1-3 also complete: mobile responsiveness, file upload, admin dashboard, LLM-as-judge eval, legal-domain reranker, data source coverage benchmark (24 queries across all 24 sub-sources).

## Remaining Opportunities (Tier 3)

These were identified as "nice to have" and not yet implemented:

| Integration | Value | Difficulty | Notes |
|-------------|-------|------------|-------|
| Cook County Tax Incentive Classes (6b, 7a) | Medium | Low | Query CCAO by PIN for property class |
| SBIF Projects | Low-Medium | Low | Historical grant data on Socrata |
| Neighborhood Opportunity Fund | Low-Medium | Low | Grant data on Socrata |
| ARO Housing Data | Low-Medium | Low | Affordable housing datasets |
| ~~Food Inspections~~ | ~~Low~~ | ~~Low~~ | **Done** — `food_inspections_api`, pass/fail/risk breakdown, recent inspections |
| ~~Vacant Buildings~~ | ~~Low-Medium~~ | ~~Low~~ | **Done** — `vacant_buildings_api`, by-department counts, recent reports with fines |
| Illinois Professional Licenses | Low | Medium | Different Socrata portal (data.illinois.gov) |

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
| CI pipeline (tests + type check) | Done — `.github/workflows/ci.yml`, needs GitHub secrets for deploy job |
| Monitoring / alerting | Partial — UptimeRobot active, Sentry SDK integrated (needs DSN) |
