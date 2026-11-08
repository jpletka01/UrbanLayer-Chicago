# FEMA flood zones from a committed Chicago copy

**Completed**: 2026-11-08
**Status**: Shipped to production (PR #205 `cd43434`, PR #206 `6eb3c11`, PR #207 `feadd75`)

## What Was Built
FEMA's `hazards.fema.gov` resets every TLS handshake from the production server in Germany (10 of 10, both IPs; `www.fema.gov` answers 403), so every live Profile said flood couldn't be checked and re-asked FEMA (~4 s) on each visit. Chicago points are now answered from `ingestion/data/fema_flood_chicago.json.gz`: FEMA's own NFHL layer 28 polygons clipped to the city (395 zones, 100% coverage, 0.5 MB), built by `python -m ingestion.build_flood_artifact` from a machine FEMA answers and matched by STRtree point-in-polygon in `retrieval/regulatory/flood.py`. Points outside the city still ask FEMA live, where a failure is still "couldn't check". The copy agreed with live FEMA at 400 of 400 points. Verifying it on production turned up two more gaps, also fixed. First, the app set no log level, so every `log.info` line was dropped, the `scorecard timings` lines included, and the CR/LF filter had no handler to sit on: `log_safety.configure()` now handles that, and two lines that logged chat text moved to DEBUG. Second, the blocked live probe `fed.fema.nfhl` now only warns while the copy is fresh (`warns_only_while_ok`). After the deploy a repeat Profile takes 44–52 ms on the server. The 1.5–2 s seen from Chile is the network route through Cloudflare's Rio edge to Nuremberg.

## Key Decisions
Decision Items 84–86 in `decisions/2026-11_frontend-rewrite.md`. Reusable lessons: a block by source address is not a client bug, so measure from the server itself (`curl` exit 35 = reset in the TLS handshake); a committed artifact needs a coverage guard, which here caught a non-unique dedupe key on the first build; and read the production logs for the line you rely on before planning to measure from it. Rebuild the copy about every six months, or when FEMA revises the Cook County maps (data health warns at 200 days). A rebuild on 2026-11-08 reproduced the zones exactly. Full story: About page, "Engineering Challenges" → "A federal map that refused our server".

## Moved from known-issues
"FEMA endpoint flakiness" (occasional 500s or empty results) has been superseded: inside Chicago FEMA is no longer called at request time.
