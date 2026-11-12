# Chat answer audit (2026-11-12)

Why: the owner stopped trusting chat after "Can I put a restaurant in 443 w wrightwood?" (RM-6) opened "Yes, likely
allowable", offered a special-use route that does not exist, closed "not permitted by right", and padded itself
with Lincoln Park permit trends, 435 food licenses, ARO counts, a flood zone and an ADU aside. This audit asks how
common those failures are, and what one turn carries into the next. No production code changed. Decision Item 113.

**Spend: $0.88–0.93 of the $1.00 cap.** $0.7034 is measured (the local backend's own `llm_calls`, priced by
`backend.llm.estimate_cost`): 19 full turns (8 question + follow-up pairs, 3 single turns). A further 54 router-only
plans went unlogged (the script called the router without opening the database, so neither the log nor the cap
guard saw them; fixed in the script); from the 19 logged router calls they cost $0.17–0.22. One turn cost $0.037 on
average, $0.07–0.09 for a cold parcel turn (the 8k-token synthesizer prompt written to the cache). The log is
`eval/results/2026-11-12-chat-audit/budget_log.md`.

**What was run.** 71 questions with one-line primary-source answers in `eval/chat_audit_questions.json` (parcel use
across R/B/C/M/D/PD, bulk, trick questions, code research, neighborhood, off-topic, out of city, vague or misspelled
addresses), 15 with follow-ups. Answers come from the use and bulk tables in the code corpus
(`ingestion/data/sections`) and the parity-tested `zoning_definitions`; parcels are the parcel kit's. Full answers:
11 questions, 8 of them with follow-ups. Router plans: 65 of the 71. Free checks: retrieval for 27 parcel questions,
and 52 plans already stored in local conversations. Scorer: `eval/chat_audit.py` (deterministic; every number
below is reproducible with `python -m eval.chat_audit score|retrieval|historical`, no model calls). The gold
patterns were written before the runs; four were corrected after reading the answers, each toward what the answer
actually said: "doesn't allow filtering" now counts as can't-tell; the gas-station "wrong" pattern was narrowed to
a special use *in C2* (the answer correctly cited a citywide special-use amendment); the vacant-building follow-up
must name the first address (6630 S Lowe); follow-up carry requires the district, not the street number.

**A correction to the trigger case's own premise.** The County records 443 W Wrightwood as a 13-story, 176-unit
building. RM-6 permits a restaurant by right as a *Residential Support Service* in a building with more than 50
dwelling units, on its first two floors, up to 5,000 sq ft per business (17-2-0207 row T, 17-9-0114, 17-17-0104-Y).
So the right answer is "yes, inside this building, within those limits". A stand-alone restaurant would still not
be allowed, and there is no special-use route. Three runs of the question gave three different answers, and none
was right: the stored run said "Yes, likely… special use… not permitted by right"; an earlier stored run said "you
would likely need a rezoning"; this audit's run said "No, not by right".

## Results

| | Count |
|---|---|
| Correct conclusion, all full turns | 12 of 19 |
| Wrong use conclusion stated flatly (confident-wrong) | 4 of 19 (B2 tavern, C2 car wash, RM-6 restaurant ×2) |
| Follow-up answered with a needless clarification | 2 of 8 follow-ups |
| Plans that fetched a source the question didn't need | 38 of 65 (parcel use questions: **17 of 17**) |
| Substantive answers padded with an unasked topic | 12 of 16 |
| Follow-ups reusing a `[N]` that now points at a different section | 4 of 8 (2 read as clear mis-citations) |
| Answers naming an internal structure ("zone definition in context", "property flags show") | 3 of 19 |
| Raw field names (`in_landmark_district`) | 0 of 19 (1 in the stored trigger answer) |
| Server citation warnings | 0 of 19 (the check only tests that `[N]` is in range) |
| Follow-up kept the same parcel (PIN) when one was resolved | 5 of 5 |

Per-question detail: `eval/results/2026-11-12-chat-audit/scores.md`; router plans: `router_scores.json`; retrieval:
`retrieval_check.json`; stored plans: `historical_plans.json`; raw SSE records: `runs.jsonl`.

## Failure patterns, ranked (harm × frequency)

### 1. Wrong use answers from the use table (confident-wrong): 4 of 19 turns, plus 2 of 2 stored runs

- **"Can I open a bar at 2200 W Chicago Ave?" (B2-3).** The table has Tavern `-` in B2 (`S` only in B3). This run:
  "requires a Special Use approval… Under [1], a tavern in a B2 district is listed as S". Both stored runs were
  also wrong ("Yes, but you'll need a Special Use approval"; "B2 zoning generally permits taverns"). 3 of 3 wrong.
- **"What about a car wash?" after a gas station at 368 W Chicago Ave (C2-5).** Car wash is `P` in C2. The answer:
  "faces the same hard prohibition… the zone definition confirms [it] prohibits car washes alongside gas stations".
  The zone definition's prose summary says only "no new gas stations"; the model stretched it.
- **The RM-6 restaurant** (above), and the code question "Are restaurants allowed in residential districts?":
  "generally not permitted", with no mention of the residential-support-service exception.

*Why.* (a) The vector search returns several districts' use tables at once: in the RM-6 run the top 5 held the M, B,
D and R use tables; 6 of 27 router queries pulled two or more other districts' tables. The model then reads one
column out of a wide flattened table. (b) The router writes the search query before the parcel's district is
known, and when it names one it guesses: 5 of the 8 queries that named a district named the wrong one, nearly
always "B3" (for M2-3, C2-5, B2-3 and B1-2 parcels), the example in its own prompt. (c) Use-standard rows point to
other sections (17-9-0114 for residential support services) that are never fetched. (d) For use questions, unlike
bulk numbers, there is no deterministic answer in the context, only `zone_definition.uses`, a one-line prose
summary the model treats as exhaustive. (e) For the RM-6 case the router did not fetch `property_domain`, so the
unit count (176) that decides the answer was not in the context.

*Naming the district in the query doesn't fix it.* A query such as "RM-6 use table allowed uses permitted special
uses" returned all four families' use tables too (`retrieval_check.json`: other districts' tables in the top 5
went *up*, from 0–3 to 4). The embedding can't tell the tables apart. The fix has to be a lookup, not a better query.

### 2. Over-fetching: 38 of 65 plans; every parcel use question

Parcel use questions fetched community-area feeds in 17 of 17 plans (business licenses 10, permits 8, food
inspections 3). The same is true of the stored conversations: 9 of 10 parcel-scoped use or bulk questions. Trick
and bulk questions: 6 of 16 (permits 5, business licenses 1). Neighborhood questions were clean (crime-only questions fetched crime
only). Code questions with no address added `regulatory_domain` in 10 of 12. That is harmless, because it can't run
without a point, but it shows the same habit.

*Why: the router prompt asks for it.* "business_launch at a specific address: include … business_api"; "development
_feasibility: include … permits_api"; "food_inspections_api … for business_launch when the business involves food";
"property_intelligence: include … crime_api, 311_api, permits_api, violations_api, business_api, and
vacant_buildings_api". These feeds cover the whole community area, not the lot.

### 3. Padding: 12 of 16 substantive answers

Topics nobody asked about: ARO (7 answers), ADU (4), flood zone (4), transit (4), brownfields (3), incentives (3),
business licenses (2), food inspections (2). Examples: the M2 restaurant answer closes with "Lincoln Park's
restaurants had a fail rate of 17.6% across 714 inspections, so budgeting for robust food safety compliance is
advisable"; the bar answer offers "SBIF grants… 15 recent projects totaling over $1 million [data:business]",
mislabeled with the business-license marker; the RM-6 answer infers "a competitive and well-regulated dining
environment" from inspection counts.

*Why: the synthesizer prompt asks for it, once the router has fetched it.* Rules 10–24b are "When X data is
present, state…" (rule 22: "always include it… Do not skip violations data"; rule 10: "mention the number of
affordable housing projects and total units"). `regulatory_domain` also always carries flood, brownfield and ARO
project counts. Over-fetching (2) and padding (3) are one defect, in two prompts.

### 4. Follow-ups lose what turn 1 said: 2 of 8 follow-ups clarified instead of answering, 1 inherited a wrong frame

- "Tell me more about the first address you listed." (after a table of Englewood vacant buildings that began with
  6630 S Lowe): "Could you provide a specific address or street name in Englewood…?" The rewrite step saw the first
  150 characters of the answer, which end before the table; the router saw only the rewrite.
- "What about a restaurant that serves drinks?" after the B2 bar answer: a clarification ("primarily a restaurant
  that serves alcohol, or primarily a bar?"), though the code answers both cases (a limited restaurant is
  permitted; a general restaurant and a tavern are not).
- "What about a car wash?" after a gas-station "no": "the same hard prohibition" (wrong; see 1).

The parcel itself carried well: 5 of 5 follow-ups that needed the parcel re-resolved the same PIN, because the
rewrite put the address back in. That is luck of phrasing, though: a follow-up over 100 characters skips the rewrite
and loses the address (see the context section below).

### 5. Citation numbers drift across turns: 4 of 8 follow-ups, 2 clear mis-citations

Turn 2's `[N]` index into turn 2's chunks, but the model reads turn 1's answer, where the same numbers meant other
sections. RM-6 follow-up: "Neither use appears in the RM-6 residential use table [4]", where turn 2's [4] is the
B/C table (17-3-0200) and the residential table wasn't retrieved at all; "[2]" became the Kinzie Corridor overlay.
M2 follow-up: "unlisted uses are prohibited under [1]", where [1] is the R districts' bulk standards. The server's
citation check passes both: it tests only that N is in range.

### 6. Same question, different conclusion (run to run)

The RM-6 question opened "Yes, likely allowable", "you would likely need a rezoning", and "No — not by right" in three
runs; the B2 bar question opened "Yes, but special use", "may be possible", and "not permitted by right — requires a
special use". The opening sentence matched the answer's own conclusion in every run of this audit (0 mixed
answers); the trigger case's "yes… not permitted" contradiction did not recur, but the variance that produced it did.

### 7. Internals in the prose (low)

No raw field names this run. 3 of 19 answers refer to internal structures ("the zone definition in context
confirms", "the regulatory data", "the property flags show"). The context goes to the model as one raw JSON dump
(`synthesizer._build_user_text`), so field names are always one slip away.

### What worked

Evanston declined ("I only cover Chicago city limits") and the follow-up resolved the Chicago address to RS-2,
answering "No, not by right" correctly. The misspelled "1256 n artesion" resolved to RM-4.5 with the right 4-unit
arithmetic, and it flagged City ownership. The density bonus at a C2-5 near the L was correctly refused (dash-3
only). The landmark-district demolition answer named the Commission's approval and the CHRS 90-day hold. The M2
restaurant answer gave the 4,000 sq ft cap. "Crime in Wicker Park" said the figure is West Town's, and the follow-up
honestly said it can't list incidents near one corner.

## Recommended fixes (next task; none made here)

Retrieval:
1. **A deterministic use answer.** Once `parcel_zoning` is known, read the district's column of its family's use
   table (17-2/3/4/5-0207, from `ingestion/data/sections`) into the context as rows: use, P/S/PD/-, use standard.
   Add the "unlisted uses are prohibited" rule (§17-X-0204), and pin the parsed table in a parity test like the bulk
   numbers. Follow the use-standard references for the rows the question touches (17-9-0114).
2. **Drop other districts' use tables** from `code_chunks` when the parcel's district is known, and fetch the
   parcel's own table by section id (the vector index already has a section index) instead of hoping it ranks.
3. **Strip district names from the router's `search_query`** for address questions (and remove "B3 permitted uses
   commercial" from the prompt's examples), so the query can't steer retrieval to a guessed district.

Router:
4. **No community-area feeds by default** for business_launch, development_feasibility and property_intelligence;
   fetch them only when the question asks about the area. Add `property_domain` to use questions at an address
   (unit counts, building class and stories decide some use rows).
5. **Carry the parcel in the full chat** the way the Profile dock does: send the last resolved PIN as `parcel_pin`
   when the follow-up names no new address, instead of relying on the rewrite to repeat it.
6. **Feed the rewrite more than 150 characters** of the last answer, at least the entities it listed (addresses,
   section numbers), and don't emit `clarification_needed` when the previous turn had a location.

Prompt:
7. **Replace "When X is present, state…" with relevance**: answer the question asked; mention another context item
   only if it changes the answer; drop "always include violations" and the ARO-count rule.
8. **The use verdict comes from the use row**: the first sentence states P/S/-/conditional from the row, and "special
   use" appears only when the row says S. Don't present `zone_definition.uses` as a complete list.
9. **Strip or renumber `[N]` in history** before it reaches the synthesizer, and extend `citation_problems` to flag
   a cited chunk whose section family doesn't match the district the sentence names.
10. **Send context as labeled sections**, not one JSON dump, and tell the model never to name its inputs.

Measure the fixes with this set: re-run the same 11 questions and 8 follow-ups (about $0.70 at today's cost) and
the router plans (about $0.20), and compare the scores here.

## What carries from one turn to the next (read from the code, before any spend)

Two chat surfaces send different history, and the backend treats them differently.

**What the browser sends.** `useChat.send` (`frontend/src/lib/useChat.ts`) sends `history` = every earlier message in
the transcript as `{role, content}`: the user's words and the assistant's full answer text (including the appended
Sources block), nothing else. The per-message `context`, `plan` and `mapData` stay in the browser. The full chat also
sends `conversation_id`; the Profile's Ask drawer and MiniChatDock (`useParcelChat`) send no conversation id, but send
`parcel_pin` and `scorecard_context` (the Profile's parcel facts) on every turn. `ChatRequest` caps history at 20
messages and 60,000 characters.

**What the backend keeps.** After each turn the stream emits a `turn_summary` (`context_manager.summarize_turn`, no
model call). The full chat saves it with the assistant message (`messages.summary_json`). It holds the question
(first 200 characters), the location, the router's sources, up to 10 **aggregate** facts (crime total and top type,
open 311 count, permit count and cost, violation count, business count, PIN/sq ft/assessed value, overlay layer
names, flood zone, incentive program names, population/income, Walk Score) and the **section numbers** of the first
5 code chunks. It holds no record-level data and no code text.

**What turn 2's three model calls see.**

| Call | Input | What it knows of turn 1 |
|---|---|---|
| Conversation rewrite (Haiku, `conversation.synthesize_query`) | Runs only if the follow-up looks like one (under 50 characters, or under 100 with a pronoun/"what about"/question opener, or a question with no street word). Sees every earlier message, **assistant answers cut to 150 characters**. A regex shortcut swaps neighborhoods for "what about X" without a model call. | The first 150 characters of each earlier answer and the user's full words |
| Router (Sonnet) | Only the rewritten (or original) question. No history, no summary. | Only what the rewrite put into one sentence |
| Synthesizer (Sonnet) | With a `conversation_id` that has stored summaries: the summaries as one user message, then the last **2 question/answer pairs verbatim**, then this turn's fresh context JSON. Without (the Profile dock): the whole transcript verbatim. | The earlier answer's text (2 pairs), the aggregate summary; never turn 1's context JSON |

**So, does a specific crime, permit or ordinance from turn 1 reach turn 2?**

- *Record-level data* (a permit's work description, a vacant-building address, a food-inspection failure): only as
  words in the earlier answer, and only while that answer is inside the 2-pair window (or always, in the Profile
  dock). The router never sees it unless it is in the first 150 characters of the answer, so a follow-up such as
  "tell me more about the first address" is routed without the address. Turn 2 re-fetches the whole feed fresh (the
  same community area, if the rewrite kept it) and the model has to match its own earlier words against new data.
  Crime never reaches the model as records at all: `crime_last_90d` is a community-area total by type; incidents go
  only to the map.
- *Code text*: turn 1's chunks are gone in turn 2; the summary keeps only section numbers. Turn 2's retrieval runs
  on the rewritten question. Turn 1's answer text still carries `[N]` markers that pointed into turn 1's chunk list;
  in turn 2 the same numbers index a different list.
- *Parcel facts*: in the full chat the parcel is re-resolved from whatever address the rewrite put back into the
  question. If the follow-up is long enough to skip the rewrite ("What about a coffee shop instead of a restaurant
  on the ground floor of that building, would that change anything?" is over 100 characters), the router gets no
  address, and turn 2 has no parcel data. The Profile dock avoids this by sending the PIN on every turn.
- *Area data that isn't about the lot* (permits, business licenses, ARO project counts): the summary records their
  counts, and the synthesizer is told to use the summaries "for continuity", so they ride into later turns as facts
  even when no later question asks for them.
