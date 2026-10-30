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
