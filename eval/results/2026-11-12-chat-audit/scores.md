# Chat audit scores (deterministic)

| id | turn | gold | 1st sentence agrees | conclusion ok | mixed | over-fetch | under-fetch | filler | leaked fields | gold sec retrieved | cited off-gold | words | $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---:|---:|
| bar_b23_chicago | 1 | no | yes | **no** |  | business_api |  | adu, aro, business, flood, transit |  | 17-17-0100, 17-3-0200 |  | 481 | 0.091 |
| bar_b23_chicago | 2 carry=**no** same_pin=yes |  | **no** | **no** |  | business_api |  |  |  | none |  | 35 | 0.004 |
| crime_wicker_park | 1 | info | — | yes |  |  |  |  |  |  |  | 234 | 0.015 |
| crime_wicker_park | 2 carry=yes same_pin=— |  | yes | yes |  |  |  |  |  |  |  | 142 | 0.014 |
| demolish_landmark_milwaukee | 1 | conditional | yes | yes |  | permits_api |  | brownfield, transit |  | 2-120-740 | 14A-4-407, 2-120-825 | 657 | 0.052 |
| evanston_duplex | 1 | decline | yes | yes |  |  |  |  |  |  |  | 28 | 0.003 |
| evanston_duplex | 2 carry=yes same_pin=— |  | yes | yes |  | permits_api |  | adu, aro, brownfield, flood |  | 17-2-0200 | 17-2-0100, 17-5-0200, 17-7-0590 | 444 | 0.042 |
| gas_station_c25_chicago | 1 | no | yes | yes |  | business_api |  | aro, flood, incentives |  | 17-3-0200 |  | 370 | 0.043 |
| gas_station_c25_chicago | 2 carry=yes same_pin=yes |  | **no** | **no** |  | business_api |  | aro, incentives |  | 17-3-0200 | 17-3-0100, 17-3-0500 | 364 | 0.048 |
| misspelled_artesian | 1 | yes | yes | yes |  | permits_api |  | adu, aro, brownfield, flood, property_value, walkscore |  | 17-2-0300 |  | 572 | 0.064 |
| restaurant_m23_clybourn | 1 | conditional | yes | yes |  | business_api, food_inspections_api |  | food, incentives, transit |  | 17-5-0200 | 17-3-0100, 17-3-0200, 17-3-0300 | 393 | 0.040 |
| restaurant_m23_clybourn | 2 carry=yes same_pin=yes |  | yes | yes |  |  |  | adu |  | none | 17-2-0300, 17-6-0400 | 321 | 0.041 |
| restaurant_rm6_wrightwood | 1 | conditional | **no** | **no** |  | business_api, food_inspections_api | property_domain | aro, food |  | 17-17-0100, 17-2-0200 | 17-3-0200 | 361 | 0.075 |
| restaurant_rm6_wrightwood | 2 carry=yes same_pin=yes |  | **no** | **no** |  | business_api |  | business |  | none | 17-3-0200, 17-7-0450 | 293 | 0.038 |
| restaurants_residential_code | 1 | no | yes | **no** |  | regulatory_domain |  |  |  | 17-2-0200, 17-9-0100 | 17-3-0200, 17-5-0200 | 321 | 0.025 |
| restaurants_residential_code | 2 carry=yes same_pin=— |  | — | yes |  | regulatory_domain |  | overlay_landmark, transit |  | 17-9-0100 | 17-2-0300, 17-3-0400, 17-4-0400 | 295 | 0.025 |
| tod_c25_chicago_bonus | 1 | no | yes | yes |  | permits_api |  | aro |  | 17-3-0400 | 17-4-0400, 2-44-085 | 368 | 0.062 |
| vacant_englewood | 1 | info | — | yes |  |  |  |  |  |  |  | 244 | 0.018 |
| vacant_englewood | 2 carry=yes same_pin=— |  | — | **no** |  | 311_api, crime_api |  |  |  |  |  | 25 | 0.005 |
