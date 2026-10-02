# Parcel kit report

Key `2026-10-01.1` · run 2026-10-02 · code `dd5360a` · source: replay of eval/results/2026-10-02-f4b/parcel_kit_raw

> Answer key for the 7-parcel Chicago kit, built from primary sources (City zoning layer, Zoning MapServer, Municipal Code text current through the Council Journal of 2026-03-18, ordinance PDFs, Cook County Assessor). NOT yet reviewed by a Chicago architect or zoning attorney: P2, P3 and P6 are the most interpretive. Overlay truth comes from the same City service UrbanLayer queries, so overlay scores are not independent.

## Summary

| Surface | Coverage | Accuracy | CW | Critical misses | A correct | Screening-grade |
|---|:-:|:-:|:-:|---|:-:|:-:|
| chat | 31/37 = 84% | 55/62 = 89% | 0 | none | 7/7 | yes |

All cells are automatic (no hand-scores file).

## chat: field scores

| Parcel | A | B | C | D | E | F |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| P1 | 2 | 2 | NP | 2 |  | 2 |
| P2 | 2 | 2 | 0 | 2 |  | NP |
| P3 | 2 | 1 | NP | 2 | 2 | 2 |
| P4 | 2 | 2 | NP | 2 |  | NP |
| P5 | 2 | 2 | NP | 2 | 2 | 2 |
| P6 | 2 | 1 | 1 | 2 |  | 2 |
| P7 | 2 | 2 | 1 | 2 |  | 1 |

`*` = hand score; `CW` = confident-wrong; `NP` = no claim.

## Chat answer completeness

| Parcel | Chars | Reaches item 6 | Ends cleanly | Cut-off notice | Silently cut off | Field names leaked |
|---|--:|:-:|:-:|:-:|:-:|---|
| P1 | 5277 | yes | yes |  |  | tod_benefits |
| P2 | 6411 | yes | yes |  |  | zone_definition |
| P3 | 7140 | yes | NO | yes |  | density_bonus_eligible |
| P4 | 6218 | yes | yes |  |  |  |
| P5 | 7498 | yes | NO | yes |  |  |
| P6 | 6203 | yes | yes |  |  |  |
| P7 | 5133 | yes | yes |  |  |  |

## Per-cell detail

### chat

- **P1.A** 2 (auto 2, auto) — district RS2
- **P1.B** 2 (auto 2, auto) — groups 2/2
- **P1.C** NP (auto NP, auto) — far absent; height_ft absent; mla absent
- **P1.D** 2 (auto 2, auto) — found 1/1
- **P1.F** 2 (auto 2, auto) — groups 2/2
- **P2.A** 2 (auto 2, auto) — district RM4.5
- **P2.B** 2 (auto 2, auto) — groups 2/2
- **P2.C** 0 (auto 0, auto) — far absent; height_ft absent; mla wrong (hedged) (400 vs 700)
- **P2.D** 2 (auto 2, auto) — found 2/2
- **P2.F** NP (auto NP, auto) — groups 0/2
- **P3.A** 2 (auto 2, auto) — district B12
- **P3.B** 1 (auto 1, auto) — groups 1/2
- **P3.C** NP (auto NP, auto) — far absent; height_ft absent; mla absent
- **P3.D** 2 (auto 2, auto) — found 3/3
- **P3.E** 2 (auto 2, auto) — groups 2/2
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
- **P6.F** 2 (auto 2, auto) — groups 2/2
- **P7.A** 2 (auto 2, auto) — district RT4
- **P7.B** 2 (auto 2, auto) — groups 2/2
- **P7.C** 1 (auto 1, auto) — far absent; height_ft absent; mla ok
- **P7.D** 2 (auto 2, auto) — found 2/2
- **P7.F** 1 (auto 1, auto) — groups 1/2

