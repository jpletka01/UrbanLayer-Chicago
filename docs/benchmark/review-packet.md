# Answer-key review packet

We are publishing a benchmark of how accurately zoning tools answer questions about hard Chicago parcels. Its value rests on the answer key being right. This packet is that key, with the source for each answer. We are asking you to check our reading of the sources, not to answer from memory.

**This packet is blind.** It contains no tool's answers, ours or anyone's, so your review is not anchored on them.

## What we are asking

1. For each field marked **Judgment**, open the cited source and tell us **agree**, **disagree** or **unsure**, with a sentence on why. If you disagree, tell us what the right answer is and where it comes from.
2. Skim the other fields. They are lookups (a district from the City's zoning layer, a number from a code table). Flag anything that looks wrong.
3. Tell us what is missing: situations in which a tool would likely get Chicago zoning wrong that these seven parcels do not test. We are growing the set to about 25 parcels and will pick from your answer.

Expected effort: about 13 judgment fields, roughly an hour with the code open.

## As of

- Key version `2026-10-01.1`, built 2026-10-01.
- Municipal Code text current through the Council Journal of 2026-03-18 (American Legal export of Title 17). An amendment after that date is not reflected; tell us if one changes an answer.
- Parcel facts come from the City of Chicago zoning layer (Data Portal `dj47-wfun`) and Zoning MapServer, Cook County Assessor data, and ordinance PDFs.
- Overlay answers (field D) read the same City map service that tools use, so they check that a tool reports the map correctly, not that the map is right. They are not the focus of this review.

## The parcels

### P1 · 6247 N Rockwell St

PIN: 13012120030000. Why it is in the set: Plain RS-2 baseline; ADU nuance (not in an ADU-allowed area).

Question put to a tool, field B: *Could I build a two-flat (two dwelling units) here?*  
Field F: *Could I add a coach house / accessory dwelling unit on this lot?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | RS-2 | City zoning layer dj47-wfun at the Assessor centroid; 17-2-0100 | skim |
| Use question | Two-flat NOT allowed (use table 17-2-0207: detached house P; two-flat '-' in RS1/RS2) | see the code sections cited in the answer | skim |
| C · Floor area ratio | 0.65 | 17-2-0304-A | skim |
| C · Height (ft) | 30 | 17-2-0311-A | skim |
| C · Minimum lot area per dwelling unit (sq ft) | 5000 | 17-2-0301-A, 17-2-0303-A (lot area per unit = min lot area in RS-2) | skim |
| Overlays and designations | aro | City Zoning MapServer layers 2-24 at the centroid | skim |
| Task question | Coach house NOT allowed (no ADU zone, layer 17; 17-7-0574) | see the code sections cited in the answer | skim |

### P2 · 1256 N Artesian Ave

PIN: 16012280180000. Why it is in the set: Vacant infill lot; geocoder trap (address interpolates into adjacent RS-3); MLA arithmetic (4 not 6).

Question put to a tool, field B: *Is a multi-unit residential building (3+ units) permitted by right? (This is a vacant lot of roughly 3,150 square feet.)*  
Field F: *What is the maximum number of dwelling units I could build by right on this lot, and could I build 6 units?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | RM-4.5 (not RS-3, which a geocoder lands in) | Ordinance A7210; the Census-geocoded address point falls in an adjacent RS-3 polygon | skim |
| Use question | Multi-unit PERMITTED (17-2-0207 row 5, RM4.5) | see the code sections cited in the answer | **Judgment** |
| C · Floor area ratio | 1.7 | 17-2-0304-A | skim |
| C · Height (ft) | 45 or 47 | 17-2-0311-A (45 ft <32 ft frontage; 47 ft otherwise) | skim |
| C · Minimum lot area per dwelling unit (sq ft) | 700 | 17-2-0303-A | skim |
| Overlays and designations | special_district, aro | 606 district (layer 9; does NOT change RM-4.5 density per 17-7-0591); ARO CPA (layer 20) | **Judgment** |
| Task question | 4 units (3,154 / 700 = 4.5 -> 4); 6 is not achievable by right | see the code sections cited in the answer | **Judgment** |

Questions:

- **P2.B**: Is multi-unit residential permitted by right in RM-4.5 on this lot, as the use table reads?
- **P2.D**: A 606 district is mapped here. Does it leave RM-4.5 density unchanged (17-7-0591), in contrast to P6 where it lowers the minimum lot area?
- **P2.F**: Is 4 the right by-right maximum? Does the code round a fractional unit count down, and is any relief available by right that would reach 6?

### P3 · 1500 W Wilson Ave

PIN: 14171060250000. Why it is in the set: B1-2 near rail: TOD parking relief yes, TOD density bonus NO (dash-2); ground-floor dwelling needs special use.

Question put to a tool, field B: *Can I build apartments above ground-floor retail, and can I put apartments on the ground floor?*  
Field F: *What are the maximum height and floor area ratio for a mixed-use building here, and does proximity to transit change what I can build (including any density or parking provisions)?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | B1-2 | dj47-wfun at the Assessor centroid | skim |
| Use question | Dwelling units above the ground floor: permitted; on the ground floor: special use (17-3-0102-D; 17-3-0103-A) | see the code sections cited in the answer | **Judgment** |
| C · Floor area ratio | 2.2 | 17-3-0403-A, dash 2 | skim |
| C · Height (ft) | 45 or 47 or 50 | 17-3-0408-A | skim |
| C · Minimum lot area per dwelling unit (sq ft) | 1000 or 700 | 17-3-0402-A (1,000; 700 for efficiency/SRO) | skim |
| Overlays and designations | tod, aro, ssa | TOD (CTA) layer; ARO CPA; SSA #31 Greater Ravenswood | skim |
| Parking / transit rule | Parking reducible up to 100% (17-10-0102-B.1(a)); density bonuses only in dash-3/D-3 districts -> NOT at B1-2 | see the code sections cited in the answer | **Judgment** |
| Task question | Height/FAR as in C; transit changes parking only, not density | see the code sections cited in the answer | **Judgment** |

Questions:

- **P3.B**: Is ground-floor dwelling a special use, with units above the ground floor permitted, in B1-2?
- **P3.E**: Does transit proximity reduce required parking only, with no density or FAR bonus, at a dash-2 district?
- **P3.F**: Same question as E, plus: are the height and FAR figures the ones that govern a mixed-use building?

### P4 · 401 N Wabash Ave

PIN: building PIN not in the Parcel Universe (condominium building). Why it is in the set: Planned Development: base-district numbers do not apply; standards live in the PD ordinance.

Question put to a tool, field B: *Is this parcel governed by an ordinary base zoning district, or by something else?*  
Field F: *What is the maximum floor area ratio and building height allowed?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | PD 835 | Ordinance 13559 (07/31/2002); PD835.pdf | skim |
| Use question | Governed by a PD, not a base district | see the code sections cited in the answer | skim |
| C · Floor area ratio | 26 | PD835.pdf pp. 35-37 (bulk table) | **Judgment** |
| C · Height (ft) | 1125 | PD835.pdf; 2010 minor-change letter | **Judgment** |
| Overlays and designations | pd, aro, tod | PD 835 (layer 2); ARO Downtown; TOD (CTA) | skim |
| Task question | FAR 26.0; height 1,125 ft per PD 835 | see the code sections cited in the answer | skim |

Questions:

- **P4.C**: Are these the right PD 835 figures: FAR 26.0 from the bulk table, and a height of 1,125 ft as modified by a 2010 minor-change letter?

### P5 · 1601 N Milwaukee Ave

PIN: 14313320180000. Why it is in the set: Overlay stack incl. an individual Chicago Landmark; geocoder trap (address interpolates into a C1-3 polygon).

Question put to a tool, field B: *Is ground-floor retail with apartments above allowed?*  
Field F: *Could I demolish the existing building and build a new mixed-use building here? What approvals or restrictions apply?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | B3-2 (not C1-3, which a geocoder lands in) | Ordinance 17230; the Census-geocoded address point falls in a C1-3 polygon (O2021-4070). Address spans 3 PINs, all B3-2 | skim |
| Use question | Yes: B3 permits dwelling units above the ground floor (17-3-0104-C) | see the code sections cited in the answer | skim |
| C · Floor area ratio | 2.2 | 17-3-0403-A | skim |
| C · Height (ft) | 45 or 47 or 50 | 17-3-0408-A | skim |
| C · Minimum lot area per dwelling unit (sq ft) | 1000 or 700 | 17-3-0402-A | skim |
| Overlays and designations | landmark_building, historic_district, national_register, tod, aro, ssa | Individual landmark (Noel State Bank, layer 7); Milwaukee Avenue landmark district HD-56 (layer 6); National Register (layer 8); TOD (CTA); ARO Inclusionary; SSA #33 Wicker Park | skim |
| Parking / transit rule | Transit-served: parking reducible up to 100% (17-10-0102-B.1(a)); no added parking for reuse of a contributing building in a landmark district (17-10-0102-A.2) | see the code sections cited in the answer | **Judgment** |
| Task question | Not by right: written approval of the Commission on Chicago Landmarks is required (Municipal Code 2-120-740) | see the code sections cited in the answer | **Judgment** |

Questions:

- **P5.E**: Is parking reducible by up to 100% for a transit-served location, with no added parking for reusing a contributing building in a landmark district?
- **P5.F**: Does an individually landmarked building in a landmark district require the Commission on Chicago Landmarks' written approval before demolition or a new building?

### P6 · 3400 N Central Park Ave

PIN: 13233160400000. Why it is in the set: RS-3 with the 606 Predominance-of-the-Block district (MLA 1,500) and a conditional ADU zone.

Question put to a tool, field B: *Could I build a two-flat here?*  
Field F: *Could I add a coach house or other additional dwelling unit here, and under what conditions or limits?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | RS-3 | dj47-wfun (polygon edited 2026-08-27) | skim |
| Use question | Two-flat PERMITTED in RS-3 (use table row 3); 606 district lowers MLA to 1,500 (17-2-0303-B.1) | see the code sections cited in the answer | **Judgment** |
| C · Floor area ratio | 0.9 | 17-2-0304-A | **Judgment** |
| C · Height (ft) | 30 | 17-2-0311-A | **Judgment** |
| C · Minimum lot area per dwelling unit (sq ft) | 1500 or 2500 | 17-2-0303-B.1 (2,500 reduced to 1,500 in a 606 district) | **Judgment** |
| Overlays and designations | special_district, adu, aro, tod | 606 district (layer 9); ADU Zone 10 (layer 17); ARO CPA; TOD (CTA) | skim |
| Task question | Allowed with limits: ADU Zone 10 -> (1) annual limit, (2) owner occupancy (17-7-0573/-0574) | see the code sections cited in the answer | **Judgment** |

Questions:

- **P6.B**: Is a two-flat permitted in RS-3, and does the 606 district lower the minimum lot area per unit from 2,500 to 1,500?
- **P6.C**: Which minimum lot area per unit applies here: 1,500 (606 district) or 2,500?
- **P6.F**: Is a coach house allowed here with exactly the annual limit and owner-occupancy conditions of ADU Zone 10?

### P7 · 1218 W George St

PIN: 14291230290000. Why it is in the set: Freshness: rezoned M1-2 -> RT-4 by an ordinance passed 2026-06-17 (open-data layer updated 2026-08-21).

Question put to a tool, field B: *Is residential use allowed on this parcel?*  
Field F: *What is the zoning here, and has it changed recently?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | RT-4 (not M1-2, which a geocoder lands in) | Ordinance O2026-0025358 (App. 23082T1), passed 2026-06-17; the address point lands in an adjacent RT-4 polygon (O2018-3982) | **Judgment** |
| Use question | Yes: RT-4 permits two-flat, townhouse and multi-unit residential (17-2-0207) | see the code sections cited in the answer | skim |
| C · Floor area ratio | 1.2 | 17-2-0304-A | skim |
| C · Height (ft) | 38 or 42 | 17-2-0311-A/B | skim |
| C · Minimum lot area per dwelling unit (sq ft) | 1000 | 17-2-0303-A | skim |
| Overlays and designations | tod, aro | TOD (CTA); ARO Inclusionary | skim |
| Task question | Yes: rezoned M1-2 -> RT-4 in June 2026 | see the code sections cited in the answer | skim |

Questions:

- **P7.A**: The rezoning ordinance passed 2026-06-17. Was it in effect on 2026-10-01 (publication and effective date), so that RT-4 rather than M1-2 is the district in effect?

## How to reply

Reply in any form, as long as each judgment field is named by its tag (for example `P2.F`). A table like this is easiest:

| Tag | agree / disagree / unsure | Note (and the right answer, with its source, if you disagree) |
|---|---|---|
| P2.F | | |

Also tell us how you would like to be credited, if at all. We will publish your role and credentials. We will publish your name only if you say yes. Every disagreement will be published alongside the agreement rate, whether or not we change the key.
