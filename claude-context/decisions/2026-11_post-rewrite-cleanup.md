# Post-rewrite cleanup (2026-11-25)

After the front-end rewrite (Items 73–133), a pass to delete what the old UI left behind. The scope and method are in the local plan `claude-context/plans/2026-11-25_post-rewrite-cleanup-prd.md`. The evidence, one row per candidate, is in `claude-context/audits/2026-11_cleanup-inventory.md`.

## Item 137: delete what only the old UI used, and make CI keep it that way (2026-11-25)

- **Decision (owner 2026-11-25: "go with your picks" on the inventory's seven questions).** Delete with evidence, not by age: every removal cites the search that found no caller (imports, and the name as a string across `frontend/src`, `e2e`, `backend`, `scripts`, `deploy`, `eval`, `ingestion`, nginx and compose). One branch, one commit per category:
  1. Frontend dead code: the old map colours (`lib/mapColors.ts`, 624 lines, one 10-line helper alive), `lib/analytics.ts`, the old chat input, Discovery's old chip strip and filter menu, the old Scorecard's failed-source module table, `parcelMap`, and about 40 unused exports. The few live pieces moved next to their only users.
  2. 1,453 translation keys nothing reads (en + es together), including the whole `landing` and `sidebar` namespaces.
  3. The Ask drawer moved onto the chat page's renderer (`ChatMessage` + `ThinkingSteps`). That deleted `MessageBubble` and the six pieces only it used. This is the one visible change.
  4. Backend: `GET /section/{id}` (and its nginx blocks), `GET /api/community-area`, `POST /api/newsletter` (the subscribers table stays), `failures.MODULES`/`in_module`, the area-stats scan, the deck.gl label helpers, the user lookups from before Item 121, and other functions only tests called.
  5. `knip --production` in CI, and the ESLint warning cap set to today's count.
- **Not done here, on purpose:**
  - **The retired $25 report's PDF path** (`/api/report`, `report_render.py`, the Jinja template, weasyprint/matplotlib/jinja2, Settings' purchases, the backup scripts' PDF mirror). It still serves past buyers' re-downloads and is wired into account deletion and backups. It goes in its own PR once the owner confirms the production database has no `report_purchases` rows.
  - **The `*Next*` file names, `src/components/`, `.ui-next`, `nx-*` and the `next` namespace.** Item 126 already decided to keep these internal names (the owner rejected the larger diff and its merge conflicts). The inventory had proposed renaming the files without having read Item 126, and this pass follows the earlier decision.
- **Alternatives:**
  - Delete by folder ("everything in `src/components/` is old UI"). Rejected: 11 of its files are live in `app/`.
  - Run `knip` once and stop. Rejected: deleting one file exposes the next (the filter menu was alive only through the chip strip), so the check runs in CI.
  - `knip` without `--production`. Rejected: test files count as entry points there, so a file only its test imports passes. A planted dead file proved it: production mode caught it and the default mode did not.
  - Keep test-only helpers. Kept only where a test uses them as the oracle for live behaviour (`provenance.entry_is_dated`, the index build's in-memory helpers, `layer_id_of`, `capacity_map.normalize_pin`, `count_user_messages`). Helpers that only test themselves went.
- **Why:**
  - `knip` 5.88 found 58 unused exports and 47 unused exported types in production mode.
  - A text-reference count over top-level Python definitions found 34 that only tests called or that nothing called.
  - A literal-key scan of the catalogs found 1,453 keys no code reads. It skipped keys under a prefix the code builds at runtime (`t(\`x.${y}\`)`) and keys under a parent read with `returnObjects`. A second check afterwards confirmed that every literal `t()` key left in the code still resolves.
- **Revisit if:**
  - The owner confirms zero report purchases: retire the PDF path (above).
  - `knip` blocks a deliberate export. Tag it `@internal` with the reason, as the three test reset hooks are.
  - The `next` namespace or the `nx-*` tokens start confusing new work (Item 126's own revisit).

**Numbers** (2026-11-25, this branch against `main` at `ecfacab`):

| Measure | Before | After |
|---|---|---|
| Frontend non-test source (`.ts/.tsx/.css` lines, `.ts/.tsx` files) | 37,094 lines, 199 files | 34,623, 185 |
| Frontend test source | 9,021 lines | 8,586 |
| Backend non-test `.py` | 53,556 lines, 178 files | 53,089, 177 |
| Backend tests | 40,788 lines | 40,325 |
| Locale JSON (en + es) | 11,577 lines, 8 namespaces | 7,449, 6 |
| Build, all chunks | 4,244 KB raw / 1,273 KB gzip | 4,049 / 1,212 |
| Main `index` chunk (every page loads it) | 864 KB / 280 KB gzip | 698 / 227 |
| ESLint warnings (cap) | 45 (65) | 35 (35) |
| vitest | 809 passed | 753 passed |
| pytest `-m "not integration"` | 3,341 passed | 3,308 passed |
| `knip --production` | 10 files, 58 exports, 47 types | clean |

- **Reproduce:**
  - `npm run build` (chunk sizes)
  - `git ls-files frontend/src | grep -E '\.(tsx?|css)$' | grep -vE '\.test\.|/test/' | xargs cat | wc -l` (and the backend equivalent)
  - `npx eslint . -f json`
  - `npm run knip`
  - `npx vitest run`
  - `python -m pytest backend/tests -q -m "not integration"`
- **Not measured:**
  - Page load time in production.
  - The live site's console after deploy (the `live-site-sweep` skill runs after the merge).
  - Integration tests, which need the live City services. Before this pass one of them failed on the City's 311 service, not on code.
