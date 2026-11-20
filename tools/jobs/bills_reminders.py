#!/usr/bin/env python3
"""Faturas detetadas no e-mail (Fase 2): lembrete na vespera e no dia do vencimento, e aviso se a fatura recorrente ainda nao chegou. Cron 09:42."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import calendar, datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HUB)
import lib, users, bills
today = lib.now().date()
eur = lambda v: f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
def next_due(day):
    for add in (0, 1):
        y, m = today.year + (today.month - 1 + add) // 12, (today.month - 1 + add) % 12 + 1
        dd = datetime.date(y, m, min(day, calendar.monthrange(y, m)[1]))
        if dd >= today: return dd
for u in users.USERS:
    if not os.path.exists(bills._p(u)): continue
    d = bills.load(u); ch = False
    for t in d["tracked"]:
        try: left = (datetime.date.fromisoformat(t["due"]) - today).days
        except ValueError: continue
        if left not in (1, 0, -1) or str(left) in t["sent"]: continue
        txt = {1: "vence amanhã", 0: "vence hoje", -1: "venceu ontem, já pagaste? (marca «Já paguei» em /finance/bills)"}[left]
        ok, msg = users.add_reminder(u, f"Fatura {t['issuer']}: {eur(t['amount'])} {txt}" + (f" · ref. {t['ref']}" if t.get("ref") else ""))
        print(u, ok, t["issuer"], left, msg)
        if ok: t["sent"].append(str(left)); ch = True
    for k, r in d["rules"].items():
        exp = next_due(int(r["day"])); left = (exp - today).days
        if left != 3 or r.get("warned") == exp.isoformat(): continue
        try: ld = datetime.date.fromisoformat(r.get("last_due") or "")
        except ValueError: ld = None
        if ld and abs((exp - ld).days) < 12: continue   # esta ocorrencia ja chegou
        if any(t["issuer"].lower() == k and abs((datetime.date.fromisoformat(t["due"]) - exp).days) < 12 for t in d["tracked"]): continue
        ok, msg = users.add_reminder(u, f"A fatura {r['issuer']} (habitualmente dia {r['day']}, ~{eur(r['amount'])}) ainda não chegou ao e-mail")
        print(u, ok, "missing", r["issuer"], msg)
        if ok: r["warned"] = exp.isoformat(); ch = True
    if ch: bills.save(u, d)
