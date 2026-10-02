# Parcel kit report

Key `2026-10-01.1` · run 2026-10-02 · code `33ef302` · source: replay of eval/results/2026-10-02-f2/parcel_kit_raw

> Answer key for the 7-parcel Chicago kit, built from primary sources (City zoning layer, Zoning MapServer, Municipal Code text current through the Council Journal of 2026-03-18, ordinance PDFs, Cook County Assessor). NOT yet reviewed by a Chicago architect or zoning attorney: P2, P3 and P6 are the most interpretive. Overlay truth comes from the same City service UrbanLayer queries, so overlay scores are not independent.

## Summary

| Surface | Coverage | Accuracy | CW | Critical misses | A correct | Screening-grade |
|---|:-:|:-:|:-:|---|:-:|:-:|
| profile | 32/37 = 86% | 53/64 = 83% | 0 | none | 7/7 | yes |
| chat | 30/37 = 81% | 52/60 = 87% | 1 | none | 7/7 | yes |

All cells are automatic (no hand-scores file).

## profile: field scores

| Parcel | A | B | C | D | E | F |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| P1 | 2 | 2 | 2 | 2 |  | NP |
| P2 | 2 | 2 | 1 | 2 |  | NP |
| P3 | 2 | 1 | 1 | 2 | 2 | 2 |
| P4 | 2 | 2 | NP | 2 |  | NP |
| P5 | 2 | 2 | 1 | 2 | 1 | 1 |
| P6 | 2 | 0 | 1 | 2 |  | 1 |
| P7 | 2 | 2 | 1 | 2 |  | NP |

`*` = hand score; `CW` = confident-wrong; `NP` = no claim.

## chat: field scores

| Parcel | A | B | C | D | E | F |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| P1 | 2 | 2 | NP | 2 |  | 2 |
| P2 | 2 | 2 | 0 CW | 2 |  | NP |
| P3 | 2 | 1 | NP | 2 | 1 | 2 |
| P4 | 2 | 2 | NP | 2 |  | NP |
| P5 | 2 | 2 | NP | 2 | 2 | 2 |
| P6 | 2 | 1 | 1 | 2 |  | 1 |
| P7 | 2 | 2 | NP | 2 |  | 1 |

`*` = hand score; `CW` = confident-wrong; `NP` = no claim.

## Parcel resolution (chat vs Profile)

| Parcel | Profile PIN | PIN chat cited | Match | Point gap (ft) | Same community area |
|---|---|---|:-:|:-:|:-:|
| P1 | 13012120030000 | 13012120030000 | yes | 0 | yes |
| P2 | 16012280180000 | 16012280180000 | yes | 0 | yes |
| P3 | 14171060250000 | 14171060250000 | yes | 0 | yes |
| P4 | 17101350390000 | 17101350381067 | NO | 0 | yes |
| P5 | 14313320180000 | 14313320180000 | yes | 0 | yes |
| P6 | 13233160400000 | 13233160400000 | yes | 0 | yes |
| P7 | 14291230290000 | 14291230290000 | yes | 0 | yes |

## Chat answer completeness

| Parcel | Chars | Reaches item 6 | Ends cleanly | Cut-off notice | Silently cut off |
|---|--:|:-:|:-:|:-:|:-:|
| P1 | 7200 | yes | NO |  | YES |
| P2 | 7201 | yes | NO |  | YES |
| P3 | 7323 | yes | NO |  | YES |
| P4 | 7521 | yes | yes |  |  |
| P5 | 7993 | yes | NO |  | YES |
| P6 | 7543 | yes | yes |  |  |
| P7 | 7362 | yes | NO |  | YES |

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
- **P3.E** 2 (auto 2, auto) — groups 2/2
- **P3.F** 2 (auto 2, auto) — groups 2/2
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
- **P2.A** 2 (auto 2, auto) — district RM4.5
- **P2.B** 2 (auto 2, auto) — groups 2/2
- **P2.C** 0 CW (auto 0 CW, auto) — far wrong (2.2 vs 1.7); height_ft wrong (38 vs 45,47); mla wrong (400 vs 700)
- **P2.D** 2 (auto 2, auto) — found 2/2
- **P2.F** NP (auto NP, auto) — groups 0/2
- **P3.A** 2 (auto 2, auto) — district B12
- **P3.B** 1 (auto 1, auto) — groups 1/2
- **P3.C** NP (auto NP, auto) — far absent; height_ft absent; mla absent
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
- **P6.B** 1 (auto 1, auto) — groups 1/2
- **P6.C** 1 (auto 1, auto) — far absent; height_ft absent; mla ok
- **P6.D** 2 (auto 2, auto) — found 4/4
- **P6.F** 1 (auto 1, auto) — groups 1/2
- **P7.A** 2 (auto 2, auto) — district RT4
- **P7.B** 2 (auto 2, auto) — groups 2/2
- **P7.C** NP (auto NP, auto) — far absent; height_ft absent; mla absent
- **P7.D** 2 (auto 2, auto) — found 2/2
- **P7.F** 1 (auto 1, auto) — groups 1/2

