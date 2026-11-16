"""Ciclo (núcleo): dados, previsões, fases, estatísticas, PIN, exportação e gravação.
A interface está em period_ui.py. Dados por utilizador em period-<user>.json (0600).
As previsões são estimativas e não substituem contraceção nem consulta médica."""
import csv, datetime, hashlib, hmac, io, json, os, re, secrets, threading, time
try:
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from kitconfig import HUB as DIR   # data next to the other hub data (KIT_HUB_DIR)
except Exception:
    DIR = os.path.dirname(os.path.abspath(__file__))
LOCK = threading.Lock()
FLOW = [("", "—"), ("manchas", "Manchas"), ("leve", "Leve"), ("média", "Média"), ("intensa", "Intensa")]
SYMPTOMS = ["Cólicas", "Dor de cabeça", "Seios sensíveis", "Acne", "Inchaço", "Cansaço", "Irritabilidade", "Dor nas costas",
            "Mais apetite", "Náuseas", "Insónias", "Desejo de doces", "Tonturas", "Dores musculares", "Libido alta"]
MOODS = ["", "Feliz", "Calma", "Energética", "Ansiosa", "Triste", "Irritada", "Sensível", "Cansada"]
OVTEST = [("", "—"), ("neg", "Negativo"), ("pos", "Positivo")]
SEX = [("", "—"), ("sim", "Sim"), ("prot", "Sim, protegido")]
DEFAULT_CYCLE, DEFAULT_PERIOD, LUTEAL = 28, 5, 14
SETTINGS = {"lang": "pt", "goal": "acompanhar", "cycle": DEFAULT_CYCLE, "period": DEFAULT_PERIOD,
            "remind": {"period": True, "ovulation": False, "late": True, "before": 2}}
PIN_TTL = 600
_FAILS = {}


def _f(user):
    return os.path.join(DIR, "period-%s.json" % re.sub(r"[^a-z0-9]", "", user))


def load(user):
    try:
        d = json.load(open(_f(user)))
    except Exception:
        d = {}
    d.setdefault("days", {})
    st = d.setdefault("settings", {})
    for k, v in SETTINGS.items():
        if isinstance(v, dict):
            st.setdefault(k, {})
            for k2, v2 in v.items():
                st[k].setdefault(k2, v2)
        else:
            st.setdefault(k, v)
    return d


def save(user, d):
    tmp = _f(user) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, _f(user))


def _d(s):
    try:
        return datetime.date.fromisoformat(s)
    except Exception:
        return None


def runs(days):
    """Períodos: sequências de dias com fluxo. Um dia sem registo entre dois dias de fluxo não separa o período."""
    flow = sorted(_d(k) for k, v in days.items() if v.get("flow") and _d(k))
    out = []
    for dt in flow:
        if out and (dt - out[-1][1]).days <= 2:
            out[-1][1] = dt
        else:
            out.append([dt, dt])
    return out


def predict(days, today, st=None):
    st = st or SETTINGS
    rs = runs(days)
    starts = [r[0] for r in rs]
    lens = [(r[1] - r[0]).days + 1 for r in rs]
    gaps = [(b - a).days for a, b in zip(starts, starts[1:]) if 18 <= (b - a).days <= 60]
    cyc = round(sum(gaps[-6:]) / len(gaps[-6:])) if gaps else int(st.get("cycle", DEFAULT_CYCLE))
    per = round(sum(lens[-6:]) / len(lens[-6:])) if lens else int(st.get("period", DEFAULT_PERIOD))
    per = max(2, min(10, per))
    info = {"cycle": cyc, "period": per, "n": len(rs), "runs": rs[-6:][::-1], "next": None, "late": 0,
            "ongoing": None, "ov": None, "fert": None, "pms": None, "starts": [], "last": starts[-1] if starts else None,
            "known": bool(gaps)}
    if rs and rs[-1][1] == today and days.get(today.isoformat(), {}).get("flow"):
        info["ongoing"] = (today - rs[-1][0]).days + 1
    if rs:
        exp = starts[-1] + datetime.timedelta(days=cyc)
        base = None
        if info["ongoing"] is not None:
            base = exp
        elif exp >= today:
            info["next"] = base = exp
        else:
            info["late"] = (today - exp).days
        if base:
            info["starts"] = [base + datetime.timedelta(days=cyc * k) for k in range(4)]
            info["ov"] = base - datetime.timedelta(days=LUTEAL)
            info["fert"] = (info["ov"] - datetime.timedelta(days=5), info["ov"] + datetime.timedelta(days=1))
            info["pms"] = (base - datetime.timedelta(days=5), base - datetime.timedelta(days=1))
    return info


def chance(info, dt):
    """Probabilidade de gravidez nesse dia: 'alta', 'média' ou 'baixa' (estimativa pelo dia da ovulação)."""
    if not info["ov"]:
        return "baixa"
    d = (dt - info["ov"]).days
    if -2 <= d <= 0:
        return "alta"
    if d in (-5, -4, -3, 1):
        return "média"
    return "baixa"


# Fases do ciclo e dicas (texto próprio). Cada fase: nome, resumo e dicas por tema.
PHASES = {
    "menstrual": ("Menstrual", "O corpo está a renovar-se; a energia costuma estar mais baixa.",
                  ["Alimentação: ferro (leguminosas, folhas verdes) e bastante água.", "Movimento: caminhadas e alongamentos suaves.",
                   "Dia a dia: descansa mais, calor na barriga ajuda nas cólicas."]),
    "folicular": ("Folicular", "A energia sobe aos poucos e a disposição melhora.",
                  ["Alimentação: proteína e fibra, refeições coloridas.", "Movimento: bom momento para treinos mais puxados ou algo novo.",
                   "Dia a dia: boa fase para planear e começar projetos."]),
    "ovulatoria": ("Ovulatória", "Pico de energia e de fertilidade; a pele e o humor costumam estar bons.",
                   ["Alimentação: refeições leves, com antioxidantes (frutos vermelhos, vegetais).", "Movimento: treinos intensos ou em grupo.",
                    "Dia a dia: dias bons para conversas e encontros."]),
    "lutea": ("Lútea", "A progesterona sobe; pode haver mais cansaço, fome e sensibilidade, sobretudo no fim.",
              ["Alimentação: hidratos complexos e magnésio (frutos secos, cacau puro) ajudam com a fome.", "Movimento: yoga, pilates, caminhadas.",
               "Dia a dia: reduz compromissos, dorme bem, sê gentil contigo."]),
}


def phase(info, today):
    """Devolve (chave, dia_do_ciclo) ou (None, None) se ainda não há período registado."""
    if not info["last"]:
        return None, None
    day = (today - info["last"]).days + 1
    if day < 1:
        return None, None
    if info["ongoing"] is not None or day <= info["period"]:
        return "menstrual", day
    ov_day = info["cycle"] - LUTEAL + 1
    if day < ov_day - 1:
        return "folicular", day
    if day <= ov_day + 1:
        return "ovulatoria", day
    return "lutea", day


def stats(days, today):
    rs = runs(days)
    starts = [r[0] for r in rs]
    cycles = [(b - a).days for a, b in zip(starts, starts[1:])]
    lens = [(r[1] - r[0]).days + 1 for r in rs]
    sym, mood = {}, {}
    for v in days.values():
        for s in v.get("sym", []):
            sym[s] = sym.get(s, 0) + 1
        if v.get("mood"):
            mood[v["mood"]] = mood.get(v["mood"], 0) + 1
    streak, dt = 0, today
    if today.isoformat() not in days:
        dt = today - datetime.timedelta(days=1)
    while dt.isoformat() in days:
        streak += 1
        dt -= datetime.timedelta(days=1)
    ok = [c for c in cycles if 18 <= c <= 60]
    return {"cycles": cycles[-12:], "lens": lens[-12:], "avg": round(sum(ok) / len(ok), 1) if ok else None,
            "min": min(ok) if ok else None, "max": max(ok) if ok else None,
            "regular": bool(ok) and (max(ok) - min(ok)) <= 7 and len(ok) >= 2,
            "sym": sorted(sym.items(), key=lambda x: -x[1])[:5], "mood": sorted(mood.items(), key=lambda x: -x[1])[:3],
            "streak": streak, "logged": len(days)}


# ---- PIN (cookie assinada, 10 min) ----
def _secret():
    p = os.path.join(DIR, ".period-secret")
    try:
        return open(p).read().strip()
    except OSError:
        s = secrets.token_hex(32)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(s)
        return s


def _hash(pin, salt):
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 120000).hex()


def has_pin(d):
    return bool(d["settings"].get("pin"))


def token(user):
    exp = str(int(time.time()) + PIN_TTL)
    return exp + "." + hmac.new(_secret().encode(), (user + exp).encode(), "sha256").hexdigest()


def cookie_value(cookie):
    m = re.search(r"(?:^|;\s*)cypin=([0-9]+\.[0-9a-f]+)", cookie or "")
    return m.group(1) if m else ""


def unlocked(user, d, cookie):
    if not has_pin(d):
        return True
    t = cookie_value(cookie)
    if not t:
        return False
    exp, sig = t.split(".", 1)
    good = hmac.new(_secret().encode(), (user + exp).encode(), "sha256").hexdigest()
    return hmac.compare_digest(sig, good) and int(exp) > time.time()


def cookie_header(user, clear=False):
    base = "Path=/finance; HttpOnly; Secure; SameSite=Strict"
    if clear:
        return {"Set-Cookie": "cypin=; Max-Age=0; " + base}
    return {"Set-Cookie": "cypin=%s; Max-Age=%d; %s" % (token(user), PIN_TTL, base)}


def try_pin(user, d, pin):
    n, until = _FAILS.get(user, (0, 0))
    if until > time.time():
        return False, "Demasiadas tentativas. Espera um minuto."
    p = d["settings"].get("pin") or {}
    if p and hmac.compare_digest(_hash(pin, p["salt"]), p["hash"]):
        _FAILS.pop(user, None)
        return True, ""
    n += 1
    _FAILS[user] = (n, time.time() + 60 if n >= 5 else 0)
    return False, "PIN errado."


def set_pin(d, pin):
    salt = secrets.token_hex(16)
    d["settings"]["pin"] = {"salt": salt, "hash": _hash(pin, salt)}


# ---- exportação ----
def export(user, fmt):
    d = load(user)
    if fmt == "csv":
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["data", "fluxo", "sintomas", "humor", "temperatura", "teste_ovulacao", "sexo", "nota"])
        for k in sorted(d["days"]):
            v = d["days"][k]
            w.writerow([k, v.get("flow", ""), "; ".join(v.get("sym", [])), v.get("mood", ""), v.get("temp", ""),
                        v.get("ov", ""), v.get("sex", ""), v.get("note", "")])
        return "text/csv; charset=utf-8", out.getvalue()
    safe = {"days": d["days"], "settings": {k: v for k, v in d["settings"].items() if k != "pin"}}
    return "application/json; charset=utf-8", json.dumps(safe, ensure_ascii=False, indent=1)


# ---- gravação (POST) ----
def _num(s, lo, hi):
    v = float(str(s).replace(",", "."))
    if not lo <= v <= hi:
        raise ValueError
    return round(v, 2)


def _lang(cookie):
    m = re.search(r"(?:^|;\s*)kitlang=(en|pt)\b", cookie or "")
    return m.group(1) if m else ""


def post(user, path, f, cookie=""):
    """Devolve (mensagem, cabeçalhos extra). Guarda o idioma da pessoa para os lembretes."""
    d = load(user)
    lang = _lang(cookie)
    if lang:
        d["settings"]["lang"] = lang
    hdr = {}
    today = datetime.date.today()
    try:
        if path == "/period/unlock":
            ok, msg = try_pin(user, d, f.get("pin", ""))
            return (msg, {}) if not ok else ("", cookie_header(user))
        if not unlocked(user, d, cookie):
            return "Introduz o PIN.", {}
        msg = ""
        if path == "/period/log":
            dt = _d(f.get("date", ""))
            if not dt or dt > today or dt < today - datetime.timedelta(days=3 * 365):
                raise ValueError
            flow = f.get("flow", "")
            if flow not in [v for v, _ in FLOW]:
                raise ValueError
            e = {"flow": flow, "sym": [s for i, s in enumerate(SYMPTOMS) if f.get("s%d" % i) == "1"]}
            mood = f.get("mood", "")
            if mood in MOODS and mood:
                e["mood"] = mood
            if f.get("temp", "").strip():
                e["temp"] = _num(f["temp"], 34.0, 42.0)
            if f.get("ov", "") in ("neg", "pos"):
                e["ov"] = f["ov"]
            if f.get("sex", "") in ("sim", "prot"):
                e["sex"] = f["sex"]
            if f.get("note", "").strip():
                e["note"] = f["note"].strip()[:300]
            key = dt.isoformat()
            if len(e) == 2 and not e["flow"] and not e["sym"]:
                d["days"].pop(key, None)
            else:
                d["days"][key] = e
            msg = "Registo guardado."
        elif path == "/period/del":
            dt = _d(f.get("date", ""))
            if not dt:
                raise ValueError
            d["days"].pop(dt.isoformat(), None)
            msg = "Dia apagado."
        elif path == "/period/settings":
            st = d["settings"]
            if f.get("goal") in ("acompanhar", "engravidar"):
                st["goal"] = f["goal"]
            st["cycle"] = max(21, min(45, int(f.get("cycle", st["cycle"]))))
            st["period"] = max(2, min(10, int(f.get("period", st["period"]))))
            st["remind"] = {"period": f.get("r_period") == "1", "ovulation": f.get("r_ov") == "1",
                            "late": f.get("r_late") == "1", "before": max(0, min(7, int(f.get("before", 2))))}
            msg = "Definições guardadas."
        elif path == "/period/pin":
            if f.get("remove") == "1":
                ok, m = try_pin(user, d, f.get("old", ""))
                if not ok:
                    return m, {}
                d["settings"].pop("pin", None)
                hdr = cookie_header(user, clear=True)
                msg = "PIN removido."
            else:
                pin = f.get("pin", "")
                if not re.fullmatch(r"\d{4,8}", pin):
                    return "O PIN tem de ter 4 a 8 dígitos.", {}
                if has_pin(d):
                    ok, m = try_pin(user, d, f.get("old", ""))
                    if not ok:
                        return m, {}
                set_pin(d, pin)
                hdr = cookie_header(user)
                msg = "PIN definido."
        elif path == "/period/wipe":
            if f.get("confirm", "").strip().upper() != "APAGAR":
                return "Escreve APAGAR para confirmar.", {}
            d["days"] = {}
            msg = "Todos os registos foram apagados."
        elif path == "/period/lock":
            return "Bloqueado.", cookie_header(user, clear=True)
        else:
            return "Pedido desconhecido.", {}
    except (KeyError, ValueError, TypeError):
        return "Dados inválidos.", {}
    with LOCK:
        save(user, d)
    return msg, hdr
