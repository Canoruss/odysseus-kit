"""AirLabs: estado e atrasos de voos (opcional). O plano gratis tem limite de consultas, por isso:
 - cada voo so e consultado quando se carrega em 'Atualizar estado' ou pelo vigia (3 h e 1 h antes da partida);
 - resultados em cache 15 minutos; contador de consultas por mes; para antes do limite."""
import datetime, json, os, re, threading, time, urllib.error, urllib.request

LOCK = threading.Lock()
TTL = 900            # segundos em cache
MONTH_CAP = 900      # margem de seguranca (a AirLabs limita por mes)
KEY_FILES = ("~/.config/odysseus-kit/airlabs.env", "~/.config/airlabs.env")
UA = "Mozilla/5.0 (X11; Linux x86_64) odysseus-flightcheck/1.0"   # sem isto o Cloudflare recusa (erro 1010)
STATUS_PT = {"scheduled": "agendado", "active": "em voo", "landed": "aterrou", "cancelled": "cancelado", "incident": "incidente", "diverted": "desviado"}


def _key():
    for f in KEY_FILES:
        try:
            for l in open(os.path.expanduser(f), encoding="utf-8"):
                if l.startswith("AIRLABS_API_KEY="):
                    v = l.split("=", 1)[1].strip().strip("\"'")
                    if v: return v
        except OSError:
            pass
    return ""


def configured(): return bool(_key())


def _jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError): return d


def _jsave(p, d):
    t = p + ".tmp"
    with open(t, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False)
    os.chmod(t, 0o600); os.replace(t, p)


def usage(base):
    m = datetime.date.today().strftime("%Y-%m")
    u = _jload(os.path.join(base, "airlabs-usage.json"), {})
    return u.get("n", 0) if u.get("month") == m else 0


def _bump(base):
    m = datetime.date.today().strftime("%Y-%m"); p = os.path.join(base, "airlabs-usage.json")
    u = _jload(p, {})
    n = (u.get("n", 0) if u.get("month") == m else 0) + 1
    _jsave(p, {"month": m, "n": n})


def _call(path, key):
    req = urllib.request.Request("https://airlabs.co/api/v9/" + path + "&api_key=" + key, headers={"User-Agent": UA, "Accept": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=20))


def _pick(resp, date):
    resp = [f for f in resp if f.get("dep_time")]
    if not resp: return None
    if date:
        for f in resp:
            if str(f["dep_time"]).startswith(date): return f
        return None
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    fut = sorted((f for f in resp if f["dep_time"] >= now), key=lambda f: f["dep_time"])
    return (fut or resp)[0]


FIELDS = ("status", "dep_iata", "arr_iata", "dep_time", "dep_estimated", "dep_delayed", "arr_time", "arr_estimated", "arr_delayed",
          "dep_terminal", "dep_gate", "arr_terminal", "arr_gate")


def lookup(base, n, date="", force=False):
    """-> {'ok': bool, 'error': str, 'info': dict|None, 't': epoch, 'cached': bool}"""
    n = re.sub(r"[^A-Z0-9]", "", str(n).upper())
    ck = "%s|%s" % (n, date)
    cp = os.path.join(base, "airlabs-cache.json")
    with LOCK:
        cache = _jload(cp, {})
        c = cache.get(ck)
        if c and time.time() - c["t"] < TTL:   # dentro dos 15 min usa sempre a cache (protege a quota)
            return {"ok": True, "error": "", "info": c["info"], "t": c["t"], "cached": True}
        key = _key()
        if not key: return {"ok": False, "error": "Chave AirLabs não configurada.", "info": None, "t": 0, "cached": False}
        if usage(base) >= MONTH_CAP:
            return {"ok": False, "error": "Limite mensal de consultas quase atingido (%d). Usa o Flightradar24." % usage(base), "info": c["info"] if c else None, "t": c["t"] if c else 0, "cached": bool(c)}
        try:
            r = _call("schedules?flight_iata=" + n, key); _bump(base)
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": "A AirLabs recusou o pedido (HTTP %d)." % e.code, "info": None, "t": 0, "cached": False}
        except Exception as e:
            return {"ok": False, "error": "Sem resposta da AirLabs: " + str(e)[:60], "info": None, "t": 0, "cached": False}
        if r.get("error"):
            msg = r["error"].get("message") if isinstance(r["error"], dict) else str(r["error"])
            return {"ok": False, "error": "AirLabs: " + str(msg)[:100], "info": None, "t": 0, "cached": False}
        f = _pick(r.get("response") or [], date)
        if not f:
            return {"ok": False, "error": "Não encontrei este voo na AirLabs (confirma o número e a data).", "info": None, "t": 0, "cached": False}
        info = {k: f.get(k) for k in FIELDS if f.get(k) not in (None, "")}
        cache[ck] = {"t": time.time(), "info": info}
        for k in [k for k, v in cache.items() if time.time() - v["t"] > 7 * 86400]: cache.pop(k, None)
        _jsave(cp, cache)
        return {"ok": True, "error": "", "info": info, "t": cache[ck]["t"], "cached": False}


def _hm(s): return str(s)[11:16] if s else ""


def describe(info):
    """Texto curto em portugues a partir da resposta."""
    if not info: return ""
    st = STATUS_PT.get(info.get("status"), info.get("status") or "")
    parts = ["Estado: " + st]
    if info.get("dep_iata") and info.get("arr_iata"): parts.append("%s → %s" % (info["dep_iata"], info["arr_iata"]))
    dep = _hm(info.get("dep_time")); est = _hm(info.get("dep_estimated"))
    if dep: parts.append("parte " + dep + ((" (previsto " + est + ")") if est and est != dep else ""))
    if info.get("dep_delayed"): parts.append("atraso na partida %s min" % info["dep_delayed"])
    arr = _hm(info.get("arr_time")); aest = _hm(info.get("arr_estimated"))
    if arr: parts.append("chega " + arr + ((" (previsto " + aest + ")") if aest and aest != arr else ""))
    if info.get("arr_delayed"): parts.append("atraso na chegada %s min" % info["arr_delayed"])
    g = " ".join(x for x in (("terminal " + str(info["dep_terminal"])) if info.get("dep_terminal") else "", ("porta " + str(info["dep_gate"])) if info.get("dep_gate") else "") if x)
    if g: parts.append("partida: " + g)
    return " · ".join(parts)


def cached_info(base, n, date=""):
    c = _jload(os.path.join(base, "airlabs-cache.json"), {}).get("%s|%s" % (re.sub(r"[^A-Z0-9]", "", n.upper()), date))
    return (c["info"], c["t"]) if c else (None, 0)
