#!/usr/bin/env python3
"""Daily ClickUp list for administrador: one Odysseus reminder at 11:00 with all open tasks as a checklist."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import datetime, json, os, subprocess, sys
from zoneinfo import ZoneInfo

ASSIGNEE = get("clickup_assignee", "me")      # membro ClickUp (nome ou email)
TZ = ZoneInfo(get("timezone", "UTC"))
CLICKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clickup_api.py")
ODY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "odysseus_api.py")
AENV = {}
try:
    for _l in open(secret_file("agent")):
        _l = _l.strip()
        if _l.startswith("export "): _l = _l[7:]
        if "=" in _l and not _l.startswith("#"):
            _k, _v = _l.split("=", 1); AENV[_k.strip()] = _v.strip().strip("'\"")
except OSError:
    pass
SUBENV = {**os.environ, **AENV}

def fetch():
    out = subprocess.run(["python3", "-I", CLICKUP, "tasks", "--assignee", ASSIGNEE],
                         capture_output=True, text=True, timeout=180)
    rows = []
    for line in out.stdout.splitlines():
        parts = [p.strip() for p in line.split(" | ")]
        if len(parts) < 5 or not parts[0] or parts[0].startswith("("):
            continue
        name, status, lst, due, url = parts[0], parts[1], parts[2], parts[3], parts[4]
        rows.append({"name": name, "status": status, "list": lst, "due": due, "url": url})
    if not rows:
        raise SystemExit("clickup returned no tasks: " + (out.stderr or out.stdout)[:300])
    return rows

def main():
    today = datetime.datetime.now(TZ).date()
    tasks = fetch()
    groups = {"Atrasadas": [], "Hoje": [], "Próximos 7 dias": [], "Mais tarde": [], "Sem data": []}
    for t in tasks:
        try:
            d = datetime.date.fromisoformat(t["due"])
        except ValueError:
            groups["Sem data"].append(t); continue
        if d < today: groups["Atrasadas"].append(t)
        elif d == today: groups["Hoje"].append(t)
        elif (d - today).days <= 7: groups["Próximos 7 dias"].append(t)
        else: groups["Mais tarde"].append(t)
    lines = [f"# Tarefas ClickUp — {today.strftime('%d/%m/%Y')}", "", f"Total: {len(tasks)} tarefas abertas", ""]
    for g, items in groups.items():
        if not items: continue
        lines.append(f"## {g} ({len(items)})")
        for t in sorted(items, key=lambda x: x["due"] if x["due"] != "-" else "9999"):
            due = "" if t["due"] == "-" else f" — {t['due']}"
            lines.append(f"- [{t['status']}] {t['name']} ({t['list']}){due}")
        lines.append("")
    items = []
    for g, its in groups.items():
        for t in sorted(its, key=lambda x: x["due"] if x["due"] != "-" else "9999"):
            due = "" if t["due"] == "-" else f" ({t['due']})"
            items.append(f"[{g}] {t['name']} — {t['list']}{due}")
    due_at = datetime.datetime.combine(today, datetime.time(11, 0), tzinfo=TZ).isoformat()
    payload = {"action": "add", "title": f"Tarefas ClickUp — {len(tasks)} abertas",
               "due_date": due_at, "items": [{"text": x, "done": False} for x in items]}
    r = subprocess.run(["python3", "-I", ODY, "POST", "/api/codex/todos", json.dumps(payload)],
                       capture_output=True, text=True, timeout=120, env=SUBENV)
    print(r.stdout.strip() or r.stderr.strip())
    return r.returncode

if __name__ == "__main__":
    sys.exit(main())
