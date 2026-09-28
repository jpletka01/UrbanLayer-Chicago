#!/usr/bin/env bash
# Production deploy, run by CI over SSH as the unprivileged `deploy` user.
#
# Installed root-owned at /usr/local/bin/urbanlayer-deploy and pinned as the
# forced command on the deploy key (see deploy/hardening-runbook.md), so the
# key can run exactly this and nothing else: whatever command the SSH client
# asks for is ignored. `deploy` may sudo this one script, which is why it is
# root-owned and not writable by that user.
set -euo pipefail

cd /opt/urbanlayer
git fetch origin
# Fast-forward only: a server-side divergence should stop the deploy, not be
# silently merged into what production serves.
git merge --ff-only origin/main
# A failed --build must fail the deploy (set -e). Otherwise the old image keeps
# running and the health check below passes on stale code.
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
sleep 10
curl -sf https://urbanlayerchicago.com/health
# Re-warm the homepage demo addresses (the restart emptied the caches).
nohup /opt/urbanlayer/deploy/warm-demo-cache.sh >/dev/null 2>&1 &
