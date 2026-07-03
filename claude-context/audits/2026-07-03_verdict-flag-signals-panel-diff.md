# Verdict signal integration — before/after on the frozen 100-address panel

_2026-07-03 · engine: feat/verdict-flag-signals · panel: eval/lot_panel.json_

## Headline

- **Category changes: 0 / 100** (guaranteed by design — flags/appeals feed reasons/caveats only; `selectCategory` never reads them)
- Verdicts gaining a new reason or caveat: **19 / 100**
- Signal firing rates: city_owned **1**, scofflaw **0**, str_prohibited **4**, appeal_upside **15** (at wins≥10 & median≥10%)

## Category distribution (after — identical to before)

- limited: 29
- strong: 25
- incentive_driven: 18
- constrained: 15
- entitlement_defined: 13

## Appeal-upside threshold sensitivity

Panel nearby-appeal stats: 97 parcels have ≥1 nearby win; median-of-medians 8.3%.

| min wins | min median | parcels firing |
|---|---|---:|
| ≥5 wins | ≥5% | 58 |
| ≥5 wins | ≥8% | 41 |
| ≥5 wins | ≥10% | 29 |
| ≥5 wins | ≥12% | 25 |
| ≥5 wins | ≥15% | 18 |
| ≥10 wins | ≥5% | 42 |
| ≥10 wins | ≥8% | 25 |
| ≥10 wins | ≥10% | 15 |
| ≥10 wins | ≥12% | 14 |
| ≥10 wins | ≥15% | 12 |
| ≥20 wins | ≥5% | 37 |
| ≥20 wins | ≥8% | 21 |
| ≥20 wins | ≥10% | 11 |
| ≥20 wins | ≥12% | 10 |
| ≥20 wins | ≥15% | 8 |
| ≥30 wins | ≥5% | 36 |
| ≥30 wins | ≥8% | 21 |
| ≥30 wins | ≥10% | 11 |
| ≥30 wins | ≥12% | 10 |
| ≥30 wins | ≥15% | 8 |

Chosen gate: **wins ≥ 10 AND median ≥ 10%** — fires on 15/100 (parcel-discriminating, not citywide noise like ARO).

## Per-address changes (19 rows; unchanged addresses omitted)

| Address | Category (before → after) | Added reasons | Added caveats |
|---|---|---|---|
| 3157 W Devon Ave | strong | reason.appealUpside | — |
| 625 W Madison St | entitlement_defined | — | caveat.strProhibited |
| 1031 E 103Rd St | constrained | reason.appealUpside | — |
| 741 W 79Th St | incentive_driven | reason.appealUpside | — |
| 1551 W Garfield Blvd | strong | reason.appealUpside | — |
| 757 W 79Th St | constrained | reason.cityOwned; reason.appealUpside | — |
| 4734 N Marine Dr | constrained | reason.appealUpside | — |
| 1555 W 47Th St | incentive_driven | reason.appealUpside | — |
| 4713 S Ashland Ave | incentive_driven | reason.appealUpside | — |
| 3949 N Clarendon Ave | limited | — | caveat.strProhibited |
| 3947 N Clarendon Ave | limited | — | caveat.strProhibited |
| 3943 W Roosevelt Rd | strong | reason.appealUpside | — |
| 3951 N Clarendon Ave | limited | — | caveat.strProhibited |
| 4715 S Ashland Ave | incentive_driven | reason.appealUpside | — |
| 3953 W Roosevelt Rd | incentive_driven | reason.appealUpside | — |
| 3955 W Roosevelt Rd | strong | reason.appealUpside | — |
| 1533 W Garfield Blvd | strong | reason.appealUpside | — |
| 737 W 79Th St | incentive_driven | reason.appealUpside | — |
| 955 E 103Rd St | constrained | reason.appealUpside | — |
