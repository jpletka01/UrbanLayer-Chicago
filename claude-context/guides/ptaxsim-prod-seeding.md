# Runbook: Seed ptaxsim.db on Production

**Why**: prod has served ZERO tax data (bill, rate, agency breakdown) since launch —
ptaxsim.db is optional-by-design and was never seeded on the box. Verified 2026-07-02
(`/api/scorecard` returns `estimated_annual_tax: null` on prod for parcels where local
returns a full bill). Findings: `claude-context/audits/2026-07-02_lot-coverage-benchmark.md`.

**After the fix ships** (`feat/lot-info-robustness`): `GET /health` reports
`"ptaxsim": true|false` (non-gating) and startup logs a WARNING when the DB is absent —
run the deploy first or this stays silent.

## Steps (run as root on 178.105.184.66)

```bash
# 1. Disk headroom — need ~11 GB free during the operation (1 GB .bz2 + 9.4 GB db)
df -h /
docker system df   # reclaim with `docker system prune` if tight

# 2. Download + decompress on the HOST first (~1 GB download, ~9.4 GB final).
#    NOTE: /opt/urbanlayer/backend/data is just the git tree — the container's
#    /app/backend/data is the NAMED VOLUME `backend_data`, so a host-side file
#    is invisible to the container until copied in (step 3).
cd /opt/urbanlayer
python3 scripts/download_ptaxsim.py   # writes backend/data/ptaxsim.db on the host

# 3. Copy into the backend_data volume (this is what actually seeds it),
#    then delete the host copy — disk is tight (the cp doubles usage briefly).
docker compose cp ./backend/data/ptaxsim.db backend:/app/backend/data/
rm backend/data/ptaxsim.db

# 4. Confirm the container sees it (path must match settings.ptaxsim_db_path)
docker compose exec backend ls -la /app/backend/data/ptaxsim.db

# 5. Restart backend so the lazy connection picks it up cleanly
docker compose restart backend
```

## Verify (live API, not just file presence)

```bash
curl -s "https://urbanlayerchicago.com/health"
#   → expect "ptaxsim": true

curl -s "https://urbanlayerchicago.com/api/scorecard?address=741+W+79Th+St" \
  | python3 -c "import json,sys; p=json.load(sys.stdin)['context']['property']; \
      print(p.get('estimated_annual_tax'), p.get('tax_code'), len(p.get('tax_breakdown') or []))"
#   → expect a dollar figure, a 5-digit tax code, and ~11 line items (was: None None 0)
```

Then re-run the coverage benchmark against prod to log the jump:
`PYTHONPATH=. python -m eval.lot_coverage --full https://urbanlayerchicago.com`

## Notes

- The DB is ~1 tax-year behind the calendar by design; `estimate_tax` clamps per-PIN.
- Annual refresh: CCAO publishes a new ptaxsim release each year (URL pinned in
  `scripts/download_ptaxsim.py`) — bump the URL and re-run this runbook.
- 4 GB RAM box caveat does not apply (box is 8 GB); the DB is read lazily via
  aiosqlite, not loaded into memory.
