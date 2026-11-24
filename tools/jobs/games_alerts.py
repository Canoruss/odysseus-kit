#!/usr/bin/env python3
"""Avisa de jogos grátis novos (Epic/Steam/GOG/itch/Prime) a quem ligou os avisos na aba Jogos grátis. Cron every 2 hours.
Na primeira execução só regista o que já existe. Uso: games_alerts.py [--dry]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hub")); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kitconfig import JOBS_STATE
import users, games
SEEN = os.path.join(JOBS_STATE, "games-seen.json"); os.makedirs(JOBS_STATE, exist_ok=True)
DRY = "--dry" in sys.argv


def main():
    first = not os.path.exists(SEEN)
    try: seen = set(json.load(open(SEEN)))
    except Exception: seen = set()
    d = games.fetch()
    if not d["now"]:
        print("sem dados"); return
    cur = {}
    for g in d["now"]:
        pl = (g.get("platforms") or "").lower()
        if any(s in pl for s in games.STORES):
            cur[g.get("open_giveaway_url") or g["title"]] = g
    new = [g for k, g in cur.items() if k not in seen]
    if not DRY: json.dump(sorted(seen | set(cur)), open(SEEN, "w"))
    if first or not new:
        print("primeira execução, registados %d" % len(cur) if first else "sem novidades"); return
    for user, st in games.alerts_load().items():
        if not st.get("on"): continue
        en = st.get("lang") == "en"
        mine = [g for g in new if any(x in (g.get("platforms") or "").lower() for x in st.get("stores", games.STORES))]
        if not mine: continue
        names = [games.re.sub(r" ?\(.*?\) Giveaway| Giveaway", "", g["title"]) for g in mine[:3]]
        more = len(mine) - 3
        title = ("Free game: " if en else "Jogo grátis: ") + ", ".join(names) + ((" +%d" % more if en else " e mais %d" % more) if more > 0 else "")
        if DRY: print("[dry]", user, title); continue
        print(user, users.add_reminder(user, title))


main()
