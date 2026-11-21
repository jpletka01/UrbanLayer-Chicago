# Error tracking: Sentry releases, source maps and triage (2026-11)

## Item 134: Sentry events tagged by deploy, frontend source maps, and a triage skill (2026-11-21)

- **Status:** built on `chore/sentry-release-triage`, gates green, not merged. The owner asked for a setup where Sentry issues can be worked by Claude Code, with fixes reaching him as PRs.
- **What was missing:** neither `sentry_sdk.init` (backend) nor `Sentry.init` (frontend) set a release or an environment, and the frontend shipped no source maps. A Sentry issue couldn't say which commit served it, local errors mixed with production ones, and frontend stack traces were minified (`index-*.js`), so neither a person nor an agent could map them to a file.
- **Decision:**
  - **Release = the deployed git SHA, environment = `production`**, set in `docker-compose.prod.yml` for both images. `deploy/urbanlayer-deploy.sh` exports `GIT_SHA` after its fast-forward. Code defaults are `development` and no release, so a local run never reads as production. The backend sets them through `Settings.sentry_environment` / `sentry_release`. The data-health alarm sender (`data_health/alerting.py`, its own `sentry_sdk.init`) picks up the same `SENTRY_ENVIRONMENT` / `SENTRY_RELEASE` env vars through the SDK's own defaults.
  - **Source maps through `@sentry/vite-plugin`, inside the image build.** Maps are built `hidden` (no `sourceMappingURL` comment) and deleted from `dist/` after upload. The plugin only runs when `SENTRY_AUTH_TOKEN`, `SENTRY_ORG` and `SENTRY_PROJECT` are all set, so dev, CI and a server without the token build exactly as before (`build.sourcemap: false`).
  - **The token is a BuildKit secret** (`secrets: sentry_auth_token` from the server's `.env`), never a build arg, so it's not in the image history.
  - **A triage skill, not an automatic routine yet:** `.claude/skills/sentry-triage/SKILL.md` sorts open production issues into data-health alarm / third-party noise / already fixed / fix / needs the owner. It fixes up to 3 with a failing test first and opens one PR per run (the owner's batch-merge rule). It never merges, never changes an issue in Sentry, and keeps request data out of the public PR.
- **Alternatives:**
  - *Upload maps from CI's own `npm run build`* instead of the server's image build. Rejected: CI's bundle is built without the DSN or Clarity ID, so its chunks differ from the served ones, and the maps wouldn't match.
  - *`sentry-cli` after the build* in the deploy script. Rejected: the maps are inside the image by then, and the deploy user is command-locked to one script.
  - *Token as a build arg.* Rejected: build args are kept in the image history.
  - *Sentry's own Seer autofix.* Not chosen for now: it doesn't run our gates (`make check`) or follow the repo's conventions, and its availability depends on the Sentry plan.
  - *A scheduled routine from day one.* Deferred: run the skill by hand on real issues first, then schedule it once its triage calls look right.
- **Why (checked 2026-11-21):**
  - Compose v5.1.3 with the secret's env var unset: the build continues and the secret file is empty. With it in `.env`: the secret is present. Checked with a throwaway Dockerfile.
  - `docker compose -f docker-compose.yml -f docker-compose.prod.yml build frontend` with no token: exit 0, 0 `.map` files in the image.
  - `vite build` with a fake token: the plugin logs `401 Unauthorized`, the build **exits 0**, debug IDs land in 54 chunks, and 0 maps are left in `dist/`. A bad or revoked token can't fail a deploy.
  - `vite build` with a placeholder DSN and `VITE_SENTRY_RELEASE=relcheck123`: the bundle carries `environment:"production",release:"relcheck123"`. Without a DSN the minifier drops the whole `Sentry.init` block, so local builds carry nothing.
- **Owner's steps before it works in production:**
  1. Reinstall the deploy script on the server (it's a root-owned copy).
  2. Add `SENTRY_AUTH_TOKEN` (an org token with the `project:releases` scope), `SENTRY_ORG` and `SENTRY_FRONTEND_PROJECT` to the server's `.env`.
  3. Sign in to the `sentry` MCP server in Claude Code.
- **Revisit if:** the server's Docker can't run `RUN --mount=type=secret` (BuildKit is needed; Compose v2+ always uses it); Sentry stops resolving frames with debug IDs; the triage skill's calls are right often enough to schedule it.

**Numbers**
- Releases tagged on production events: 0% → 100% once the deploy script is reinstalled (not measured live yet).
- Frontend events with source-mapped frames: 0% → expected 100% of releases built with the token (not measured live yet).
- Image size: unchanged, since the maps are deleted before the nginx stage copies `dist/`.
- **Reproduce:** `SENTRY_AUTH_TOKEN=x SENTRY_ORG=x SENTRY_PROJECT=x npx vite build; find dist -name '*.map' | wc -l` (expect 0, exit 0).
- **Not measured:** the upload's added build time on the server (the plugin uploads about 55 chunks' maps); whether EU-region org tokens need `SENTRY_URL`.
