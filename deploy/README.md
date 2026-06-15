# Deploy units

## Property Discovery — monthly index rebuild

The prospecting index (`backend/data/discovery_index.db`, persistent volume) goes stale as CCAO
assessments/sales/characteristics update. These systemd units rebuild it monthly with `--refresh`
(which rebuilds exactly the community areas already in the index — so expanding coverage with a
one-off `--community-areas …`/`--all` run automatically carries forward).

### Install on the prod host (`178.105.184.66`)

```bash
cd /opt/urbanlayer && git pull               # get the unit files (this deploy/ dir)
sudo cp deploy/discovery-index-rebuild.service deploy/discovery-index-rebuild.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now discovery-index-rebuild.timer
systemctl list-timers discovery-index-rebuild.timer        # confirm next run
```

### Run a rebuild on demand

```bash
sudo systemctl start discovery-index-rebuild.service       # same as the monthly run
journalctl -u discovery-index-rebuild.service -f           # watch it
```

### Expand coverage (one-off), then let the timer follow

The builder is **memory-bounded by construction** (per-CA ingest + streaming finalize), and runs
**off the live backend** in an ephemeral `run --rm` container, so a build never OOMs the serving
process. `--community-areas` *adds* to the existing index (parcels upsert; meta is recomputed over
the whole accumulated index — `community_areas` / `populated_fields` / `recipe_counts` are correct
cumulatively, not just the last batch). `--refresh` afterwards rebuilds exactly the current set.

```bash
# off-box build (own cgroup, shares the backend_data volume, skips qdrant); then reload
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps backend \
  python -m backend.discovery.index_build --community-areas <new batch>
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend
```

#### Expansion is RUNTIME-bounded, not build-bounded (8 GB box, hard cap)

The build is safe at any size, but the backend loads the **entire** index into RAM at startup
(~2 KB/parcel). On the 8 GB box that is the real ceiling. Expand in batches and let measurement
decide how far to go:

```bash
# after each batch + restart, measure the serving backend's resident memory
docker stats --no-stream $(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps -q backend)
free -m
```

**Stop rule:** keep backend RSS **≤ ~5.5 GB** (leaves ~2 GB for qdrant/frontend/OS/page-cache +
request spikes). When the measured curve says the next batch would breach that, **stop** and record
the final supported CA set. Do **not** run `--all` blindly — full city (~1.8M ≈ ~3.7 GB of snapshot
alone) is not expected to fit under the cap, and that is an accepted limit (no box bump).
