---
name: eval-refresh
description: Re-run UrbanLayer's eval suites, record dated results, and keep EVALS.md and eval/results/history.csv current. Use before and after changes to retrieval, chunking, prompts, the router, models, or Profile data sources, and whenever someone asks "did this make it better?". Covers the $0 suites (default) and the paid LLM suites (only with the user's OK), plus the rule for changing gold labels.
---

# Eval refresh

The quality story lives in `EVALS.md` (method, latest results, history, known gaps). Results go
in `eval/results/<YYYY-MM-DD>/`, and each kept run appends a row to `eval/results/history.csv`.

## 1. The $0 suites (run these by default)

They need the local Qdrant populated with the full corpus; lot coverage also needs a running
backend and `backend/data/ptaxsim.db`.

```bash
D=eval/results/$(date +%F); mkdir -p $D
RERANKER_ENABLED=false PYTHONPATH=. .venv/bin/python -m eval.retrieval_benchmark --out $D/retrieval.md --json-out $D/retrieval.json
RERANKER_ENABLED=true  PYTHONPATH=. .venv/bin/python -m eval.retrieval_benchmark --out $D/retrieval_reranked.md --json-out $D/retrieval_reranked.json   # the ablation (~75 s)
.venv/bin/uvicorn backend.main:app --port 8001 &      # in the background; wait for /health
PYTHONPATH=. .venv/bin/python -m eval.lot_coverage --full http://localhost:8001 --out $D/lot_coverage.md --json-out $D/lot_coverage.json   # ~20 min
```

Then copy `$D/retrieval.json` to `eval/benchmark_results.json`, which the admin dashboard
serves, and stop the backend you started.

## 2. The LLM suites (cost money, so ask first)

Router ~$0.50; full pipeline + judge ~$5; source coverage ~$2–3; about $7–10 all together. The
API balance is small, so get the user's explicit OK and say the estimate. Lift the anonymous
limits for the run only:

```bash
RATE_LIMIT_ANON_DAY=0 RATE_LIMIT_ANON_HOUR=0 DAILY_API_BUDGET_USD=25 .venv/bin/uvicorn backend.main:app --port 8001
PYTHONPATH=. .venv/bin/python -m eval.run_eval --router-only --json-out $D/router.json
PYTHONPATH=. .venv/bin/python -m eval.run_eval --full http://localhost:8001 --judge --json-out $D/full.json
PYTHONPATH=. .venv/bin/python -m eval.source_coverage --full http://localhost:8001 --json-out $D/coverage.json
```

`--json-out` records the git SHA, models and a prompt hash, so only compare runs that measured
the same system. In `--full` mode a query fails on any `citation_warnings`, the server's check
that every `[N]` / `[data:x]` is backed by the context.

## 3. Record it

- Append one row per kept run to `eval/results/history.csv`:
  `date,suite,git_ref,n,headline,notes`.
- Update the "Latest results" tables in `EVALS.md`, and the history table if something moved.
- Commit the results folder with the change it measures. Ship via the `ship-and-verify` skill.

## 4. When a case fails: system bug or wrong label?

Read what was retrieved before touching anything. On 2026-09-28 `demolition_permit` graded D
because retrieval found the *better* section (§14A-4-407 "DEMOLITION") after Title 14 was
indexed, and the gold predated that. Change a gold label only with evidence, and when you do:

1. put a dated comment on the query saying what changed and why;
2. note it in EVALS.md (the "Failures the evals turned into fixes" or history sections);
3. re-run so the committed result reflects the corrected label.

Never relabel just to make a number go up.

## Guardrails

- The scorer code is tested in CI (`eval/tests/`, `eval/test_judge.py`). If you change a
  scorer, update those tests; a scorer bug silently changes every number.
- Known gaps (reference-free judge, small n, single-turn English only, unmeasured
  nondeterminism) are listed in EVALS.md. Don't overclaim past them.
