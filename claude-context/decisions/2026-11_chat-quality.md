# Chat answer quality (from 2026-11-12)

Decisions made while measuring and fixing chat answers. The audit itself is
`claude-context/audits/2026-11-12_chat-answer-audit.md`.

## Item 118: the chat answer audit (2026-11-12)

**Decision.** Measure chat with a wide, gold-labeled question set before changing any prompt or retrieval code:
`eval/chat_audit_questions.json` (71 questions, 15 follow-ups) and a deterministic scorer `eval/chat_audit.py`. The
$1 budget went to full answers on the questions that test the suspected failures (wrong use answers, over-fetching,
padding, follow-up context), and router-only plans on the rest. No production code changed; the fixes are the next
item, ranked in the audit.

**Alternatives.**
- *Extend `eval/queries.json`.* Its schema is one expected plan per question; this set needs a gold conclusion,
  source expectations both ways (need / not needed), relevant topics for the padding check, and a follow-up. A
  sibling file keeps `run_eval` unchanged.
- *An LLM judge.* Rejected for this pass: the budget, and EVALS.md's known gap (Sonnet grading Sonnet, uncalibrated).
  Every check here is a regex or a set difference, so a rerun after the fix is comparable.
- *Run every question end to end.* About $0.04 a turn; $1 buys about 25 turns. Breadth on the router (65 plans,
  about $0.004 each) plus depth on 19 turns measured both questions the owner asked: how common, and what carries.

**Why (evidence).**
- *Gold labels from the corpus, not memory.* Use rows were read from `ingestion/data/sections/17-{2,3,4,5}-0200.json`,
  bulk numbers from the parity-tested `zoning_definitions`, parcels from the parcel kit. Reading the RM-6 table
  changed the trigger case's own expected answer: 17-2-0207 row T permits a Residential Support Service in RM-6/6.5,
  17-17-0104-Y lists restaurants as one, and 17-9-0114 limits it to buildings with more than 50 units, first two
  floors, 5,000 sq ft. `/api/scorecard` for 443 W Wrightwood gives 176 units and 13 stories (Assessor commercial
  valuation), so the gold is "yes, inside this building, within those limits", not the "no" the owner and this
  audit's first draft assumed.
- *Spend read from the backend's own `llm_calls`*, on a fresh database for this worktree, so the table is the
  audit's log and `DAILY_API_BUDGET_USD=1.00` was a backstop. The router-only path ran in-process without an open
  database, and 54 calls went unlogged; their cost was estimated from the 19 logged router calls ($0.17–0.22), the
  total is $0.88–0.93, and the script now opens the database first.
- *A district-aware query was tested before being recommended*, and it failed: naming "RM-6" in the query still
  returns the B, D and M use tables. So the recommendation is a lookup by section, not a better query.

**Numbers** (2026-11-12, local backend at `d8a920d`, Sonnet 4.6 router and synthesizer, Haiku 4.5 rewrite):
- Correct conclusions 12 of 19 turns; confident-wrong use answers 4 of 19.
- Over-fetch 38 of 65 plans; parcel use questions 17 of 17; stored conversations 9 of 10 parcel-scoped questions.
- Padding 12 of 16 substantive answers; `[N]` drift 4 of 8 follow-ups; needless clarification 2 of 8 follow-ups.
- Router search query named a wrong district in 5 of 8 queries that named one.
- Cost per turn: mean $0.037; a cold parcel turn $0.07–0.09.
- *Reproduce:* `PYTHONPATH=. python -m eval.chat_audit score` (re-scores `runs.jsonl` and `router_runs.jsonl`),
  `… retrieval` and `… historical --db <chicago.db>`; none call a model. A new run: `… pairs --ids <ids> --cap 1.00`
  against a backend with `RATE_LIMIT_ANON_DAY=0 RATE_LIMIT_ANON_HOUR=0`.
- *Not measured:* run-to-run variance beyond the three stored runs of two questions (each question ran once here);
  the Profile dock path (no `conversation_id`, PIN sent each turn); Spanish; the 52 router-only questions' answers;
  production (local stack only).

**Revisit if** the scorer's regexes misread a new answer style (it was tuned against these 19 answers; its gold
patterns were written before the runs, the can't-tell pattern and three gold patterns were corrected after reading
them, recorded in the audit), or the use table or the router's source list changes.
