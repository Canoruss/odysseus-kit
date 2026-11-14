#!/usr/bin/env python3
"""Lembretes dos dias de treino (seg/qua/sex): refeição, glicose antes, treino do dia e glicose depois. Cron 06:05."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
CFG = os.path.join(JOBS_STATE, "config.json")
DONE = os.path.join(JOBS_STATE, "gym-done.json")
cfg = {"gym_days": [0, 2, 4]}
try: cfg.update(json.load(open(CFG)))
except OSError: pass
NAMES = {0: "Treino A: glúteos e pernas", 2: "Treino B: peito, costas e ombros", 4: "Treino C: posterior, glúteos e abdominais"}
t = lib.now(); wd = t.weekday()
if wd not in cfg["gym_days"]: sys.exit(0)
key = t.date().isoformat()
try: done = json.load(open(DONE))
except Exception: done = {}
if done.get("date") == key: sys.exit(0)
at = lambda h, m: datetime.datetime.combine(t.date(), datetime.time(h, m), tzinfo=lib.TZ)
plan = [(at(16, 15), "Refeição antes do treino (conta os hidratos na página Glicose)"),
        (at(16, 45), "Medir a glicose antes do treino"),
        (at(17, 15), NAMES.get(wd, "Treino de hoje")),
        (at(19, 30), "Medir a glicose depois do treino")]
for when, title in plan:
    if when > t:
        ok, msg = lib.add_todo(title, when); print(ok, title, msg)
json.dump({"date": key}, open(DONE, "w"))
