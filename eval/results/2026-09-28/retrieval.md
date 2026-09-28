# Retrieval Quality Benchmark

## Summary

- **Queries**: 28
- **Chunks evaluated**: 137
- **Grades**: A=24  B=4  C=0  D=0  F=0

### Aggregate Metrics

| Metric | Count | % |
|---|---:|---:|
| Gold section hits | 65/137 | 47% |
| Duplicate section slots | 0/137 | 0% |
| Table fragments (<=3 rows) | 4/137 | 3% |
| Low-content chunks | 0/137 | 0% |

## Per-Query Results

| Grade | ID | Question | Gold Hits | Dups | Table Frags | Issues |
|:---:|---|---|:---:|:---:|:---:|---|
| **A** | `setback_single_family` | What are the setback requirements for a single-family h | 2/5 | 0 | 0 |  |
| **A** | `home_occupation` | Can I run a small bakery business from my home? | 1/5 | 0 | 0 |  |
| **A** | `minimum_lot_size` | What's the minimum lot size for building in an RS-3 zon | 1/5 | 0 | 0 |  |
| **A** | `adu_allowed` | Are accessory dwelling units allowed in Chicago? | 2/5 | 0 | 0 |  |
| **A** | `noise_ordinance` | What are the noise ordinance rules in Chicago? | 4/5 | 0 | 0 |  |
| **A** | `fence_height` | How tall can a fence be in a residential area? | 3/5 | 0 | 0 |  |
| **A** | `garage_conversion` | Can I convert my garage into a living space? | 3/5 | 0 | 0 |  |
| **A** | `short_term_rental` | What are the regulations for Airbnb and short-term rent | 2/5 | 0 | 0 |  |
| **A** | `deck_setback` | How close to the property line can I build a deck? | 1/5 | 0 | 0 |  |
| **A** | `food_trucks` | What are the regulations for food trucks in Chicago? | 4/5 | 0 | 0 |  |
| **A** | `tree_removal` | Do I need a permit to cut down a tree on my property? | 4/5 | 0 | 0 |  |
| **B** | `lot_coverage_rm5` | What is the maximum lot coverage allowed in an RM-5 dis | 1/5 | 0 | 1 |  |
| **A** | `landscaping_requirements` | What are the landscaping requirements for new construct | 3/5 | 0 | 0 |  |
| **A** | `rooftop_deck` | Can I build a rooftop deck on my building? | 2/5 | 0 | 0 |  |
| **A** | `liquor_school_distance` | How far does a bar need to be from a school to get a li | 5/5 | 0 | 0 |  |
| **B** | `restaurant_parking` | How many parking spots does a restaurant need to provid | 1/5 | 0 | 1 |  |
| **A** | `affordable_housing` | What are the affordable housing requirements for develo | 2/2 | 0 | 0 |  |
| **A** | `buildable_lot_definition` | What is the definition of a buildable lot under the Chi | 2/5 | 0 | 0 |  |
| **B** | `b3_far` | What is the maximum FAR in a B3-2 community shopping di | 2/5 | 0 | 1 |  |
| **A** | `m1_setbacks` | What are the setback requirements in an M1 limited manu | 2/5 | 0 | 0 |  |
| **A** | `loading_requirements` | What are the off-street loading dock requirements for c | 1/5 | 0 | 0 |  |
| **A** | `transition_zone` | What are the transition zone buffer requirements betwee | 3/5 | 0 | 0 |  |
| **A** | `cannabis_dispensary` | What are the zoning regulations for cannabis dispensari | 1/5 | 0 | 0 |  |
| **A** | `pd_process` | What is the planned development approval process in Chi | 5/5 | 0 | 0 |  |
| **B** | `b1_height` | What is the maximum building height in a B1-1 neighborh | 1/5 | 0 | 1 |  |
| **A** | `parking_residential_multifamily` | How many parking spaces are required for a multi-family | 2/5 | 0 | 0 |  |
| **A** | `demolition_permit` | What are the requirements for a demolition permit in Ch | 3/5 | 0 | 0 |  |
| **A** | `coach_house_adu` | What are the rules for building a coach house or access | 2/5 | 0 | 0 |  |

## Detailed Chunk Analysis

### `setback_single_family` — Grade A
**Q:** What are the setback requirements for a single-family home in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.6935 | `17-2-0500` |  | (part 3 of 9)  (c) The minimum separation at the ground-floor only may be reduced to 20 feet for int |
| 2 | Y | 0.6736 | `17-17-0300` |  | (part 9 of 14)  [TABLE] Columns: Obstruction/Projection into Required Setback \| Front \| Side \| Rear  |
| 3 |  | 0.6652 | `17-3-0400` |  | (part 3 of 16)  17-3-0404 Front Setbacks. No front setback is required in B or C districts, except o |
| 4 | Y | 0.6647 | `17-2-0300` |  | (part 19 of 23)  [TABLE] Columns: District \| Minimum Side Setback Row 1: District: RS1; Minimum Side |
| 5 |  | 0.6537 | `17-4-0400` |  | (part 5 of 11)  2. DR Districts. Buildings and structures in DR districts are subject to the R distr |

---

### `home_occupation` — Grade A
**Q:** Can I run a small bakery business from my home?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.5105 | `4-6-270` |  | (part 5 of 10)  (24) any activity that requires a children's services facility license under Chapter |
| 2 |  | 0.5067 | `4-8-020` |  | (part 3 of 7)  (b) Wholesale food establishment – License required – Exceptions. Except as otherwise |
| 3 |  | 0.4963 | `4-8-048` |  | (part 2 of 2)  (b) Applicants for a mobile food vendor license to engage in a mobile food dispenser, |
| 4 |  | 0.489 | `4-8-036` |  | (part 4 of 5)  (b) Except as otherwise provided in this subsection, in addition to the general appli |
| 5 |  | 0.4845 | `4-8-032` |  | (part 2 of 2)  (b) Prior to issuing a retail food establishment license which shall authorize a lice |

---

### `minimum_lot_size` — Grade A
**Q:** What's the minimum lot size for building in an RS-3 zoning district?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7508 | `17-2-0300` |  | (part 3 of 23)  17-2-0303-A Minimum Lot Area per Unit Standards. All development in R districts is s |
| 2 |  | 0.698 | `17-7-0590` |  | (part 2 of 3)  17-7-0593-A In the RS3 district, located in boundaries as identified in Section 17-7- |
| 3 |  | 0.6694 | `17-3-0400` |  | (part 3 of 16)  17-3-0404 Front Setbacks. No front setback is required in B or C districts, except o |
| 4 |  | 0.6616 | `17-17-0300` |  | (part 1 of 14)  17-17-0301 Division of Improved Zoning Lots. No improved zoning lot may be divided i |
| 5 |  | 0.6569 | `17-2-0100` |  | (part 1 of 3)  17-2-0101 Generally. The "R", residential districts are intended to create, maintain  |

---

### `adu_allowed` — Grade A
**Q:** Are accessory dwelling units allowed in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.8142 | `17-9-0200` |  | (part 4 of 8)  17. Dwelling units contained within coach houses lawfully established after May 1, 20 |
| 2 | Y | 0.7618 | `17-7-0570` |  | (part 2 of 8)  (1) Annual limits. In the zoning districts specified in the table below, no more than |
| 3 |  | 0.7247 | `17-15-0300` |  | (part 3 of 6)  17-15-0303-C Detached houses that are a nonconforming use in a B, C or M district may |
| 4 |  | 0.7168 | `17-10-1000` |  | (part 4 of 9)  2. Allowed automotive lifts within residential buildings shall be operated by a valet |
| 5 |  | 0.7154 | `14B-11-1107` |  | (part 6 of 16)  1107.6.2.2.1.2 Other than multi-story housing.  In buildings three stories or less i |

---

### `noise_ordinance` — Grade A
**Q:** What are the noise ordinance rules in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7653 | `8-32-010` |  | This chapter may be referred to as the Chicago Noise Ordinance.  Legislative history: (Added Coun. J |
| 2 |  | 0.738 | `4-244-164` |  | (part 2 of 4)  (d) (1) A performer shall comply in all respects with the relevant portions of the no |
| 3 | Y | 0.7209 | `8-32-060` |  | An area shall be designated a noise sensitive zone following passage of an ordinance amending Sectio |
| 4 | Y | 0.7126 | `8-32-030` |  | The superintendent of police is authorized to adopt such rules and regulations as he may deem approp |
| 5 | Y | 0.707 | `8-32-090` |  | (part 2 of 2)  (e) The Chief Sustainability Officer is authorized to promulgate rules to enforce thi |

---

### `fence_height` — Grade A
**Q:** How tall can a fence be in a residential area?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.6966 | `17-11-0200` |  | (part 2 of 12)  17-11-0201-F The provisions of Sections 17-11-0201-B, 17-11-0201-C, 17-11-0201-D, an |
| 2 | Y | 0.6578 | `17-5-0600` |  | (part 2 of 2)  17-5-0602-A Screening from Other Zoning Districts. All outdoor work areas situated on |
| 3 |  | 0.6466 | `17-2-0500` |  | (part 4 of 9)  (a) When the end wall of a row of townhouse units faces the front wall or rear wall o |
| 4 |  | 0.6343 | `14B-31-3114` |  | (part 1 of 2)  The following language is adopted as a new Section 3114:  " 3114. FENCES  3114.1 Gene |
| 5 | Y | 0.6261 | `10-28-281.7` |  | (a) Fences shall be not less than six feet high of solid construction sheathed with one-inch lumber  |

---

### `garage_conversion` — Grade A
**Q:** Can I convert my garage into a living space?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.5513 | `18-28-901.5` |  | Gas appliances are not allowed in garages unless either:  1. The gas appliance is a direct vent heat |
| 2 |  | 0.5339 | `14N-R5-R505` |  | The provisions of Section R505 of IECC-RE are not adopted. The following is adopted as Section R505: |
| 3 | Y | 0.5335 | `18-28-403.10` |  | For the purpose of all garage ventilation requirements found in Table 18-28-403.3, the following rul |
| 4 |  | 0.5263 | `17-9-0100` |  | (part 3 of 54)  4. The residential portion of the business live/work unit shall include cooking spac |
| 5 | Y | 0.5173 | `18-28-403.13` |  | If a mechanical ventilating system is used in a public garage, the system shall not be required to o |

---

### `short_term_rental` — Grade A
**Q:** What are the regulations for Airbnb and short-term rentals in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7052 | `4-13-260` |  | (part 3 of 5)  (8) Shared housing host is not a natural person. If the short term residential rental |
| 2 |  | 0.7035 | `4-6-300` |  | (part 19 of 37)  (10) Notification to police of illegal activity – Required. If a licensee knows or  |
| 3 |  | 0.689 | `4-14-060` |  | (part 4 of 4)  (f) Listing and rental in buildings with five or more dwelling units – Prohibited. It |
| 4 |  | 0.6815 | `17-17-0100` |  | (part 23 of 42)  3. Vacation Rental. A dwelling unit that contains 6 or fewer sleeping rooms that ar |
| 5 | Y | 0.6626 | `4-13-220` |  | (part 3 of 5)  (c) Identification of local contact person – Required. Each licensee under this Artic |

---

### `deck_setback` — Grade A
**Q:** How close to the property line can I build a deck?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.674 | `17-17-0200` |  | (part 15 of 42)  17-17-0260 Front Property Line. That property line that abuts or is along an existi |
| 2 | Y | 0.6525 | `17-2-0300` |  | (part 13 of 23)  2. unobstructed open space along all property lines other than street property line |
| 3 |  | 0.627 | `17-2-0500` |  | (part 3 of 9)  (c) The minimum separation at the ground-floor only may be reduced to 20 feet for int |
| 4 |  | 0.6268 | `17-3-0400` |  | (part 5 of 16)  17-3-0407-B General. Unless otherwise expressly stated, exterior building walls are  |
| 5 |  | 0.6239 | `17-12-1000` |  | (part 8 of 16)  2. Off-premise signs are prohibited entirely within 100 feet of any residential dist |

---

### `food_trucks` — Grade A
**Q:** What are the regulations for food trucks in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.7742 | `9-64-170` |  | (part 8 of 15)  (iii) Parking prohibited between 2:00 A.M. and 7:00 A.M. It shall be unlawful for an |
| 2 | Y | 0.7459 | `7-38-134` |  | (part 2 of 2)  (3) food products remaining after each day’s operation shall be stored only in a lice |
| 3 | Y | 0.7416 | `7-38-128` |  | (a) Except as otherwise provided in this chapter, the Commissioner of Health shall have authority to |
| 4 | Y | 0.7253 | `7-38-138` |  | (a) The commissary linked to a mobile food preparer must have a servicing area approved by the Depar |
| 5 | Y | 0.7236 | `7-38-136` |  | (part 1 of 2)  (a) All mobile food trucks shall be equipped with a handwashing sink and a three-comp |

---

### `tree_removal` — Grade A
**Q:** Do I need a permit to cut down a tree on my property?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.5996 | `10-32-120` |  | During the erection, alteration, repair, demolition or removal of any building or structure, or exca |
| 2 | Y | 0.5685 | `10-32-130` |  | No person shall remove any permitted device intended for the support or protection of a public tree  |
| 3 | Y | 0.5626 | `10-32-110` |  | No person shall secure, hang, fasten, attach or run any rope, wire, sign, decoration, electrical dev |
| 4 |  | 0.5604 | `17-9-0100` |  | (part 34 of 54)  c. Existing mature trees (more than 3 inches in diameter) and natural land forms on |
| 5 | Y | 0.5565 | `10-32-060` |  | No person other than the Deputy Commissioner shall plant, remove, trim, spray or chemically inject o |

---

### `lot_coverage_rm5` — Grade B
**Q:** What is the maximum lot coverage allowed in an RM-5 district?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.6303 | `17-2-0300` |  | (part 6 of 23)  17-2-0304-C Premiums. Multi-unit residential buildings located in an RM6 or RM6.5 di |
| 2 |  | 0.6128 | `17-2-0100` |  | (part 2 of 3)  17-2-0104 RM, Residential Multi-Unit Districts.  17-2-0104-A General. The primary pur |
| 3 |  | 0.5921 | `17-5-0400` |  | (part 1 of 3)  17-5-0401 General. Bulk and density standards in the M districts vary according to th |
| 4 |  | 0.5667 | `17-3-0400` | frag(2) | (part 14 of 16)  [TABLE] Columns: District \| Maximum Building Height (feet) - Lot frontage of 25 fee |
| 5 |  | 0.5659 | `17-6-0400` |  | (part 6 of 36)  a. this on-site production limit shall not apply in PMD 4B, and the Zoning Board of  |

---

### `landscaping_requirements` — Grade A
**Q:** What are the landscaping requirements for new construction in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7712 | `17-11-0400` |  | (part 1 of 2)  In the event that the City Council or Plan Commission adopts plans, designs or guidel |
| 2 |  | 0.7408 | `10-32-220` |  | (part 3 of 3)  The soil volume and composition for required parkway trees or planters shall meet the |
| 3 | Y | 0.7086 | `17-11-0200` |  | (part 5 of 12)  5. Existing trees that have a minimum caliper size of 2.5 inches may be counted towa |
| 4 | Y | 0.7079 | `17-11-0100` |  | (part 2 of 3)  17-11-0102-C construction, repair or rehabilitation of or upon any detached house , t |
| 5 |  | 0.6831 | `17-2-0500` |  | (part 6 of 9)  2. Required common open space must be located in one or more usable, common areas, ea |

---

### `rooftop_deck` — Grade A
**Q:** Can I build a rooftop deck on my building?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7402 | `4-388-065` |  | (part 2 of 2)  (e) every deck built over the roof of the building shall be a noncombustible deck sur |
| 2 |  | 0.7306 | `14B-15-1510` |  | (part 5 of 6)  Enclosed features shall have exterior walls constructed as required for the building  |
| 3 |  | 0.7263 | `14B-2-203` |  | (part 2 of 4)  2. Building height shall be measured to the top of a parapet wall that exceeds 42 inc |
| 4 | Y | 0.7193 | `4-388-170` |  | (part 2 of 2)  (c) Subject to Section 4-388-175(a), the highest deck level and above shall be open a |
| 5 |  | 0.7135 | `14B-15-1513` |  | (part 2 of 8)  1513.2.3 Type of construction.  Rooftop access penthouses shall be constructed with w |

---

### `liquor_school_distance` — Grade A
**Q:** How far does a bar need to be from a school to get a liquor license?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.6257 | `4-60-020` |  | (part 2 of 5)  (d) In addition to the restrictions cited in Section 6-11 of the Illinois Liquor Cont |
| 2 | Y | 0.6035 | `4-60-040` |  | (part 11 of 12)  If the applicant is seeking a liquor license for a premises and the local liquor co |
| 3 | Y | 0.5921 | `4-60-010` |  | (part 8 of 8)  "Tavern license" means a city license for the retail sale of alcoholic liquor in an e |
| 4 | Y | 0.5819 | `4-60-110` |  | (part 1 of 3)  (a) A person licensed pursuant to this chapter is authorized to sell alcoholic liquor |
| 5 | Y | 0.5689 | `4-60-076` |  | (part 2 of 3)  (c) A separate Outdoor Entertainment Venue liquor license shall be required for each  |

---

### `restaurant_parking` — Grade B
**Q:** How many parking spots does a restaurant need to provide?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.6445 | `7-38-115` |  | (part 2 of 5)  (f) No operator of a mobile food vehicle shall park or stand such vehicle within 200  |
| 2 |  | 0.6002 | `17-10-0100` |  | (part 10 of 12)  17-10-0102-D Small Dwelling Units. The Zoning Administrator is authorized to approv |
| 3 | Y | 0.5843 | `17-10-0200` | frag(1) | (part 22 of 22)  [TABLE] Columns: District \| Minimum Automobile Parking Ratio (Per unit or gross flo |
| 4 |  | 0.5733 | `17-10-0400` |  | (part 1 of 3)  The following rules apply when calculating off-street parking requirements.  17-10-04 |
| 5 |  | 0.5701 | `14B-11-1106` |  | (part 3 of 3)  [TABLE] Columns: TOTAL PARKING SPACES PROVIDED IN PARKING FACILITIES \| REQUIRED MINIM |

---

### `affordable_housing` — Grade A
**Q:** What are the affordable housing requirements for developers in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.8274 | `2-44-080` |  | (part 18 of 30)  (2) To the extent that redevelopment plans approved pursuant to the TIF Act provide |
| 2 | Y | 0.8262 | `2-44-085` |  | (part 15 of 39)  (3) Owner-occupied projects. Developers of owner-occupied projects shall provide th |

---

### `buildable_lot_definition` — Grade A
**Q:** What is the definition of a buildable lot under the Chicago zoning code?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.8021 | `16-4-050` |  | (part 2 of 2)  (h) Zoning Lot. "Zoning lot" means a single tract of land located within a single blo |
| 2 |  | 0.7317 | `14R-2-202` |  | (part 9 of 9)  35. Insert the following definition:  " ZONING LOT. As defined in Chapter 2 of the Ch |
| 3 | Y | 0.7303 | `17-15-0200` |  | 17-15-0201 Definition. A nonconforming lot is a tract of land lawfully established as a lot on a pla |
| 4 |  | 0.7025 | `17-8-0300` |  | Planned developments may consist of one or more lots to be developed as a unit, whether simultaneous |
| 5 |  | 0.6985 | `17-2-0300` |  | (part 1 of 23)  17-2-0301 Lot Area.  17-2-0301-A Minimum Lot Area Standards. All development in R di |

---

### `b3_far` — Grade B
**Q:** What is the maximum FAR in a B3-2 community shopping district?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.6395 | `17-3-0100` |  | (part 2 of 5)  17-3-0103-B The B2 district permits residential dwelling units on or above the ground |
| 2 |  | 0.5852 | `17-6-0400` |  | (part 4 of 36)  3. Urban Farm. Retail sales are limited to sales of goods produced on site, and sale |
| 3 | Y | 0.5599 | `17-3-0400` |  | (part 2 of 16)  17-3-0402-C Exceptions. In the case of a building permit application for the convers |
| 4 | Y | 0.5466 | `17-3-0300` |  | (part 5 of 8)  2. Newly established detached houses and two-flats are prohibited uses in B and C dis |
| 5 |  | 0.5348 | `17-7-0300` | frag(3) | (part 3 of 3)  [TABLE] Columns: Base District Zoning Classification \| Maximum Building Height (which |

---

### `m1_setbacks` — Grade A
**Q:** What are the setback requirements in an M1 limited manufacturing district?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7148 | `17-5-0400` |  | (part 1 of 3)  17-5-0401 General. Bulk and density standards in the M districts vary according to th |
| 2 |  | 0.6467 | `17-5-0100` |  | 17-5-0101 Generally. The "M", Manufacturing districts are intended to accommodate manufacturing, war |
| 3 | Y | 0.6004 | `17-4-0400` |  | (part 5 of 11)  2. DR Districts. Buildings and structures in DR districts are subject to the R distr |
| 4 |  | 0.5984 | `17-7-0550` |  | (part 2 of 2)  The minimum front setback in Subdistrict D is forty (40) feet.  See Section 17-17-030 |
| 5 |  | 0.5943 | `17-2-0500` |  | (part 3 of 9)  (c) The minimum separation at the ground-floor only may be reduced to 20 feet for int |

---

### `loading_requirements` — Grade A
**Q:** What are the off-street loading dock requirements for commercial buildings?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.6546 | `17-10-1100` |  | (part 2 of 6)  1. Unless otherwise expressly stated, all area-based (square feet) loading standards  |
| 2 |  | 0.6346 | `17-3-0500` |  | (part 3 of 14)  2. The bottom of any window or product display window used to satisfy this requireme |
| 3 |  | 0.6336 | `17-4-0400` |  | (part 7 of 11)  17-4-0410-B Additional Standards.  1. Required open space must be located on the sam |
| 4 |  | 0.6311 | `17-10-1000` |  | (part 3 of 9)  1. Automotive lifts shall be used only as expressly provided in this Section 17-10-10 |
| 5 |  | 0.6085 | `17-10-0500` |  | (part 1 of 3)  17-10-0501 Required off-street parking areas are to be used solely for the parking of |

---

### `transition_zone` — Grade A
**Q:** What are the transition zone buffer requirements between residential and commercial districts?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.6377 | `17-5-0600` |  | (part 2 of 2)  17-5-0602-A Screening from Other Zoning Districts. All outdoor work areas situated on |
| 2 | Y | 0.6363 | `17-3-0100` |  | (part 4 of 5)  17-3-0106-A The primary purpose of the C2, Motor Vehicle-Related Commercial district  |
| 3 |  | 0.6264 | `17-7-0400` |  | (part 3 of 18)  2. Buffer Area C-2, defined by the following boundaries: West Ancona Street or the c |
| 4 | Y | 0.6166 | `17-3-0300` |  | (part 3 of 8)  (b) The view of outdoor areas used to store goods and materials that are not availabl |
| 5 |  | 0.607 | `11-4-1560` |  | All Class III recycling facilities, sanitary landfills, incinerators, resource recovery facilities a |

---

### `cannabis_dispensary` — Grade A
**Q:** What are the zoning regulations for cannabis dispensaries in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.8007 | `17-9-0100` |  | (part 48 of 54)  2. Cannabis craft growers may be allowed to conduct retail sales of cannabis produc |
| 2 |  | 0.7584 | `17-7-0560` |  | 17-7-0561 Purpose. To exclude an area in and around the central business district which, because of  |
| 3 |  | 0.7337 | `17-14-0300` |  | (part 6 of 6)  17-14-0303-G Subject to applicable law, cannabis business establishments shall includ |
| 4 |  | 0.733 | `17-17-0100` |  | (part 41 of 42)  2. Cannabis Cultivation Center. A facility operated by an organization or business  |
| 5 |  | 0.7161 | `17-3-0200` |  | (part 36 of 37)  [TABLE] Columns: USE GROUP - Use Category \| USE GROUP - Use Category - Specific Use |

---

### `pd_process` — Grade A
**Q:** What is the planned development approval process in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.745 | `17-13-0600` |  | (part 7 of 8)  17-13-0611-C An approved minor change is valid for 12 months from the date of the let |
| 2 | Y | 0.7271 | `17-8-0800` |  | Mandatory and elective planned developments must be reviewed and approved in accordance with the pro |
| 3 | Y | 0.717 | `17-8-0500` |  | (part 7 of 11)  17-8-0513 Large Residential Developments. Planned development review and approval is |
| 4 | Y | 0.709 | `17-8-0900` |  | (part 1 of 15)  17-8-0901 Uses, Bulk, Density and Intensity. Planned developments are subject to str |
| 5 | Y | 0.7089 | `17-8-0600` |  | (part 1 of 2)  Applicants for developments that do not meet the minimum criteria for a mandatory pla |

---

### `b1_height` — Grade B
**Q:** What is the maximum building height in a B1-1 neighborhood shopping district?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 |  | 0.6308 | `17-7-0200` |  | (part 2 of 4)  17-7-0203-A The maximum permitted building height for new construction within Near No |
| 2 | Y | 0.6191 | `17-3-0400` |  | (part 12 of 16)  [TABLE] Columns: District \| Maximum Building Height (feet) - Lot frontage of 25 fee |
| 3 |  | 0.6155 | `17-12-1000` |  | (part 3 of 16)  17-12-1003-D Minimum Guaranteed Sign Area for Ground-floor Tenants. This standard is |
| 4 |  | 0.6016 | `17-7-0300` | frag(3) | (part 3 of 3)  [TABLE] Columns: Base District Zoning Classification \| Maximum Building Height (which |
| 5 |  | 0.5992 | `17-3-0100` |  | (part 1 of 5)  17-3-0101 Generally. The "B" and "C" (Business and Commercial) districts are intended |

---

### `parking_residential_multifamily` — Grade A
**Q:** How many parking spaces are required for a multi-family residential building?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.6926 | `17-10-0100` |  | (part 10 of 12)  17-10-0102-D Small Dwelling Units. The Zoning Administrator is authorized to approv |
| 2 |  | 0.6746 | `17-10-1100` |  | (part 4 of 6)  [TABLE] Columns: Use \| Gross Floor Area (Square Feet) \| Required Loading Spaces \| Spa |
| 3 |  | 0.6404 | `17-10-1000` |  | (part 5 of 9)  1. Where the first building permit application for the project is submitted after Oct |
| 4 |  | 0.6328 | `17-10-0500` |  | (part 1 of 3)  17-10-0501 Required off-street parking areas are to be used solely for the parking of |
| 5 | Y | 0.6224 | `17-3-0300` |  | (part 7 of 8)  4. Residential building projects shall not have a number of parking spaces in excess  |

---

### `demolition_permit` — Grade A
**Q:** What are the requirements for a demolition permit in Chicago?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.8443 | `14A-4-407` |  | (part 2 of 8)  The written permit application must identify the property address and describe the bu |
| 2 |  | 0.8015 | `14A-4-404` |  | (part 4 of 16)  The permit application must specify the number of devices and type of equipment to b |
| 3 | Y | 0.7985 | `11-4-2170` |  | (part 1 of 12)  (a) Demolition of buildings, facilities or other structures: notice of intent to dem |
| 4 | Y | 0.796 | `15-4-311` |  | (part 4 of 4)  (g) Additional Requirements. A license issued for this purpose shall not be valid unl |
| 5 |  | 0.7954 | `14A-2-202` |  | (part 4 of 11)  8. Demolition accomplished using explosives.  9. Demolition-related activity that is |

---

### `coach_house_adu` — Grade A
**Q:** What are the rules for building a coach house or accessory dwelling unit?

| # | Gold | Score | Section | Flags | Preview |
|:---:|:---:|---:|---|---|---|
| 1 | Y | 0.7254 | `17-9-0200` |  | (part 3 of 8)  8. A minimum separation of 15 feet must be provided between the rear wall of the prin |
| 2 | Y | 0.6995 | `17-7-0570` |  | (part 2 of 8)  (1) Annual limits. In the zoning districts specified in the table below, no more than |
| 3 |  | 0.6593 | `13-4-010` |  | (part 3 of 21)  "Bed-and-breakfast establishment" means an owner-occupied, single-family residential |
| 4 |  | 0.6526 | `2-44-106` |  | (part 1 of 6)  (a) Title. This section shall be known and cited as the “Additional Dwelling Unit Ord |
| 5 |  | 0.6454 | `14B-3-310` |  | (part 3 of 3)  Residential Group R-5 occupancy shall include buildings with no more than four storie |

---

## Category Summary

| Category | Grades | Gold Hits | Dups | Frags |
|---|---|---:|---:|---:|
| accessory_structures | A A | 5/10 | 0 | 0 |
| definitions | A | 2/5 | 0 | 0 |
| dimensional_standards | A A A B B A B | 10/35 | 0 | 3 |
| licensing | A A A | 11/15 | 0 | 0 |
| non_zoning | A A A | 11/15 | 0 | 0 |
| parking | B A A | 4/15 | 0 | 1 |
| planned_development | A A | 7/7 | 0 | 0 |
| site_design | A A | 6/10 | 0 | 0 |
| use_rules | A A A A A | 9/25 | 0 | 0 |

## Key Findings

*(auto-generated from benchmark data)*
