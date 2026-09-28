#!/usr/bin/env bash
# Keep the homepage's demo addresses warm.
#
# A cold Property Profile fans out to 25+ public data sources (15–40 s); a warm
# one comes from the backend's TTL caches in about a second. The "Try" chips on
# the homepage are what a first-time visitor clicks, so this requests them after
# each deploy (the caches are in-memory and reset on restart) and on a timer
# (deploy/warm-demo-cache.timer, every 10 minutes; the shortest source cache is 15).
# GET /api/scorecard makes no LLM calls.
set -u
BASE="${1:-https://urbanlayerchicago.com}"
for address in "1601 N Milwaukee Ave" "4520 N Clark St" "1550 N Wells St"; do
  curl -s -o /dev/null -m 90 -w "%{http_code} %{time_total}s  $address\n" \
    -G "$BASE/api/scorecard" --data-urlencode "address=$address" || true
done
