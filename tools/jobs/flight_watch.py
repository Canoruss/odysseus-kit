#!/usr/bin/env python3
"""Vigia dos voos guardados de TODOS os utilizadores (flights-<user>.json): consulta a AirLabs 3 h e 1 h antes da partida
e cria um lembrete no Odysseus se houver atraso (>= 15 min), cancelamento ou mudanca de porta.
Cron: */10 * * * *  (nao gasta consultas se nada estiver para acontecer).   --dry  -> so mostra, nao cria lembretes."""
import datetime, json, os, re, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kitconfig import OWNER, JOBS_STATE, HUB
FIN = os.environ.get("FLIGHT_FINANCE_DIR", HUB)                       # onde ficam os dados do Hub
sys.path.insert(0, os.environ.get("FLIGHT_MODULES_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hub")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airlabs, lib, users

DRY = "--dry" in sys.argv
STATE = os.environ.get("FLIGHT_WATCH_STATE", os.path.join(JOBS_STATE, "flight-watch.json"))
MIN_DELAY = 15


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError): return d


def dep_dt(info):
    s = (info or {}).get("dep_estimated") or (info or {}).get("dep_time")
    try: return datetime.datetime.strptime(str(s)[:16], "%Y-%m-%d %H:%M")
    except ValueError: return None


def alerts(info, prev):
    out = []
    st = info.get("status")
    if st == "cancelled": out.append(("cancelado", "foi CANCELADO"))
    d = info.get("dep_delayed") or 0
    if d and int(d) >= MIN_DELAY: out.append(("atraso%s" % d, "está atrasado %s min (parte às %s)" % (d, str(info.get("dep_estimated") or info.get("dep_time"))[11:16])))
    g = info.get("dep_gate")
    if g and prev.get("dep_gate") and g != prev["dep_gate"]: out.append(("porta" + str(g), "mudou de porta: agora %s" % g))
    return out


def main():
    state = jload(STATE, {})
    for user in users.USERS:
        watch(user, jload(os.path.join(FIN, "flights-%s.json" % user), []), state)
    now = datetime.datetime.now()
    for k in [k for k in state if k.split("|")[-1] < (now.date() - datetime.timedelta(days=2)).isoformat()]: state.pop(k)
    if not DRY:
        tmp = STATE + ".tmp"; json.dump(state, open(tmp, "w")); os.replace(tmp, STATE)


def watch(user, flights, state):
    now = datetime.datetime.now()
    today, tomorrow = now.date().isoformat(), (now.date() + datetime.timedelta(days=1)).isoformat()
    for f in flights:
        n, date = f.get("n", ""), f.get("date", "")
        if date not in (today, tomorrow): continue
        key = "%s|%s|%s" % (user, n, date)
        st = state.setdefault(key, {"done": [], "alerts": [], "last": {}})
        info, t = airlabs.cached_info(FIN, n, date)
        if not info:                                   # primeiro contacto: so depois das 06:00, para saber a hora de partida
            if now.hour < 6: continue
            r = airlabs.lookup(FIN, n, date, force=True)
            print(key, "primeira consulta:", r["error"] or "ok")
            if not r["ok"]: continue
            info = r["info"]; st["last"] = info
        dt = dep_dt(info)
        if not dt: continue
        hours = (dt - now).total_seconds() / 3600
        for stage, limit in (("t3", 3.0), ("t1", 1.0)):
            if hours <= limit and hours > -0.5 and stage not in st["done"]:
                r = airlabs.lookup(FIN, n, date, force=True)
                print(key, stage, "faltam %.1f h:" % hours, r["error"] or "ok")
                st["done"].append(stage)
                if not r["ok"]: continue
                for code, text in alerts(r["info"], st.get("last") or {}):
                    if code in st["alerts"]: continue
                    title = "Voo %s %s%s" % (n, text, (" · " + f["note"]) if f.get("note") else "")
                    if DRY: print("  [dry] lembrete:", user, title); continue
                    ok, msg = users.add_reminder(user, title, urgent=True); print("  lembrete:", user, ok, title)
                    if ok: st["alerts"].append(code)
                st["last"] = r["info"]


main()
