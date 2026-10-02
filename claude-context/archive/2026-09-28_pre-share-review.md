# Pre-share review and production hardening (2026-09-28)

**Completed**: 2026-09-28
**Status**: Shipped to production (PRs #24–#30, plus #20)

## What was done
A multi-lens review before sharing the repo publicly: discovery (codebase map, clean-clone
health check, live-site audit, git/security audit), then five reviewer personas (AI-consultancy
senior engineer, first-time visitor, clean-clone onboarding, appsec/production readiness, code
skimmer), then a prioritized plan executed as small PRs, each verified on the live site. The
production server was then hardened with `deploy/hardening-runbook.md`. The reusable workflow is
the personal `pre-share-review` skill; the repo-specific follow-through is in the `ship-and-verify`,
`live-site-sweep` and `eval-refresh` skills (`.claude/skills/`).

| PR | Scope |
|---|---|
| [#24](https://github.com/jpletka01/UrbanLayer-Chicago/pull/24) | Security: real client IP for rate limits, ownership checks, fail-closed prod config, CSP, input validation |
| [#25](https://github.com/jpletka01/UrbanLayer-Chicago/pull/25) | Visible bugs: chat crash, Discovery CSRF race, fake homepage data, verdict contradiction, 404, Chicago-only, honest loading |
| [#26](https://github.com/jpletka01/UrbanLayer-Chicago/pull/26) | Repo hygiene + onboarding: lint in CI, hermetic tests, Makefile, env examples, Node 24 |
| [#27](https://github.com/jpletka01/UrbanLayer-Chicago/pull/27) | Evals: EVALS.md, fresh $0 runs, history recovered from git, citation checker, cost table |
| [#28](https://github.com/jpletka01/UrbanLayer-Chicago/pull/28) | README rewrite; anonymous 401 console errors |
| [#29](https://github.com/jpletka01/UrbanLayer-Chicago/pull/29) | "Purchases coming soon" while Stripe is unconfigured |
| [#30](https://github.com/jpletka01/UrbanLayer-Chicago/pull/30) | Runbook corrections; unused zoning collection removed |

## Bugs found (all fixed)
- **Security:** anonymous rate limits keyed on the client-controlled first `X-Forwarded-For`
  entry (unlimited anonymous chat, and a way to exhaust the shared daily LLM budget); upload
  download/delete with no ownership check; any conversation's upload list readable anonymously;
  any signed-in user could read any conversation's share token; `/chat` loaded another
  conversation's turn summaries and uploads by id; "clear all" deleted every user's upload
  files; fail-open defaults (no Google client id = everyone admin, a public dev JWT secret,
  unsigned Stripe webhooks); PIN interpolated unvalidated into SoQL; mock reports reachable by
  customers; Stripe webhook retries double-counted purchases.
- **User-facing:** parcel chat crashed on `change_pct=None` ("new this month" trend categories;
  broken since July); Discovery empty on first visit (CSRF cookie race); homepage demo card
  showed invented facts for a real address; verdict said "built at the limit" beside "66% unused";
  out-of-Chicago addresses got a full profile with the $25 offer; unknown routes rendered blank;
  "~2 seconds" claimed while cold lookups take 15–40 s; the CSP blocked Clarity and the theme
  script; anonymous pages logged 401s; buy buttons failed silently (Stripe unconfigured);
  `[data:vacant_buildings]`/`[data:food_inspections]` rendered as literal text; rules-of-hooks
  crashes in two charts.
- **Measurement:** the LLM judge's documented weights were never applied and fenced replies
  scored all-F; a retrieval "regression" was a stale gold label (Title 14 indexed after the
  question was written); Haiku 4.5 priced at 3.5 rates and cache tokens unpriced in the budget cap;
  five unit tests made real network calls and the zoning parity test silently skipped in CI.

## Lessons worth keeping
- **Verify on the live site, every time.** Each PR was checked through the public API and the
  served bundle (a string only the new code contains), and finished with the live sweep.
- **"Degrades gracefully" hides test leaks.** A conftest guard that fails any network attempt
  found five tests quietly calling Socrata or a local Qdrant.
- **A failing eval case is a question, not a verdict.** Check whether the label is stale before
  "fixing" retrieval (the demolition case), and record why a label changed.
- **The hosted deploy action (Go SSH) negotiates ECDSA first:** pin the server's ECDSA host key.
- **`adduser --system` needs `--home`** or sshd never finds the user's key.
- **Hetzner Cloud Firewall, not ufw,** for Dockerized hosts (Docker bypasses ufw).
- **Without required checks, `gh pr merge --auto` merges immediately.** `main` now requires
  `test` + `lint`, and repo auto-merge is off.
- **`gh run list --limit 1` isn't reliably newest-first here;** use explicit run ids.
- **Check claims against the server before writing them down:** "backups never ran" was wrong;
  the server's cron entry had the right path all along.
