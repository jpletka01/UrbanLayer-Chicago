# Scorecard chat grounding — bypass (2026-06-21) — SHIPPED (`main` @ `43ad976`)

The Scorecard→chat handoff ships the parcel's already-resolved `ContextObject` sub-objects (`scorecard_context`)
so the answerer reads them directly and `_retrieve` skips the property/regulatory/incentives/zoning/aro fetches
(**bypass**); vector_search/neighborhood/activity still retrieve (**augment**).

**Reusable lesson — the router seam:** 3 bugs, one root cause: the router sets intent from raw text before the pin
can anchor, and `_apply_parcel_hint` only rescues address-typed plans (drift hazard; deictic→clarification;
bare-`?pin=`→splash). This drove the later conversation-sticky grounding — see `archive/2026-06-30_verdict-grounding-ux.md`.
Current grounding behavior is documented in `frontend/CLAUDE.md → Scorecard chat grounding`. Historical marker.
