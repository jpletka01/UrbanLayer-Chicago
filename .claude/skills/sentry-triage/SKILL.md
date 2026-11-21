---
name: sentry-triage
description: Triage UrbanLayer's open Sentry issues and fix the ones that are real code bugs, ending in one branch and one PR that the owner merges. Use when asked to look at Sentry, check what's broken in production, fix reported errors, or run the scheduled Sentry sweep. Needs the Sentry connector (MCP server `sentry`). Never merges, never changes an issue's status in Sentry, never touches the server.
---

# Sentry triage

Turns open production errors into reviewed fixes. A run reads Sentry, sorts each issue into one of
four outcomes, fixes at most **3** real bugs on one branch, and opens **one** PR (the owner wants
ready work batched into one PR and one deploy). Merging deploys, so it stops at the PR.

## 0. Before you start

- The Sentry connector must answer. Call its `whoami`; if it fails, say "Sentry isn't connected:
  run `/mcp` → sentry → Authenticate" and stop.
- Org and projects (EU region): fill in on the first connected run and commit the change.
  - org: `TODO`
  - backend project: `TODO` · frontend project: `TODO`
- Start from fresh `origin/main`: `git fetch origin && git switch -c fix/sentry-<yyyy-mm-dd> origin/main --no-track`.
  Leave any other branch's work alone.

## 1. List what's open

Ask Sentry (`find_issues`) for **unresolved** issues in **`environment:production`**, both projects,
seen in the last 14 days, most events first. Take up to 15. Events without an environment tag
predate 2026-11-21 (Item 134); treat them as production, but say so.

## 2. Sort every issue into one outcome

| Outcome | How to tell | What to do |
|---|---|---|
| **Data-health alarm** | fingerprint/title starts `data-health`, "Data source stale", the Cron monitor `data-health-check`, or the weekly kit gate | Not a code bug. List it and point at `claude-context/guides/data-health.md`. |
| **Third-party noise** | top in-app frame is outside our code (Clarity `clarity.ms`, browser extensions, `chrome-extension://`, a bot's user agent, `ResizeObserver loop`) | List it. Suggest an inbound filter for the owner; don't add code to swallow it. |
| **Already fixed** | the event's `release` SHA is older than a commit that touches the failing frame: `git log --oneline <release>..origin/main -- <file>` | List it with the fixing commit. The owner resolves it in Sentry. |
| **Fix** | the failing frame is in `backend/` or `frontend/src/`, and you can write a test that fails the same way | Fix it (step 3), at most 3 per run. The rest are listed as "next run". |
| **Needs the owner** | can't reproduce, needs a product call, touches billing/auth/identity, prompts, zoning data, or a committed data artifact | List it with what you found and the question to ask. |

Read each issue with `get_issue_details` (stack, latest event, tags, release). For the frontend,
frames should show real file names. If they're minified (`index-*.js`), source maps were missing
for that release (no `SENTRY_AUTH_TOKEN` on the server at build time). Say so, and match by the
error message.

## 3. Fix

For each **Fix** issue, in its own commit:

1. Find the code. Load context first with the `load-urbanlayer-context` skill when the area is new.
2. Write the failing test first (backend: `backend/tests/`, hermetic, mock the source; frontend:
   vitest beside the file). It must fail for the reason Sentry shows.
3. Make the smallest fix that passes it. Follow `backend/CLAUDE.md` patterns: a failed source
   raises and caches nothing (Item 65), never returns a checked "none".
4. Commit: `fix(<area>): <what broke> (Sentry <SHORT-ID>)`.

Then gate the branch exactly as CI does: `make check`. `npm run lint` must exit 0 (warnings are
capped). A red gate you can't fix moves that issue to **Needs the owner** and drops its commit.

## 4. One PR

`git push -u origin HEAD`, then `gh pr create --base main`. Body: one section per fixed issue with
the Sentry short ID, the error type and message, the failing frame, the cause in a sentence, and
the test that covers it, plus the full triage table from step 2.

**The repo is public.** Put in the PR only the error type, the message, and our own frames. Never
paste request data, URLs with query strings, breadcrumbs, user or IP fields, cookies, or the
addresses people searched.

Don't use `Fixes <ID>` keywords or change any issue's status: the owner merges, and resolves in
Sentry once the fix is live (the release tag shows which deploy carried it).

## Never

- Merge, push to `main`, or enable auto-merge.
- Touch the production server, or run anything that spends Anthropic API credits (no live chat,
  kit or judge runs). Chat tests only when the fix is in chat itself.
- Resolve, ignore, assign or comment on Sentry issues.
- Fix more than 3 issues or open more than 1 PR in a run.

## Report

End with the triage table (issue, events, outcome, one line) and the PR link, or "nothing to fix"
when no issue was a **Fix**.
