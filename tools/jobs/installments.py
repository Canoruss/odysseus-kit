#!/usr/bin/env python3
"""Aviso de prestações: 3 dias, 1 dia e no próprio dia do vencimento (dívidas com 'due_day' em finance-tool/data.json). Cron 09:40."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import calendar, datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
DATA = os.path.join(HUB, "data.json"); SENT = os.path.join(JOBS_STATE, "installments-sent.json")
try: sent = json.load(open(SENT))
except Exception: sent = {}
t = lib.now(); today = t.date()
d = json.load(open(DATA))
def next_due(day):
    for add in (0, 1):
        y, m = today.year + (today.month - 1 + add) // 12, (today.month - 1 + add) % 12 + 1
        dd = datetime.date(y, m, min(day, calendar.monthrange(y, m)[1]))
        if dd >= today: return dd
for debt in d.get("debts", []):
    try: day = int(debt.get("due_day") or 0)
    except ValueError: continue
    if not 1 <= day <= 31: continue
    due = next_due(day); left = (due - today).days
    if left not in (3, 1, 0): continue
    k = f"{debt['name']}|{due.isoformat()}|{left}"
    if k in sent: continue
    eur = f"{float(debt['amount']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    when = t + datetime.timedelta(minutes=1)
    title = f"Prestação {debt['name']}: {eur} € " + ("vence hoje" if left == 0 else f"vence em {left} dia" + ("s" if left > 1 else ""))
    ok, msg = lib.add_todo(title, when); print(ok, title, msg)
    if ok: sent[k] = True
for x in d.get("recurring", []):  # despesas mensais (renda, contas...)
    try: day = int(x.get("day") or 0)
    except ValueError: continue
    if not 1 <= day <= 31: continue
    due = next_due(day); left = (due - today).days
    if left not in (3, 1, 0): continue
    k = f"rec|{x['name']}|{due.isoformat()}|{left}"
    if k in sent: continue
    eur = f"{float(x['amount']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    when = t + datetime.timedelta(minutes=1)
    title = f"Pagar {x['name']}: {eur} € " + ("hoje" if left == 0 else f"em {left} dia" + ("s" if left > 1 else ""))
    ok, msg = lib.add_todo(title, when); print(ok, title, msg)
    if ok: sent[k] = True
json.dump(sent, open(SENT, "w"))
