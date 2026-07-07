# Lot Information Coverage Report

_2026-07-07 18:56Z · 100 panel addresses · 0 fetch errors_

**First-hit coverage** = what one page load shows; **persistent coverage**
= best the data can support (transient retrieval failures excluded). Parcels
where the field is legitimately absent (vacant land → no building sqft,
exempt → no tax) are excluded from both bases.

## Field Coverage

| Field | Tier | Present | Missing (persistent) | Missing (transient) | Expected absent | First-hit | Persistent |
|---|---|---:|---:|---:|---:|---:|---:|
| `pin_resolved` | identity | 97 | 3 | 0 | 0 | 97.0% | 97.0% |
| `pin_authoritative` | identity | 97 | 3 | 0 | 0 | 97.0% | 97.0% |
| `pin_matches_truth` | identity | 97 | 3 | 0 | 0 | 97.0% | 97.0% |
| `property_record` | identity | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `land_sqft` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `bldg_sqft` | critical | 88 | 12 | 0 | 0 | 88.0% | 88.0% |
| `bldg_class` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `year_built` | critical | 88 | 12 | 0 | 0 | 88.0% | 88.0% |
| `assessed_value` | critical | 82 | 0 | 0 | 18 | 100.0% | 100.0% |
| `assessment_history` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `tax_bill` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `tax_rate` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `zoning_class` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `zoning_far` | critical | 87 | 1 | 0 | 12 | 98.9% | 98.9% |
| `stories` | secondary | 69 | 31 | 0 | 0 | 69.0% | 69.0% |
| `units` | secondary | 31 | 69 | 0 | 0 | 31.0% | 31.0% |
| `sales_history` | secondary | 76 | 24 | 0 | 0 | 76.0% | 76.0% |
| `comparables` | secondary | 80 | 20 | 0 | 0 | 80.0% | 80.0% |

## Persistent Missing Rate by Property Class

| Field | commercial | exempt | industrial | multifamily | residential |
|---|---:|---:|---:|---:|---:|
| `pin_resolved` | 0% of 48 | 6% of 18 | 0% of 2 | 0% of 11 | 10% of 21 |
| `pin_authoritative` | 0% of 48 | 6% of 18 | 0% of 2 | 0% of 11 | 10% of 21 |
| `pin_matches_truth` | 0% of 48 | 6% of 18 | 0% of 2 | 0% of 11 | 10% of 21 |
| `property_record` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `land_sqft` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `bldg_sqft` | 2% of 48 | 61% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `bldg_class` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `year_built` | 2% of 48 | 61% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `assessed_value` | 0% of 48 | — | 0% of 2 | 0% of 11 | 0% of 21 |
| `assessment_history` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `tax_bill` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `tax_rate` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `zoning_class` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `zoning_far` | 2% of 41 | 0% of 14 | 0% of 2 | 0% of 10 | 0% of 21 |
| `stories` | 42% of 48 | 50% of 18 | 0% of 2 | 18% of 11 | 0% of 21 |
| `units` | 98% of 48 | 100% of 18 | 100% of 2 | 9% of 11 | 5% of 21 |
| `sales_history` | 17% of 48 | 67% of 18 | 0% of 2 | 0% of 11 | 19% of 21 |
| `comparables` | 31% of 48 | 6% of 18 | 100% of 2 | 0% of 11 | 10% of 21 |

## Addresses With Persistent Critical Gaps

| Address | Class | Group | Missing critical fields |
|---|---|---|---|
| 12200 S Hoxie Ave | 580 | commercial | `bldg_sqft`, `year_built`, `zoning_far` |
| 7101 S South Chicago Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 7030 N Sacramento Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 7115 S South Chicago Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 11901 S Loomis St | EX | exempt | `bldg_sqft`, `year_built` |
| 1555 N State Pkwy | EX | exempt | `bldg_sqft`, `year_built` |
| 1401 W 19Th St | EX | exempt | `bldg_sqft`, `year_built` |
| 11901 S Ashland Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 7117 S South Chicago Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 1550 N Astor St | EX | exempt | `bldg_sqft`, `year_built` |
| 1441 W 119Th St | EX | exempt | `bldg_sqft`, `year_built` |
| 3101 W Touhy Ave | EX | exempt | `bldg_sqft` |
| 1460 W 112Th St | EX | exempt | `year_built` |
