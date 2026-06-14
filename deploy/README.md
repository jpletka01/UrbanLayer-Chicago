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

```bash
# inside the backend container — build wider; --refresh afterwards rebuilds this same set
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -d backend \
  python -m backend.discovery.index_build --community-areas 24,22,7,6,28,<more>
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend
```

> Before `--all` (~1.8M parcels): the O(N) `_pin_lookup` was fixed (memoized per dataVersion),
> but still sanity-check container memory for holding the full snapshot.
