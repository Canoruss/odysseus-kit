#!/usr/bin/env python3
"""ClickUp helper for the bridge Claude (token: CLICKUP_API_TOKEN env ou ~/.config/odysseus-kit/clickup.env).

  clickup.py members                      list workspace members (id, name, email)
  clickup.py tasks [--assignee NAME] [--all] [--list ID]   open tasks (--all includes done/closed); prints name | status | list | due | url
  clickup.py task ID                      one task as JSON
"""
import json, os, sys, urllib.parse, urllib.request

import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import get as _get, secret_file as _sf
TEAM = _get("clickup_team", "")  # id da equipa ClickUp (assistente de configuracao)


def token():
    t = os.environ.get("CLICKUP_API_TOKEN")
    if not t:
        for line in open(_sf("clickup")):
            if line.startswith("CLICKUP_API_TOKEN="):
                t = line.split("=", 1)[1].strip()
    return t


def api(path, **params):
    q = urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(f"https://api.clickup.com/api/v2/{path}" + (f"?{q}" if q else ""), headers={"Authorization": token()})
    return json.load(urllib.request.urlopen(req, timeout=60))


def members():
    return [m["user"] for t in api("team")["teams"] if t["id"] == TEAM for m in t["members"]]


def main(a):
    if not a:
        return print(__doc__)
    if a[0] == "members":
        for u in members():
            print(u["id"], u["username"], u.get("email", ""))
    elif a[0] == "task":
        print(json.dumps(api(f"task/{a[1]}"), indent=1, ensure_ascii=False))
    elif a[0] == "tasks":
        p = {"include_closed": "true" if "--all" in a else "false", "subtasks": "true", "order_by": "due_date"}
        if "--assignee" in a:
            name = a[a.index("--assignee") + 1].lower()
            hit = [u for u in members() if name in u["username"].lower() or name in u.get("email", "").lower()]
            if not hit:
                sys.exit("no member matches " + name)
            p["assignees[]"] = [u["id"] for u in hit[:1]]
        if "--list" in a:
            p["list_ids[]"] = [a[a.index("--list") + 1]]
        page, rows = 0, []
        while True:
            d = api(f"team/{TEAM}/task", page=page, **p)["tasks"]
            rows += d
            if len(d) < 100:
                break
            page += 1
        for t in rows:
            if "--all" not in a and t["status"]["type"] in ("closed", "done"):
                continue
            due = __import__("datetime").datetime.fromtimestamp(int(t["due_date"]) / 1000).strftime("%Y-%m-%d") if t.get("due_date") else "-"
            print(f'{t["name"]} | {t["status"]["status"]} | {t["list"]["name"]} | {due} | {t["url"]}')
        print(f"({sum(1 for _ in rows)} fetched)", file=sys.stderr)


main(sys.argv[1:])
