# Parcel kit report

Key `2026-10-01.1` · run 2026-10-02 · code `1f97199` · source: live run against http://localhost:8001

> Answer key for the 7-parcel Chicago kit, built from primary sources (City zoning layer, Zoning MapServer, Municipal Code text current through the Council Journal of 2026-03-18, ordinance PDFs, Cook County Assessor). NOT yet reviewed by a Chicago architect or zoning attorney: P2, P3 and P6 are the most interpretive. Overlay truth comes from the same City service UrbanLayer queries, so overlay scores are not independent.

## Summary

| Surface | Coverage | Accuracy | CW | Critical misses | A correct | Screening-grade |
|---|:-:|:-:|:-:|---|:-:|:-:|
| profile | 35/37 = 95% | 68/70 = 97% | 0 | none | 7/7 | yes |

All cells are automatic (no hand-scores file).

## profile: field scores

| Parcel | A | B | C | D | E | F |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| P1 | 2 | 2 | 2 | 2 |  | 2 |
| P2 | 2 | 2 | 2 | 2 |  | 2 |
| P3 | 2 | 1 | 2 | 2 | 2 | 2 |
| P4 | 2 | 2 | NP | 2 |  | NP |
| P5 | 2 | 2 | 2 | 2 | 1 | 2 |
| P6 | 2 | 2 | 2 | 2 |  | 2 |
| P7 | 2 | 2 | 2 | 2 |  | 2 |

`*` = hand score; `CW` = confident-wrong; `NP` = no claim.

## Provenance (Profile: district, standards and expected overlays with a dated source)

**46/46** stated facts carry a dated source; **25/46** carry a date the source itself gives (an edit/effective date or the code's current-through date). The rest carry only the date we queried them.

| Parcel | Facts | With any date | Source-side date | Missing |
|---|--:|--:|--:|---|
| P1 | 5 | 5 | 4 |  |
| P2 | 6 | 6 | 4 |  |
| P3 | 7 | 7 | 4 |  |
| P4 | 4 | 4 | 1 |  |
| P5 | 10 | 10 | 4 |  |
| P6 | 8 | 8 | 4 |  |
| P7 | 6 | 6 | 4 |  |

## Resolution record (Profile: how the address became a parcel)

**7/7** parcels' records match what the county's address records say (expectations observed from those datasets, not independent truth).

| Parcel | Method | Parcels at the address | Problems |
|---|---|--:|---|
| P1 | address_points | 1 |  |
| P2 | assessor_addresses | 1 |  |
| P3 | address_points | 2 |  |
| P4 | address_points | 51 |  |
| P5 | address_points | 3 |  |
| P6 | assessor_addresses | 1 |  |
| P7 | address_points | 1 |  |

## Where the page says it stops (Profile: notes that apply to each parcel)

**7/7** parcels carry exactly the notes that apply to them.

| Parcel | Notes | Problems |
|---|---|---|
| P1 | aldermanic, map_lag, code_vintage, official_letter |  |
| P2 | aldermanic, map_lag, code_vintage, official_letter |  |
| P3 | aldermanic, map_lag, code_vintage, official_letter |  |
| P4 | planned_development, aldermanic, map_lag, code_vintage, official_letter |  |
| P5 | landmark, aldermanic, map_lag, code_vintage, official_letter |  |
| P6 | adu_limits, aldermanic, map_lag, code_vintage, official_letter |  |
| P7 | recently_rezoned, aldermanic, map_lag, code_vintage, official_letter |  |

## Per-cell detail

### profile

- **P1.A** 2 (auto 2, auto) — district RS2
- **P1.B** 2 (auto 2, auto) — groups 1/1
- **P1.C** 2 (auto 2, auto) — far ok; height_ft ok; mla ok
- **P1.D** 2 (auto 2, auto) — found 1/1
- **P1.F** 2 (auto 2, auto) — groups 1/1
- **P2.A** 2 (auto 2, auto) — district RM4.5
- **P2.B** 2 (auto 2, auto) — groups 1/1
- **P2.C** 2 (auto 2, auto) — far ok; height_ft ok; mla ok
- **P2.D** 2 (auto 2, auto) — found 2/2
- **P2.F** 2 (auto 2, auto) — groups 1/1
- **P3.A** 2 (auto 2, auto) — district B12
- **P3.B** 1 (auto 1, auto) — groups 1/2
- **P3.C** 2 (auto 2, auto) — far ok; height_ft ok; mla ok
- **P3.D** 2 (auto 2, auto) — found 3/3
- **P3.E** 2 (auto 2, auto) — groups 2/2
- **P3.F** 2 (auto 2, auto) — groups 2/2
- **P4.A** 2 (auto 2, auto) — district PD835
- **P4.B** 2 (auto 2, auto) — groups 1/1
- **P4.C** NP (auto NP, auto) — far absent; height_ft absent
- **P4.D** 2 (auto 2, auto) — found 3/3
- **P4.F** NP (auto NP, auto) — groups 0/2
- **P5.A** 2 (auto 2, auto) — district B32
- **P5.B** 2 (auto 2, auto) — groups 1/1
- **P5.C** 2 (auto 2, auto) — far ok; height_ft ok; mla ok
- **P5.D** 2 (auto 2, auto) — found 6/6
- **P5.E** 1 (auto 1, auto) — groups 1/2
- **P5.F** 2 (auto 2, auto) — groups 2/2
- **P6.A** 2 (auto 2, auto) — district RS3
- **P6.B** 2 (auto 2, auto) — groups 1/1
- **P6.C** 2 (auto 2, auto) — far ok; height_ft ok; mla ok
- **P6.D** 2 (auto 2, auto) — found 4/4
- **P6.F** 2 (auto 2, auto) — groups 2/2
- **P7.A** 2 (auto 2, auto) — district RT4
- **P7.B** 2 (auto 2, auto) — groups 1/1
- **P7.C** 2 (auto 2, auto) — far ok; height_ft ok; mla ok
- **P7.D** 2 (auto 2, auto) — found 2/2
- **P7.F** 2 (auto 2, auto) — groups 1/1

