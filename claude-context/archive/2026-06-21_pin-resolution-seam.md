# PIN-resolution seam fix (2026-06-21) — SHIPPED (`main` @ `6a23793`)

Two address→parcel resolvers disagreed: the scorecard's authoritative `resolved_pin` (Address Points `78yw-iddh`)
correctly returned `approximate` for absent addresses, while the property orchestrator's nearest-centroid bbox
fallback returned a *neighbor* (470 vs 481 W Deming — a dense-block row-cap truncation evicting the true nearest).
Fix: (1) the Socrata fallback orders by distance **server-side** (`$order` on `pabr-t5kh`) + refuse-on-cap;
(2) a reverse round-trip gate `parcel_address_matches()` (number+direction+parity); (3) `/api/scorecard` promotes a
fallback PIN to identity only if it round-trips, else withholds it (`resolved_pin=null`, `nearest_parcel_unverified`
so the UI caveats property/comps); (4) flagship demo address swapped 2400→**1601 N Milwaukee Ave**.

The canonical resolver contract now lives in the **living** `guides/parcel-resolution-truth-model.md` and
`core/known-issues.md`. Full story on the About page → **Parcel Identity**. Historical marker.
