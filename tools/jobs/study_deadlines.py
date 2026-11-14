#!/usr/bin/env python3
"""Avisos dos prazos dos trabalhos de Estudo (3 dias, 1 dia e no proprio dia) como lembretes no Odysseus.
Administrador: via lib.add_todo. Membro: login na conta dele (~/.config/odysseus-kit/member.env). Cron 09:45.
--dry  -> so mostra o que criaria."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
import datetime, json, os, sys, urllib.request, http.cookiejar
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

DRY = "--dry" in sys.argv
FIN = os.environ.get("STUDY_DIR", HUB)
SENT = os.environ.get("STUDY_SENT", os.path.join(JOBS_STATE, "study-sent.json"))
B = os.environ.get("ODYSSEUS_LOCAL_URL", "http://127.0.0.1:7860")


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def due_jobs(user, sent, today):
    out = []
    for t in jload(os.path.join(FIN, "study-%s.json" % user), {}).get("tasks", []):
        if t.get("status") == "entregue": continue
        try: due = datetime.date.fromisoformat(t.get("due", ""))
        except Exception: continue
        left = (due - today).days
        if left not in (3, 1, 0): continue
        k = "%s|%s|%s|%d" % (user, t.get("id"), due.isoformat(), left)
        if k in sent: continue
        when = "hoje" if left == 0 else "em %d dia%s" % (left, "s" if left > 1 else "")
        title = "Entrega %s: %s%s" % (when, t.get("title") or t.get("name") or "trabalho", (" (" + t["type"] + ")") if t.get("type") else "")
        out.append((k, title))
    return out


def member_session():
    env = {}
    for l in open(os.path.expanduser("~/.config/odysseus-kit/member.env")):
        if "=" in l: a, b = l.strip().split("=", 1); env[a] = b
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    r = urllib.request.Request(B + "/api/auth/login", json.dumps({"username": env["ODY_USER"], "password": env["ODY_PASSWORD"]}).encode(), {"Content-Type": "application/json"})
    op.open(r, timeout=30)
    return op


def main():
    sent = jload(SENT, {})
    today = lib.now().date()
    due = (lib.now() + datetime.timedelta(minutes=1)).replace(tzinfo=None, microsecond=0)
    for user in (OWNER, "member"):
        jobs = due_jobs(user, sent, today)
        if not jobs: continue
        op = None
        for k, title in jobs:
            if DRY: print("[dry]", user, "|", title); continue
            try:
                if user == OWNER:
                    ok, msg = lib.add_todo(title, due)
                else:
                    op = op or member_session()
                    r = urllib.request.Request(B + "/api/notes", json.dumps({"title": title, "content": "", "due_date": due.isoformat()}).encode(), {"Content-Type": "application/json"})
                    ok = op.open(r, timeout=30).status == 200
                print(user, "OK" if ok else "FALHOU", title)
                if ok: sent[k] = True
            except Exception as e:
                print(user, "ERRO", title, repr(e)[:120])
    if not DRY:
        tmp = SENT + ".tmp"; json.dump(sent, open(tmp, "w")); os.replace(tmp, SENT)


main()
