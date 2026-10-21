# Production hardening runbook

One-time server and account changes that can't be made from the repo. Work through them in
order. Every step can be undone, and none of them takes the site down if you follow the
verify-before-you-lock-out rule in step 3.

`<PROD_HOST>` is the server address. It is intentionally not written in this public repo.

**Status: completed on the production server 2026-09-28.** The steps are kept for rebuilding
the box or setting up another one. Commands below run as root; on the current server, log in
as the admin user and prefix them with `sudo`.

## Why these steps

- **The origin answers directly on its IP**, bypassing Cloudflare. The app no longer trusts
  headers from non-Cloudflare sources (`frontend/nginx.prod.conf`), so this isn't a
  rate-limit hole any more. It still exposes the origin to scanning and to load that
  Cloudflare never sees.
- **CI logs in as `root`** with a key that can do anything on the box.
- **Production settings aren't enforced yet.** They are only checked at startup once
  `ENVIRONMENT=production` is set (step 5).

## 0. Preflight (read-only)

On the server, list which required settings exist. This prints names only, never values:

```bash
cd /opt/urbanlayer
for v in GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET JWT_SECRET AUTH_COOKIE_SECURE FRONTEND_URL \
         STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET ANTHROPIC_API_KEY; do
  grep -q "^$v=." .env && echo "set      $v" || echo "MISSING  $v"
done
awk -F= '/^JWT_SECRET=/{print "JWT_SECRET length:", length($2)}' .env
```

Every line must say `set`, and the JWT secret must be at least 32 characters. If
`JWT_SECRET` is missing or short, generate one with `openssl rand -hex 32`. Rotating it signs
everyone out once.

## 1. Cap LLM spend (account, 2 min)

- In the **Anthropic Console → Billing**, turn auto-reload off (or set a monthly limit). The
  prepaid balance then becomes a hard ceiling.
- The app also enforces `DAILY_API_BUDGET_USD` (default $5/day). Set it lower in `.env` if
  the balance is small.
- In **Cloudflare → Security → WAF → Rate limiting rules**, add a rule: `URI Path equals /chat`
  and `Method equals POST` → block for 10 minutes if the same IP exceeds 10 requests per
  minute. This throttles abuse before it reaches the origin.

## 2. Admin user, before touching root (10 min)

You need a non-root way in before root login is disabled.

```bash
adduser --disabled-password --gecos "" jack
usermod -aG sudo jack
passwd jack                                   # sudo password (SSH stays key-only)
mkdir -p /home/jack/.ssh && cp ~/.ssh/authorized_keys /home/jack/.ssh/
chown -R jack:jack /home/jack/.ssh && chmod 700 /home/jack/.ssh && chmod 600 /home/jack/.ssh/authorized_keys
```

**From a second terminal**, confirm `ssh jack@<PROD_HOST>` and `sudo -v` both work. Don't
continue until they do.

## 3. Least-privilege deploy user (15 min)

CI gets a key that can run the deploy script and nothing else.

On your laptop, create a dedicated key:

```bash
ssh-keygen -t ed25519 -N "" -C "github-actions-deploy" -f ~/.ssh/urbanlayer_deploy
```

On the server:

```bash
install -o root -g root -m 755 /opt/urbanlayer/deploy/urbanlayer-deploy.sh /usr/local/bin/urbanlayer-deploy
# --home matters: a --system user otherwise gets /nonexistent as its home, sshd never
# finds the key, and the login is refused.
adduser --system --group --home /home/deploy --shell /bin/sh deploy
echo 'deploy ALL=(root) NOPASSWD: /usr/local/bin/urbanlayer-deploy' > /etc/sudoers.d/urbanlayer-deploy
chmod 440 /etc/sudoers.d/urbanlayer-deploy && visudo -c
mkdir -p /home/deploy/.ssh
# Paste the PUBLIC key (~/.ssh/urbanlayer_deploy.pub) after the options:
echo 'restrict,command="sudo /usr/local/bin/urbanlayer-deploy" ssh-ed25519 AAAA... github-actions-deploy' \
  > /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh && chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
```

`deploy` is deliberately **not** in the `docker` group, because docker group membership is
equivalent to root. It gets root only through the one sudo rule.

Test it from your laptop. This runs a real (no-op if up to date) deploy:

```bash
ssh -i ~/.ssh/urbanlayer_deploy deploy@<PROD_HOST> anything-here   # the command is ignored
```

Then, in **GitHub → Settings → Secrets → Actions**:

| Secret | Value |
|---|---|
| `SERVER_USER` | `deploy` |
| `SERVER_SSH_KEY` | contents of `~/.ssh/urbanlayer_deploy` (the private key) |
| `SERVER_HOST_FINGERPRINT` | output of `ssh-keygen -lf /etc/ssh/ssh_host_ecdsa_key.pub -E sha256 \| awk '{print $2}'` run on the server. Use the **ECDSA** key: the deploy action's Go SSH client negotiates ECDSA before ed25519, and pinning the ed25519 fingerprint fails with "host key fingerprint mismatch". |

Also set **GitHub → Settings → Environments → `production`** to allow deploys only from
`main`. Push a docs-free change and confirm the deploy job goes green. Once it does,
remove the old root key from `/root/.ssh/authorized_keys`.

## 4. Lock down SSH (5 min)

```bash
cat > /etc/ssh/sshd_config.d/10-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
AllowUsers jack deploy
EOF
sshd -t && systemctl reload ssh
```

Keep your existing session open and confirm a **new** `ssh jack@<PROD_HOST>` still works
before logging out.

## 5. Enforce production settings (2 min)

Only once step 0 shows everything set:

```bash
cd /opt/urbanlayer
echo 'ENVIRONMENT=production' >> .env
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 20 backend
```

If a setting is missing, the backend logs `Refusing to start in production` and names it.
Fix `.env` and re-run. To back out, delete the `ENVIRONMENT` line.

## 6. Firewall the origin (Hetzner Cloud Firewall, 10 min)

Use the **Hetzner Cloud Firewall**, not `ufw`. Docker writes its own iptables rules for
published ports, which bypass ufw, so ufw can't restrict nginx's 80/443.

In **Hetzner Console → Firewalls**, create `urbanlayer-origin` with these inbound rules, and
apply it to the server:

| Port | Source |
|---|---|
| 443/tcp | every range from <https://www.cloudflare.com/ips-v4> and <https://www.cloudflare.com/ips-v6> |
| 80/tcp | same Cloudflare ranges |
| 22/tcp | `0.0.0.0/0, ::/0` (key-only, no root, and the deploy key is command-locked) |

Hetzner's form, in practice:
- Put the Cloudflare ranges in the rule's **source** box, and remove its pre-filled
  "Any IPv4" / "Any IPv6" chips from the 443 and 80 rules. Keep them on the 22 rule.
- Put a single port in **Port** and leave **Port range** empty. A blank Port means all
  ports, and `443-443` is rejected.
- Leave **Outbound** empty (allow all). The app calls city, county and Anthropic APIs.

Check from a laptop: a direct request to the origin must time out, while the site still
answers through Cloudflare (step 10).

Port 22 stays open because GitHub-hosted runners deploy from unpredictable IPs. The tighter
option is to join the box and the deploy job to a Tailscale tailnet
(`tailscale/github-action`), then limit 22 to your IP and the tailnet.

Cloudflare's ranges change rarely. When they do, update both this firewall and the
`set_real_ip_from` list in `frontend/nginx.prod.conf`.

## 7. Cloudflare settings (5 min)

- **SSL/TLS → Overview:** Full (strict). The origin already has a Cloudflare Origin CA certificate.
- **SSL/TLS → Edge Certificates:** Minimum TLS Version 1.2, and Always Use HTTPS on.
- **Optional:** SSL/TLS → Origin Server → Authenticated Origin Pulls. This needs
  `ssl_client_certificate` + `ssl_verify_client on` in nginx. With the firewall in place it's
  defense in depth.

## 8. Automatic security updates (5 min)

```bash
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
# Reboot at a quiet hour when a kernel update needs it:
echo 'Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:30";' > /etc/apt/apt.conf.d/52urbanlayer-reboot
```

## 8b. Keep the demo addresses warm (2 min)

A first lookup of an address takes 15–40 s; the homepage's "Try" addresses should load
in about a second for a first-time visitor.

```bash
cp /opt/urbanlayer/deploy/warm-demo-cache.{service,timer} /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now warm-demo-cache.timer
```

The deploy script also warms them after each restart.

## 8c. Backups, and getting them off the box (20 min)

`chicago.db` (users, conversations, purchases, analytics) is the one irreplaceable file;
Qdrant, the Discovery index and ptaxsim can all be rebuilt from source.
`scripts/backup_db.sh` defaults to the real database, the `chicago.db` file in the
`backend_data` volume, and keeps the newest 7 copies in `/opt/urbanlayer/backups`.

**On the server** (as root). The copies hold user data, so the folder is `root:jack`
with setgid and the script's `umask 027` makes each copy `640`: `jack` can read them
for the off-box pull, nobody else can.

```bash
apt install -y sqlite3
chown root:jack /opt/urbanlayer/backups && chmod 2750 /opt/urbanlayer/backups
( crontab -l 2>/dev/null | grep -v backup_db.sh
  echo '0 3 * * * /opt/urbanlayer/scripts/backup_db.sh >> /var/log/urbanlayer-backup.log 2>&1' ) | crontab -
/opt/urbanlayer/scripts/backup_db.sh >> /var/log/urbanlayer-backup.log 2>&1   # once by hand
crontab -l && tail -3 /var/log/urbanlayer-backup.log
```

The server runs on UTC, so 03:00 is 21:00/22:00 Chicago time.

> **2026-10-20:** root's crontab was found **empty**. The entry was lost in the
> 2026-09-28 hardening, so no backup ran from Sept 28 to Oct 20. It's restored (with the
> log redirect, which the old entry lacked). WS6 M2 adds a server-side backup-age alarm.

**Off the box: a pull to Jack's Mac** (free, no new accounts). The Mac pulls rather than
the server pushing, so the server holds no credential for anything else.

1. A dedicated key with no passphrase (so `launchd` can use it unattended), which the
   server accepts **only** for read-only `rrsync` of the backups folder. It can't open
   a shell, write, or leave that folder (all three checked 2026-10-20):

   ```bash
   ssh-keygen -t ed25519 -N '' -C 'urbanlayer-backup-pull (read-only rrsync)' -f ~/.ssh/urbanlayer_backup_pull
   PUB=$(cat ~/.ssh/urbanlayer_backup_pull.pub)
   ssh urbanlayer-prod "echo 'command=\"/usr/bin/rrsync -ro /opt/urbanlayer/backups/\",restrict $PUB' >> ~/.ssh/authorized_keys"
   ```

   Then add a `Host urbanlayer-backup` alias to `~/.ssh/config`, with the server's
   `HostName`, `User jack`, `IdentityFile ~/.ssh/urbanlayer_backup_pull` and
   `IdentitiesOnly yes`. The script connects through that alias, so the origin IP (which
   Cloudflare hides) stays out of this public repo.

2. `scripts/pull_backups.sh` copies `urbanlayer_*.db` into `~/Backups/urbanlayer` (mode
   700) and keeps the newest 60. It prunes by name, never by age, so the Mac's copies survive
   if the server stops making new ones. It runs `PRAGMA quick_check` on the newest copy and
   shows a macOS notification if the pull fails, the check fails, or the newest copy is over
   36 h old.

3. The launchd job runs it at login and every 4 hours; a run missed during sleep fires on
   wake. Its log is at `~/Library/Logs/urbanlayer-backup-pull.log`.

   ```bash
   sed -e "s|__HOME__|$HOME|g" -e "s|__REPO__|$PWD|g" deploy/launchd/com.urbanlayer.backup-pull.plist \
     > ~/Library/LaunchAgents/com.urbanlayer.backup-pull.plist
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.urbanlayer.backup-pull.plist
   launchctl kickstart gui/$(id -u)/com.urbanlayer.backup-pull   # run now
   ```

Two macOS quirks are handled in the script. macOS's `openrsync` sends `--dirs` for
`-r --include/--exclude`, which rrsync rejects, so it pulls with a remote glob instead.
And `sqlite3 -readonly` can't open the copies, so the check uses a `file:...?immutable=1` URI.

The copies on the Mac are **not encrypted**, and FileVault was off on 2026-10-20. Turning
FileVault on covers them.

**Test a restore** (last done 2026-10-20, from `urbanlayer_20261021_013112.db`: sha256
matched the server copy, `integrity_check` ok, schema v14 = `backend/db.py`'s
`_SCHEMA_VERSION`, and a local backend booted on it with `/health` all true):

```bash
mkdir -p /tmp/restore && cp "$(ls -1 ~/Backups/urbanlayer/urbanlayer_*.db | sort -r | head -1)" /tmp/restore/chicago.db
sqlite3 /tmp/restore/chicago.db 'PRAGMA integrity_check; SELECT MAX(version) FROM schema_version;'
DB_PATH=/tmp/restore/chicago.db uvicorn backend.main:app --port 8011 &   # then: curl localhost:8011/health
```

To restore prod: stop the backend, copy the chosen file over
`/var/lib/docker/volumes/urbanlayer_backend_data/_data/chicago.db`, delete any
`chicago.db-wal`/`-shm` beside it, then start the backend again.

## 9. Check the vector store wasn't tampered with (5 min)

Qdrant was reachable without auth from the internet until 2026-09-08, so the municipal-code
corpus could in principle have been edited. That would be a prompt-injection path.

Compare the point count with a trusted local build (as of 2026-09-28 both have
`chicago_municipal_code` = 16,576; checked on prod that day):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python -c "
import httpx
print(httpx.get('http://qdrant:6333/collections/chicago_municipal_code').json()['result']['points_count'])"
```

If the count differs, or to be certain, rebuild the collection from source
(`python -m ingestion.update --full` against the prod Qdrant) or restore them from a local
snapshot.

## 10. Verify from outside

From your laptop:

```bash
# Should time out (origin only answers Cloudflare):
curl -m 5 --resolve urbanlayerchicago.com:443:<PROD_HOST> https://urbanlayerchicago.com/health
# Should be refused:
ssh -o BatchMode=yes root@<PROD_HOST> true
# Should still work, through Cloudflare:
curl -s https://urbanlayerchicago.com/health
```
