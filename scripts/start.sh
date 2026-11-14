#!/usr/bin/env bash
# Arranca as ferramentas do Odysseus KIT (hub, traducao, canva) em segundo plano.
# Uso: bash scripts/start.sh [stop]
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="${KIT_LOG_DIR:-$HOME/.local/share/odysseus-kit/logs}"; mkdir -p "$LOGDIR"
svc() {  # nome  ficheiro
  if [ "$1" = "stop" ]; then pkill -f "python3 -I $ROOT/tools/$3" 2>/dev/null; return; fi
  if pgrep -f "python3 -I $ROOT/tools/$2" >/dev/null; then echo "$1: ja esta a correr"; return; fi
  (setsid nohup python3 -I "$ROOT/tools/$2" >>"$LOGDIR/$1.log" 2>&1 </dev/null &)
  echo "$1: arrancado (log em $LOGDIR/$1.log)"
}
if [ "$1" = "stop" ]; then
  for f in hub/server.py translate/server.py canva/server.py ../setup/wizard.py; do pkill -f "python3 -I $ROOT/tools/$f" 2>/dev/null; done; echo parado; exit 0
fi
svc hub hub/server.py; svc translate translate/server.py; svc canva canva/server.py; svc wizard ../setup/wizard.py
