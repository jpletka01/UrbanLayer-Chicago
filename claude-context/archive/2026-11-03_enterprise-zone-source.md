# Enterprise Zone source

**Completed**: 2026-11-03
**Status**: Shipped to production (PR #181, merge `b61d91b`)

## What Was Built
The City's Enterprise Zone map view `64xf-pyvh` started returning its 6 zones with `geometry: null`, so every parcel read "not in an Enterprise Zone" and the Discovery flag was false citywide. The loader now reads the map's backing dataset `bwpt-y235` (zones named "Chicago Enterprise Zone 1"–"6"), and an empty or failed boundary layer raises: the Profile shows "Not checked", the report "Couldn't check today", and Discovery leaves the flag NULL (TIF too).

## Key Decisions
Decision Item 64 in `decisions/2026-10_build-queue.md`. Reusable lesson: a source that answers with nothing usable is a failure, not a finding; check `modifyingViewUid` in `/api/views/<id>.json` when a Socrata map view goes blank. Full story: About page, "Engineering Challenges" → "A source that went blank without failing".

## Open
The production Discovery index still has `in_enterprise_zone` false everywhere until it is rebuilt (Jack deferred the rebuild on 2026-11-03).
