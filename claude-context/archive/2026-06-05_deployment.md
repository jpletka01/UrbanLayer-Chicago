# Deployment bring-up (2026-06-05) — SHIPPED

Phase-by-phase first deploy to the Hetzner box (`178.105.184.66` / `/opt/urbanlayer`). All phases complete.
Live ops, `.env` template, deploy commands, monitoring, and backups are the **living** doc `guides/deployment.md`;
full infra narrative is on the About page → **Infrastructure & Deployment**. This file is a historical marker.

**Key facts that outlived the bring-up:** push to `main` = deploy (server auto-pulls + rebuilds); verify the
running image via the live API, not git HEAD.
