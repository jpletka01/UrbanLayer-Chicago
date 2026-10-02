# How UrbanLayer's quality is measured

UrbanLayer answers questions that people act on: what can be built on a parcel,
what it pays in tax, what the zoning code says. Every change to retrieval,
prompts, or data sources is checked against fixed question sets before and
after, and the results are kept in the repo. This page describes each suite,
the latest results, their history, and where the evals are still weak.

## The loop

1. **A fixed, representative set** of questions or addresses, with expected
   outcomes written down before the run.
2. **Run the real system**: the same router, retrieval, and APIs production
   uses, never a mock.
3. **Score expected against actual**, deterministically wherever possible, and
   with an LLM judge only for what can't be checked mechanically.
4. **Keep the report.** Results go in [`eval/results/`](eval/results/), dated,
   and each run is a row in [`history.csv`](eval/results/history.csv).
5. **Investigate failures before changing labels.** A failing case is either a
   system bug (fix the system) or a wrong expectation (fix the label, and
   record why; see the demolition example below).

## Suites

| Suite | What it measures | n | Scoring | LLM cost / run | Runtime |
|---|---|---:|---|---:|---:|
| Retrieval benchmark ([`retrieval_benchmark.py`](eval/retrieval_benchmark.py)) | Does vector search put the right municipal-code sections in the top results? | 28 questions | Deterministic A–F: gold sections in top 3, duplicates, table fragments, required terms | $0 | ~6 s |
| Lot coverage ([`lot_coverage.py`](eval/lot_coverage.py)) | For real parcels, which Property Profile facts are present, and is each absence legitimate? | 100 addresses | Deterministic field classification: present / missing (persistent vs transient) / expected-absent | $0 | ~20 min |
| Parcel kit ([`parcel_kit.py`](eval/parcel_kit.py)) | For 7 hard Chicago parcels with a primary-source answer key, are the zoning district, bulk numbers, overlays and the task answer right, on the Profile and in chat? | 7 parcels × 6 fields × 2 surfaces | Mechanical for district, numbers and overlays; expected-phrase rubric for use and task answers; optional hand-score file | $0 Profile, ~$1 chat | ~8 min |
| Router ([`run_eval.py --router-only`](eval/run_eval.py)) | Does the router pick the right data sources, intent, location and disclaimer? | 44 questions | Deterministic checks against a hand-labeled expected plan | ~$0.50 | ~4 min |
| Full pipeline ([`run_eval.py --full`](eval/run_eval.py)) | End-to-end over SSE: plan, retrieved sections, citation validity, per-phase latency | 44 questions | Deterministic, plus optional LLM judge (`--judge`) | ~$3–5 (+~$1.50 judge) | ~25 min |
| Source coverage ([`source_coverage.py`](eval/source_coverage.py)) | Does each data source reach the context, and does the answer use it? | 29 questions | Per source: COVERED / SYNTHESIS_GAP / RETRIEVAL_GAP / HALLUCINATION | ~$2–3 | ~12 min |

Checks that run in CI on every push, with no API keys:

- [`test_zoning_ordinance_parity.py`](backend/tests/test_zoning_ordinance_parity.py)
  diffs every hand-typed zoning standard (FAR, height, lot area per unit)
  against the ordinance tables parsed from the municipal code.
- [`eval/tests/`](eval/tests/) and [`eval/test_judge.py`](eval/test_judge.py)
  test the scorers themselves: plan checks, the retrieval A–F rules, coverage
  statuses, lot-field classification against a recorded response, and judge
  parsing and weighting. A scorer bug would silently change every number on
  this page.
- [`backend/citations.py`](backend/citations.py) runs on every production chat
  answer. It flags any `[N]` citing a code chunk that wasn't retrieved, and any
  `[data:x]` citing data that wasn't in the context. Findings are logged and
  reported on the stream's `done` event, and `run_eval --full` fails the query.

### The parcel kit

The public write-up, with every parcel's key, the dated results, the failures and a blank scorecard for scoring another tool, is [`docs/benchmark/`](docs/benchmark/README.md), generated from the committed results by `make benchmark`.

The other suites ask whether the system reproduces its own inputs. The kit asks
whether it is *right*. [`eval/kit/parcels.json`](eval/kit/parcels.json) holds
seven parcels chosen because each one breaks a lazy system: a vacant lot whose
address geocodes into the neighboring district, a parcel inside a landmark
district, a Planned Development whose numbers aren't in any base-district table,
and a parcel rezoned three months ago. The answer for each was read from primary
sources (the City's zoning layer and zoning map service, the Municipal Code text,
ordinance PDFs, Cook County Assessor data), with the source recorded per field.

Two surfaces are scored on the same six fields, using the same standard prompt
for chat and the address only (no PIN, as a first-time user would type it):

| Field | What is scored |
|---|---|
| A | Zoning district in effect. A wrong answer is a **critical miss** |
| B | The use question (is a two-flat allowed?) |
| C | Bulk numbers: FAR, height, minimum lot area per unit |
| D | Overlays and designations, as a set (missing, false and denied ones counted) |
| E | Parking / transit rule (two parcels) |
| F | The parcel's task question (max units, demolition approvals, ADU limits) |

Each field scores 2 / 1 / 0, or NP when the system makes no claim, and a wrong
answer stated flatly is flagged CW (confident-wrong). A, C and D are scored
mechanically; B, E and F by expected-phrase rubrics, and a person's scores can
override any field (`--manual`). The report prints how often the automatic score
agrees with the hand score, because the rubrics were written with the first run
in view: that agreement is in-sample, not a held-out accuracy.

**Limits that matter when quoting it.** Seven parcels show *kinds* of failure,
not a rate. The key has not yet been reviewed by a Chicago architect or zoning
attorney (P2, P3 and P6 are the most interpretive). Overlay truth comes from the
same City service the backend queries, so overlay scores are not independent.
Code text is current through the Council Journal of 2026-03-18.

```bash
make kit-replay   # re-score the recorded 2026-10-01 runs: no network, no cost
make kit          # run the live backend, then score it (RATE_LIMIT_ANON_DAY=50 RATE_LIMIT_ANON_HOUR=50 on the backend)
```

### How the gold data was built

- **Retrieval.** Each question names the code sections a correct answer must
  come from (`gold_sections`) and why, taken from reading the ordinance. Grade
  A needs at least two gold hits, including in the top three.
- **Lot coverage.** The panel is sampled once from Cook County Address Points,
  stratified across the seven Chicago townships with a fixed seed, then frozen
  in [`lot_panel.json`](eval/lot_panel.json), so every run measures the same
  parcels. The county's PIN for each address is the identity truth. Fields
  that are legitimately absent (vacant land has no building area, exempt
  parcels have no tax bill) are excluded, not counted as misses.
- **Router and full pipeline.** Each question has a hand-written expected plan
  (sources, intent, community area, disclaimer), and for code questions the
  section prefixes retrieval must hit.

## Latest results (2026-09-28)

Only the $0 suites were re-run for this snapshot; the LLM-dependent suites
cost about $7–10 per full pass. Full reports are in
[`eval/results/2026-09-28/`](eval/results/2026-09-28/).

**Retrieval**, 28 questions:

| Configuration | A | B | C | D | F | Wall time |
|---|---:|---:|---:|---:|---:|---:|
| Reranker off (production) | 24 | 4 | 0 | 0 | 0 | 5.8 s |
| Reranker on (bge-reranker-v2-m3, 20% blend) | 25 | 3 | 0 | 0 | 0 | ~75 s |

The cross-encoder improves one question by one grade at roughly 13× the time
on a laptop. On the production CPUs it measured ~40 s per search and caused
the June report timeouts, so it stays off. The evidence for that decision is
this table, not intuition.

**Parcel kit**, 7 parcels (2026-10-01, [report](eval/results/2026-10-01/parcel_kit.md)).
These are the first numbers on a primary-source key, and they are not flattering:

| Surface | Coverage | Accuracy | Confident-wrong | Wrong district (critical) |
|---|---:|---:|---:|---|
| Property Profile | 86% | 80% | 2 | none (7/7 right) |
| Chat, address typed cold | 76–81% | 68% | 7 | 2 of 7 (P2, P5) |
| Chat after F1 (typed address resolved to its parcel) | 86% | 81% | 1 | none (7/7 right) |
| Profile after F2 (no false TOD density bonus) | 86% | 83% | 0 | none (7/7 right) |
| Chat after F2 | 81% | 87% | 1 | none (7/7 right) |
| Chat after F4 (answers no longer cut off silently) | 84% | 89% | 0 | none (7/7 right) |
| Profile after F3 (binding number shown) | 89% | 94% | 0 | none (7/7 right) |
| Chat after F3 | 95% | 90% | 0 | none (7/7 right) |
| Profile after F5a (freshness stamps) | 92% | 94% | 0 | none (7/7 right) |
| Chat after F5a | 95% | 97% | 0 | none (7/7 right) |
| Profile after F7 (overlays named) | 95% | 97% | 0 | none (7/7 right) |
| Chat after F7 (6 of 7 parcels scored*) | 94% | 93% | 0 | none (6/6 right) |

The Profile resolves the parcel from the address-point record and gets the
district right on all seven. Chat resolves the same address by geocode and lands
in the neighboring district on two of them; the wrong districts and the
neighboring-parcel facts all trace to that. Most chat answers also stop at the token cap (6 of 7 in the
latest run end mid-sentence or mid-table). The range in the chat row is two runs:
the recorded hand-scored run (76% / 68% / 7) and an automatically scored re-run
the same day (81% / 68% / 7). Chat varies run to run, so compare runs by the
cases that fail, not by the third digit. The key is not yet
reviewed by a Chicago professional; treat these as a diagnosis, not a benchmark.

The third row is the same kit after fix F1: chat now resolves a typed address
through Address Points like the Profile does ([report](eval/results/2026-10-01-f1/parcel_kit.md)).
Wrong districts went from 2 to 0 and the cited PIN matches the Profile's on all
seven parcels. The one confident-wrong field left is P2's bulk numbers, which the
model still fills in from memory (FAR 2.2 instead of 1.7); that is the next fix
(F3). One run, automatic scoring, rubrics written against the earlier run.

Fix F2 removed a false claim the kit found on the Profile: transit-served parcels
were told they get "reduced parking minimums and a density bonus". The code gives
every transit-served district parking relief but FAR, height and density increases
only to dash-3 districts, and only through an entitlement. One helper now decides
this, is pinned to the ordinance text in a test, and feeds the Profile, chat and
the report text ([report](eval/results/2026-10-02-f2/parcel_kit.md)). The Profile
now meets the kit's screening-grade rule (no critical miss, no confident-wrong
field, accuracy above 80%); read that as "passes this 7-parcel check", not as
reliance-grade.

Fix F4 attacked a different defect, found by reading the answers rather than
scoring them: chat answers stopped at the 2,000-token cap, mid-sentence, with
nothing to say so, and two lost the final question entirely. The prompt now sets
an 800-word budget and bans a closing recap; if the model still hits the cap the
stream appends a visible "cut off, reply continue" notice and the `done` event
carries `truncated: true` ([report](eval/results/2026-10-02-f4b/parcel_kit.md)).
Silently cut-off answers went from 6 of 7 to 0, and every answer now reaches the
last question. 2 of 7 (the transit-heavy P3 and P5) still hit the cap and say so;
raising the cap is the next lever and is a cost decision. The chat confident-wrong
count falling to 0 in that run is run-to-run variance (the model hedged P2's
numbers this time), not a fix: F3 is still open. Scorer refinements made along the
way re-scored the F2 chat row from 84% / 84% to 81% / 87%; compare runs by replaying
them through the same scorer.

Fix F3 supplied the number a unit count actually turns on. The Profile never showed
minimum lot area per dwelling unit, and chat filled it in from memory: on the vacant
RM-4.5 lot it said 1,000 sq ft and FAR 2.2 (the table says 700 and 1.7) and
concluded "3 units" instead of 4. The zoning table now carries the per-unit
minimum for every district, the Profile card shows "max units by lot area" with its
arithmetic and says plainly that FAR, height and parking can bind first, and the
same table and unit yield reach chat on every parcel-resolved turn, with a rule
against quoting a standard that isn't in the data. On the same lot chat now says
FAR 1.7, 700 sq ft per unit, "3,191 ÷ 700 = 4.6 → 4 units" and that six is not
achievable by right ([report](eval/results/2026-10-02-f3/parcel_kit.md)). Two
corrected "uses" lists (RS-3 allows a two-flat; RT-4 allows multi-unit) are pinned
to the use table in a test. Still open: 2 of 7 chat answers name an internal field
(`tod_benefits`) despite the prompt, which the kit now counts; setbacks were not
added in F3 and the 606 reduction is described, not applied.

Fix F5a answered the kit's freshness probe. P7 was rezoned from M1-2 to RT-4 by an
ordinance passed on June 16, 2026, and the product could not say so: the City's layer
returns the ordinance date, the last-edited date and the clerk's ordinance number
and link, and all of it was discarded, while the application number (23082T1) was
shown as "the ordinance" and read by the chat model as a year. The lookup now keeps
those fields, calls the application number what it is, flags a district changed
within 180 days, and every Profile carries two stamps: when this district's zoning
record was last updated, and the date the indexed Municipal Code is current
through (read from the export's own header at ingestion). On P7 the Profile now
carries a caveat that the district changed by an ordinance dated 2026-06-16, and chat
names that ordinance with a link to the Clerk's record, says the code text is
current through March 18, 2026, and notes that the map can lag a passed
amendment by up to 90 days ([report](eval/results/2026-10-02-f5a/parcel_kit.md)).
Not built: a "passed but not yet on the map" bridge (F5b) — it needs the Clerk's
API spike and depends on how a competitor handles the same parcel. The stamp says
when *this district's record* was edited; it is not a claim that the whole City map
was refreshed that day.

Fix F7 named what the overlays were. The Profile called the 606 district "Special
Districts", said "ADU eligible" for any parcel the ADU layer hit (and never named the
zone or its limits), linked nothing for a Planned Development, and described a
landmark's consequence as "expect design review". The layers carry the real names,
links and limits; they are now shown, each statement pinned to the code text: the 606
district by name with its code link and its real scope (RS-3 and RT-3.5 only), the ADU
zone and its limitations (P6: Zone 10, annual limit and owner occupancy), coach houses
"by right" in RT, RM and B/C with the layer artifact dropped, the PD's number and its
ordinance PDF, and "the Commission on Chicago Landmarks must approve in writing"
(§2-120-740) for a landmark or landmark district
([report](eval/results/2026-10-02-f7/parcel_kit.md)). The Profile's task answers for
P1 (coach house not allowed), P5 and P6 went from partial to correct.
*P7's chat call failed mid-run because the Anthropic account ran out of credit, so it
is reported as not scored rather than counted; the chat row covers six parcels.

The first Phase 2 milestone (V1) makes the Profile's facts checkable: `/api/scorecard`
now returns a `provenance` map with a dated source for the district (and the
ordinance behind it), each standard (and the code section it comes from, pinned to the
code's own headings), each overlay (and the City layer it came from), the parcel
identity, the area figures and the code's vintage. The kit counts how many stated
facts carry one: **46 of 46**, but only **25 of 46** carry a date the source itself
gives (an edit or effective date, or the code's current-through date); overlays and
parcel identity carry only the date we queried them, because the City's layers publish
no per-feature date. Taxes, comparables and permits are not covered yet
([report](eval/results/2026-10-02-v1/parcel_kit.md)).

V3 shows how the address became the parcel instead of only a PIN and a check. The
record names the matching source, lists every parcel the two county address records
give for the address, and says when they disagree or the identity could not be
confirmed. Run on the seven parcels it turned up things a single green check hid:
P2 (a vacant lot) has no address point and resolves through the Assessor; P5's
address maps to three parcels; P3's two official sources name *different* parcels;
and P4 is a condominium building (one building PIN, about fifty unit PINs) whose
building PIN has no parcel record, so its property figures may describe a neighbor.
The kit checks each record against what those datasets say (7 of 7), which tests that
the Profile reports the county's records faithfully, not that the records are right
([report](eval/results/2026-10-02-v3/parcel_kit.md)).

V4 makes the Profile say where it stops. Each parcel now carries the notes that apply
to it: a Planned Development's numbers aren't the base district's (with the ordinance
link), a landmark's alterations need the Commission's written approval, a recently
rezoned district may not be on the City's map yet, an ADU zone's limits apply; and
the ones true of every parcel: the alderman's notice role, the map's 90-day lag, the
code's vintage and the City's Zoning Verification Letter as the official
confirmation. The code statements are pinned to the ingested text; the letter's fee
and timing are the Office of the Zoning Administrator's published terms as checked on
2026-09-30. The kit requires exactly the right notes on each parcel (7 of 7). One note,
the Chicago Historic Resources Survey demolition hold, is unit-tested only because no
kit parcel is rated orange or red
([report](eval/results/2026-10-02-v4/parcel_kit.md)).

V5 stops the chat model from writing its own sources. The kit now counts the URLs in
each chat answer that we did not supply (that appear nowhere in the parcel's Profile
payload): 9 of 18 in the first baseline run, 5 of 14 and 1 of 10 in two later runs,
including American Legal links whose ids the model composed (one id cited for two
different sections) and Legistar links nobody gave it. A streaming guard now drops any
URL we did not supply (a link keeps its words), and a sources block is appended from
the provenance map and the code chunks the answer actually cited, with the code's
current-through date. Replaying the recorded answers through the guard offline shows
what it removes (10, 5 and 1 URLs) and that every URL we supplied survives. This is
**not verified on live chat**: it needs chat credits, and the guard is deliberately
conservative (a real City page the model wrote is dropped unless we supplied it).

**Lot coverage**, 100 fixed addresses, 0 fetch errors:

| Field | Coverage | Note |
|---|---:|---|
| PIN resolved and matches the county's | 97% | The 3 misses are adjacent W 19th St addresses the county data doesn't match confidently; the profile marks them unconfirmed instead of guessing |
| Land area, class, zoning, assessment history, tax bill and rate | 100% | |
| Zoning FAR | 98.9% | |
| Building area, year built | 88% | Misses are almost all tax-exempt parcels, which the assessor doesn't characterize |
| Stories | 69% | Secondary field |
| Units | 31% | Secondary field; no reliable non-residential source |

**After fix F6 (2026-10-02, [report](eval/results/2026-10-02-f6/lot_coverage.md)).** Building area read
76 present / 12 missing / 12 explained absences. The 12 are not a regression: they
are members of multi-PIN commercial units (Presidential Towers' 745,629 sq ft across
7 PINs, a 27-PIN unit) whose assessor total had been attributed to a single lot.
The Profile now withholds that figure for such a lot, shows the unit total beside it
as "recorded for an N-parcel complex", and the coverage suite counts it as an
explained absence rather than a miss or a hit. PIN, land, year built and zoning FAR
are unchanged and there were 0 fetch errors. The kit's scores did not move (the
kit has no field for existing FAR); the check that matters is the P3 payload: no
floor area for the lot and no FAR of 10.07.

`/api/scorecard` latency from a laptop: p50 3.1 s, p90 7.3 s. First lookups on
the production server take 15–40 s, so most of the production wait is the
server's own network path to the city and county APIs, not the application.

## History (recovered from git)

The earlier reports were removed in a July documentation cleanup; they are
recovered from git history into [`history.csv`](eval/results/history.csv).

| When | Suite | Result | What changed |
|---|---|---|---|
| May 28 | Full pipeline | 22/26 → 26/26 pass; p95 latency 59 s → 24 s | Router generates better search queries for zoning retrieval |
| May 30 – Jun 1 | Retrieval (18 q) | A: 6 → 11 → 13 → 15 | Embedding upgrade, keyword boost, table consolidation; then reranking and batched cross-references |
| Jun 4 – 6 | Source coverage | 73% → 89% → 93% | Missing sources wired in; 3 hallucinations fixed |
| Jun 9 | Retrieval (28 q) | 75% → 100% A/B | Synonym expansion, keyword-aware dedup |
| Jul 3 | Lot coverage | land 21% → 100%, building 20% → 88%, FAR 83% → 98.9%, **tax 0% → 100%** | Four root causes (below) |
| Sep 28 | Retrieval (28 q) | 24 A / 4 B | Stale gold label corrected (below) |

## Failures the evals turned into fixes

- **Production served no tax data for weeks.** The lot-coverage panel showed
  `tax_bill` missing for every parcel: the 9.4 GB property-tax database had
  never been seeded on the server, and the code degraded silently. It is now
  seeded, and `/health` reports whether it's present.
  ([write-up](claude-context/archive/2026-07-03_lot-info-robustness.md))
- **Hand-typed zoning numbers were fiction.** A calculation audit diffed
  `zoning_definitions.py` against the ordinance text already in the repo and
  found invented heights and a lot-coverage standard that doesn't exist in
  Title 17. The parity test now blocks that class of error in CI.
  ([write-up](claude-context/archive/2026-07-06_calc-audit.md))
- **The report timed out, and it wasn't memory.** The first suspect was OOM.
  Measurement showed the reranker hanging each search for 40–60 s, so the
  report now reads a precomputed zoning cache and the reranker is off.
  ([write-up](claude-context/archive/2026-06-16_report-oom-reranker.md))
- **A neighbor's parcel shown as "exact".** Two address resolvers disagreed.
  The fix only trusts a fallback PIN when its own address round-trips to the
  input; otherwise the profile says the parcel is unconfirmed.
  ([write-up](claude-context/archive/2026-06-21_pin-resolution-seam.md))
- **A stale label, not a regression** (Sep 28). `demolition_permit` graded D:
  the top result was §14A-4-407, "DEMOLITION". When the question was written,
  the building code (Title 14) wasn't indexed, so its gold named adjacent
  chapters. Since Title 14 was indexed, retrieval found the better section.
  The gold now includes 14A-4-407 and 11-4-2170, and the reason is recorded on
  the question. Labels are changed only with that kind of evidence.

## Known gaps

Stated plainly, since these limit what the numbers above can claim:

- **The LLM judge is reference-free and Sonnet grades Sonnet.** It scores
  faithfulness to the retrieved context, not correctness against a known
  answer, and it has not been calibrated against human grades. Next step:
  about 15 zoning questions with gold answers drawn from the parity-tested
  tables, a separate correctness dimension, and a hand-graded sample to
  measure judge agreement.
- **Small n per category.** 44 router questions across ~30 categories means
  one question moves a category's rate a lot. Totals are meaningful;
  per-category rates mostly aren't.
- **Single-turn, English, hand-written.** No multi-turn, Profile→chat
  hand-off, Spanish, or adversarial (prompt-injection) cases yet, and none are
  sampled from real traffic, although `request_logs` records it.
- **Nondeterminism isn't measured.** The router runs at the default
  temperature and each question is run once. Temperature 0 plus pass@3 would
  separate flakiness from real regressions; that change should land together
  with a router eval run showing it doesn't cost accuracy.
- **Coverage "hallucination" is regex-based.** `source_coverage` flags a
  hallucination when an answer matches a data pattern for a source that isn't
  in the context. Loose patterns can produce false positives, so these are
  leads to read, not verdicts.

## Running the evals

```bash
make setup                        # once
# $0 suites (need a populated Qdrant; lot coverage needs a running backend)
PYTHONPATH=. python -m eval.retrieval_benchmark --out eval/results/$(date +%F)/retrieval.md --json-out eval/results/$(date +%F)/retrieval.json
PYTHONPATH=. python -m eval.lot_coverage --full http://localhost:8001 --out eval/results/$(date +%F)/lot_coverage.md --json-out eval/results/$(date +%F)/lot_coverage.json

# LLM suites (spend API credit; lift the anonymous rate limit and budget for the run)
RATE_LIMIT_ANON_DAY=0 RATE_LIMIT_ANON_HOUR=0 DAILY_API_BUDGET_USD=25 uvicorn backend.main:app --port 8001
PYTHONPATH=. python -m eval.run_eval --router-only --json-out eval/results/$(date +%F)/router.json
PYTHONPATH=. python -m eval.run_eval --full http://localhost:8001 --judge --json-out eval/results/$(date +%F)/full.json
PYTHONPATH=. python -m eval.source_coverage --full http://localhost:8001 --json-out eval/results/$(date +%F)/coverage.json
```

`run_eval --json-out` records the git SHA, the router and synthesizer models,
and a hash of `backend/prompts.py` with every run, so results are only
compared when they measured the same system. Append a row to
[`history.csv`](eval/results/history.csv) for each run you keep.
