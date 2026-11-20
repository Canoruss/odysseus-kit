#!/usr/bin/env python3
"""Avisa de eventos referidos em emails recentes que NAO estao no calendario do Odysseus.
Emails -> Groq extrai eventos com data futura -> compara com o calendario -> cria um lembrete (notificacao).
Por utilizador: --user <dono> (default, API do agente) ou --user <membro> (login do utilizador). --dry so mostra; --days N (default 3) janela de emails.
Desativar: tools-prefs / remover do cron."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import datetime, json, os, re, subprocess, sys, time, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib, users

DRY = "--dry" in sys.argv
DAYS = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 3
USER = sys.argv[sys.argv.index("--user") + 1] if "--user" in sys.argv else OWNER
SENT = os.path.join(JOBS_STATE, "email-events-sent.json" if USER == OWNER else "email-events-sent-%s.json" % USER)
PATHS = {OWNER: ("/api/codex/emails?folder=INBOX&limit=40&offset=0", "/api/codex/emails/%s?folder=%s", "/api/codex/calendar/events?start=%s&end=%s"),
         "other": ("/api/email/list?folder=INBOX&limit=40", "/api/email/read/%s?folder=%s", "/api/calendar/events?start=%s&end=%s")}
P = PATHS[OWNER if USER == OWNER else "other"]
MODEL = "qwen/qwen3.8-27b"


def api(method, path, body=None):
    if USER != OWNER:
        try: return json.load(users._session(USER).open(users.B + path, timeout=120))
        except Exception as e: raise RuntimeError("API %s falhou: %r" % (path, e))
    cmd = ["python3", "-I", lib.ODY, method, path] + ([json.dumps(body)] if body is not None else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=lib.ENV)
    try: return json.loads(r.stdout)
    except Exception: raise RuntimeError("API %s falhou: %s" % (path, (r.stdout or r.stderr)[:200]))


def groq(prompt):
    key = [l.strip().split("=", 1)[1] for l in open(secret_file("groq")) if l.startswith("GROQ_API_KEY=")][0]
    body = {"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}]}
    rq = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", json.dumps(body).encode(),
                                {"Content-Type": "application/json", "Authorization": "Bearer " + key, "User-Agent": "odysseus-reminders/1.0"})
    for i in range(4):
        try:
            return json.loads(json.load(urllib.request.urlopen(rq, timeout=60))["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == 3: raise
            time.sleep(8 * (i + 1))


def extract(em, body, today):
    p = ("Hoje é %s (Europe/Lisbon). Do email abaixo extrai SÓ compromissos reais com data (e idealmente hora) FUTURA: "
         "reuniões, consultas, voos, reservas, entregas agendadas, eventos a que o destinatário vai. "
         "Ignora newsletters, promoções, faturas, avisos de segurança e datas passadas. "
         'Responde JSON: {"events":[{"title":"...","start":"YYYY-MM-DDTHH:MM" ou "YYYY-MM-DD" se sem hora,"location":"..."}]} (lista vazia se nada).\n\n'
         "De: %s <%s>\nAssunto: %s\n\n%s") % (today.isoformat(), em.get("from_name"), em.get("from_address"), em.get("subject"), body[:3500])
    return groq(p).get("events", []) or []


DATEISH = re.compile(r"\d{1,2}[/.-]\d{1,2}|\d{1,2}[h:]\d{2}|\b(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|feb|apr|may|aug|sep|oct|dec)\w*|amanh|segunda|terça|quarta|quinta|sexta|s[áa]bado|domingo|monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow", re.I)


def words(s): return {w for w in re.findall(r"\w{4,}", (s or "").lower())}


def in_calendar(ev, cal):
    d = ev["start"][:10]
    for c in cal:
        if (c.get("dtstart") or c.get("start") or "")[:10] != d: continue
        if words(ev["title"]) & words(c.get("summary") or c.get("title")): return True
        if "T" in ev["start"] and "T" in str(c.get("dtstart") or c.get("start")) and (c.get("dtstart") or c.get("start"))[11:16] == ev["start"][11:16]: return True
    return False


def main():
    sent = {}
    try: sent = json.load(open(SENT))
    except Exception: pass
    now = lib.now(); today = now.date()
    mails = api("GET", P[0]).get("emails", [])
    cutoff = now.timestamp() - DAYS * 86400
    mails = [m for m in mails if m.get("date_epoch", 0) >= cutoff]
    cal = api("GET", P[2] % (today.isoformat() + "T00:00:00", (today + datetime.timedelta(days=120)).isoformat() + "T23:59:59"))
    cal = cal if isinstance(cal, list) else cal.get("events", [])
    print("emails %d (últimos %d dias), eventos no calendário %d" % (len(mails), DAYS, len(cal)))
    for m in mails:
        k0 = m.get("message_id") or m["uid"]
        if k0 in sent: continue
        try:
            full = api("GET", P[1] % (m["uid"], m.get("folder", "INBOX")))
            body = full.get("body", "")
            if not DATEISH.search((m.get("subject") or "") + " " + body[:3500]):
                sent[k0] = True; continue
            time.sleep(2)
            evs = extract(m, body, today)
        except Exception as e:
            print("erro", m["uid"], repr(e)[:120]); continue
        sent[k0] = True
        for ev in evs:
            try:
                st = datetime.datetime.fromisoformat(ev["start"][:16] if "T" in ev["start"] else ev["start"][:10] + "T09:00")
            except Exception: continue
            if st.date() < today or in_calendar(ev, cal): continue
            quando = st.strftime("%d/%m %H:%M") if "T" in ev["start"] else st.strftime("%d/%m")
            title = "📅 Não está no calendário: %s (%s)%s — email de %s" % (ev["title"], quando, (", " + ev["location"]) if ev.get("location") else "", m.get("from_name") or m.get("from_address"))
            if DRY: print("[dry]", title); continue
            ok, msg = users.add_reminder(USER, title, now + datetime.timedelta(minutes=1))
            print("OK" if ok else "FALHOU " + msg, title)
    if not DRY:
        tmp = SENT + ".tmp"; json.dump(sent, open(tmp, "w")); os.replace(tmp, SENT)


main()
