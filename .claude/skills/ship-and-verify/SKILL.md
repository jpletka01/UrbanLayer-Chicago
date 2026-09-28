---
name: ship-and-verify
description: Ship a change to UrbanLayer production and prove it is live. Use whenever code or docs need to reach `main` — branch, local gates, PR, required checks, merge (which deploys), then verification against the live site. Covers the repo's branch protection, the CI deploy path, and the gh/GitHub gotchas that bit on 2026-09-28.
---

# Ship and verify

`main` **is** production: merging to `main` deploys within minutes. So every change goes
branch → PR → required checks → merge → live verification, and **the user approves each merge**
(ask; approval for one PR doesn't carry to the next).

## 1. Branch and gate locally

```bash
git checkout main && git pull origin main && git checkout -b <type>/<short-name>
make check    # ruff, eslint (0 errors, warnings capped), backend + eval-scorer + vitest tests, npm run build
```

- `main` has branch protection with **required checks `test` and `lint`, enforced for admins**:
  every change, docs included, needs a PR. Direct pushes to `main` are rejected.
- `npm run build` (strict `tsc -b`) is the real frontend gate, not `tsc --noEmit`.
- Unit tests must stay hermetic: `backend/tests/conftest.py` fails any test that opens a network
  connection. Mock the source; don't loosen the guard.
- Keep commits small and logical, conventional-commit style, with the attribution trailer the
  session provides. Split a file across commits with hunk staging rather than lumping.

## 2. PR, checks, merge

```bash
git push -u origin HEAD
gh pr create --base main --title "…" --body "…"    # what changed, why, how verified
```

- **Repo auto-merge is disabled.** `gh pr merge --auto` errors; without required checks it
  used to merge instantly. Wait for the checks instead: start one background `sleep 240`, then
  read the result once. Don't write a polling loop.
- Read the checks: `gh pr view <N> --json mergeStateStatus,statusCheckRollup`.
  `CLEAN` plus `test`/`lint` = `SUCCESS` → `gh pr merge <N> --merge` (merge commits, matching
  history).
- A Dependabot PR that's behind `main`: comment `@dependabot rebase`, or test the merge
  locally in a worktree before merging.

## 3. What happens on merge

CI (`.github/workflows/ci.yml`): `test` + `lint` → `changes` (skips deploy when only `.md` or
`claude-context/` changed) → `deploy`. Deploy SSHes in as the **`deploy`** user, whose key is
command-locked to `/usr/local/bin/urbanlayer-deploy`: fast-forward merge, `docker compose up
--build`, health check, cache warm. The host key is pinned (`SERVER_HOST_FINGERPRINT`, the
server's **ECDSA** key). A failed build fails the job and the old containers keep serving.

## 4. Verify it's live (don't trust git or a green job alone)

- **Frontend change:** wait until the served bundle contains a string only the new code has.
  Run it in the background so it notifies once:
  ```bash
  for i in $(seq 1 50); do js=$(curl -s https://urbanlayerchicago.com/ | grep -o 'assets/index-[^"]*\.js' | head -1); curl -s "https://urbanlayerchicago.com/$js" | grep -q '<unique string>' && { echo live; exit 0; }; sleep 30; done; exit 1
  ```
- **Backend change:** probe the endpoint whose behavior changed (e.g. a new status code or
  field), plus `curl -s https://urbanlayerchicago.com/health`.
- **Anything user-facing:** `cd frontend && npm run sweep:live` (see the `live-site-sweep` skill).
- Confirm the deploy job itself: `gh run view <run-id> --json jobs`.

## Gotchas

- **`gh run list --limit 1` is not reliably newest-first here** (it once returned a months-old
  run, which GitHub then refused to re-run). List several with `createdAt` and use explicit ids.
- Re-run only a failed deploy: `gh run rerun <run-id> --failed`. Secrets are read at run time,
  so fixing a secret and re-running works.
- `host key fingerprint mismatch` → the pin is the wrong key type; pin ECDSA.
- **Server access is the user's.** The auto-mode classifier blocks Claude's SSH reads and writes
  on production. Hand the user exact commands. `ssh urbanlayer-prod` logs in as `jack`;
  root login is disabled, so server commands need `sudo`, including `docker compose`. Break
  glass: Hetzner web console.
- The origin only accepts Cloudflare on 80/443 (Hetzner Cloud Firewall). To test the origin
  directly, `curl --resolve … <ip>` should time out; that's the expected result.
- Purchases are off (Stripe unconfigured); see `core/known-issues.md`.
