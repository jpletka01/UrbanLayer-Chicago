# Chat audit model budget log (hard cap $1.00)

Spend read from the local backend's own llm_calls table (port 8011, this worktree's fresh chicago.db), priced by backend.llm.estimate_cost.

| When | Question id | Turn | Message | Cost | Running total |
|---|---|---|---|---:|---:|
| 15:38 | restaurant_rm6_wrightwood | turn 1 | Can I put a restaurant in 443 w wrightwood? | $0.0750 | $0.0750 |
| 15:39 | restaurant_rm6_wrightwood | follow-up | What about a coffee shop instead? | $0.0375 | $0.1125 |
| 15:50 | bar_b23_chicago | turn 1 | Can I open a bar at 2200 W Chicago Ave? | $0.0912 | $0.2036 |
| 15:50 | bar_b23_chicago | follow-up | What about a restaurant that serves drinks? | $0.0041 | $0.2078 |
| 15:50 | restaurants_residential_code | turn 1 | Are restaurants allowed in residential zoning districts in Chicago? | $0.0245 | $0.2323 |
| 15:50 | restaurants_residential_code | follow-up | What does that section say about how big it can be? | $0.0250 | $0.2573 |
| 15:51 | crime_wicker_park | turn 1 | How much crime was there in Wicker Park in the last 90 days? | $0.0147 | $0.2721 |
| 15:51 | crime_wicker_park | follow-up | Which of those happened near Division and Damen? | $0.0141 | $0.2862 |
| 15:51 | vacant_englewood | turn 1 | Which vacant buildings were reported in Englewood recently? | $0.0180 | $0.3042 |
| 15:51 | vacant_englewood | follow-up | Tell me more about the first address you listed. | $0.0051 | $0.3093 |
| 15:52 | restaurant_m23_clybourn | turn 1 | Could I open a restaurant at 1930 N Clybourn Ave? | $0.0405 | $0.3498 |
| 15:52 | restaurant_m23_clybourn | follow-up | And could I live in an apartment upstairs? | $0.0409 | $0.3907 |
| 15:53 | gas_station_c25_chicago | turn 1 | Can I open a gas station at 368 W Chicago Ave? | $0.0426 | $0.4334 |
| 15:53 | gas_station_c25_chicago | follow-up | What about a car wash? | $0.0477 | $0.4811 |
| 15:54 | evanston_duplex | turn 1 | Can I build a duplex in Evanston? | $0.0028 | $0.4839 |
| 15:54 | evanston_duplex | follow-up | OK, what about 6247 N Rockwell St in Chicago? | $0.0417 | $0.5256 |
| 15:55 | misspelled_artesian | turn 1 | can i bild apartmnts at 1256 n artesion | $0.0635 | $0.5891 |
| 15:56 | tod_c25_chicago_bonus | turn 1 | Can I get a density bonus at 368 W Chicago Ave because it's near transit? | $0.0624 | $0.6515 |
| 15:56 | demolish_landmark_milwaukee | turn 1 | Can I demolish the building at 1601 N Milwaukee Ave? | $0.0519 | $0.7034 |
| 16:00 | router-only x54 | | | | $0.7034 |
| 16:05 | router-only x54 | router | (54 questions, see router_runs.jsonl) | est. $0.17–0.22 (not logged) | est. $0.88–0.93 |

The 54 router-only calls ran in the script's own process without an open database connection, so `tracked_create`
could not log them ("Failed to log LLM call") and the cap check could not see them. Their cost is estimated from
the 19 logged router calls of this audit (output tokens per character of the plan JSON: mean 0.313, max 0.355;
cache reads of the 3,133-token system prompt): $0.173 at the mean, $0.222 at the max with one cache write. All
spending stopped there. **Total: $0.7034 measured + $0.17–0.22 estimated = $0.88–0.93 of the $1.00 cap.** The script
now opens the database before router-only runs.
