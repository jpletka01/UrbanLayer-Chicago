# Lot Information Coverage Report

_2026-07-02 20:44Z · 100 panel addresses · 0 fetch errors_

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
| `land_sqft` | critical | 21 | 79 | 0 | 0 | 21.0% | 21.0% |
| `bldg_sqft` | critical | 20 | 80 | 0 | 0 | 20.0% | 20.0% |
| `bldg_class` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `year_built` | critical | 20 | 80 | 0 | 0 | 20.0% | 20.0% |
| `assessed_value` | critical | 82 | 0 | 0 | 18 | 100.0% | 100.0% |
| `assessment_history` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `tax_bill` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `tax_rate` | critical | 100 | 0 | 0 | 0 | 100.0% | 100.0% |
| `zoning_class` | critical | 96 | 0 | 4 | 0 | 96.0% | 100.0% |
| `zoning_far` | critical | 83 | 13 | 4 | 0 | 83.0% | 87.0% |
| `stories` | secondary | 1 | 99 | 0 | 0 | 1.0% | 1.0% |
| `units` | secondary | 0 | 100 | 0 | 0 | 0.0% | 0.0% |
| `sales_history` | secondary | 76 | 24 | 0 | 0 | 76.0% | 76.0% |
| `comparables` | secondary | 86 | 14 | 0 | 0 | 86.0% | 86.0% |

## Persistent Missing Rate by Property Class

| Field | commercial | exempt | industrial | multifamily | residential |
|---|---:|---:|---:|---:|---:|
| `pin_resolved` | 0% of 48 | 6% of 18 | 0% of 2 | 0% of 11 | 10% of 21 |
| `pin_authoritative` | 0% of 48 | 6% of 18 | 0% of 2 | 0% of 11 | 10% of 21 |
| `pin_matches_truth` | 0% of 48 | 6% of 18 | 0% of 2 | 0% of 11 | 10% of 21 |
| `property_record` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `land_sqft` | 100% of 48 | 100% of 18 | 100% of 2 | 100% of 11 | 0% of 21 |
| `bldg_sqft` | 100% of 48 | 100% of 18 | 100% of 2 | 100% of 11 | 5% of 21 |
| `bldg_class` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `year_built` | 100% of 48 | 100% of 18 | 100% of 2 | 100% of 11 | 5% of 21 |
| `assessed_value` | 0% of 48 | — | 0% of 2 | 0% of 11 | 0% of 21 |
| `assessment_history` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `tax_bill` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `tax_rate` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `zoning_class` | 0% of 48 | 0% of 18 | 0% of 2 | 0% of 11 | 0% of 21 |
| `zoning_far` | 17% of 48 | 22% of 18 | 0% of 2 | 9% of 11 | 0% of 21 |
| `stories` | 100% of 48 | 100% of 18 | 100% of 2 | 100% of 11 | 95% of 21 |
| `units` | 100% of 48 | 100% of 18 | 100% of 2 | 100% of 11 | 100% of 21 |
| `sales_history` | 17% of 48 | 67% of 18 | 0% of 2 | 0% of 11 | 19% of 21 |
| `comparables` | 15% of 48 | 22% of 18 | 100% of 2 | 9% of 11 | 0% of 21 |

## Addresses With Persistent Critical Gaps

| Address | Class | Group | Missing critical fields |
|---|---|---|---|
| 623 W Madison St | 597 | commercial | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 3101 W Touhy Ave | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 625 W Madison St | 597 | commercial | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 2250 E 130Th St | 587 | commercial | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 7101 S South Chicago Ave | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 7115 S South Chicago Ave | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 1514 W 33Rd St | 531 | commercial | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 1 S Halsted St | 529 | commercial | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 12200 S Hoxie Ave | 580 | commercial | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 4700 N Marine Dr | 591 | commercial | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 9633 S Cottage Grove Ave | 397 | multifamily | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 2240 E 130Th St | 593 | commercial | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 7117 S South Chicago Ave | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built`, `zoning_far` |
| 741 W 79Th St | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 3341 S Kedzie Ave | 593 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 5503 S Halsted St | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 5 S Austin Blvd | 318 | multifamily | `land_sqft`, `bldg_sqft`, `year_built` |
| 3157 W Devon Ave | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 7167 W Irving Park Rd | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 1031 E 103Rd St | 663 | industrial | `land_sqft`, `bldg_sqft`, `year_built` |
| 7149 W Belmont Ave | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 1551 W Garfield Blvd | 523 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 929 E 103Rd St | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 4539 W 31St St | 593 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 7030 N Sacramento Ave | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 3100 S Kilbourn Ave | 593 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 933 E 95Th St | 593 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 757 W 79Th St | 318 | multifamily | `land_sqft`, `bldg_sqft`, `year_built` |
| 5521 S Ashland Ave | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 2329 W Madison St | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 7155 W Belmont Ave | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 3250 S Kilbourn Ave | 593 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 5501 S Halsted St | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 1555 W 47Th St | 592 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 11901 S Loomis St | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 3151 W Devon Ave | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 9611 S Cottage Grove Ave | 593 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 4713 S Ashland Ave | 592 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 1555 N State Pkwy | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 1401 W 19Th St | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 7 S Austin Blvd | 318 | multifamily | `land_sqft`, `bldg_sqft`, `year_built` |
| 1427 W 111Th St | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 3149 W Devon Ave | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 1431 W 111Th St | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 3425 S Kedzie Ave | 593 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 11901 S Ashland Ave | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 3949 N Clarendon Ave | 318 | multifamily | `land_sqft`, `bldg_sqft`, `year_built` |
| 2327 W Madison St | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 2243 S Pulaski Rd | 530 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 3947 N Clarendon Ave | 318 | multifamily | `land_sqft`, `bldg_sqft`, `year_built` |
| 755 W Lawrence Ave | 523 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 3943 W Roosevelt Rd | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 4757 N Ashland Ave | 318 | multifamily | `land_sqft`, `bldg_sqft`, `year_built` |
| 3345 S Kedzie Ave | 593 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 3951 N Clarendon Ave | 318 | multifamily | `land_sqft`, `bldg_sqft`, `year_built` |
| 4715 S Ashland Ave | 592 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 3955 N Western Ave | 523 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 4761 N Western Ave | 592 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 3953 W Roosevelt Rd | 590 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 2331 W Madison St | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 1531 W Lawrence Ave | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 1500 W 33Rd St | 580 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 5505 S Halsted St | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 2239 S Pulaski Rd | 530 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 2337 W Irving Park Rd | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 2343 W Irving Park Rd | 318 | multifamily | `land_sqft`, `bldg_sqft`, `year_built` |
| 7171 W Irving Park Rd | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 3955 W Roosevelt Rd | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 4759 N Western Ave | 592 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 1533 W Garfield Blvd | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 1440 W 33Rd St | 580 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 955 E 103Rd St | 663 | industrial | `land_sqft`, `bldg_sqft`, `year_built` |
| 1535 W Lawrence Ave | 318 | multifamily | `land_sqft`, `bldg_sqft`, `year_built` |
| 9 S Austin Blvd | 318 | multifamily | `land_sqft`, `bldg_sqft`, `year_built` |
| 1460 W 112Th St | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 4753 N Western Ave | 592 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 7153 W Belmont Ave | 517 | commercial | `land_sqft`, `bldg_sqft`, `year_built` |
| 1550 N Astor St | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 1441 W 119Th St | EX | exempt | `land_sqft`, `bldg_sqft`, `year_built` |
| 7141 N Kedzie Ave | 299 | residential | `bldg_sqft`, `year_built` |
