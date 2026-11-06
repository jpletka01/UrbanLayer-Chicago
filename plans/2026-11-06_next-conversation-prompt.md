# UrbanLayer handoff — WS2 PR4 (updated 2026-11-06, end of session)

Work in the main checkout at `/Users/jack/projects/chicago`. Read `CLAUDE.md`, `backend/CLAUDE.md` (WS2 section), `claude-context/core/known-issues.md` (WS2 PR4 entry) and decision Item 70 in `claude-context/decisions/2026-10_build-queue.md`. Inspect the branches and PRs yourself; don't take this file as proof.

## State

- **#192** `codex/ws2-proposal-reader` (draft, CI green): the offline Type 1 filing reader, now v5 (`ws2-pr4a-5`).
  - It downloads only the Ordinance (Legislation) and the Narrative and Plans (Exhibits); the Application and EDS are never requested.
  - Panels: `eval/filing_panel.json` (34 rows), `eval/filing_panel_historical.json` (15, spent) and `eval/filing_panel_accruing.json` (5, **sealed**).
- **#193** `codex/ws2-proposal-details-profile` (draft, based on #192; CI doesn't run on a non-main base): premium-gated proposal details on `/api/scorecard` plus the collapsed Profile UI. It is synced with #192. The phone and budget check ran with a local fixture: 76 passed. One failure, twoflat's Build section at 313 words, came from a stale local pending store; with fresh data it measures its 303-word baseline and passes.
- **#191** (dependency batch) is separate and untouched.
- Nothing is merged; `main` and production are unchanged. Both `pending_proposal_details_enabled` and `pending_filing_reader_enabled` are false, and `backend/pending_filing_details.json` is empty.

## Measured

| Reader | Held-out set | Precision | Recall | Wrong values | Gate |
|---|---|---|---|---|---|
| v3 | panel's own 13 rows | 93.1% | 80.6% | 4 | FAIL |
| v4 | 15 passed Type 1 filings, 2023–2026 | 96.8% | 76.3% | 2 | FAIL (zero allowed) |
| v5 | accruing set | – | – | – | sealed, 5 of 10 rows |

All labels are assistant drafts that no person has checked. Spent sets report `post_hoc` for any later reader.

## Jack's decision (2026-11-06)

Keep the gate rules as they are (30-row panel, ≥10 held out, precision ≥95%, recall ≥60%, **zero** wrong value/page/unit) and wait until the accruing set has 10 unseen filings, then score v5 once.

## Next steps (after the next City Council meeting with zoning introductions)

1. Find newly introduced pending Type 1 matters: `python -m backend.legislation.filing_reader --limit N --skip <every record already in the three panels> --head-sizes`, then `--download-dir research/pending-filing-pdfs/accruing`. The reader is frozen at v5; don't change parsing before scoring.
2. Label each new row from the page images under the rules in `eval/filing_panel.json`, add it to `eval/filing_panel_accruing.json`, and don't run the parser on it first.
3. At 10 or more rows: `PYTHONPATH=. python -m eval.filing_panel --fresh-panel eval/filing_panel_accruing.json --out eval/results/...`. Record the result whether it passes or fails, set `held_out_scored_with`, and update Item 70, known-issues, `history.csv` and the PR.
4. A pass still needs: Jack (or a person he names) checks the labels (`human_verified` + `verified_by`/`verified_on`); the phone-layout and budget check (`npm run test:mobile`) is re-run with real reviewed entries; and separate approval for every merge or deploy and for enabling the flag.

## Privacy

- Private PDFs and the OCR cache live under the ignored `research/pending-filing-pdfs/` (`panel/`, `historical/`, `accruing/`), plus 21 older flat PDFs from the first pass, kept until Jack decides.
- Never commit PDFs or OCR text. Pre-2023 matters are single combined PDFs (which would bundle the EDS), so they are not a source.
- No model call is authorized for this reader.
