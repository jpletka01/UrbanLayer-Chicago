# 03 — Filter Registry

The registry is a **single, versioned, static artifact** authored once, served by the backend at
`GET /api/discovery/registry`, and consumed by both backend (compile + evaluate) and frontend (UI + topic
compile). One source ⇒ no FE/BE drift on predicate kinds or topic definitions.

## Registry schema

```ts
interface Registry {
  version: string;            // bumped on any filter/topic change
  filters: FilterDef[];
  topics:  TopicDef[];        // see 04
  sortKeys: SortKeyDef[];
  defaultSort: SortSpec;      // used when no input sets sort
  broadMinFilters: number;    // diagnostics "broad" threshold (06)
}

interface FilterDef {
  id:           string;           // FilterId
  category:     "location" | "property_use" | "zoning_dev" | "incentives" | "financial" | "condition_risk";
  kind:         "enum" | "range" | "flag" | "region";
  field:        string;           // the parcel attribute this predicate reads
  unknownPolicy:"exclude" | "include";   // REQUIRED — behavior when attribute is missing (see below)
  enumValues?:  string[];         // required when kind = "enum"
  unit?:        string;           // for range filters (sqft, usd, year…), display only
  contradicts?: string[];        // filter ids that are statically contradictory (06)
}

interface SortKeyDef { key: string; field: string; }
```

## Predicate kinds — evaluation semantics

| kind | Matches parcel `p` when | Notes |
|---|---|---|
| `enum`   | `p.field ∈ values` | OR within `values` |
| `range`  | `(min ≤ p.field)` and `(p.field ≤ max)` for whichever bounds are present | inclusive; `min>max` ⇒ never matches |
| `flag`   | `value=true` → `p.field` is present/true; `value=false` → `p.field` is absent/false | boolean polarity, both directions valid |
| `region` | `p` lies in any of `regions` | OR within; point-in-polygon / radius handled by the field resolver |

## Missing values — `unknownPolicy` (REQUIRED, definitional)

When `p.field` is missing/NULL, the predicate evaluates **deterministically** by the filter's
`unknownPolicy`:

- `exclude` → predicate is `false` (parcel dropped). **Default for all filters unless stated.**
- `include` → predicate is `true` (parcel kept).

This MUST live in the registry and be applied uniformly by the evaluator. The evaluator MUST NOT branch
on missing values in any other way. *Why this exists:* over real municipal data, attribute coverage is
incomplete; leaving NULL behavior undefined makes the evaluator non-deterministic and silently drops
candidates. Defining it here makes exclusion-by-unknown explicit and countable (see diagnostics 06,
`excludedUnknown`).

## Filter set (this build)

| Category | Filters (id → kind) |
|---|---|
| location | `neighborhood→region`, `ward→region`, `radius→region`, `transit_proximity→range` |
| property_use | `land_use→enum`, `vacancy→flag`, `lot_size→range`, `building_size→range`, `year_built→range`, `units→range` |
| zoning_dev | `zoning_group→enum`, `density_band→range`, `overlay→enum`, `adu_eligible→flag`, `aro_zone→flag` |
| incentives | `tif→flag`, `opportunity_zone→flag`, `enterprise_zone→flag`, `sbif_nof→flag` |
| financial | `assessed_value→range`, `last_sale_price→range`, `sale_recency→range`, `price_per_sf→range`, `improvement_ratio→range` |
| condition_risk | `open_violations→range`, `f311_redflags→range`, `floodplain→flag`, `brownfield→flag`, `crime_index→range` |

`density_band` declares `contradicts: []` at the field level but the compiler SHOULD reject a
`density_band` predicate with no `zoning_group` predicate present (a density band is meaningless without
a zoning family); this is a compile-time validation, not an evaluator concern.

> No new filters may be added in this build. Adding one = registry version bump + new `FilterDef` only;
> never a code change in the evaluator.
