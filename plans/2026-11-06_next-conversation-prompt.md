# UrbanLayer handoff — 2026-11-06

Work in the main checkout at `/Users/jack/projects/chicago`. Read `AGENTS.md`, the relevant repo skills, `backend/CLAUDE.md` WS2 section, `claude-context/core/known-issues.md` WS2 entry, `claude-context/decisions/2026-10_build-queue.md` Item 70, and `plans/2026-10-27_next-wave.md` §§6.9–6.13. Do not assume prior assistant statements are proof; inspect code and PRs.

## State

- `main` was not changed or deployed in this conversation. Current checkout is `codex/ws2-proposal-reader`, pushed to origin. Check its HEAD at the start of the next session.
- Draft PR #192: https://github.com/jpletka01/UrbanLayer-Chicago/pull/192 — WS2 PR4a offline groundwork. CI test, lint, and CodeQL passed; deploy skipped. It is not a completed proposal-detail feature.
- PR #191: https://github.com/jpletka01/UrbanLayer-Chicago/pull/191 — independent dependency batch, open, checks passed. Do not accidentally combine it with #192.
- Preserve unrelated untracked `.claude/launch.json`, `frontend/vite.wave.config.ts`, and other files in `plans/`. This handoff file is untracked and local only unless deliberately added to Git.
- WS2 PR3 is already shipped. The monthly review of `backend/pending_impacts.json` is ongoing operational work.

## What #192 actually contains

- Default-off `pending_proposal_details_enabled` and `pending_filing_reader_enabled` flags.
- Offline Type 1 Clerk metadata selection and HEAD size manifest, bounded private PDF download, local page OCR/EDS screening, narrow deterministic label parser.
- Empty committed `backend/pending_filing_details.json`, validator requiring `hand_reviewed` fields and page citations, and `internal.pending_filing_details_review` health probe.
- Evaluation helper with 30-panel/10-held-out minimum, 95% precision, 60% recall, and zero wrong page/unit/value gate. This is code for a gate, **not a measured result**.
- Decision Item 70, backend context and known-issues updates. Local non-integration backend suite: 2,751 passed, 66 deselected; PR CI passed.

## Safety correction and private sample

Clerk query found 921 pending candidates and 192 likely Type 1 title hits. A 30-file metadata manifest totalled 16,318,264 bytes. All 30 were downloaded privately under ignored `research/pending-filing-pdfs/`. OCR found bundled EDS page 2 in nine packets. Those nine downloaded copies were deleted; 21 PDFs remain. The first downloader had briefly retained the packets; the corrected code rejects any packet with an EDS or unreadable page. OCR classification is not proof that all remaining pages are EDS-free. Human page review is required before labels or publication. Never commit PDFs or real OCR transcripts. No model was called.

## Remaining work

1. Complete a hand-checked 30-filing panel using only safe pages; find additional candidates as needed. Reuse PR3's 20 Legislation PDFs only where appropriate. Record train/held-out split, actual precision and recall, wrong-unit/page counts, and parser coverage. If the gate fails, record failure and leave the reader off. Do not invent labels or a passing score.
2. Make PR4a reviewable as a complete quality-gated offline reader; inspect and strengthen page-level EDS handling and artifact validation. The current narrow parser has no from/to district extraction and no measured accuracy. The current draft PR is groundwork, not ready to merge as the feature.
3. Implement PR4b separately: optional user resolution on `/api/scorecard`; apply gating after shared cache; premium response `Cache-Control: private, no-store`; free/anonymous JSON must contain no extracted value or PDF URL. Stripe is not set up, so premium currently means voucher/admin comps. Remove proposal details from the frontend `scorecard_context` sent to chat. Keep chat/report grounding out of scope. Join only current lifecycle, record, attachment URL/name/type against the reviewed artifact; same-URL replacement cannot be checked on the request path.
4. Keep `pending_proposal_details_enabled=false` until separately approved field-by-field production verification. `pending_filing_reader_enabled=false` is reserved for a future model fallback; no production model use is authorized. UI disclosure starts collapsed; dates, page citations and links in evidence tray, units on numbers, Lucide icons, es-MX usted translations, Profile budget/mobile gates. Add the About-page deterministic-reading entry. Update docs and decisions for the actual implementation.
5. Do not merge either PR into `main` without explicit deploy approval. User previously authorized pushing branches and opening PRs, but not merging. The user asked for minimal check-ins and to carry work through rather than stopping at routine milestones.

At the start of the next conversation, audit the actual branch/PR state, then continue the unfinished WS2 PR4 wave. Report any material blocker honestly. Never state that the full wave or its accuracy gate is complete until measured evidence exists.
