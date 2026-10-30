# Parcel kit report

Key `2026-10-01.1` · run 2026-10-02 · code `dd5360a` · source: replay of eval/results/2026-10-02-f4/parcel_kit_raw

> Answer key for the 7-parcel Chicago kit, built from primary sources (City zoning layer, Zoning MapServer, Municipal Code text current through the Council Journal of 2026-03-18, ordinance PDFs, Cook County Assessor). NOT yet reviewed by a Chicago architect or zoning attorney: P2, P3 and P6 are the most interpretive. Overlay truth comes from the same City service UrbanLayer queries, so overlay scores are not independent.

## Summary

| Surface | Coverage | Accuracy | CW | Critical misses | A correct | Screening-grade |
|---|:-:|:-:|:-:|---|:-:|:-:|
| chat | 33/37 = 89% | 54/66 = 82% | 1 | none | 7/7 | yes |

All cells are automatic (no hand-scores file).

## chat: field scores

| Parcel | A | B | C | D | E | F |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| P1 | 2 | 2 | NP | 2 |  | 2 |
| P2 | 2 | 2 | 0 CW | 2 |  | 1 |
| P3 | 2 | 1 | 0 | 2 | 1 | 2 |
| P4 | 2 | 2 | NP | 2 |  | NP |
| P5 | 2 | 2 | NP | 2 | 2 | 2 |
| P6 | 2 | 2 | 1 | 2 |  | 1 |
| P7 | 2 | 2 | 0 | 2 |  | 1 |

`*` = hand score; `CW` = confident-wrong; `NP` = no claim.

## Chat answer completeness

| Parcel | Chars | Reaches item 6 | Ends cleanly | Cut-off notice | Silently cut off | Field names leaked |
|---|--:|:-:|:-:|:-:|:-:|---|
| P1 | 6470 | yes | yes |  |  | zone_definition |
| P2 | 6224 | yes | yes |  |  | zone_definition |
| P3 | 7438 | yes | NO | yes |  |  |
| P4 | 6500 | yes | yes |  |  |  |
| P5 | 7604 | yes | NO | yes |  |  |
| P6 | 7096 | yes | NO | yes |  |  |
| P7 | 6374 | yes | yes |  |  |  |

## Per-cell detail

### chat

- **P1.A** 2 (auto 2, auto) — district RS2
- **P1.B** 2 (auto 2, auto) — groups 2/2
- **P1.C** NP (auto NP, auto) — far absent; height_ft absent; mla absent
- **P1.D** 2 (auto 2, auto) — found 1/1
- **P1.F** 2 (auto 2, auto) — groups 2/2
- **P2.A** 2 (auto 2, auto) — district RM4.5
- **P2.B** 2 (auto 2, auto) — groups 2/2
- **P2.C** 0 CW (auto 0 CW, auto) — far wrong (2.2 vs 1.7); height_ft ok; mla absent
- **P2.D** 2 (auto 2, auto) — found 2/2
- **P2.F** 1 (auto 1, auto) — groups 0/2
- **P3.A** 2 (auto 2, auto) — district B12
- **P3.B** 1 (auto 1, auto) — groups 1/2
- **P3.C** 0 (auto 0, auto) — far ok; height_ft wrong (hedged) (38 vs 45,47,50); mla absent
- **P3.D** 2 (auto 2, auto) — found 3/3
- **P3.E** 1 (auto 1, auto) — groups 1/2
- **P3.F** 2 (auto 2, auto) — groups 2/2
- **P4.A** 2 (auto 2, auto) — district PD835
- **P4.B** 2 (auto 2, auto) — groups 2/2
- **P4.C** NP (auto NP, auto) — far absent; height_ft absent
- **P4.D** 2 (auto 2, auto) — found 3/3
- **P4.F** NP (auto NP, auto) — groups 0/2
- **P5.A** 2 (auto 2, auto) — district B32
- **P5.B** 2 (auto 2, auto) — groups 2/2
- **P5.C** NP (auto NP, auto) — far absent; height_ft absent; mla absent
- **P5.D** 2 (auto 2, auto) — found 6/6
- **P5.E** 2 (auto 2, auto) — groups 2/2
- **P5.F** 2 (auto 2, auto) — groups 2/2
- **P6.A** 2 (auto 2, auto) — district RS3
- **P6.B** 2 (auto 2, auto) — groups 2/2
- **P6.C** 1 (auto 1, auto) — far absent; height_ft absent; mla ok
- **P6.D** 2 (auto 2, auto) — found 4/4
- **P6.F** 1 (auto 1, auto) — groups 1/2
- **P7.A** 2 (auto 2, auto) — district RT4
- **P7.B** 2 (auto 2, auto) — groups 2/2
- **P7.C** 0 (auto 0, auto) — far absent; height_ft absent; mla wrong (hedged) (1500 vs 1000)
- **P7.D** 2 (auto 2, auto) — found 2/2
- **P7.F** 1 (auto 1, auto) — groups 1/2

