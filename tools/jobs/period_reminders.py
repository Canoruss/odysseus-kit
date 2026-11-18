#!/usr/bin/env python3
"""Lembretes da aba Ciclo na conta de cada utilizador (período, janela fértil, atraso). Daily cron (e.g. 09:47). With --pill (cron every 10 min): creates the pill reminder.
Só avisa quem já registou pelo menos um período e não desligou o lembrete nas definições da aba.
Uso: period_reminders.py [--dry]   (--dry só mostra o que criaria)"""
import datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hub"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kitconfig import JOBS_STATE
import lib, users, period

SENT = os.path.join(JOBS_STATE, "period-sent.json")
os.makedirs(JOBS_STATE, exist_ok=True)
DRY = "--dry" in sys.argv
PILL = "--pill" in sys.argv   # cron 00:10: cria o lembrete da pílula de hoje à hora escolhida


def pill_jobs(user, today):
    """Cron de 10 em 10 min: perto da hora escolhida cria o lembrete, mas só se a pílula de hoje ainda não foi marcada."""
    d = period.load(user)
    r = d["settings"].get("remind", {})
    if not r.get("pill") or not d["settings"].get("takes_pill"):
        return []
    if d["days"].get(today.isoformat(), {}).get("pill"):
        return []   # já tomou
    en = d["settings"].get("lang") == "en"
    t = r.get("pill_time", "09:00")
    when = datetime.datetime.combine(today, datetime.time(int(t[:2]), int(t[3:])))
    now = lib.now().replace(tzinfo=None)
    if not (when - datetime.timedelta(minutes=10) <= now < when + datetime.timedelta(hours=3)):
        return []
    return [("pill", today.toordinal(), "Take your pill 💊" if en else "Tomar a pílula 💊", max(when, now + datetime.timedelta(minutes=1)))]


def jobs_for(user, today):
    d = period.load(user)
    if not period.runs(d["days"]):
        return []
    st, r = d["settings"], d["settings"]["remind"]
    en = st.get("lang") == "en"
    info = period.predict(d["days"], today, st)
    out = []
    if r["period"] and info["next"]:
        left = (info["next"] - today).days
        if left in {int(r["before"]), 0}:
            if en:
                title = "Period expected " + ("today" if left == 0 else "in %d day%s" % (left, "s" if left > 1 else ""))
            else:
                title = "Menstruação prevista " + ("hoje" if left == 0 else "em %d dia%s" % (left, "s" if left > 1 else ""))
            out.append(("period", "%d|%d" % (left, info["next"].toordinal()), title))
    if r["ovulation"] and info["fert"] and info["fert"][0] == today:
        title = ("Your fertile window starts today (ovulation expected on %d/%d)" if en else
                 "Começa hoje a janela fértil (ovulação prevista a %d/%d)") % (info["ov"].day, info["ov"].month)
        out.append(("fert", str(today.toordinal()), title))
    if r["late"] and info["late"] in (1, 3, 7):
        n = info["late"]
        if en:
            extra = " You can take a pregnancy test now." if st["goal"] == "engravidar" else ""
            title = "Period late %d day%s.%s Log it when it starts." % (n, "s" if n > 1 else "", extra)
        else:
            extra = " Já podes fazer um teste de gravidez." if st["goal"] == "engravidar" else ""
            title = "Menstruação atrasada %d dia%s.%s Regista quando começar." % (n, "s" if n > 1 else "", extra)
        out.append(("late", "%d|%d" % (n, info["last"].toordinal()), title))
    return out


def main():
    try:
        sent = json.load(open(SENT))
    except Exception:
        sent = {}
    today = lib.now().date()
    n = 0
    for user in users.USERS:
        try:
            jobs = [j + (None,) for j in jobs_for(user, today)] if not PILL else pill_jobs(user, today)
        except Exception as e:
            print("erro", user, repr(e)[:100]); continue
        for kind, key, title, when in jobs:
            k = "%s|%s|%s" % (user, kind, key)
            if k in sent:
                continue
            if DRY:
                print("[dry]", user, "->", title); continue
            ok, msg = users.add_reminder(user, title, when)
            print(user, ok, title, msg[:60])
            if ok:
                sent[k] = today.isoformat(); n += 1
    if not DRY:
        sent = {k: v for k, v in sent.items() if (today - datetime.date.fromisoformat(v)).days < 90}
        json.dump(sent, open(SENT, "w"))
    print("lembretes criados:" if not DRY else "simulação concluída:", n)


if __name__ == "__main__":
    main()
