# Lot Information Coverage Report

_2026-07-03 02:13Z · 100 panel addresses · 0 fetch errors_

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
| `bldg_sqft` | critical | 85 | 15 | 0 | 0 | 85.0% | 85.0% |
| `bldg_class` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `year_built` | critical | 47 | 53 | 0 | 0 | 47.0% | 47.0% |
| `assessed_value` | critical | 82 | 0 | 0 | 18 | 100.0% | 100.0% |
| `assessment_history` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `tax_bill` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `tax_rate` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `zoning_class` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `zoning_far` | critical | 87 | 1 | 0 | 12 | 98.9% | 98.9% |
| `stories` | secondary | 46 | 54 | 0 | 0 | 46.0% | 46.0% |
| `units` | secondary | 20 | 80 | 0 | 0 | 20.0% | 20.0% |
| `sales_history` | secondary | 76 | 24 | 0 | 0 | 76.0% | 76.0% |
| `comparables` | secondary | 82 | 18 | 0 | 0 | 82.0% | 82.0% |

## Persistent Missing Rate by Property Class

| Field | commercial | exempt | industrial | multifamily | residential |
|---|---:|---:|---:|---:|---:|
| `pin_resolved` | 0% of 48 | 6% of 18 | 0% of 2 | 0% of 11 | 10% of 21 |
| `pin_authoritative` | 0% of 48 | 6% of 18 | 0% of 2 | 0% of 11 | 10% of 21 |
| `pin_matches_truth` | 0% of 48 | 6% of 18 | 0% of 2 | 0% of 11 | 10% of 21 |
| `property_record` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `land_sqft` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `bldg_sqft` | 2% of 48 | 72% of 18 | 0% of 2 | 0% of 11 | 5% of 21 |
| `bldg_class` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `year_built` | 58% of 48 | 72% of 18 | 100% of 2 | 91% of 11 | 0% of 21 |
| `assessed_value` | 0% of 48 | — | 0% of 2 | 0% of 11 | 0% of 21 |
| `assessment_history` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `tax_bill` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `tax_rate` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `zoning_class` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `zoning_far` | 2% of 41 | 0% of 14 | 0% of 2 | 0% of 10 | 0% of 21 |
| `stories` | 62% of 48 | 61% of 18 | 100% of 2 | 91% of 11 | 5% of 21 |
| `units` | 100% of 48 | 100% of 18 | 100% of 2 | 100% of 11 | 5% of 21 |
| `sales_history` | 17% of 48 | 67% of 18 | 0% of 2 | 0% of 11 | 19% of 21 |
| `comparables` | 23% of 48 | 22% of 18 | 100% of 2 | 9% of 11 | 0% of 21 |

## Addresses With Persistent Critical Gaps

| Address | Class | Group | Missing critical fields |
|---|---|---|---|
| 12200 S Hoxie Ave | 580 | commercial | `bldg_sqft`, `year_built`, `zoning_far` |
| 3101 W Touhy Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 929 E 103Rd St | EX | exempt | `bldg_sqft`, `year_built` |
| 7101 S South Chicago Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 7030 N Sacramento Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 7115 S South Chicago Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 11901 S Loomis St | EX | exempt | `bldg_sqft`, `year_built` |
| 1555 N State Pkwy | EX | exempt | `bldg_sqft`, `year_built` |
| 1401 W 19Th St | EX | exempt | `bldg_sqft`, `year_built` |
| 11901 S Ashland Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 7117 S South Chicago Ave | EX | exempt | `bldg_sqft`, `year_built` |
| 1460 W 112Th St | EX | exempt | `bldg_sqft`, `year_built` |
| 1550 N Astor St | EX | exempt | `bldg_sqft`, `year_built` |
| 1441 W 119Th St | EX | exempt | `bldg_sqft`, `year_built` |
| 5 S Austin Blvd | 318 | multifamily | `year_built` |
| 623 W Madison St | 597 | commercial | `year_built` |
| 1031 E 103Rd St | 663 | industrial | `year_built` |
| 625 W Madison St | 597 | commercial | `year_built` |
| 2250 E 130Th St | 587 | commercial | `year_built` |
| 1551 W Garfield Blvd | 523 | commercial | `year_built` |
| 4539 W 31St St | 593 | commercial | `year_built` |
| 3100 S Kilbourn Ave | 593 | commercial | `year_built` |
| 933 E 95Th St | 593 | commercial | `year_built` |
| 757 W 79Th St | 318 | multifamily | `year_built` |
| 2329 W Madison St | 517 | commercial | `year_built` |
| 7155 W Belmont Ave | 517 | commercial | `year_built` |
| 3250 S Kilbourn Ave | 593 | commercial | `year_built` |
| 1555 W 47Th St | 592 | commercial | `year_built` |
| 9611 S Cottage Grove Ave | 593 | commercial | `year_built` |
| 1514 W 33Rd St | 531 | commercial | `year_built` |
| 7 S Austin Blvd | 318 | multifamily | `year_built` |
| 1 S Halsted St | 529 | commercial | `year_built` |
| 3425 S Kedzie Ave | 593 | commercial | `year_built` |
| 7141 N Kedzie Ave | 299 | residential | `bldg_sqft` |
| 3949 N Clarendon Ave | 318 | multifamily | `year_built` |
| 2327 W Madison St | 517 | commercial | `year_built` |
| 2243 S Pulaski Rd | 530 | commercial | `year_built` |
| 3947 N Clarendon Ave | 318 | multifamily | `year_built` |
| 4757 N Ashland Ave | 318 | multifamily | `year_built` |
| 3951 N Clarendon Ave | 318 | multifamily | `year_built` |
| 4700 N Marine Dr | 591 | commercial | `year_built` |
| 4761 N Western Ave | 592 | commercial | `year_built` |
| 2331 W Madison St | 517 | commercial | `year_built` |
| 1531 W Lawrence Ave | 517 | commercial | `year_built` |
| 1500 W 33Rd St | 580 | commercial | `year_built` |
| 9633 S Cottage Grove Ave | 397 | multifamily | `year_built` |
| 2239 S Pulaski Rd | 530 | commercial | `year_built` |
| 2337 W Irving Park Rd | 517 | commercial | `year_built` |
| 2240 E 130Th St | 593 | commercial | `year_built` |
| 1440 W 33Rd St | 580 | commercial | `year_built` |
| 955 E 103Rd St | 663 | industrial | `year_built` |
| 1535 W Lawrence Ave | 318 | multifamily | `year_built` |
| 9 S Austin Blvd | 318 | multifamily | `year_built` |
| 7153 W Belmont Ave | 517 | commercial | `year_built` |
