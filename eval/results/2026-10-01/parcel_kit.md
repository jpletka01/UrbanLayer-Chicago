# Parcel kit report

Key `2026-10-01.1` · run 2026-10-01 · code `dd481c5` · source: replay of eval/results/2026-10-01/parcel_kit_raw

> Answer key for the 7-parcel Chicago kit, built from primary sources (City zoning layer, Zoning MapServer, Municipal Code text current through the Council Journal of 2026-03-18, ordinance PDFs, Cook County Assessor). NOT yet reviewed by a Chicago architect or zoning attorney: P2, P3 and P6 are the most interpretive. Overlay truth comes from the same City service UrbanLayer queries, so overlay scores are not independent.

## Summary

| Surface | Coverage | Accuracy | CW | Critical misses | A correct | Screening-grade |
|---|:-:|:-:|:-:|---|:-:|:-:|
| profile | 32/37 = 86% | 51/64 = 80% | 2 | none | 7/7 | no |
| chat | 30/37 = 81% | 41/60 = 68% | 7 | P2, P5 | 5/7 | no |

All cells are automatic (no hand-scores file).

## profile: field scores

| Parcel | A | B | C | D | E | F |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| P1 | 2 | 2 | 2 | 2 |  | NP |
| P2 | 2 | 2 | 1 | 2 |  | NP |
| P3 | 2 | 1 | 1 | 2 | 1 CW | 1 CW |
| P4 | 2 | 2 | NP | 2 |  | NP |
| P5 | 2 | 2 | 1 | 2 | 1 | 1 |
| P6 | 2 | 0 | 1 | 2 |  | 1 |
| P7 | 2 | 2 | 1 | 2 |  | NP |

`*` = hand score; `CW` = confident-wrong; `NP` = no claim.

## chat: field scores

| Parcel | A | B | C | D | E | F |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| P1 | 2 | 2 | NP | 2 |  | 2 |
| P2 | 0 CW | 0 CW | 0 CW | 2 |  | 1 CW |
| P3 | 2 | 1 | NP | 1 CW | 1 | NP |
| P4 | 2 | 2 | NP | 2 |  | NP |
| P5 | 0 CW | 2 | 0 | 1 CW | 2 | NP |
| P6 | 2 | 1 | 1 | 2 |  | 1 |
| P7 | 2 | 2 | NP | 2 |  | 1 |

`*` = hand score; `CW` = confident-wrong; `NP` = no claim.

## Parcel resolution (chat vs Profile)

| Parcel | Profile PIN | PIN chat cited | Match | Point gap (ft) | Same community area |
|---|---|---|:-:|:-:|:-:|
| P1 | 13012120030000 | 13012120090000 | NO | 211 | NO |
| P2 | 16012280180000 | 16012280240000 | NO | 176 | yes |
| P3 | 14171060250000 | 14171060250000 | yes | 64 | yes |
| P4 | 17101350390000 | 17101350382166 | NO | 107 | yes |
| P5 | 14313320180000 | 14314240440000 | NO | 139 | NO |
| P6 | 13233160400000 | 13233160400000 | yes | 79 | NO |
| P7 | 14291230290000 | 14291230300000 | NO | 64 | yes |

## Chat answer completeness

| Parcel | Chars | Reaches item 6 | Ends cleanly |
|---|--:|:-:|:-:|
| P1 | 7095 | yes | NO |
| P2 | 7483 | yes | NO |
| P3 | 7343 | yes | NO |
| P4 | 7339 | yes | NO |
| P5 | 7987 | yes | NO |
| P6 | 7567 | yes | NO |
| P7 | 7267 | yes | yes |

## Per-cell detail

### profile

- **P1.A** 2 (auto 2, auto) — district RS2
- **P1.B** 2 (auto 2, auto) — groups 1/1
- **P1.C** 2 (auto 2, auto) — far ok; height_ft ok; mla ok
- **P1.D** 2 (auto 2, auto) — found 1/1
- **P1.F** NP (auto NP, auto) — groups 0/1
- **P2.A** 2 (auto 2, auto) — district RM4.5
- **P2.B** 2 (auto 2, auto) — groups 1/1
- **P2.C** 1 (auto 1, auto) — far ok; height_ft ok; mla absent
- **P2.D** 2 (auto 2, auto) — found 2/2
- **P2.F** NP (auto NP, auto) — groups 0/1
- **P3.A** 2 (auto 2, auto) — district B12
- **P3.B** 1 (auto 1, auto) — groups 1/2
- **P3.C** 1 (auto 1, auto) — far ok; height_ft ok; mla absent
- **P3.D** 2 (auto 2, auto) — found 3/3
- **P3.E** 1 CW (auto 1 CW, auto) — groups 1/2
- **P3.F** 1 CW (auto 1 CW, auto) — groups 1/2
- **P4.A** 2 (auto 2, auto) — district PD835
- **P4.B** 2 (auto 2, auto) — groups 1/1
- **P4.C** NP (auto NP, auto) — far absent; height_ft absent
- **P4.D** 2 (auto 2, auto) — found 3/3
- **P4.F** NP (auto NP, auto) — groups 0/2
- **P5.A** 2 (auto 2, auto) — district B32
- **P5.B** 2 (auto 2, auto) — groups 1/1
- **P5.C** 1 (auto 1, auto) — far ok; height_ft ok; mla absent
- **P5.D** 2 (auto 2, auto) — found 6/6
- **P5.E** 1 (auto 1, auto) — groups 1/2
- **P5.F** 1 (auto 1, auto) — groups 1/2
- **P6.A** 2 (auto 2, auto) — district RS3
- **P6.B** 0 (auto 0, auto) — groups 0/1
- **P6.C** 1 (auto 1, auto) — far ok; height_ft ok; mla absent
- **P6.D** 2 (auto 2, auto) — found 4/4
- **P6.F** 1 (auto 1, auto) — groups 1/2
- **P7.A** 2 (auto 2, auto) — district RT4
- **P7.B** 2 (auto 2, auto) — groups 1/1
- **P7.C** 1 (auto 1, auto) — far ok; height_ft ok; mla absent
- **P7.D** 2 (auto 2, auto) — found 2/2
- **P7.F** NP (auto NP, auto) — groups 0/1

### chat

- **P1.A** 2 (auto 2, auto) — district RS2
- **P1.B** 2 (auto 2, auto) — groups 2/2
- **P1.C** NP (auto NP, auto) — far absent; height_ft absent; mla absent
- **P1.D** 2 (auto 2, auto) — found 1/1
- **P1.F** 2 (auto 2, auto) — groups 2/2
- **P2.A** 0 CW (auto 0 CW, auto) — district RS3, key RM4.5
- **P2.B** 0 CW (auto 0 CW, auto) — matched a wrong-claim pattern
- **P2.C** 0 CW (auto 0 CW, auto) — far absent; height_ft absent; mla wrong (1500 vs 700)
- **P2.D** 2 (auto 2, auto) — found 2/2
- **P2.F** 1 CW (auto 1 CW, auto) — groups 0/2
- **P3.A** 2 (auto 2, auto) — district B12
- **P3.B** 1 (auto 1, auto) — groups 1/2
- **P3.C** NP (auto NP, auto) — far absent; height_ft absent; mla absent
- **P3.D** 1 CW (auto 1 CW, auto) — found 2/3; missing ssa; denied ssa
- **P3.E** 1 (auto 1, auto) — groups 1/2
- **P3.F** NP (auto NP, auto) — groups 0/2
- **P4.A** 2 (auto 2, auto) — district PD835
- **P4.B** 2 (auto 2, auto) — groups 2/2
- **P4.C** NP (auto NP, auto) — far absent; height_ft absent
- **P4.D** 2 (auto 2, auto) — found 3/3
- **P4.F** NP (auto NP, auto) — groups 0/2
- **P5.A** 0 CW (auto 0 CW, auto) — district C13, key B32
- **P5.B** 2 (auto 2, auto) — groups 2/2
- **P5.C** 0 (auto 0, auto) — far wrong (hedged) (3 vs 2.2); height_ft absent; mla absent
- **P5.D** 1 CW (auto 1 CW, auto) — found 5/6; missing landmark_building; false pedestrian_street
- **P5.E** 2 (auto 2, auto) — groups 2/2
- **P5.F** NP (auto NP, auto) — groups 0/2
- **P6.A** 2 (auto 2, auto) — district RS3
- **P6.B** 1 (auto 1, auto) — groups 1/2
- **P6.C** 1 (auto 1, auto) — far absent; height_ft absent; mla ok
- **P6.D** 2 (auto 2, auto) — found 4/4
- **P6.F** 1 (auto 1, auto) — groups 1/2
- **P7.A** 2 (auto 2, auto) — district RT4
- **P7.B** 2 (auto 2, auto) — groups 2/2
- **P7.C** NP (auto NP, auto) — far absent; height_ft absent; mla absent
- **P7.D** 2 (auto 2, auto) — found 2/2
- **P7.F** 1 (auto 1, auto) — groups 1/2

