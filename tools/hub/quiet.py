"""Horas de silêncio comuns a todos os lembretes automáticos (Ciclo, Foco, Jogos, Faturas, Estudo...). Dados por conta em quiet.json."""
import os, json, re, html, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(HERE, "quiet.json")
E = html.escape
_T = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _u(u): return re.sub(r"[^a-z0-9]", "", str(u).lower())


def load(u):
    try: d = json.load(open(F)).get(_u(u), {})
    except (OSError, ValueError): d = {}
    return {"on": bool(d.get("on")), "from": d.get("from") or "22:00", "to": d.get("to") or "08:00"}


def save(u, on, a, b):
    try: d = json.load(open(F))
    except (OSError, ValueError): d = {}
    cur = load(u)
    d[_u(u)] = {"on": bool(on), "from": a if _T.match(a or "") else cur["from"], "to": b if _T.match(b or "") else cur["to"]}
    tmp = F + ".tmp"; fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(d, f)
    os.replace(tmp, F)


def shift(u, when):
    """Se 'when' cai nas horas de silêncio do utilizador, devolve o fim do silêncio; senão devolve 'when'."""
    q = load(u)
    if not q["on"]: return when
    h = lambda s: datetime.time(int(s[:2]), int(s[3:]))
    a, b, t = h(q["from"]), h(q["to"]), when.time()
    inq = (a <= t or t < b) if a > b else (a <= t < b)
    if not inq: return when
    end = when.replace(hour=b.hour, minute=b.minute, second=0, microsecond=0)
    if end <= when: end += datetime.timedelta(days=1)
    return end


def box(u, lang, back):
    en = lang == "en"; q = load(u)
    L = lambda pt, e: e if en else pt
    return (f'<form method="post" action="/finance/quiet" style="max-width:560px;margin:18px auto;padding:12px;background:#262a31;border-radius:10px;color:#eee">'
            f'<b>🌙 {E(L("Horas de silêncio", "Quiet hours"))}</b><br><small style="color:#9aa3b2">{E(L("Os lembretes automáticos (não urgentes) esperam pelo fim do silêncio. Avisos de voo passam sempre.", "Automatic (non-urgent) reminders wait until quiet hours end. Flight alerts always get through."))}</small><br>'
            f'<input type="hidden" name="back" value="{E(back)}"><label><input type="checkbox" name="on" value="1"{" checked" if q["on"] else ""}> {E(L("Ativar", "Enable"))}</label> '
            f'{E(L("das", "from"))} <input type="time" name="from" value="{q["from"]}"> {E(L("às", "to"))} <input type="time" name="to" value="{q["to"]}"> <button>{E(L("Guardar", "Save"))}</button></form>')
