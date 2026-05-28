# Eval report — router_only

**25/26 passed.**

## Results

| ID | ✓ | Category | Question | Notes |
|---|---|---|---|---|
| `neighborhood_overview_named` | ✅ | neighborhood_overview | What's going on in Wicker Park? |  |
| `neighborhood_overview_address` | ✅ | address_lookup | What's going on near 2400 N Milwaukee Ave? |  |
| `crime_trend_named` | ✅ | crime | Crime trends in Logan Square last 90 days |  |
| `crime_recent_week` | ✅ | crime_edge | What crimes happened in West Town this week? |  |
| `311_complaints` | ❌ | 311 | What are the top open 311 complaints in Englewood? | expected intent='neighborhood_overview', got 'incident_lookup' |
| `permits_neighborhood` | ✅ | permits | Has there been a lot of new construction in West Loop? |  |
| `business_lookup` | ✅ | business | What bars and restaurants are licensed in Bucktown? |  |
| `zoning_legal_residential_bar` | ✅ | zoning_legal | Can I open a bar in a residential district? |  |
| `zoning_use_specific` | ✅ | zoning_use_lookup | Is a daycare allowed in an RT-4 zoning district? |  |
| `zoning_dimension_height` | ✅ | zoning_dimensions | What is the maximum building height in an RM-5 district? |  |
| `zoning_coach_house` | ✅ | zoning_use_lookup | Are coach houses allowed in RS-3 zoning? |  |
| `definition_lookup` | ✅ | definition | What is a 'coach house' under the Chicago zoning code? |  |
| `permit_requirements` | ✅ | permit_requirements | Do I need a permit to install a fence? |  |
| `no_location_crime` | ✅ | clarification | What's the crime rate? |  |
| `no_location_311` | ✅ | clarification | How many 311 complaints are there? |  |
| `downtown_alias` | ✅ | alias_resolution | What's happening downtown? |  |
| `loop_alias` | ✅ | alias_resolution | Crime in the Loop |  |
| `south_loop` | ✅ | alias_resolution | What's near the South Loop? |  |
| `ambiguous_lincoln_park` | ✅ | ambiguity | Tell me about Lincoln Park |  |
| `trend_violent_crime` | ✅ | trend | Is violent crime up in Austin? |  |
| `specific_block` | ✅ | incident_lookup | Any recent incidents on the 1600 block of N Damen Ave? |  |
| `rats` | ✅ | 311_specific | Are there rat complaints in Logan Square? |  |
| `violation_landlord` | ✅ | violations | Are there building violations on my landlord's properties in Pilsen? |  |
| `parking_requirements` | ✅ | zoning_parking | How many parking spaces are required for a 30-unit apartment building? |  |
| `sign_regs` | ✅ | zoning_signs | What's the maximum sign size for a B3 commercial district? |  |
| `mixed_overview_legal` | ✅ | compound | What's the zoning at 2400 N Milwaukee and what's the recent crime there? |  |