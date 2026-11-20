#!/usr/bin/env python3
"""Faturas no e-mail (Fase 3): procura automatica uma vez por dia, so para quem ligou o interruptor em /finance/bills. Avisa se houver faturas novas. Cron 08:17 todos os dias."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HUB)
import users, bills
for u in users.USERS:
    if not os.path.exists(bills._p(u)) or not bills.load(u).get("auto"): continue
    a0 = len(bills.load(u).get("alerts", []))
    try: n = bills.scan(u, auto=True)
    except Exception as e: print(u, "erro", repr(e)[:150]); continue
    print(u, "novas:", n)
    na = len(bills.load(u).get("alerts", [])) - a0
    if na > 0: print(u, users.add_reminder(u, "⚠️ Aviso de pagamento falhado/devolvido no e-mail — vê /finance/bills"))
    if n - max(na, 0) > 0:
        n -= max(na, 0)
        ok, msg = users.add_reminder(u, "🧾 %d fatura%s nova%s por confirmar em /finance/bills" % (n, "s" if n > 1 else "", "s" if n > 1 else ""))
        print(u, ok, msg)
