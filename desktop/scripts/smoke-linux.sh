#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
mkdir -p evidence
binary=${1:-src-tauri/target/release/odysseus-desktop}
export ODYSSEUS_TEST_BINARY="$binary"
xvfb-run -a -s '-screen 0 1200x800x24' dbus-run-session -- bash -eu -c '
  profile=$(mktemp -d)
  export XDG_CONFIG_HOME="$profile/config" XDG_CACHE_HOME="$profile/cache" XDG_DATA_HOME="$profile/data"
  export LIBGL_ALWAYS_SOFTWARE=1
  "$ODYSSEUS_TEST_BINARY" >"$profile/app.log" 2>&1 &
  pid=$!
  trap "kill $pid 2>/dev/null || true" EXIT
  for i in $(seq 1 40); do
    kill -0 "$pid" || { echo "Arranque falhou. Registo em $profile/app.log"; exit 1; }
    if xwininfo -root -tree | grep -qi Odysseus; then break; fi
    sleep 1
  done
  sleep 8
  kill -0 "$pid"
  ffmpeg -hide_banner -loglevel error -f x11grab -video_size 1200x800 -i "$DISPLAY" -frames:v 1 -threads 1 -y evidence/odysseus-linux.png
  echo "Captura em evidence/odysseus-linux.png. Registo em $profile/app.log"
'
