# UrbanLayer parcel benchmark

Seven hard Chicago parcels, each with an answer key built from primary sources, asked the same six questions of the product's **Property Profile** (a deterministic page) and of its **chat** (the same standard prompt, address only). It was built to find where a zoning tool is wrong, so it includes the failures.

> **Read the limits before quoting a number** (section 6). Seven parcels; the key is not yet reviewed by a Chicago professional.

## 1. Current results

| Surface | Run | Parcels scored | Coverage | Accuracy | Confident-wrong fields | Wrong districts | Scoring |
|---|---|:-:|:-:|:-:|:-:|---|---|
| Property Profile | 2026-10-02 (`1f97199`) | 7/7 | 95% | 97% | 0 | none | automatic |
| Chat | 2026-10-02 (`ff1b64b`) | 7/7 | 95% | 97% | 0 | none | automatic |

*Coverage* is the share of the 37 scored fields the tool made a claim on; *accuracy* is points earned (2 / 1 / 0) over points possible on the fields it answered; a *confident-wrong* field is wrong and stated without hedging; a *wrong district* is the critical failure, because everything else derives from it. The two surfaces' current runs come from different code versions (the most recent run that scored all seven parcels on each surface).

## 2. Parcel by parcel

Score per field: **2** correct, **1** partial, **0** wrong, **NP** no claim; **CW** marks a confident-wrong answer. Fields: A district, B use question, C bulk numbers, D overlays, E parking/transit (P3 and P5 only), F the parcel's task question.

### P1 · 6247 N Rockwell St · key district **RS-2**

*Plain RS-2 baseline; ADU nuance (not in an ADU-allowed area).*

| Field | Question | Key answer | Profile | Chat |
|---|---|---|:-:|:-:|
| A | Zoning district | RS-2 | 2 | 2 |
| B | Use question | Two-flat NOT allowed (use table 17-2-0207: detached house P; two-flat '-' in RS1/RS2) | 2 | 2 |
| C | Bulk numbers | far 0.65; height 30; mla 5000 | 2 | 1 |
| D | Overlays | aro | 2 | 2 |
| F | Task answer | Coach house NOT allowed (no ADU zone, layer 17; 17-7-0574) | 2 | 2 |

### P2 · 1256 N Artesian Ave · key district **RM-4.5**

*Vacant infill lot; geocoder trap (address interpolates into adjacent RS-3); MLA arithmetic (4 not 6).*

| Field | Question | Key answer | Profile | Chat |
|---|---|---|:-:|:-:|
| A | Zoning district | RM-4.5 | 2 | 2 |
| B | Use question | Multi-unit PERMITTED (17-2-0207 row 5, RM4.5) | 2 | 2 |
| C | Bulk numbers | far 1.7; height 45, 47; mla 700 | 2 | 2 |
| D | Overlays | special_district, aro | 2 | 2 |
| F | Task answer | 4 units (3,154 / 700 = 4.5 -> 4); 6 is not achievable by right | 2 | 2 |

### P3 · 1500 W Wilson Ave · key district **B1-2**

*B1-2 near rail: TOD parking relief yes, TOD density bonus NO (dash-2); ground-floor dwelling needs special use.*

| Field | Question | Key answer | Profile | Chat |
|---|---|---|:-:|:-:|
| A | Zoning district | B1-2 | 2 | 2 |
| B | Use question | Dwelling units above the ground floor: permitted; on the ground floor: special use (17-3-0102-D; 17-3-0103-A) | 1 | 2 |
| C | Bulk numbers | far 2.2; height 45, 47, 50; mla 1000, 700 | 2 | 2 |
| D | Overlays | tod, aro, ssa | 2 | 2 |
| E | Parking / transit | Parking reducible up to 100% (17-10-0102-B.1(a)); density bonuses only in dash-3/D-3 districts -> NOT at B1-2 | 2 | 1 |
| F | Task answer | Height/FAR as in C; transit changes parking only, not density | 2 | 2 |

### P4 · 401 N Wabash Ave · key district **PD 835**

*Planned Development: base-district numbers do not apply; standards live in the PD ordinance.*

| Field | Question | Key answer | Profile | Chat |
|---|---|---|:-:|:-:|
| A | Zoning district | PD 835 | 2 | 2 |
| B | Use question | Governed by a PD, not a base district | 2 | 2 |
| C | Bulk numbers | far 26; height 1125 | NP | NP |
| D | Overlays | pd, aro, tod | 2 | 2 |
| F | Task answer | FAR 26.0; height 1,125 ft per PD 835 | NP | NP |

### P5 · 1601 N Milwaukee Ave · key district **B3-2**

*Overlay stack incl. an individual Chicago Landmark; geocoder trap (address interpolates into a C1-3 polygon).*

| Field | Question | Key answer | Profile | Chat |
|---|---|---|:-:|:-:|
| A | Zoning district | B3-2 | 2 | 2 |
| B | Use question | Yes: B3 permits dwelling units above the ground floor (17-3-0104-C) | 2 | 2 |
| C | Bulk numbers | far 2.2; height 45, 47, 50; mla 1000, 700 | 2 | 2 |
| D | Overlays | landmark_building, historic_district, national_register, tod, aro, ssa | 2 | 2 |
| E | Parking / transit | Transit-served: parking reducible up to 100% (17-10-0102-B.1(a)); no added parking for reuse of a contributing building in a landmark district (17-10-0102-A.2) | 1 | 2 |
| F | Task answer | Not by right: written approval of the Commission on Chicago Landmarks is required (Municipal Code 2-120-740) | 2 | 2 |

### P6 · 3400 N Central Park Ave · key district **RS-3**

*RS-3 with the 606 Predominance-of-the-Block district (MLA 1,500) and a conditional ADU zone.*

| Field | Question | Key answer | Profile | Chat |
|---|---|---|:-:|:-:|
| A | Zoning district | RS-3 | 2 | 2 |
| B | Use question | Two-flat PERMITTED in RS-3 (use table row 3); 606 district lowers MLA to 1,500 (17-2-0303-B.1) | 2 | 2 |
| C | Bulk numbers | far 0.9; height 30; mla 1500, 2500 | 2 | 2 |
| D | Overlays | special_district, adu, aro, tod | 2 | 2 |
| F | Task answer | Allowed with limits: ADU Zone 10 -> (1) annual limit, (2) owner occupancy (17-7-0573/-0574) | 2 | 2 |

### P7 · 1218 W George St · key district **RT-4**

*Freshness: rezoned M1-2 -> RT-4 by an ordinance passed 2026-06-17 (open-data layer updated 2026-08-21).*

| Field | Question | Key answer | Profile | Chat |
|---|---|---|:-:|:-:|
| A | Zoning district | RT-4 | 2 | 2 |
| B | Use question | Yes: RT-4 permits two-flat, townhouse and multi-unit residential (17-2-0207) | 2 | 2 |
| C | Bulk numbers | far 1.2; height 38, 42; mla 1000 | 2 | 2 |
| D | Overlays | tod, aro | 2 | 2 |
| F | Task answer | Yes: rezoned M1-2 -> RT-4 in June 2026 | 2 | 2 |

## 3. How the numbers moved

Each row is a dated run of the real system on one code version (`make kit`), scored the same way. Every change here shipped because an earlier row showed a failure; the reports linked are the raw evidence.

| Run | Date | Code | Profile accuracy / confident-wrong | Chat accuracy / confident-wrong | Chat wrong districts | Report |
|---|---|---|:-:|:-:|---|---|
| Starting point (recorded 2026-10-01, hand-scored B/E/F) | 2026-10-01 | `dd481c5` | 80% / 2 | 68% / 7 | P2, P5 | recorded run in `eval/kit/baseline/` |
| Chat resolves a typed address to its parcel (F1) | 2026-10-01 | `b9bda71` |  | 81% / 1 | none | [report](../../eval/results/2026-10-01-f1/parcel_kit.md) |
| No false transit 'density bonus' claim (F2) | 2026-10-02 | `dd5360a` | 83% / 0 | 87% / 1 | none | [report](../../eval/results/2026-10-02-f2/parcel_kit.md) |
| The binding number: lot area per unit + unit yield (F3) | 2026-10-02 | `dd5360a` | 94% / 0 | 90% / 0 | none | [report](../../eval/results/2026-10-02-f3/parcel_kit.md) |
| When the district last changed, and how current the code is (F5a) | 2026-10-02 | `ff1b64b` | 94% / 0 | 97% / 0 | none | [report](../../eval/results/2026-10-02-f5a/parcel_kit.md) |
| Overlays named, with what they require (F7) | 2026-10-02 | `341e91a` | 97% / 0 |  |  | [report](../../eval/results/2026-10-02-f7/parcel_kit.md) |
| Where the page says it stops (V4) | 2026-10-02 | `1f97199` | 97% / 0 |  |  | [report](../../eval/results/2026-10-02-v4/parcel_kit.md) |

## 4. What the first run found

The starting point is the uncomfortable part, and it is kept on purpose. The Profile resolved the right district on all seven parcels but showed a false claim (that every transit-served parcel gets a density bonus; only dash-3 districts can, and only by entitlement) and never showed the number a unit count turns on (minimum lot area per unit). Chat, given only an address, located the parcel from a geocoded street point instead of the parcel, which put it in the neighboring district on two of seven parcels (a vacant RM-4.5 lot answered as RS-3, a landmark answered as a C1-3 parcel), invented bulk numbers from memory, and stopped at its token cap mid-answer on most parcels without saying so. A recent rezoning could not be stated at all, and a multi-parcel strip center's building area had been attributed to a single lot.

## 5. The answer key

Key version `2026-10-01.1`, in [`eval/kit/parcels.json`](../../eval/kit/parcels.json), with the source for every field. Sources: the City's open-data zoning layer and its zoning map service (overlays), the Municipal Code text (American Legal export, current through the Council Journal of 2026-03-18), ordinance PDFs, and Cook County Assessor data. Where the key and the product agree because they read the same City service, that is noted (overlays). The key fixed three errors in an earlier version that had used the product's own output as ground truth.

**Outside review: pending.** The reviewer is sent the [blind review packet](review-packet.md) (the key and its sources, none of any tool's answers). Their agreement rate and every disagreement will be published here, whether or not the key changes.

## 6. Limits

- Seven parcels show kinds of failure. They are not a statistically reliable accuracy rate.
- The answer key was built from primary sources but has not yet been reviewed by a Chicago architect or zoning attorney (the most interpretive parcels are P2, P3 and P6).
- Overlay truth comes from the same City service the product queries, so overlay scores are not independent evidence. District, bulk numbers and the task answers are.
- Use-question, parking and task answers are scored by expected-phrase rubrics that were written while looking at earlier runs, so agreement with a person's scores is in-sample.
- Chat answers vary from run to run; one run per row. Compare runs by the cases that fail, not by the third digit.
- Code text is current through the Council Journal of 2026-03-18; a later amendment is not in the key.

## 7. Reproduce it

```bash
make kit-replay    # re-score the recorded runs: no network, no cost; reproduces the starting-point row
make kit           # run the live system on the 7 parcels, then score it (Profile is free; chat costs about $1)
PYTHONPATH=. python -m eval.benchmark   # regenerate this page from the committed results
```

The scorer, rubrics and its tests are in [`eval/parcel_kit.py`](../../eval/parcel_kit.py). District, bulk numbers and overlays are scored mechanically; use, parking and task answers by expected-phrase rubrics; a person's scores can override any field (`--manual`), and every report states how often the automatic score agreed with the hand score.

## 8. Scoring another tool

UrbanLayer is the only tool published here for now; other tools will be added after review and a terms-of-service check. To score one yourself: enter each address **alone** (no PIN, no district), use the standard prompt below for chat tools, record the answer as shown without correcting it, and score against the key with the rubric above.

Standard prompt (per parcel, with its use and task questions from the key):

> I'm evaluating the property at <ADDRESS> in Chicago, Illinois for a possible project. Tell me, with sources: (1) the zoning district currently in effect for this parcel; (2) <USE QUESTION>; (3) the key bulk and density standards that apply (FAR, max height, min lot area per dwelling unit, setbacks, as applicable); (4) any overlays or special designations that apply (Planned Development, landmark/historic district, transit-oriented or transit-served location, ADU area, ARO zone, special service area, special districts); (5) the parking requirement and any transit-related reduction; (6) <TASK QUESTION> For each item cite the specific Municipal Code section or official source and tell me how I can verify it. Say how confident you are and what you could not determine.

| Parcel | A district | B use | C bulk | D overlays | E parking/transit | F task | Notes |
|---|:-:|:-:|:-:|:-:|:-:|:-:|---|
| P1 6247 N Rockwell St | | | | | n/a | | |
| P2 1256 N Artesian Ave | | | | | n/a | | |
| P3 1500 W Wilson Ave | | | | |  | | |
| P4 401 N Wabash Ave | | | | | n/a | | |
| P5 1601 N Milwaukee Ave | | | | |  | | |
| P6 3400 N Central Park Ave | | | | | n/a | | |
| P7 1218 W George St | | | | | n/a | | |

*One generic-LLM reference run (a model with web search and no access to this repository) was recorded once on 2026-10-01 for context: it made a claim on about a third of the fields and was right on about half of those. It is one model and one harness, and its raw output is not part of this repository, so it is not reproducible from here.*
