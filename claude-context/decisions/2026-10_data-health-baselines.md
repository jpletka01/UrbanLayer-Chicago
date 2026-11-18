# Data health: measured baselines

Format: see `README.md` in this folder. A baseline moves only after the change is understood, never to silence an alarm.

---

## Item 1: the pedestrian-street overlay baseline moves from 2 features to 58 (2026-10-30)

**Decision:** `_OVERLAY_ROWS` records 58 features for Zoning MapServer layer 4 ("Pedestrian Street"), so the count band is 46 to 73 instead of 1 to 3. The `chi.zoning.overlay.pedestrian_street` source had been alarming ("58 features, expected 1 to 3"); that was the baseline being stale, not the layer being broken.

- **Why it is the baseline and not the layer.** The layer name and fields are unchanged (`OBJECTID, BUFFERDIST, NAME, SHAPE...`, polygons). The 58 features carry real designation names (`PEDESTRIAN STREET`, `PEDESTRIAN STREET RETAIL`, `PEDESTRIAN STREET SIX-CORNER`, `PEDESTRIAN_STREET_DOWNTOWN`); 48 have buffer 0 and 10 have none. A point query at State and Madison (a pedestrian street) now returns one polygon; Clark at Addison, which the applied-law notes say the City's map does not show yet, returns none.
- **Alternative: acknowledge the alarm** (`_ACK_UNTIL`). Rejected: an acknowledgement says "known and tolerated", and this is a change we now understand and want the next one to be measured against.
- **Alternative: widen the band.** Rejected: a band of 1 to 60 would hide the layer shrinking back to a handful.

**What it means for users.** The Profile and chat read this layer live, so the pedestrian-street flag was already firing on more addresses than before this change; nothing in the serving code changes here. `legislation/applied.py` still adds its own ahead-of-the-map notes where the map misses a designation (its comment that the layer "rarely detects pedestrian streets" describes the old 2-polygon layer and is now stale).

**Revisit if:** the count moves outside 46 to 73 again (the City adds or retires designations), or a sentinel parcel's pedestrian-street value flips unexpectedly.

**Numbers**
- **Before:** 2 features (measured 2026-10-02), band 1 to 3.
- **After:** 58 features, band 46 to 73. Measured 2026-10-30 with `returnCountOnly` against the public layer.
- **Not measured:** when the City made the change (the alarm appeared between 2026-10-28 and 2026-10-30); how many Profile addresses now show the flag; whether the new polygons match each designated street's legal extent.
- **Reproduce:** `python -m backend.data_health.check --dry-run | grep pedestrian`

---

## Item 2: the two production alarms of 2026-11-18: street centerlines frozen, NOF Small acknowledged (2026-11-18)

The /admin Overview (Item 130) showed `/health` reporting `"alarms": 2`. The local dry run reproduces exactly two: `chi.street_centerlines` and `chi.nof_small`. Each was judged on its own.

**`chi.street_centerlines` (`pr57-gg9e`): a wrong rule, now `frozen`.**
- **Decision:** `Frozen("2021-06-11", ...)` with no age tolerances, replacing `warn_days=730, alarm_days=1460`.
- **Why:** the City's current centerline dataset was last refreshed 2021-06-11 (`rowsUpdatedAt`; `publicationDate` the same day; `max(status_dat)` = 2016-01-25; 56,338 segments). The catalog lists five older "Deprecated" centerline datasets and no successor. It crossed 1,460 days on 2025-06-11, before Item 67 registered it, so it alarmed from its first run: the rule could never have been green. What matters for a static layer is change: the block-face rule (`block_face.py`), the base map tiles (`base_tiles.py`) and the Assessor-address match (`assessor_address.py`) were all built against this copy, and a refresh means rebuilding the tiles and re-checking block faces. A frozen source alarms on exactly that.
- **Alternative: acknowledge it.** Rejected: an ack expires and says "stale, tolerated"; this layer is not stale in any sense users feel (Chicago's streets are stable), and an expiring ack would return the same false alarm in January.
- **Alternative: a longer age (say 10 years).** Rejected: it still alarms one day for no reason, and never says when the data actually moves.
- **What users see:** nothing changes; the Profile's RS-3 block-face check and the map keep reading the same data.
- **Revisit if:** the City publishes a new centerline dataset or refreshes this one (the frozen rule alarms), at which point rebuild the base tiles and re-run the block-face tests.

**`chi.nof_small` (`rym7-49n8`): a real upstream lag, acknowledged like NOF Large.**
- **Decision:** an `Ack` until 2027-01-31 (the shared `_ACK_UNTIL`), keeping the quarterly-based tolerances (120/270 days).
- **Why:** the publisher says "Data are updated quarterly", but rows were last updated 2026-02-02 (289 days on 2026-11-18; it crossed the 270-day alarm on 2026-10-30). Content: 126 completed projects, newest `approval_date` 2025-08-25, newest `completion_date` 2026-01-12. The catalog has no successor (searching "neighborhood opportunity fund" returns only the Small and Large datasets; Large has been stale since 2023-09-19 and acked since 2026-10-21). This is the City's lag, not ours; nothing to rebuild.
- **What users see meanwhile:** only chat uses it, as a list of completed NOF Small grants near a place (`grant_programs.py`), and the list is exactly what the City publishes; recent grants (after early 2026) are missing. No Profile fact rests on it.
- **Alternative: leave it alarming.** Rejected: a standard-severity chat-only list paging daily trains people to ignore the alarm path. **Alternative: relax to 400/540.** Rejected: the quarterly claim is the publisher's; the ack records that they are not meeting it and expires so someone looks again.
- **Revisit if:** the dataset updates (the ack becomes moot), the City publishes a successor, or the ack reaches 2027-01-31 still stale (it becomes an alarm again; consider retiring the source from chat with NOF Large when WS0 audits grant data).

**Numbers**
- **Before:** `/health` `"alarms": 2` (2026-11-18, production); local `check --dry-run`: `ALRM chi.nof_small` (289 d, alarm after 270), `ALRM chi.street_centerlines` (1,986 d, alarm after 1,460).
- **After:** local dry run `ack chi.nof_small`, `froz chi.street_centerlines`, "0 would alert". Production returns to 0 alarms on the first daily run after the deploy (not measured yet).
- **Reproduce:** `python -m backend.data_health.check --dry-run --only chi.street_centerlines,chi.nof_small`; `curl -s 'https://data.cityofchicago.org/resource/rym7-49n8.json?$select=max(approval_date),max(completion_date),count(*)'`; `curl -s https://data.cityofchicago.org/api/views/pr57-gg9e.json` (`rowsUpdatedAt`).
- **Not measured:** how many chat answers have cited NOF Small since February; whether the production store's alarms match the local dry run's (production-only sources such as backups, ptaxsim and the Discovery index cannot alarm locally).
