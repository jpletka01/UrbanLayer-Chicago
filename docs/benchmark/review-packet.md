# Answer-key review packet

We are publishing a benchmark of how accurately zoning tools answer questions about hard Chicago parcels. Its value rests on the answer key being right. This packet is that key, with the source for each answer. We are asking you to check our reading of the sources, not to answer from memory.

**This packet is blind.** It contains no tool's answers, ours or anyone's, so your review is not anchored on them.

## What we are asking

1. For each field marked **Judgment**, open the cited source and tell us **agree**, **disagree** or **unsure**, with a sentence on why. If you disagree, tell us what the right answer is and where it comes from.
2. Skim the other fields. They are lookups (a district from the City's zoning layer, a number from a code table). Flag anything that looks wrong.
3. Tell us what is missing: situations in which a tool would likely get Chicago zoning wrong that these seven parcels do not test. We are growing the set to about 25 parcels and will pick from your answer.

Expected effort: about 21 judgment fields, roughly an hour with the code open.

## As of

- Key version `2026-10-02.1`: parcels P1 to P7 built 2026-10-01, later parcels on the date each carries as `added`.
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

PIN: 14313320180000. Why it is in the set: Overlay stack incl. a Chicago Landmark district and a CHRS orange-rated building; geocoder trap (address interpolates into a C1-3 polygon).

Question put to a tool, field B: *Is ground-floor retail with apartments above allowed?*  
Field F: *Could I demolish the existing building and build a new mixed-use building here? What approvals or restrictions apply?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | B3-2 (not C1-3, which a geocoder lands in) | Ordinance 17230; the Census-geocoded address point falls in a C1-3 polygon (O2021-4070). Address spans 3 PINs, all B3-2 | skim |
| Use question | Yes: B3 permits dwelling units above the ground floor (17-3-0104-C) | see the code sections cited in the answer | skim |
| C · Floor area ratio | 2.2 | 17-3-0403-A | skim |
| C · Height (ft) | 45 or 47 or 50 | 17-3-0408-A | skim |
| C · Minimum lot area per dwelling unit (sq ft) | 1000 or 700 | 17-3-0402-A | skim |
| Overlays and designations | historic_district, national_register, tod, aro, ssa | Milwaukee Avenue Chicago Landmark district HD-56, designated 2008-04-09 (layer 6); National Register (layer 8); TOD (CTA); ARO Inclusionary; SSA #33 Wicker Park. NOT an individual Chicago Landmark: Noel State Bank is in layer 7, which holds the Chicago Historic Resources Survey's orange/red-rated buildings (9,298 records, most with no designation date), and is absent from the City's official Chicago Landmarks list (data portal tdab-kixi, 317 landmarks) and from layer 5 (landmark boundaries). Corrected 2026-10-02: the first key read layer 7 as 'individual landmarks'. | **Judgment** |
| Parking / transit rule | Transit-served: parking reducible up to 100% (17-10-0102-B.1(a)); no added parking for reuse of a contributing building in a landmark district (17-10-0102-A.2) | see the code sections cited in the answer | **Judgment** |
| Task question | Not by right: the parcel is in the Milwaukee Avenue Chicago Landmark district, so a permit to alter, demolish or build needs written approval of the Commission on Chicago Landmarks (Municipal Code 2-120-740) | see the code sections cited in the answer | **Judgment** |

Questions:

- **P5.D**: We say this is not an individual Chicago Landmark, only inside the Milwaukee Avenue landmark district (designated 2008): the City's landmark-boundary layer and its official landmarks list have no entry for it, and the map layer that does name it is the historic-resources survey (orange rating). Is that right?
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

### P8 · 233 S Wacker Dr

PIN: 17162160090000. Why it is in the set: Downtown DC-16: base FAR 16 with bonuses, no height cap but a Planned Development height threshold, and its own use table (ground-floor dwellings are a special use).

Question put to a tool, field B: *Can I build apartments above ground-floor office or retail space, and can I put apartments on the ground floor?*  
Field F: *What is the maximum floor area ratio and building height allowed here, and can the floor area ratio be exceeded?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | DC-16 | dj47-wfun at the Assessor centroid | skim |
| Use question | Dwelling units above the ground floor: permitted; multi-unit on the ground floor: special use (use table 17-4-0207, rows 3 and 4: DC 'P' above, 'S' on the ground floor) | see the code sections cited in the answer | **Judgment** |
| C · Floor area ratio | 16 | 17-4-0405-A (DC-16 base FAR 16.0) | skim |
| C · Minimum lot area per dwelling unit (sq ft) | 100 | 17-4-0404-A (dash -16: dwelling units 100) | skim |
| Overlays and designations | tod, aro | TOD (CTA); ARO Downtown | skim |
| Task question | Base FAR 16.0 (17-4-0405-A) with bonus floor area available (17-4-0405-B, 17-4-1000); no maximum building height (17-4-0407), but Planned Development approval is required at 440 ft or more (residential) and 600 ft or more (nonresidential) (17-8-0512-B) | see the code sections cited in the answer | **Judgment** |

Questions:

- **P8.B**: In a DC district, are dwelling units above the ground floor permitted and multi-unit on the ground floor a special use?
- **P8.F**: Is the base FAR 16.0 with bonuses available, no maximum height, and Planned Development approval required at 440 ft (residential) or 600 ft (nonresidential) or more?

### P9 · 3441 W Irving Park Rd

PIN: 13232020060000. Why it is in the set: B3-3 inside the transit-served-location distances: the positive case. Density, FAR and height increases exist at dash-3 but only through a Type I map amendment, a PD or an ARO entitlement, not by right.

Question put to a tool, field B: *Is ground-floor retail with apartments above allowed, and what minimum lot area per dwelling unit applies?*  
Field F: *Does being near transit let me build more than the base standards here, and by what process?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | B3-3 | dj47-wfun at the Assessor centroid | skim |
| Use question | Yes: dwelling units above the ground floor are permitted in B3 (use table 17-3-0207, row 3) | see the code sections cited in the answer | skim |
| C · Floor area ratio | 3 | 17-3-0403-A, dash 3 | skim |
| C · Height (ft) | 50 or 55 or 60 or 65 | 17-3-0408-A (dash 3: 50/55/65/65 with compliant ground-floor commercial; 50/50/60/60 without, by lot frontage) | skim |
| C · Minimum lot area per dwelling unit (sq ft) | 400 or 300 | 17-3-0402-A (dash 3: 400 per dwelling unit; 300 efficiency) | skim |
| Overlays and designations | tod, aro, ssa | TOD (CTA); ARO; SSA Albany Park (observed from the City layers 2026-10-02) | skim |
| Parking / transit rule | Parking reducible up to 100% in a transit-served location (17-10-0102-B.1(a)) | see the code sections cited in the answer | skim |
| Task question | Yes, but not by right: in a B3 district within 2,640 ft of a rail station or 1,320 ft of a bus corridor, reduced lot area per unit, higher FAR (3.5 to 4.0 with ARO units) and added height are allowed only through a Type I zoning map amendment, a Planned Development, or an ARO entitlement (17-3-0402-B, 17-3-0403-B, 17-3-0408-B) | see the code sections cited in the answer | **Judgment** |

Questions:

- **P9.F**: At a B3-3 parcel within the transit-served-location distances, are lower lot area per unit, a higher FAR and extra height available only through a Type I map amendment, a Planned Development or an ARO entitlement, and never by right?

### P10 · 1930 N Clybourn Ave

PIN: 14324060010000. Why it is in the set: M2-3 manufacturing district: residential is not a listed use and unlisted uses are prohibited, so a use-allowed lookup must say no.

Question put to a tool, field B: *Could I build apartments here (new residential or a conversion)?*  
Field F: *What would it take to put housing on this parcel?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | M2-3 | dj47-wfun at the Assessor centroid | skim |
| Use question | No: household living is not in the M-district use table (17-5-0207) and uses not listed are prohibited (17-5-0204) | see the code sections cited in the answer | **Judgment** |
| C · Floor area ratio | 3 | 17-5-0404 (dash 3) | skim |
| Overlays and designations | tod, aro | TOD (CTA); ARO (observed from the City layers 2026-10-02) | skim |
| Task question | Not by right: it needs a zoning map amendment to a district that allows residential (Type I, 17-13-0302) or a Planned Development (17-13-0600) | see the code sections cited in the answer | skim |

Questions:

- **P10.B**: Is residential use prohibited in an M2 district because household living is not in the use table and unlisted uses are prohibited?

### P11 · 3500 N Lake Shore Dr

PIN: 14211120100000. Why it is in the set: RM-6.5 inside the Lakefront Protection District: no height cap but a PD threshold, a separate ordinance (Chapter 16-4), and a CHRS orange-rated building that is NOT a designated landmark.

Question put to a tool, field B: *Is a multi-unit residential building permitted by right?*  
Field F: *What review beyond the zoning district's standards applies to a new building on this parcel?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | RM-6.5 | dj47-wfun at the Assessor centroid | skim |
| Use question | Yes: multi-unit (3+ units) residential is permitted in RM-6.5 (use table 17-2-0207, row 5) | see the code sections cited in the answer | skim |
| C · Floor area ratio | 6.6 | 17-2-0304-A (RM-6.5: 6.60; premium may apply, 17-2-0304-C) | skim |
| C · Minimum lot area per dwelling unit (sq ft) | 300 | 17-2-0303-A (dwelling units 300) | skim |
| Overlays and designations | lakefront, aro, national_register | Lakefront Protection District (Private Lakefront, layer 3); ARO; National Register individual property 'The Cornelia' (layer 8). A CHRS orange-rated building (layer 7) but NOT a designated Chicago Landmark: absent from layer 5 and from the official landmarks list (tdab-kixi). Observed from the City layers 2026-10-02 | **Judgment** |
| Task question | All development in the Lake Michigan and Chicago Lakefront Protection District is subject to Chapter 16-4, the Lakefront Protection Ordinance (17-6-0204-B), in addition to the zoning standards; a building of 140 ft or more also needs Planned Development approval in RM-6.5 (17-8-0512-A) | see the code sections cited in the answer | **Judgment** |

Questions:

- **P11.D**: We say this is a National Register property and a historic-survey orange building, but not a designated Chicago Landmark. Is that the right reading of the City's layers?
- **P11.F**: Is a new building in the Lakefront Protection District subject to Chapter 16-4 in addition to the zoning standards?

### P12 · 368 W Chicago Ave

PIN: 17044360170000. Why it is in the set: C2-5 near rail: parking relief applies, but the density, FAR and height increases for transit-served locations exist only in dash-3 districts, not dash-5.

Question put to a tool, field B: *Can I build apartments above ground-floor retail, and what minimum lot area per dwelling unit applies?*  
Field F: *Does being near transit let me build more density here than the base standards?*

| Field | Our answer | Source | Review |
|---|---|---|---|
| Zoning district | C2-5 | dj47-wfun at the Assessor centroid | skim |
| Use question | Yes: dwelling units above the ground floor are permitted in C2 (use table 17-3-0207, row 3) | see the code sections cited in the answer | skim |
| C · Floor area ratio | 5 | 17-3-0403-A, dash 5 | skim |
| C · Height (ft) | 50 or 55 or 65 or 70 or 75 or 80 | 17-3-0408-A (dash 5: 50/55/70/80 with compliant ground-floor commercial; 50/50/65/75 without, by lot frontage; more than the 100-ft-lot height only by PD) | skim |
| C · Minimum lot area per dwelling unit (sq ft) | 200 or 135 | 17-3-0402-A (dash 5: 200 per dwelling unit; 135 efficiency) | skim |
| Overlays and designations | tod, aro | TOD (CTA); ARO (observed from the City layers 2026-10-02) | skim |
| Parking / transit rule | Parking reducible up to 100% in a transit-served location (17-10-0102-B.1(a)) | see the code sections cited in the answer | skim |
| Task question | Transit changes parking only: the transit-served-location increases in density, FAR and height apply to B-3 and C-3 districts (and D-3), not dash-5 (17-3-0402-B, 17-3-0403-B, 17-3-0408-B) | see the code sections cited in the answer | **Judgment** |

Questions:

- **P12.F**: Do the transit-served-location increases (density, FAR, height) apply to dash-3 districts only, so that a C2-5 parcel near rail gets parking relief but no density increase?

## How to reply

Reply in any form, as long as each judgment field is named by its tag (for example `P2.F`). A table like this is easiest:

| Tag | agree / disagree / unsure | Note (and the right answer, with its source, if you disagree) |
|---|---|---|
| P2.F | | |

Also tell us how you would like to be credited, if at all. We will publish your role and credentials. We will publish your name only if you say yes. Every disagreement will be published alongside the agreement rate, whether or not we change the key.
