"""Cria lembretes (todos) no Odysseus a partir de cron. Lê as credenciais de ~/.config/odysseus/agent.env."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import datetime, json, os, subprocess
from zoneinfo import ZoneInfo
TZ = ZoneInfo(get("timezone", "UTC"))
ODY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "odysseus_api.py")
ENV = dict(os.environ)
try:
    for l in open(secret_file("agent")):
        l = l.strip()
        if l.startswith("export "): l = l[7:]
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1); ENV[k.strip()] = v.strip().strip("'\"")
except OSError:
    pass

def now(): return datetime.datetime.now(TZ)

def add_todo(title, when, items=None):
    payload = {"action": "add", "title": title, "due_date": when.isoformat()}
    if items: payload["items"] = [i if isinstance(i, dict) else {"text": str(i), "done": False} for i in items]
    r = subprocess.run(["python3", "-I", ODY, "POST", "/api/codex/todos", json.dumps(payload)], capture_output=True, text=True, timeout=120, env=ENV)
    return r.returncode == 0, (r.stdout or r.stderr).strip()[:200]
