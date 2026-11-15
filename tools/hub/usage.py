"""Uso dos modelos/servicos para a barra junto ao utilizador (GET /finance/usage). Cache de 5 min.
Claude: mesma fonte que o /usage do Claude Code (nao oficial; se falhar mostra 'indisponivel').
Groq: cabecalhos x-ratelimit de um pedido minimo (de 30 em 30 min, ~5% da quota diaria).
DeepL: /v2/usage (oficial). AirLabs: contador local. Gemini: sem API de uso."""
import datetime, json, os, sys, threading, time, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kitconfig import secret_file

H = os.path.expanduser("~")
_lock = threading.Lock()
_cache = {"t": 0, "data": None}
_groq = {"t": 0, "row": None}
UA = "odysseus-kit-usage/1.0"


def _env(path, key):
    try:
        for l in open(os.path.expanduser(path)):
            if l.startswith(key + "="): return l.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return ""


def _get(url, headers, data=None, timeout=12):
    r = urllib.request.Request(url, data=data, headers=dict({"User-Agent": UA}, **headers))
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.headers, json.loads(resp.read() or b"{}")


def _when(iso):
    try:
        d = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except Exception:
        return ""
    now = datetime.datetime.now().astimezone()
    if d.date() == now.date(): return "às %s" % d.strftime("%H:%M")
    dias = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    return "%s %s" % (dias[d.weekday()], d.strftime("%H:%M"))


def claude():
    try:
        o = json.load(open(H + "/.claude/.credentials.json"))["claudeAiOauth"]
        _, d = _get("https://api.anthropic.com/api/oauth/usage",
                    {"Authorization": "Bearer " + o["accessToken"], "anthropic-beta": "oauth-2025-04-20"})
    except Exception as e:
        return {"name": "Claude", "error": "indisponível"}
    names = {"session": "Sessão (5 h)", "weekly_all": "Semana · todos"}
    rows = []
    for l in d.get("limits") or []:
        label = names.get(l.get("kind"))
        if not label and l.get("kind") == "weekly_scoped":
            label = "Semana · " + ((((l.get("scope") or {}).get("model") or {}).get("display_name")) or "modelo")
        if not label: continue
        rows.append({"label": label, "pct": round(float(l.get("percent") or 0)), "reset": _when(l.get("resets_at") or "")})
    if not rows:                                  # formato antigo
        for k, label in (("five_hour", "Sessão (5 h)"), ("seven_day", "Semana · todos")):
            v = d.get(k) or {}
            if v.get("utilization") is not None:
                rows.append({"label": label, "pct": round(v["utilization"]), "reset": _when(v.get("resets_at") or "")})
    ex = d.get("extra_usage") or {}
    extra = ""
    if ex.get("is_enabled") and ex.get("used_credits"):
        extra = "créditos extra: %.2f %s" % (ex["used_credits"] / 100, ex.get("currency") or "")
    return {"name": "Claude", "rows": rows, "note": extra}


def groq():
    if _groq["row"] and time.time() - _groq["t"] < 1800: return _groq["row"]
    k = _env(secret_file("groq"), "GROQ_API_KEY")
    if not k: return None
    try:
        body = json.dumps({"model": "qwen/qwen3.8-27b", "messages": [{"role": "user", "content": "1"}], "max_tokens": 1}).encode()
        h, _ = _get("https://api.groq.com/openai/v1/chat/completions", {"Authorization": "Bearer " + k, "Content-Type": "application/json"}, body)
        lim, rem = int(h.get("x-ratelimit-limit-requests") or 0), int(h.get("x-ratelimit-remaining-requests") or 0)
        row = {"name": "Groq", "rows": [{"label": "Pedidos/dia", "pct": round(100 * (lim - rem) / lim) if lim else 0,
                                          "reset": "%d de %d livres" % (rem, lim)}]}
    except urllib.error.HTTPError as e:
        row = {"name": "Groq", "rows": [{"label": "Pedidos/dia", "pct": 100, "reset": "limite atingido"}]} if e.code == 429 else {"name": "Groq", "error": "indisponível"}
    except Exception:
        row = {"name": "Groq", "error": "indisponível"}
    _groq.update(t=time.time(), row=row)
    return row


def deepl():
    k = _env(secret_file("deepl"), "DEEPL_API_KEY")
    if not k: return None
    try:
        _, d = _get(("https://api-free.deepl.com" if k.endswith(":fx") else "https://api.deepl.com") + "/v2/usage", {"Authorization": "DeepL-Auth-Key " + k})
        c, l = d.get("character_count", 0), d.get("character_limit", 0) or 1
        return {"name": "DeepL", "rows": [{"label": "Caracteres/mês", "pct": round(100 * c / l), "reset": "%d mil de %d mil" % (c // 1000, l // 1000)}]}
    except Exception:
        return {"name": "DeepL", "error": "indisponível"}


def airlabs():
    try:
        import airlabs as A
        used, lim = int(A.usage(os.path.dirname(os.path.abspath(__file__))) or 0), 1000
        return {"name": "AirLabs", "rows": [{"label": "Consultas/mês", "pct": round(100 * used / lim), "reset": "%d de %d" % (used, lim)}]}
    except Exception:
        return None


def get():
    with _lock:
        if _cache["data"] and time.time() - _cache["t"] < 300: return _cache["data"]
        items = [x for x in (claude(), groq(), deepl(), airlabs()) if x]
        items.append({"name": "Gemini", "note": "o plano grátis não tem API de uso"})
        data = {"items": items, "updated": time.strftime("%H:%M")}
        _cache.update(t=time.time(), data=data)
        return data
