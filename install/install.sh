#!/usr/bin/env bash
# Odysseus KIT: one-command server setup for a fresh Ubuntu/Debian machine
# (for example a free Oracle Cloud "Always Free" VM).
#
# It installs Docker, starts Odysseus (official image, pinned) + ChromaDB + SearXNG,
# puts HTTPS (Caddy) in front, installs the KIT tools as services and wires the KIT
# front-end into Odysseus. Everything runs on THIS machine, in YOUR account.
# Nothing is sent anywhere else: no telemetry, no accounts, no keys that are not yours.
#
# Usage:  bash install.sh [options]
#   --domain NAME      public host name (default: <your-public-ip>.sslip.io, which gets a free certificate)
#   --admin-user NAME  Odysseus administrator (default: admin)
#   --timezone TZ      e.g. Europe/Lisbon (default: this machine's time zone)
#   --home-dir DIR     where to keep the server files (default: ~/odysseus-server)
#   --kit-dir DIR      KIT checkout (default: the one this script is in, else ~/odysseus-kit)
#   --no-firewall      do not touch iptables
#   --help
set -euo pipefail

IMAGE_VERSION="1.0.2"
ODY_IMAGE="ghcr.io/pewdiepie-archdaemon/odysseus:${IMAGE_VERSION}"
KIT_REPO="https://github.com/Canoruss/odysseus-kit"

DOMAIN=""; ADMIN_USER="admin"; TZNAME=""; SRV_DIR="$HOME/odysseus-server"; KIT_DIR=""; FIREWALL=1
while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="$2"; shift 2;;
    --admin-user) ADMIN_USER="$2"; shift 2;;
    --timezone) TZNAME="$2"; shift 2;;
    --home-dir) SRV_DIR="$2"; shift 2;;
    --kit-dir) KIT_DIR="$2"; shift 2;;
    --no-firewall) FIREWALL=0; shift;;
    -h|--help) sed -n 2,22p "$0"; exit 0;;
    *) echo "Unknown option: $1 (try --help)"; exit 2;;
  esac
done

say()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ "$ADMIN_USER" =~ ^[a-z][a-z0-9_-]{1,31}$ ]] || die "--admin-user must be 2-32 chars: lowercase letters, digits, - or _ (starting with a letter)."
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else command -v sudo >/dev/null || die "Run as root or install sudo."; SUDO="sudo"; fi
ME="$(id -un)"; MYUID="$(id -u)"; MYGID="$(id -g)"
[ "$MYUID" -eq 0 ] && warn "Running as root: files will belong to root. A normal user with sudo is recommended."

# ---------------------------------------------------------------- 0. checks
say "Checking this machine"
command -v apt-get >/dev/null || die "This script supports Ubuntu/Debian (apt). On other systems follow docs/INSTALL.md."
case "$(uname -m)" in x86_64|aarch64) ;; *) die "Unsupported CPU: $(uname -m)";; esac
MEM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
DISK_GB=$(df -P "$HOME" | awk 'NR==2 {print int($4/1024/1024)}')
echo "CPU: $(uname -m), RAM: ${MEM_MB} MB, free disk: ${DISK_GB} GB"
[ "$MEM_MB" -ge 1800 ] || die "Not enough RAM (${MEM_MB} MB). Use at least 2 GB (the Oracle ARM 'Ampere A1' free shape is ideal)."
[ "$MEM_MB" -ge 3500 ] || warn "Less than 4 GB of RAM: it will work but may be slow."
[ "$DISK_GB" -ge 12 ] || die "Not enough free disk (${DISK_GB} GB). Need about 12 GB."
[ -n "$TZNAME" ] || TZNAME="$(cat /etc/timezone 2>/dev/null || timedatectl show -p Timezone --value 2>/dev/null || echo UTC)"

# ---------------------------------------------------------------- 1. packages
say "Installing packages (Docker, Python, git, curl, openssl)"
export DEBIAN_FRONTEND=noninteractive
$SUDO apt-get update -y
$SUDO apt-get install -y ca-certificates curl git openssl patch python3 >/dev/null
if ! command -v docker >/dev/null; then
  $SUDO apt-get install -y docker.io >/dev/null || die "Could not install Docker."
fi
if ! $SUDO docker compose version >/dev/null 2>&1; then
  $SUDO apt-get install -y docker-compose-v2 >/dev/null 2>&1 || $SUDO apt-get install -y docker-compose-plugin >/dev/null 2>&1 \
    || die "Could not install the Docker Compose plugin (package docker-compose-v2). See https://docs.docker.com/engine/install/"
fi
$SUDO systemctl enable --now docker >/dev/null 2>&1 || true
$SUDO docker info >/dev/null 2>&1 || die "Docker is installed but not running."
PYV=$(python3 -c 'import sys; print("%d%02d" % sys.version_info[:2])')
[ "$PYV" -ge 311 ] || die "Python 3.11+ is required (found $(python3 --version)). Ubuntu 24.04 is recommended."
D="$SUDO docker"

# ---------------------------------------------------------------- 2. KIT checkout
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "$KIT_DIR" ]; then
  if [ -f "$HERE/../tools/hub/server.py" ]; then KIT_DIR="$(cd "$HERE/.." && pwd)"; else KIT_DIR="$HOME/odysseus-kit"; fi
fi
if [ ! -f "$KIT_DIR/tools/hub/server.py" ]; then
  say "Downloading the KIT ($KIT_REPO)"
  git clone --depth 1 "$KIT_REPO" "$KIT_DIR"
fi
[ -f "$KIT_DIR/web/ody-extras.js" ] || die "KIT files not found in $KIT_DIR"
echo "KIT: $KIT_DIR"

# ---------------------------------------------------------------- 3. address
if [ -z "$DOMAIN" ]; then
  IP=""
  IP="$(curl -fsS -m 4 -H 'Authorization: Bearer Oracle' http://169.254.169.254/opc/v2/vnics/ 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin)[0].get("publicIp",""))' 2>/dev/null || true)"
  [ -n "$IP" ] || IP="$(curl -fsS -m 6 https://api.ipify.org 2>/dev/null || true)"
  [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "Could not detect the public IP. Pass --domain yourname.example.com"
  DOMAIN="${IP//./-}.sslip.io"
fi
[[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || die "Invalid --domain."
echo "Address: https://$DOMAIN"

# ---------------------------------------------------------------- 4. server files
say "Creating the server files in $SRV_DIR"
mkdir -p "$SRV_DIR"/{data,logs,config/searxng,caddy-data,caddy-config}
chmod 700 "$SRV_DIR"
ENVF="$SRV_DIR/.env"
if [ -f "$ENVF" ]; then
  echo "Keeping the existing $ENVF (passwords unchanged)."
else
  ADMIN_PASS="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"
  SEARX_SECRET="$(openssl rand -hex 24)"
  umask 077
  cat >"$ENVF" <<EOF
ODYSSEUS_ADMIN_USER=$ADMIN_USER
ODYSSEUS_ADMIN_PASSWORD=$ADMIN_PASS
SEARXNG_SECRET=$SEARX_SECRET
PUID=$MYUID
PGID=$MYGID
TZ=$TZNAME
PUBLIC_HOST=$DOMAIN
EOF
  umask 022
fi
# shellcheck disable=SC1090
ADMIN_USER="$(grep '^ODYSSEUS_ADMIN_USER=' "$ENVF" | cut -d= -f2-)"
ADMIN_PASS="$(grep '^ODYSSEUS_ADMIN_PASSWORD=' "$ENVF" | cut -d= -f2-)"
sed -i "s|^PUBLIC_HOST=.*|PUBLIC_HOST=$DOMAIN|" "$ENVF"

cat >"$SRV_DIR/config/searxng/settings.yml" <<'EOF'
use_default_settings: true
general:
  instance_name: "Odysseus search"
  enable_metrics: false
search:
  safe_search: 0
  formats: [html, json]
server:
  secret_key: "__SEARXNG_SECRET__"
  limiter: false
  image_proxy: false
EOF

cat >"$SRV_DIR/docker-compose.yml" <<EOF
# Generated by the Odysseus KIT installer. Safe to edit; re-running install.sh keeps your .env.
services:
  odysseus:
    image: $ODY_IMAGE
    container_name: odysseus
    ports:
      - "127.0.0.1:7860:7000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./ody-extras.js:/app/static/js/ody-extras.js:ro
      - ./kit-config.js:/app/static/js/kit-config.js:ro
      - ./index.html:/app/static/index.html:ro
    environment:
      - ODYSSEUS_ADMIN_USER=\${ODYSSEUS_ADMIN_USER}
      - ODYSSEUS_ADMIN_PASSWORD=\${ODYSSEUS_ADMIN_PASSWORD}
      - ADMIN_USERNAME=\${ODYSSEUS_ADMIN_USER}
      - ADMIN_PASSWORD=\${ODYSSEUS_ADMIN_PASSWORD}
      - AUTH_ENABLED=true
      - LOCALHOST_BYPASS=false
      - SECURE_COOKIES=true
      - ALLOWED_ORIGINS=https://\${PUBLIC_HOST}
      - CHROMADB_HOST=chromadb
      - CHROMADB_PORT=8000
      - SEARXNG_INSTANCE=http://searxng:8080
      - SEARXNG_URL=http://searxng:8080
      - PUID=\${PUID}
      - PGID=\${PGID}
      - TZ=\${TZ}
    depends_on:
      - chromadb
      - searxng
    restart: unless-stopped

  chromadb:
    image: docker.io/chromadb/chroma:latest
    volumes:
      - chromadb-data:/chroma/chroma
    environment:
      - ANONYMIZED_TELEMETRY=FALSE
    restart: unless-stopped

  searxng:
    image: docker.io/searxng/searxng:2026.5.31-7159b8aed
    entrypoint:
      - /bin/sh
      - -c
      - |
        set -eu
        sed "s|__SEARXNG_SECRET__|\$\${SEARXNG_SECRET}|g" /tmp/settings.yml.template > /etc/searxng/settings.yml
        exec /usr/local/searxng/entrypoint.sh
    volumes:
      - searxng-data:/etc/searxng
      - ./config/searxng/settings.yml:/tmp/settings.yml.template:ro
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080/
      - SEARXNG_SECRET=\${SEARXNG_SECRET}
    cap_drop: [ALL]
    cap_add: [CHOWN, SETGID, SETUID, DAC_OVERRIDE]
    restart: unless-stopped

  caddy:
    image: docker.io/library/caddy:2
    network_mode: host          # reaches Odysseus (127.0.0.1:7860) and the KIT tools (127.0.0.1:879x)
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./caddy-data:/data
      - ./caddy-config:/config
    environment:
      - PUBLIC_HOST=\${PUBLIC_HOST}
    restart: unless-stopped

volumes:
  chromadb-data:
  searxng-data:
EOF

cat >"$SRV_DIR/Caddyfile" <<'EOF'
{$PUBLIC_HOST} {
	encode zstd gzip
	header {
		Strict-Transport-Security "max-age=31536000"
		X-Content-Type-Options nosniff
		-Server
	}
	# KIT tools live on the same host name as Odysseus (they read the Odysseus session cookie)
	handle /finance* {
		reverse_proxy 127.0.0.1:8792
	}
	handle /translate* {
		reverse_proxy 127.0.0.1:8791
	}
	handle /canva* {
		reverse_proxy 127.0.0.1:8793
	}
	handle {
		reverse_proxy 127.0.0.1:7860 {
			flush_interval -1
		}
	}
}
EOF

# ---------------------------------------------------------------- 5. pull + front-end wiring
say "Downloading Odysseus $IMAGE_VERSION (about 2 GB, a few minutes)"
( cd "$SRV_DIR" && $D compose --env-file "$ENVF" pull )

say "Wiring the KIT front-end into Odysseus"
cp "$KIT_DIR/web/ody-extras.js" "$SRV_DIR/ody-extras.js"
CID="$($D create "$ODY_IMAGE")"
$D cp "$CID:/app/static/index.html" "$SRV_DIR/index.html"
$D rm "$CID" >/dev/null
$SUDO chown "$MYUID:$MYGID" "$SRV_DIR/index.html"   # docker cp ran as root
python3 -I - "$SRV_DIR/index.html" <<'PY'
import sys, re
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
tags = '<script src="/static/js/kit-config.js"></script>\n<script src="/static/js/ody-extras.js"></script>\n'
if "ody-extras.js" not in s:
    m = re.search(r'<script[^>]*type="module"', s)
    if m:
        s = s[:m.start()] + tags + s[m.start():]
    elif "</body>" in s:
        s = s.replace("</body>", tags + "</body>", 1)
    else:
        sys.exit("index.html: no place to add the KIT script")
    open(p, "w", encoding="utf-8").write(s)
print("index.html ready")
PY

# Optional core patches (Auto model routing, sampling defaults, base persona, memory audit batching,
# quieter email logs). Applied to a copy of the stock files; all-or-nothing, never blocks the install.
if [ "${KIT_PATCHES:-1}" = "1" ] && [ -d "$KIT_DIR/patches" ] && command -v patch >/dev/null; then
  say "Applying the KIT core patches"
  PW="$SRV_DIR/patched"; rm -rf "$PW"; mkdir -p "$PW/app"
  CID="$($D create "$ODY_IMAGE")"
  OKP=1; MOUNTS=""
  for pf in "$KIT_DIR"/patches/*.patch; do
    rel="$(sed -n 's|^+++ b/||p' "$pf" | head -1 | cut -f1)"
    mkdir -p "$PW/app/$(dirname "$rel")"
    $D cp "$CID:/app/$rel" "$PW/app/$rel" 2>/dev/null || { OKP=0; break; }
    MOUNTS="$MOUNTS $rel"
  done
  $D rm "$CID" >/dev/null
  $SUDO chown -R "$MYUID:$MYGID" "$PW"
  if [ "$OKP" = 1 ]; then
    for pf in "$KIT_DIR"/patches/*.patch; do
      ( cd "$PW/app" && patch -p1 --no-backup-if-mismatch -s < "$pf" ) >/dev/null 2>&1 || { OKP=0; break; }
    done
  fi
  if [ "$OKP" = 1 ]; then
    for f in auto_router.py llm_defaults.py; do cp "$KIT_DIR/patches/$f" "$PW/app/src/$f"; done
    python3 -I - "$SRV_DIR/docker-compose.yml" "$PW/app" $MOUNTS src/auto_router.py src/llm_defaults.py <<'PY'
import sys
comp, root, files = sys.argv[1], sys.argv[2], sys.argv[3:]
s = open(comp).read()
anchor = "      - ./index.html:/app/static/index.html:ro\n"
add = "".join("      - ./patched/app/%s:/app/%s:ro\n" % (f, f) for f in files)
if "./patched/app/" not in s:
    s = s.replace(anchor, anchor + add, 1)
    open(comp, "w").write(s)
print("patches mounted:", len(files))
PY
  else
    warn "Core patches did not apply cleanly to this Odysseus version; continuing without them."
    rm -rf "$PW"
  fi
fi

# ---------------------------------------------------------------- 6. KIT config (the in-app Setup tool can change everything later)
say "Writing the KIT configuration"
CONF_DIR="$HOME/.config/odysseus-kit"
mkdir -p "$CONF_DIR"; chmod 700 "$CONF_DIR"
python3 -I - "$CONF_DIR" "$ADMIN_USER" "$DOMAIN" "$TZNAME" <<'PY'
import json, os, sys
d, owner, dom, tz = sys.argv[1:5]
p = os.path.join(d, "config.json")
try: c = json.load(open(p))
except Exception: c = {}
c.update({"owner": owner, "owner_name": owner.capitalize(), "public_url": "https://" + dom, "timezone": tz})
c.setdefault("features", {})
c.setdefault("odysseus_url", "http://127.0.0.1:7860")
json.dump(c, open(p, "w"), indent=2, ensure_ascii=False); os.chmod(p, 0o600)
pub = {"owner": owner, "member": c.get("member", "member"), "features": c["features"]}
open(os.path.join(d, "kit-config.js"), "w").write("window.KIT_CONFIG = " + json.dumps(pub) + ";\n")
PY
cp "$CONF_DIR/kit-config.js" "$SRV_DIR/kit-config.js"

# ---------------------------------------------------------------- 7. KIT services
say "Installing the KIT services (hub, translation, canva, setup wizard)"
mkdir -p "$HOME/.local/share/odysseus-kit/logs"
for pair in "kit-hub:tools/hub/server.py" "kit-translate:tools/translate/server.py" "kit-canva:tools/canva/server.py" "kit-wizard:setup/wizard.py"; do
  name="${pair%%:*}"; file="${pair#*:}"
  $SUDO tee "/etc/systemd/system/$name.service" >/dev/null <<EOF
[Unit]
Description=Odysseus KIT: $name
After=network-online.target docker.service
[Service]
User=$ME
Environment=HOME=$HOME
ExecStart=/usr/bin/python3 -I $KIT_DIR/$file
Restart=always
RestartSec=3
StandardOutput=append:$HOME/.local/share/odysseus-kit/logs/$name.log
StandardError=append:$HOME/.local/share/odysseus-kit/logs/$name.log
[Install]
WantedBy=multi-user.target
EOF
done
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now kit-hub kit-translate kit-canva kit-wizard >/dev/null 2>&1

# daily reminders for the Cycle tab (only runs once you have created an agent token: see docs/INSTALL.md section 5)
CRONLINE="47 9 * * *  [ -f $CONF_DIR/agent.env ] && python3 -I $KIT_DIR/tools/jobs/period_reminders.py >>\$HOME/.local/share/odysseus-kit/logs/period-reminders.log 2>&1"
LOGD="\$HOME/.local/share/odysseus-kit/logs"
PILLLINE="*/10 * * * *  [ -f $CONF_DIR/agent.env ] && python3 -I $KIT_DIR/tools/jobs/period_reminders.py --pill >>$LOGD/pill-reminders.log 2>&1"
GAMESLINE="17 */2 * * *  [ -f $CONF_DIR/agent.env ] && python3 -I $KIT_DIR/tools/jobs/games_alerts.py >>$LOGD/games-alerts.log 2>&1"
SCANLINE="0 4 * * *  python3 -I $KIT_DIR/tools/jobs/nightly_scan.py --quiet >>$LOGD/nightly-scan.log 2>&1"
( crontab -l 2>/dev/null | grep -v -e 'period_reminders.py' -e 'games_alerts.py' -e 'nightly_scan.py' || true; echo "$CRONLINE"; echo "$PILLLINE"; echo "$GAMESLINE"; echo "$SCANLINE" ) | crontab - 2>/dev/null || warn "Could not install the cron jobs (reminders, pill, free-game alerts, nightly scan)."

# ---------------------------------------------------------------- 8. firewall (host level only)
if [ "$FIREWALL" -eq 1 ] && command -v iptables >/dev/null && $SUDO iptables -S INPUT 2>/dev/null | grep -q -E 'REJECT|DROP|-P INPUT DROP'; then
  say "Opening ports 80 and 443 on this machine's firewall"
  for p in 80 443; do
    $SUDO iptables -C INPUT -p tcp --dport $p -j ACCEPT 2>/dev/null || $SUDO iptables -I INPUT 1 -p tcp --dport $p -j ACCEPT
  done
  if command -v netfilter-persistent >/dev/null; then $SUDO netfilter-persistent save >/dev/null 2>&1 || true
  else $SUDO apt-get install -y iptables-persistent >/dev/null 2>&1 && $SUDO netfilter-persistent save >/dev/null 2>&1 || warn "Could not make the firewall rules permanent."; fi
fi

# ---------------------------------------------------------------- 9. start
say "Starting Odysseus"
( cd "$SRV_DIR" && $D compose --env-file "$ENVF" up -d )
printf 'Waiting for Odysseus'
OK=0
for i in $(seq 1 90); do
  if curl -fsS -m 3 -o /dev/null http://127.0.0.1:7860/login 2>/dev/null; then OK=1; break; fi
  printf '.'; sleep 4
done
echo
[ "$OK" -eq 1 ] || { warn "Odysseus did not answer in 6 minutes. See: cd $SRV_DIR && sudo docker compose logs odysseus"; exit 1; }

HUB=$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8792/login || true)
TRN=$(curl -s -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8791/login || true)
echo "Odysseus: up | KIT hub: HTTP $HUB | translation: HTTP $TRN"

cat <<EOF

================ Done ================
Open:       https://$DOMAIN
User:       $ADMIN_USER
Password:   $ADMIN_PASS      (also saved in $ENVF, mode 600; change it in Odysseus after logging in)

Still to do (about 5 minutes):
 1. On Oracle Cloud: open ports 80 and 443 for this VM. In the console go to
    Networking > your VCN > Security Lists > Default > Add Ingress Rules (source 0.0.0.0/0, TCP, port 80 and 443).
    This cannot be done from inside the VM. Without it the site is not reachable from outside.
 2. Log in, then add your AI key: Odysseus settings > Models (your own key; the KIT never has one).
 3. Tools > Setup: turn the KIT features you want on or off and fill in the optional keys.
 4. In the Android app: set the server address to https://$DOMAIN

Update later:  bash $KIT_DIR/install/install.sh        (keeps your data and passwords)
Remove:        bash $KIT_DIR/install/uninstall.sh
EOF
