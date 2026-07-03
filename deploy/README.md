# DealScanner v3 — server runbook

Fresh Ubuntu 24.04 box → running app, in order. The short version of the "why":
the previous deployment was compromised through password SSH left enabled, so
every hardening step below is non-optional.

## 0. Provision (provider console)

- Ubuntu 24.04 LTS, CX22-class is plenty.
- Add the Mac's `~/.ssh/id_ed25519_dealscanner.pub` at creation time.
- Add a provider cloud firewall too: inbound 22/80/443 only (second layer —
  cloud-init can't undo this one).

## 1. Harden (as root, first login)

```bash
ssh -i ~/.ssh/id_ed25519_dealscanner root@NEW_IP
# copy deploy/harden.sh over (scp) or paste it, then:
bash harden.sh
```

Verify from a SECOND terminal before closing: key login works, password login refused.
If the paranoia pass at the end prints anything unexpected — STOP.

## 2. Runtime deps (as root)

```bash
apt-get install -y git curl sqlite3 caddy
curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && apt-get install -y nodejs
su - dealscanner -c 'curl -fsSL https://astral.sh/uv/install.sh | sh'
```

(If `caddy` isn't in the distro repo, use the official Caddy apt repo per caddyserver.com/docs/install.)

## 3. App (as dealscanner)

```bash
sudo mkdir -p /opt/dealscanner-v2 && sudo chown dealscanner:dealscanner /opt/dealscanner-v2
git clone git@github.com:OWNER/dealscanner.git /opt/dealscanner-v2   # or https + token
cd /opt/dealscanner-v2

# secrets — POST-ROTATION values only
cp .env.example .env && chmod 600 .env && $EDITOR .env

# engine + api
cd engine && ~/.local/bin/uv sync --extra api --extra scrape && cd ..

# web — build ON the server, never rsync build artifacts
cd web && npm ci && NEXT_PUBLIC_API=/api npm run build && cd ..

# data: restore the clean DB backup from the Mac (scp), or start empty:
#   scp -i ~/.ssh/id_ed25519_dealscanner <backup>/dealscanner.db dealscanner@IP:/opt/dealscanner-v2/data/
# empty start: engine/.venv/bin/dsv2 initdb && engine/.venv/bin/dsv2 seed
chmod +x deploy/scan.sh
```

## 4. Services (as root)

```bash
cp /opt/dealscanner-v2/deploy/dealscanner-{api,web,scan}.service /etc/systemd/system/
cp /opt/dealscanner-v2/deploy/dealscanner-scan.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now dealscanner-api dealscanner-web dealscanner-scan.timer

cp /opt/dealscanner-v2/deploy/Caddyfile /etc/caddy/Caddyfile   # edit domain first!
systemctl reload caddy
```

## 5. Verify (do not skip)

```bash
curl -s localhost:8099/health                      # {"ok":true,...}
curl -s localhost:3001 | head -1                   # html
systemctl list-timers | grep dealscanner           # next 07:00 ET run scheduled
systemd-run --uid=dealscanner --wait -p EnvironmentFile=/opt/dealscanner-v2/.env \
    /opt/dealscanner-v2/deploy/scan.sh             # one manual end-to-end run
journalctl -u dealscanner-scan --no-pager | tail   # after the first scheduled fire
```

Then: digest email arrived? healthchecks.io check green? magic-link login works via
the public URL? Cut DNS over. Delete the old VPS after a quiet week.
