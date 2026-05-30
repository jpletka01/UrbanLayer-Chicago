# Retrieval Quality Benchmark

## Summary

- **Queries**: 18
- **Chunks evaluated**: 90
- **Grades**: A=6  B=4  C=4  D=3  F=1

### Aggregate Metrics

| Metric | Count | % |
|---|---:|---:|
| Gold section hits | 48/90 | 53% |
| Duplicate section slots | 16/90 | 18% |
| Table fragments (<=3 rows) | 4/90 | 4% |
| Low-content chunks | 0/90 | 0% |

## Per-Query Results

| Grade | ID | Question | Gold Hits | Dups | Table Frags | Issues |
|:---:|---|---|:---:|:---:|:---:|---|
| **C** | `setback_single_family` | What are the setback requirements for a single-family h | 2/5 | 2 | 1 | 2 duplicate chunk(s) from same section: 17-2-0300, 17-3-0400; answer terms missi |
| **D** | `home_occupation` | Can I run a small bakery business from my home? | 1/5 | 1 | 0 | gold section(s) found but not in top-3; 1 duplicate chunk(s) from same section:  |
| **B** | `minimum_lot_size` | What's the minimum lot size for building in an RS-3 zon | 3/5 | 2 | 1 | 2 duplicate chunk(s) from same section: 17-2-0300 |
| **C** | `adu_allowed` | Are accessory dwelling units allowed in Chicago? | 3/5 | 2 | 0 | 2 duplicate chunk(s) from same section: 17-9-0200; answer terms missing from res |
| **A** | `noise_ordinance` | What are the noise ordinance rules in Chicago? | 2/5 | 0 | 0 |  |
| **F** | `fence_height` | How tall can a fence be in a residential area? | 0/5 | 0 | 0 | MISS: none of the 5 chunks match expected sections; answer terms missing from re |
| **A** | `garage_conversion` | Can I convert my garage into a living space? | 2/5 | 0 | 0 |  |
| **B** | `short_term_rental` | What are the regulations for Airbnb and short-term rent | 5/5 | 1 | 0 | 1 duplicate chunk(s) from same section: 4-13-260 |
| **D** | `deck_setback` | How close to the property line can I build a deck? | 1/5 | 0 | 0 | gold section(s) found but not in top-3; answer terms missing from results: ['set |
| **A** | `food_trucks` | What are the regulations for food trucks in Chicago? | 4/5 | 0 | 0 |  |
| **A** | `tree_removal` | Do I need a permit to cut down a tree on my property? | 4/5 | 0 | 0 |  |
| **D** | `lot_coverage_rm5` | What is the maximum lot coverage allowed in an RM-5 dis | 2/5 | 2 | 1 | gold section(s) found but not in top-3; 2 duplicate chunk(s) from same section:  |
| **B** | `landscaping_requirements` | What are the landscaping requirements for new construct | 4/5 | 1 | 0 | 1 duplicate chunk(s) from same section: 17-11-0200 |
| **A** | `rooftop_deck` | Can I build a rooftop deck on my building? | 3/5 | 0 | 0 |  |
| **C** | `liquor_school_distance` | How far does a bar need to be from a school to get a li | 5/5 | 2 | 0 | 2 duplicate chunk(s) from same section: 4-60-020; answer terms missing from resu |
| **B** | `restaurant_parking` | How many parking spots does a restaurant need to provid | 1/5 | 0 | 1 |  |
| **C** | `affordable_housing` | What are the affordable housing requirements for develo | 5/5 | 3 | 0 | 3 duplicate chunk(s) from same section: 2-44-080, 2-44-085 |
| **A** | `buildable_lot_definition` | What is the definition of a buildable lot under the Chi | 1/5 | 0 | 0 |  |

## Detailed Chunk Analysis

### `setback_single_family` — Grade C
**Q:** What are the setback requirements for a single-family home in Chicago?

- 2 duplicate chunk(s) from same section: 17-2-0300, 17-3-0400
- answer terms missing from results: ['feet']

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7406 | `17-2-0300` |  | (part 8 of 27)  3. When the subject lot abuts a corner lot fronting on the same street , the average |
| 2 |  | 0.7396 | `17-2-0500` |  | (part 2 of 12)  (b) Required front wall and rear wall setbacks may be reduced to match the predomina |
| 3 |  | 0.7336 | `17-3-0400` |  | (part 3 of 19)  17-3-0404 Front Setbacks. No front setback is required in B or C districts, except o |
| 4 | Y | 0.7331 | `17-2-0300` | frag(2) | (part 23 of 27)  [TABLE] Columns: District \| Minimum Side Setback Row 9: District: RM6; Minimum Side |
| 5 |  | 0.7266 | `17-3-0400` |  | (part 4 of 19)  17-3-0406 Side Setbacks. No side setbacks are required in B and C districts, except  |

---

### `home_occupation` — Grade D
**Q:** Can I run a small bakery business from my home?

- gold section(s) found but not in top-3
- 1 duplicate chunk(s) from same section: 4-8-020

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.6312 | `4-8-020` |  | (part 4 of 7)  (d) Shared kitchen – License required. No person shall engage in the business of a sh |
| 2 |  | 0.6223 | `4-8-039` |  | (part 1 of 7)  (a) (1) Shared kitchen user license required – Covered activities. A shared kitchen u |
| 3 |  | 0.6201 | `4-8-020` |  | (part 3 of 7)  (b) Wholesale food establishment – License required – Exceptions. Except as otherwise |
| 4 | Y | 0.6194 | `4-6-270` |  | (part 7 of 10)  (7) allow the total square footage of any home occupation, including any accessory b |
| 5 |  | 0.616 | `16-12-080` |  | (part 1 of 2)  (a) An urban homestead program shall be established in each enterprise zone. In this  |

---

### `minimum_lot_size` — Grade B
**Q:** What's the minimum lot size for building in an RS-3 zoning district?

- 2 duplicate chunk(s) from same section: 17-2-0300

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.749 | `17-2-0300` |  | (part 3 of 27)  17-2-0303-A Minimum Lot Area per Unit Standards. All development in R districts is s |
| 2 | Y | 0.73 | `17-2-0300` |  | (part 1 of 27)  17-2-0301 Lot Area.  17-2-0301-A Minimum Lot Area Standards. All development in R di |
| 3 | Y | 0.7292 | `17-2-0300` |  | (part 16 of 27)  [TABLE] Columns: District \| Minimum Lot Area* (square feet) Row 1: District: RS1; M |
| 4 |  | 0.7229 | `17-7-0590` |  | (part 2 of 3)  17-7-0593-A In the RS3 district, located in boundaries as identified in Section 17-7- |
| 5 |  | 0.7172 | `17-3-0400` | frag(1) | (part 18 of 19)  [TABLE] Columns: District \| Maximum Building Height (feet) - Lot frontage of 25 fee |

---

### `adu_allowed` — Grade C
**Q:** Are accessory dwelling units allowed in Chicago?

- 2 duplicate chunk(s) from same section: 17-9-0200
- answer terms missing from results: ['accessory dwelling', 'additional dwelling']

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.8064 | `17-9-0200` |  | (part 4 of 8)  17. Dwelling units contained within coach houses lawfully established after May 1, 20 |
| 2 |  | 0.7952 | `4-6-270` |  | (part 6 of 10)  (1) conduct a home occupation in violation of Section 17-9-0202 or other applicable  |
| 3 | Y | 0.793 | `17-9-0200` |  | (part 1 of 8)  17-9-0201 General.  17-9-0201-A Unless otherwise expressly stated in this Zoning Ordi |
| 4 | Y | 0.7813 | `17-9-0200` |  | (part 2 of 8)  2. That the 60% coverage limit does not apply to accessory garage buildings in the RM |
| 5 |  | 0.7732 | `13-72-020` |  | (part 9 of 10)  (2) A description of the location, ownership, and availability to unit owners and th |

---

### `noise_ordinance` — Grade A
**Q:** What are the noise ordinance rules in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.8494 | `8-32-010` |  | This chapter may be referred to as the Chicago Noise Ordinance.  Legislative history: (Added Coun. J |
| 2 |  | 0.8443 | `4-244-164` |  | (part 2 of 4)  (d) (1) A performer shall comply in all respects with the relevant portions of the no |
| 3 |  | 0.8352 | `10-8-070` |  | The making, causing or permitting to be made of any unnecessary noise of any kind whatsoever, or the |
| 4 |  | 0.827 | `4-224-012` |  | It shall be unlawful to maintain, within 200 feet of any residence, a machine shop or a foundry wher |
| 5 | Y | 0.8215 | `8-32-150` |  | For any noise source not specifically addressed in Part B of this chapter, except where exempted or  |

---

### `fence_height` — Grade F
**Q:** How tall can a fence be in a residential area?

- MISS: none of the 5 chunks match expected sections
- answer terms missing from results: ['height']

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.7533 | `17-11-0200` |  | (part 3 of 13)  (b) Visual screening must be located between the perimeter of the vehicular use area |
| 2 |  | 0.7382 | `7-28-070` |  | No yard, lot, premises or enclosure or part thereof, shall be used, kept, maintained, or operated, f |
| 3 |  | 0.7331 | `10-28-281.7` |  | (a) Fences shall be not less than six feet high of solid construction sheathed with one-inch lumber  |
| 4 |  | 0.7104 | `17-2-0300` |  | (part 14 of 27)  Figure 17-2-0310-C1  2. Facing Other Front or Rear Walls. When the front wall or re |
| 5 |  | 0.7096 | `7-12-050` |  | (part 4 of 10)  (1) While on the owner's property, the owner must securely confine the dangerous ani |

---

### `garage_conversion` — Grade A
**Q:** Can I convert my garage into a living space?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.6714 | `13-72-055` |  | A developer undertaking renovation of a building containing five or more dwelling units in anticipat |
| 2 |  | 0.6524 | `17-2-0500` |  | (part 6 of 12)  2. Required common open space must be located in one or more usable, common areas, e |
| 3 | Y | 0.645 | `18-28-403.10` |  | For the purpose of all garage ventilation requirements found in Table 18-28-403.3, the following rul |
| 4 | Y | 0.6423 | `18-28-901.5` |  | Gas appliances are not allowed in garages unless either:  1. The gas appliance is a direct vent heat |
| 5 |  | 0.6408 | `16-12-080` |  | (part 1 of 2)  (a) An urban homestead program shall be established in each enterprise zone. In this  |

---

### `short_term_rental` — Grade B
**Q:** What are the regulations for Airbnb and short-term rentals in Chicago?

- 1 duplicate chunk(s) from same section: 4-13-260

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.8081 | `4-13-260` |  | (part 4 of 5)  (11) Short term residential rental is located in a restricted residential zone and wa |
| 2 | Y | 0.8012 | `4-13-250` |  | Editor's note – Coun. J. 9-9-20, p. 20269, § 14 (as amended by Coun. J. 3-24-21, p. 28843, § 1), rep |
| 3 | Y | 0.7961 | `4-13-260` |  | (part 1 of 5)  (a) Conditions of ineligibility for listing. A short term residential rental shall be |
| 4 | Y | 0.7892 | `4-13-215` |  | The intermediary shall be required to make available in a conspicuous place on its platform an elect |
| 5 | Y | 0.7887 | `4-13-240` |  | (part 3 of 4)  (e) Additional reports and data. Each licensee under this Article II shall provide ad |

---

### `deck_setback` — Grade D
**Q:** How close to the property line can I build a deck?

- gold section(s) found but not in top-3
- answer terms missing from results: ['setback']

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.7131 | `17-9-0100` |  | (part 41 of 54)  7. Except in M, PMD and T districts, no freestanding facility may be located within |
| 2 |  | 0.708 | `17-8-0900` |  | (part 7 of 15)  5. Large retail developments and shopping centers should help reinforce the characte |
| 3 |  | 0.7044 | `10-28-283` |  | (part 1 of 4)  (A) Construction. No construction canopy shall be designed with less than six feet of |
| 4 |  | 0.7008 | `17-2-0500` |  | (part 6 of 12)  2. Required common open space must be located in one or more usable, common areas, e |
| 5 | Y | 0.7 | `17-2-0300` |  | (part 13 of 27)  2. unobstructed open space along all property lines other than street property line |

---

### `food_trucks` — Grade A
**Q:** What are the regulations for food trucks in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7923 | `4-8-037` |  | (part 1 of 4)  The City Council may from time to time define areas, in the interest of preserving pu |
| 2 |  | 0.7831 | `10-28-593` |  | (part 1 of 4)  The Department of Transportation shall review an Outdoor Dining Street Permit applica |
| 3 | Y | 0.7814 | `7-38-075` |  | (part 1 of 2)  (a) Every vehicle used by a mobile food vendor in the conduct of such business shall  |
| 4 | Y | 0.779 | `7-38-136` |  | (part 1 of 2)  (a) All mobile food trucks shall be equipped with a handwashing sink and a three-comp |
| 5 | Y | 0.7771 | `7-38-115` |  | (part 1 of 5)  (a) Mobile food vehicles shall move from place to place upon the public ways and shal |

---

### `tree_removal` — Grade A
**Q:** Do I need a permit to cut down a tree on my property?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7421 | `10-32-130` |  | No person shall remove any permitted device intended for the support or protection of a public tree  |
| 2 | Y | 0.7371 | `10-32-060` |  | No person other than the Deputy Commissioner shall plant, remove, trim, spray or chemically inject o |
| 3 | Y | 0.7208 | `10-32-120` |  | During the erection, alteration, repair, demolition or removal of any building or structure, or exca |
| 4 | Y | 0.7172 | `10-32-230` |  | In connection with the installation of parkway trees required to be installed pursuant to the provis |
| 5 |  | 0.7121 | `17-11-0200` |  | (part 5 of 13)  5. Existing trees that have a minimum caliper size of 2.5 inches may be counted towa |

---

### `lot_coverage_rm5` — Grade D
**Q:** What is the maximum lot coverage allowed in an RM-5 district?

- gold section(s) found but not in top-3
- 2 duplicate chunk(s) from same section: 17-5-0400, 17-2-0300
- answer terms missing from results: ['lot coverage', 'percent']

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.7438 | `17-2-0100` |  | (part 2 of 3)  17-2-0104 RM, Residential Multi-Unit Districts.  17-2-0104-A General. The primary pur |
| 2 |  | 0.7298 | `17-5-0400` |  | (part 1 of 3)  17-5-0401 General. Bulk and density standards in the M districts vary according to th |
| 3 |  | 0.7157 | `17-5-0400` | frag(3) | (part 3 of 3)  [TABLE] Columns: District \| Maximum Floor Area Ratio* Row 1: District: Dash 1; Maximu |
| 4 | Y | 0.7144 | `17-2-0300` |  | (part 3 of 27)  17-2-0303-A Minimum Lot Area per Unit Standards. All development in R districts is s |
| 5 | Y | 0.7116 | `17-2-0300` |  | (part 6 of 27)  17-2-0304-C Premiums. Multi-unit residential buildings located in an RM6 or RM6.5 di |

---

### `landscaping_requirements` — Grade B
**Q:** What are the landscaping requirements for new construction in Chicago?

- 1 duplicate chunk(s) from same section: 17-11-0200

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7933 | `17-11-0500` |  | 17-11-0501 All landscape materials required by this chapter must be installed in accordance with sta |
| 2 |  | 0.7794 | `17-8-0900` |  | (part 10 of 15)  17-8-0909 Parks, Open Space, and Landscaping.  17-8-0909-A General Intent. Planned  |
| 3 | Y | 0.7777 | `17-11-0200` |  | (part 5 of 13)  5. Existing trees that have a minimum caliper size of 2.5 inches may be counted towa |
| 4 | Y | 0.7754 | `17-11-0200` |  | (part 4 of 13)  3. Any pre-existing vehicular use areas must have ornamental fencing installed behin |
| 5 | Y | 0.7741 | `17-11-0400` |  | (part 2 of 2)  1. Develop industrial sites to mitigate environmental impact through thoughtful desig |

---

### `rooftop_deck` — Grade A
**Q:** Can I build a rooftop deck on my building?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7089 | `17-17-0300` |  | (part 7 of 14)  3. Solar photovoltaic or solar thermal panels in all districts are not considered wh |
| 2 |  | 0.7028 | `10-28-283` |  | (part 1 of 4)  (A) Construction. No construction canopy shall be designed with less than six feet of |
| 3 | Y | 0.7015 | `4-388-065` |  | (part 2 of 2)  (e) every deck built over the roof of the building shall be a noncombustible deck sur |
| 4 | Y | 0.6891 | `4-388-170` |  | (part 2 of 2)  (c) Subject to Section 4-388-175(a), the highest deck level and above shall be open a |
| 5 |  | 0.6789 | `17-8-0900` |  | (part 9 of 15)  1. Buildings should have a clearly defined vertical appearance, comprised of a base, |

---

### `liquor_school_distance` — Grade C
**Q:** How far does a bar need to be from a school to get a liquor license?

- 2 duplicate chunk(s) from same section: 4-60-020
- answer terms missing from results: ['feet']

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7502 | `4-60-020` |  | (part 2 of 5)  (d) In addition to the restrictions cited in Section 6-11 of the Illinois Liquor Cont |
| 2 | Y | 0.7171 | `4-60-020` |  | (part 4 of 5)  (3) An applicant seeking a distance requirement reduction shall make a written submis |
| 3 | Y | 0.7152 | `4-60-020` |  | (part 1 of 5)  (a) No person shall sell at retail any alcoholic liquor without first having obtained |
| 4 | Y | 0.705 | `4-60-074` |  | (part 2 of 6)  (b) A separate Riverwalk Venue liquor license shall be required for each outdoor loca |
| 5 | Y | 0.7035 | `4-60-076` |  | (part 2 of 3)  (c) A separate Outdoor Entertainment Venue liquor license shall be required for each  |

---

### `restaurant_parking` — Grade B
**Q:** How many parking spots does a restaurant need to provide?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.7252 | `7-38-115` |  | (part 2 of 5)  (f) No operator of a mobile food vehicle shall park or stand such vehicle within 200  |
| 2 |  | 0.7144 | `10-36-330` |  | (part 3 of 5)  (vi) Remote parking, Economy Lot E – valet parking: A maximum rate not to exceed $22. |
| 3 | Y | 0.7133 | `17-10-0200` | frag(2) | (part 20 of 26)  [TABLE] Columns: District \| Minimum Automobile Parking Ratio (per unit or gross flo |
| 4 |  | 0.7103 | `4-232-095` |  | Any person who engages in the business of valet parking operator without first having obtained the r |
| 5 |  | 0.7062 | `17-10-0900` |  | (part 5 of 8)  17-10-0904-C Valet Parking. An accessible passenger loading zone must be provided at  |

---

### `affordable_housing` — Grade C
**Q:** What are the affordable housing requirements for developers in Chicago?

- 3 duplicate chunk(s) from same section: 2-44-080, 2-44-085

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.825 | `2-44-080` |  | (part 12 of 30)  (2) for an existing building that contains a mixed-use occupancy with one use being |
| 2 | Y | 0.8101 | `2-44-085` |  | (part 14 of 41)  (F) Required percentage of affordable units. The percentage of dwelling units requi |
| 3 | Y | 0.8086 | `2-44-080` |  | (part 11 of 30)  (2) City land sales. Whenever the City sells real property to any developer and suc |
| 4 | Y | 0.805 | `2-44-080` |  | (part 13 of 30)  (2) Higher income areas. In higher income areas, a developer subject to the provisi |
| 5 | Y | 0.8044 | `2-44-085` |  | (part 15 of 41)  (3) Owner-occupied projects. Developers of owner-occupied projects shall provide th |

---

### `buildable_lot_definition` — Grade A
**Q:** What is the definition of a buildable lot under the Chicago zoning code?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.8357 | `16-4-050` |  | (part 2 of 2)  (h) Zoning Lot. "Zoning lot" means a single tract of land located within a single blo |
| 2 |  | 0.8027 | `17-8-0300` |  | Planned developments may consist of one or more lots to be developed as a unit, whether simultaneous |
| 3 | Y | 0.7966 | `17-17-0300` |  | (part 1 of 14)  17-17-0301 Division of Improved Zoning Lots. No improved zoning lot may be divided i |
| 4 |  | 0.788 | `17-15-0200` |  | 17-15-0201 Definition. A nonconforming lot is a tract of land lawfully established as a lot on a pla |
| 5 |  | 0.7851 | `17-1-1300` |  | No more than one principal detached residential building may be located on a zoning lot , and a prin |

---

## Category Summary

| Category | Grades | Gold Hits | Dups | Frags |
|---|---|---:|---:|---:|
| accessory_structures | F A | 3/10 | 0 | 0 |
| definitions | A | 1/5 | 0 | 0 |
| dimensional_standards | C B D D | 8/20 | 6 | 3 |
| licensing | B A C | 14/15 | 3 | 0 |
| non_zoning | A A | 6/10 | 0 | 0 |
| parking | B | 1/5 | 0 | 1 |
| planned_development | C | 5/5 | 3 | 0 |
| site_design | B | 4/5 | 1 | 0 |
| use_rules | D C A | 6/15 | 3 | 0 |

## Key Findings

*(auto-generated from benchmark data)*

### Problem Queries

- **setback_single_family** (grade C): 2 duplicate chunk(s) from same section: 17-2-0300, 17-3-0400; answer terms missing from results: ['feet']
- **home_occupation** (grade D): gold section(s) found but not in top-3; 1 duplicate chunk(s) from same section: 4-8-020
- **adu_allowed** (grade C): 2 duplicate chunk(s) from same section: 17-9-0200; answer terms missing from results: ['accessory dwelling', 'additional dwelling']
- **fence_height** (grade F): MISS: none of the 5 chunks match expected sections; answer terms missing from results: ['height']
- **deck_setback** (grade D): gold section(s) found but not in top-3; answer terms missing from results: ['setback']
- **lot_coverage_rm5** (grade D): gold section(s) found but not in top-3; 2 duplicate chunk(s) from same section: 17-5-0400, 17-2-0300; answer terms missing from results: ['lot coverage', 'percent']
- **liquor_school_distance** (grade C): 2 duplicate chunk(s) from same section: 4-60-020; answer terms missing from results: ['feet']
- **affordable_housing** (grade C): 3 duplicate chunk(s) from same section: 2-44-080, 2-44-085

### Section Duplication

These queries returned multiple chunks from the same section, wasting result diversity:

- **setback_single_family**: {'17-2-0300': 2, '17-3-0400': 2}
- **minimum_lot_size**: {'17-2-0300': 3}
- **adu_allowed**: {'17-9-0200': 3}
- **lot_coverage_rm5**: {'17-5-0400': 2, '17-2-0300': 2}
- **liquor_school_distance**: {'4-60-020': 3}
- **affordable_housing**: {'2-44-080': 3, '2-44-085': 2}
