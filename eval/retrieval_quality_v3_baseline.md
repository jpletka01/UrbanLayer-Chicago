# Retrieval Quality Benchmark

## Summary

- **Queries**: 18
- **Chunks evaluated**: 87
- **Grades**: A=13  B=1  C=4  D=0  F=0

### Aggregate Metrics

| Metric | Count | % |
|---|---:|---:|
| Gold section hits | 48/87 | 55% |
| Duplicate section slots | 0/87 | 0% |
| Table fragments (<=3 rows) | 1/87 | 1% |
| Low-content chunks | 0/87 | 0% |

## Per-Query Results

| Grade | ID | Question | Gold Hits | Dups | Table Frags | Issues |
|:---:|---|---|:---:|:---:|:---:|---|
| **A** | `setback_single_family` | What are the setback requirements for a single-family h | 1/5 | 0 | 0 |  |
| **A** | `home_occupation` | Can I run a small bakery business from my home? | 1/5 | 0 | 0 |  |
| **C** | `minimum_lot_size` | What's the minimum lot size for building in an RS-3 zon | 1/5 | 0 | 0 | answer terms missing from results: ['square feet'] |
| **C** | `adu_allowed` | Are accessory dwelling units allowed in Chicago? | 2/5 | 0 | 0 | answer terms missing from results: ['accessory dwelling'] |
| **A** | `noise_ordinance` | What are the noise ordinance rules in Chicago? | 4/5 | 0 | 0 |  |
| **A** | `fence_height` | How tall can a fence be in a residential area? | 3/5 | 0 | 0 |  |
| **A** | `garage_conversion` | Can I convert my garage into a living space? | 3/5 | 0 | 0 |  |
| **A** | `short_term_rental` | What are the regulations for Airbnb and short-term rent | 4/5 | 0 | 0 |  |
| **A** | `deck_setback` | How close to the property line can I build a deck? | 1/5 | 0 | 0 |  |
| **A** | `food_trucks` | What are the regulations for food trucks in Chicago? | 4/5 | 0 | 0 |  |
| **A** | `tree_removal` | Do I need a permit to cut down a tree on my property? | 4/5 | 0 | 0 |  |
| **C** | `lot_coverage_rm5` | What is the maximum lot coverage allowed in an RM-5 dis | 1/5 | 0 | 0 | answer terms missing from results: ['lot coverage', 'percent'] |
| **A** | `landscaping_requirements` | What are the landscaping requirements for new construct | 4/5 | 0 | 0 |  |
| **A** | `rooftop_deck` | Can I build a rooftop deck on my building? | 5/5 | 0 | 0 |  |
| **C** | `liquor_school_distance` | How far does a bar need to be from a school to get a li | 5/5 | 0 | 0 | answer terms missing from results: ['feet'] |
| **B** | `restaurant_parking` | How many parking spots does a restaurant need to provid | 1/5 | 0 | 1 |  |
| **A** | `affordable_housing` | What are the affordable housing requirements for develo | 2/2 | 0 | 0 |  |
| **A** | `buildable_lot_definition` | What is the definition of a buildable lot under the Chi | 2/5 | 0 | 0 |  |

## Detailed Chunk Analysis

### `setback_single_family` — Grade A
**Q:** What are the setback requirements for a single-family home in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.6993 | `17-2-0500` |  | (part 3 of 9)  (c) The minimum separation at the ground-floor only may be reduced to 20 feet for int |
| 2 |  | 0.6817 | `17-3-0400` |  | (part 3 of 16)  17-3-0404 Front Setbacks. No front setback is required in B or C districts, except o |
| 3 | Y | 0.6812 | `17-2-0300` |  | (part 19 of 23)  [TABLE] Columns: District \| Minimum Side Setback Row 1: District: RS1; Minimum Side |
| 4 |  | 0.6782 | `17-17-0300` |  | (part 9 of 14)  [TABLE] Columns: Obstruction/Projection into Required Setback \| Front \| Side \| Rear  |
| 5 |  | 0.6696 | `17-4-0400` |  | (part 5 of 11)  2. DR Districts. Buildings and structures in DR districts are subject to the R distr |

---

### `home_occupation` — Grade A
**Q:** Can I run a small bakery business from my home?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.5258 | `4-8-020` |  | (part 3 of 7)  (b) Wholesale food establishment – License required – Exceptions. Except as otherwise |
| 2 | Y | 0.5174 | `4-6-270` |  | (part 5 of 10)  (24) any activity that requires a children's services facility license under Chapter |
| 3 |  | 0.5148 | `4-8-048` |  | (part 2 of 2)  (b) Applicants for a mobile food vendor license to engage in a mobile food dispenser, |
| 4 |  | 0.5071 | `4-8-036` |  | (part 4 of 5)  (b) Except as otherwise provided in this subsection, in addition to the general appli |
| 5 |  | 0.5023 | `4-8-032` |  | (part 2 of 2)  (b) Prior to issuing a retail food establishment license which shall authorize a lice |

---

### `minimum_lot_size` — Grade C
**Q:** What's the minimum lot size for building in an RS-3 zoning district?

- answer terms missing from results: ['square feet']

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7503 | `17-2-0300` |  | (part 3 of 23)  17-2-0303-A Minimum Lot Area per Unit Standards. All development in R districts is s |
| 2 |  | 0.7038 | `17-7-0590` |  | (part 2 of 3)  17-7-0593-A In the RS3 district, located in boundaries as identified in Section 17-7- |
| 3 |  | 0.6764 | `17-3-0400` |  | (part 3 of 16)  17-3-0404 Front Setbacks. No front setback is required in B or C districts, except o |
| 4 |  | 0.6648 | `17-17-0300` |  | (part 1 of 14)  17-17-0301 Division of Improved Zoning Lots. No improved zoning lot may be divided i |
| 5 |  | 0.6636 | `17-2-0100` |  | (part 1 of 3)  17-2-0101 Generally. The "R", residential districts are intended to create, maintain  |

---

### `adu_allowed` — Grade C
**Q:** Are accessory dwelling units allowed in Chicago?

- answer terms missing from results: ['accessory dwelling']

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.769 | `17-9-0200` |  | (part 4 of 8)  17. Dwelling units contained within coach houses lawfully established after May 1, 20 |
| 2 |  | 0.7309 | `4-6-270` |  | (part 6 of 10)  (1) conduct a home occupation in violation of Section 17-9-0202 or other applicable  |
| 3 | Y | 0.7171 | `17-7-0570` |  | (part 1 of 8)  17-7-0571 Purpose. To establish designated areas for the legal development of Additio |
| 4 |  | 0.717 | `17-10-1000` |  | (part 4 of 9)  2. Allowed automotive lifts within residential buildings shall be operated by a valet |
| 5 |  | 0.7098 | `17-9-0100` |  | (part 14 of 54)  17-9-0113.1 Residential Storage Warehouse. Residential storage warehouses are permi |

---

### `noise_ordinance` — Grade A
**Q:** What are the noise ordinance rules in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7663 | `8-32-010` |  | This chapter may be referred to as the Chicago Noise Ordinance.  Legislative history: (Added Coun. J |
| 2 |  | 0.7373 | `4-244-164` |  | (part 2 of 4)  (d) (1) A performer shall comply in all respects with the relevant portions of the no |
| 3 | Y | 0.7191 | `8-32-060` |  | An area shall be designated a noise sensitive zone following passage of an ordinance amending Sectio |
| 4 | Y | 0.7103 | `8-32-030` |  | The superintendent of police is authorized to adopt such rules and regulations as he may deem approp |
| 5 | Y | 0.7048 | `8-32-070` |  | (part 1 of 2)  (a) No person on the public way shall employ any device or instrument that creates or |

---

### `fence_height` — Grade A
**Q:** How tall can a fence be in a residential area?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.6777 | `17-11-0200` |  | (part 2 of 12)  17-11-0201-F The provisions of Sections 17-11-0201-B, 17-11-0201-C, 17-11-0201-D, an |
| 2 | Y | 0.652 | `17-5-0600` |  | (part 2 of 2)  17-5-0602-A Screening from Other Zoning Districts. All outdoor work areas situated on |
| 3 |  | 0.6402 | `17-2-0500` |  | (part 4 of 9)  (a) When the end wall of a row of townhouse units faces the front wall or rear wall o |
| 4 | Y | 0.634 | `10-28-281.7` |  | (a) Fences shall be not less than six feet high of solid construction sheathed with one-inch lumber  |
| 5 |  | 0.6234 | `17-2-0300` |  | (part 14 of 23)  Figure 17-2-0310-C1  2. Facing Other Front or Rear Walls. When the front wall or re |

---

### `garage_conversion` — Grade A
**Q:** Can I convert my garage into a living space?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.5607 | `18-28-901.5` |  | Gas appliances are not allowed in garages unless either:  1. The gas appliance is a direct vent heat |
| 2 | Y | 0.5543 | `18-28-403.10` |  | For the purpose of all garage ventilation requirements found in Table 18-28-403.3, the following rul |
| 3 |  | 0.5342 | `17-9-0100` |  | (part 3 of 54)  4. The residential portion of the business live/work unit shall include cooking spac |
| 4 | Y | 0.5246 | `18-28-403.13` |  | If a mechanical ventilating system is used in a public garage, the system shall not be required to o |
| 5 |  | 0.5218 | `11-6-060` |  | (part 6 of 9)  (10) Replace or retrofit existing High Density Discharge (H.I.D.) fixtures, such as m |

---

### `short_term_rental` — Grade A
**Q:** What are the regulations for Airbnb and short-term rentals in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7128 | `4-13-240` |  | (part 1 of 4)  (a) Departmental report – Required. Each licensee under this Article II shall submit  |
| 2 |  | 0.7015 | `4-6-300` |  | (part 19 of 37)  (10) Notification to police of illegal activity – Required. If a licensee knows or  |
| 3 | Y | 0.6987 | `4-13-220` |  | (part 3 of 5)  (c) Identification of local contact person – Required. Each licensee under this Artic |
| 4 | Y | 0.698 | `4-13-260` |  | (part 3 of 5)  (8) Shared housing host is not a natural person. If the short term residential rental |
| 5 | Y | 0.6806 | `4-13-215` |  | The intermediary shall be required to make available in a conspicuous place on its platform an elect |

---

### `deck_setback` — Grade A
**Q:** How close to the property line can I build a deck?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.6661 | `17-17-0200` |  | (part 15 of 42)  17-17-0260 Front Property Line. That property line that abuts or is along an existi |
| 2 | Y | 0.6558 | `17-2-0300` |  | (part 13 of 23)  2. unobstructed open space along all property lines other than street property line |
| 3 |  | 0.6287 | `17-2-0500` |  | (part 3 of 9)  (c) The minimum separation at the ground-floor only may be reduced to 20 feet for int |
| 4 |  | 0.6285 | `17-3-0400` |  | (part 5 of 16)  17-3-0407-B General. Unless otherwise expressly stated, exterior building walls are  |
| 5 |  | 0.6254 | `17-12-1000` |  | (part 8 of 16)  2. Off-premise signs are prohibited entirely within 100 feet of any residential dist |

---

### `food_trucks` — Grade A
**Q:** What are the regulations for food trucks in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.7601 | `9-64-170` |  | (part 8 of 15)  (iii) Parking prohibited between 2:00 A.M. and 7:00 A.M. It shall be unlawful for an |
| 2 | Y | 0.7456 | `7-38-134` |  | (part 2 of 2)  (3) food products remaining after each day’s operation shall be stored only in a lice |
| 3 | Y | 0.7411 | `7-38-128` |  | (a) Except as otherwise provided in this chapter, the Commissioner of Health shall have authority to |
| 4 | Y | 0.7238 | `7-38-138` |  | (a) The commissary linked to a mobile food preparer must have a servicing area approved by the Depar |
| 5 | Y | 0.7219 | `7-38-136` |  | (part 1 of 2)  (a) All mobile food trucks shall be equipped with a handwashing sink and a three-comp |

---

### `tree_removal` — Grade A
**Q:** Do I need a permit to cut down a tree on my property?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.6058 | `10-32-120` |  | During the erection, alteration, repair, demolition or removal of any building or structure, or exca |
| 2 | Y | 0.5832 | `10-32-130` |  | No person shall remove any permitted device intended for the support or protection of a public tree  |
| 3 | Y | 0.5769 | `10-32-110` |  | No person shall secure, hang, fasten, attach or run any rope, wire, sign, decoration, electrical dev |
| 4 | Y | 0.5704 | `10-32-060` |  | No person other than the Deputy Commissioner shall plant, remove, trim, spray or chemically inject o |
| 5 |  | 0.5642 | `17-9-0100` |  | (part 34 of 54)  c. Existing mature trees (more than 3 inches in diameter) and natural land forms on |

---

### `lot_coverage_rm5` — Grade C
**Q:** What is the maximum lot coverage allowed in an RM-5 district?

- answer terms missing from results: ['lot coverage', 'percent']

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.6376 | `17-2-0300` |  | (part 6 of 23)  17-2-0304-C Premiums. Multi-unit residential buildings located in an RM6 or RM6.5 di |
| 2 |  | 0.6162 | `17-2-0100` |  | (part 2 of 3)  17-2-0104 RM, Residential Multi-Unit Districts.  17-2-0104-A General. The primary pur |
| 3 |  | 0.604 | `17-5-0400` |  | (part 1 of 3)  17-5-0401 General. Bulk and density standards in the M districts vary according to th |
| 4 |  | 0.5806 | `17-6-0400` |  | (part 6 of 36)  a. this on-site production limit shall not apply in PMD 4B, and the Zoning Board of  |
| 5 |  | 0.5786 | `17-4-0400` |  | (part 1 of 11)  17-4-0401 General. Bulk and density standards in the "D" districts vary according to |

---

### `landscaping_requirements` — Grade A
**Q:** What are the landscaping requirements for new construction in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7569 | `17-11-0400` |  | (part 1 of 2)  In the event that the City Council or Plan Commission adopts plans, designs or guidel |
| 2 |  | 0.7371 | `10-32-220` |  | (part 3 of 3)  The soil volume and composition for required parkway trees or planters shall meet the |
| 3 | Y | 0.7154 | `17-11-0200` |  | (part 5 of 12)  5. Existing trees that have a minimum caliper size of 2.5 inches may be counted towa |
| 4 | Y | 0.7022 | `17-11-0100` |  | (part 2 of 3)  17-11-0102-C construction, repair or rehabilitation of or upon any detached house , t |
| 5 | Y | 0.6939 | `17-11-0500` |  | 17-11-0501 All landscape materials required by this chapter must be installed in accordance with sta |

---

### `rooftop_deck` — Grade A
**Q:** Can I build a rooftop deck on my building?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.724 | `4-388-065` |  | (part 2 of 2)  (e) every deck built over the roof of the building shall be a noncombustible deck sur |
| 2 | Y | 0.7018 | `4-388-170` |  | (part 2 of 2)  (c) Subject to Section 4-388-175(a), the highest deck level and above shall be open a |
| 3 | Y | 0.6942 | `4-388-175` |  | (part 1 of 3)  The following provisions apply to buildings in the Wrigley Field Adjacent Area in whi |
| 4 | Y | 0.6871 | `4-388-220` |  | (a) Notwithstanding any provision of the building code to the contrary, no building permit shall be  |
| 5 | Y | 0.6814 | `17-17-0300` |  | (part 7 of 14)  3. Solar photovoltaic or solar thermal panels in all districts are not considered wh |

---

### `liquor_school_distance` — Grade C
**Q:** How far does a bar need to be from a school to get a liquor license?

- answer terms missing from results: ['feet']

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.647 | `4-60-020` |  | (part 2 of 5)  (d) In addition to the restrictions cited in Section 6-11 of the Illinois Liquor Cont |
| 2 | Y | 0.6145 | `4-60-040` |  | (part 11 of 12)  If the applicant is seeking a liquor license for a premises and the local liquor co |
| 3 | Y | 0.6023 | `4-60-010` |  | (part 8 of 8)  "Tavern license" means a city license for the retail sale of alcoholic liquor in an e |
| 4 | Y | 0.6004 | `4-60-110` |  | (part 1 of 3)  (a) A person licensed pursuant to this chapter is authorized to sell alcoholic liquor |
| 5 | Y | 0.5866 | `4-60-076` |  | (part 2 of 3)  (c) A separate Outdoor Entertainment Venue liquor license shall be required for each  |

---

### `restaurant_parking` — Grade B
**Q:** How many parking spots does a restaurant need to provide?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.6536 | `7-38-115` |  | (part 2 of 5)  (f) No operator of a mobile food vehicle shall park or stand such vehicle within 200  |
| 2 |  | 0.6064 | `17-10-0100` |  | (part 10 of 12)  17-10-0102-D Small Dwelling Units. The Zoning Administrator is authorized to approv |
| 3 | Y | 0.6 | `17-10-0200` | frag(1) | (part 22 of 22)  [TABLE] Columns: District \| Minimum Automobile Parking Ratio (Per unit or gross flo |
| 4 |  | 0.5883 | `17-10-0400` |  | (part 1 of 3)  The following rules apply when calculating off-street parking requirements.  17-10-04 |
| 5 |  | 0.5838 | `4-232-090` |  | Sections 4-232-060 through 4-232-080 shall not apply to any business establishment that provides pat |

---

### `affordable_housing` — Grade A
**Q:** What are the affordable housing requirements for developers in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.8166 | `2-44-080` |  | (part 18 of 30)  (2) To the extent that redevelopment plans approved pursuant to the TIF Act provide |
| 2 | Y | 0.8154 | `2-44-085` |  | (part 15 of 39)  (3) Owner-occupied projects. Developers of owner-occupied projects shall provide th |

---

### `buildable_lot_definition` — Grade A
**Q:** What is the definition of a buildable lot under the Chicago zoning code?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7987 | `16-4-050` |  | (part 2 of 2)  (h) Zoning Lot. "Zoning lot" means a single tract of land located within a single blo |
| 2 | Y | 0.7313 | `17-15-0200` |  | 17-15-0201 Definition. A nonconforming lot is a tract of land lawfully established as a lot on a pla |
| 3 |  | 0.7107 | `17-8-0300` |  | Planned developments may consist of one or more lots to be developed as a unit, whether simultaneous |
| 4 |  | 0.7064 | `17-2-0300` |  | (part 1 of 23)  17-2-0301 Lot Area.  17-2-0301-A Minimum Lot Area Standards. All development in R di |
| 5 |  | 0.6929 | `17-4-0400` |  | (part 2 of 11)  17-4-0404-C MLA Reduction for Transit-Served Locations. Projects in D-3 districts lo |

---

## Category Summary

| Category | Grades | Gold Hits | Dups | Frags |
|---|---|---:|---:|---:|
| accessory_structures | A A | 8/10 | 0 | 0 |
| definitions | A | 2/5 | 0 | 0 |
| dimensional_standards | A C A C | 4/20 | 0 | 0 |
| licensing | A A C | 13/15 | 0 | 0 |
| non_zoning | A A | 8/10 | 0 | 0 |
| parking | B | 1/5 | 0 | 1 |
| planned_development | A | 2/2 | 0 | 0 |
| site_design | A | 4/5 | 0 | 0 |
| use_rules | A C A | 6/15 | 0 | 0 |

## Key Findings

*(auto-generated from benchmark data)*

### Problem Queries

- **minimum_lot_size** (grade C): answer terms missing from results: ['square feet']
- **adu_allowed** (grade C): answer terms missing from results: ['accessory dwelling']
- **lot_coverage_rm5** (grade C): answer terms missing from results: ['lot coverage', 'percent']
- **liquor_school_distance** (grade C): answer terms missing from results: ['feet']
