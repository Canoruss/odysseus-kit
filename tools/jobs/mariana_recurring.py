#!/usr/bin/env python3
"""Avisos das despesas mensais do membro (3 dias, 1 dia e no próprio dia) como lembretes na conta dela. Cron 09:40."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import calendar, datetime, json, os, urllib.request, http.cookiejar
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
DATA = os.path.join(HUB, "data-member.json"); SENT = os.path.join(JOBS_STATE, "member-sent.json")
env = {}
for l in open(os.path.expanduser("~/.config/odysseus-kit/member.env")):
    if "=" in l: k, v = l.strip().split("=", 1); env[k] = v
try: sent = json.load(open(SENT))
except Exception: sent = {}
t = lib.now(); today = t.date()
m = json.load(open(DATA))
def next_due(day):
    for add in (0, 1):
        y, mo = today.year + (today.month - 1 + add) // 12, (today.month - 1 + add) % 12 + 1
        dd = datetime.date(y, mo, min(day, calendar.monthrange(y, mo)[1]))
        if dd >= today: return dd
jobs = []
for x in m.get("recurring", []):
    due = next_due(int(x["day"])); left = (due - today).days
    if left not in (3, 1, 0): continue
    k = f"{x['name']}|{due.isoformat()}|{left}"
    if k in sent: continue
    eur = f"{float(x['amount']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    jobs.append((k, f"Pagar {x['name']}: {eur} € " + ("hoje" if left == 0 else f"em {left} dia" + ("s" if left > 1 else ""))))
if jobs:
    B = "http://127.0.0.1:7860"
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def post(path, body):
        r = urllib.request.Request(B + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        return op.open(r, timeout=30).status
    post("/api/auth/login", {"username": env["ODY_USER"], "password": env["ODY_PASSWORD"]})
    due = (t + datetime.timedelta(minutes=1)).replace(tzinfo=None, microsecond=0).isoformat()
    for k, title in jobs:
        print(post("/api/notes", {"title": title, "content": "", "due_date": due}), title); sent[k] = True
json.dump(sent, open(SENT, "w"))
