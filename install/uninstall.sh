#!/usr/bin/env bash
# Removes what install.sh created. Your data is kept unless you pass --purge.
#   bash uninstall.sh [--purge] [--home-dir DIR]
set -uo pipefail
PURGE=0; SRV_DIR="$HOME/odysseus-server"
while [ $# -gt 0 ]; do case "$1" in --purge) PURGE=1; shift;; --home-dir) SRV_DIR="$2"; shift 2;; *) echo "Unknown option $1"; exit 2;; esac; done
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

echo "Stopping KIT services..."
for n in kit-hub kit-translate kit-canva kit-wizard; do
  $SUDO systemctl disable --now "$n" >/dev/null 2>&1; $SUDO rm -f "/etc/systemd/system/$n.service"
done
$SUDO systemctl daemon-reload
( crontab -l 2>/dev/null | grep -v 'period_reminders.py' ) | crontab - 2>/dev/null

if [ -f "$SRV_DIR/docker-compose.yml" ]; then
  echo "Stopping containers..."
  if [ "$PURGE" -eq 1 ]; then ( cd "$SRV_DIR" && $SUDO docker compose --env-file "$SRV_DIR/.env" down -v --rmi all 2>&1 | tail -3 )
  else ( cd "$SRV_DIR" && $SUDO docker compose --env-file "$SRV_DIR/.env" down 2>&1 | tail -3 ); fi
fi
if [ "$PURGE" -eq 1 ]; then
  echo "Deleting data (--purge)..."
  $SUDO rm -rf "$SRV_DIR" "$HOME/.config/odysseus-kit" "$HOME/.local/share/odysseus-kit"
  echo "Everything removed. Docker itself was left installed."
else
  echo "Done. Data kept in $SRV_DIR and ~/.config/odysseus-kit (use --purge to delete it)."
fi
