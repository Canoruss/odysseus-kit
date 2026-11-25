#!/usr/bin/env bash
# Testes de comportamento em Xvfb: instância única, janela, bandeja, --minimized
set -u
cd "$(dirname "$0")/.."
B=${1:-src-tauri/target/release/odysseus-desktop}
export B
xvfb-run -a -s '-screen 0 1200x800x24' dbus-run-session -- bash -u -c '
p=$(mktemp -d); export XDG_CONFIG_HOME=$p/c XDG_CACHE_HOME=$p/k XDG_DATA_HOME=$p/d LIBGL_ALWAYS_SOFTWARE=1
res(){ echo "$1: $2"; }
"$B" >$p/a.log 2>&1 & A=$!
for i in $(seq 1 40); do xwininfo -root -tree | grep -qi odysseus && break; sleep 1; done
sleep 3
xwininfo -root -tree | grep -qi odysseus && res janela PASS || res janela FAIL
n0=$(pgrep -xc odysseus-deskto)
"$B" >$p/b.log 2>&1 & sleep 6
n1=$(pgrep -xc odysseus-deskto)
[ "$n1" = "$n0" ] && res instancia-unica PASS || res instancia-unica "FAIL ($n0 -> $n1)"
kill -0 $A 2>/dev/null && res processo-vivo PASS || res processo-vivo FAIL
grep -qi "panic\|error" $p/a.log && { res log-erros "AVISO"; grep -i "panic\|error" $p/a.log | head -3; } || res log-erros PASS
kill $A 2>/dev/null; sleep 2; pkill -x odysseus-deskto
# --minimized
"$B" --minimized >$p/m.log 2>&1 & M=$!
sleep 12
vis=0; for w in $(xwininfo -root -tree | grep -i "odysseus" | grep -o "0x[0-9a-f]*" | sort -u); do xwininfo -id $w 2>/dev/null | grep -q IsViewable && vis=$((vis+1)); done
kill -0 $M 2>/dev/null && res minimized-vivo PASS || res minimized-vivo FAIL
echo "minimized janelas-visiveis=$vis (0 esperado)"
kill $M 2>/dev/null; pkill -x odysseus-deskto; true
'
