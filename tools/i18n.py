"""Traducao das paginas do KIT (fonte: portugues). Dicionario em i18n/en.json (gerado por scripts/build_i18n.py, editavel).
Idioma de cada pedido: cookie 'kitlang' (en|pt)  >  config 'language'  >  'en'.
translate(texto, lang, mode) -> texto traduzido. mode: 'html' (paginas), 'json' (respostas JSON)."""
import json, os, re

from kitconfig import get, _TOOLS

ROOT = os.path.dirname(_TOOLS)
DICT_PATH = os.environ.get("KIT_I18N_FILE", os.path.join(ROOT, "i18n", "en.json"))
SUPPORTED = ("en", "pt")
SOURCE = "pt"
_PH = re.compile(r"\{[^{}]*\}")
_cache = {"mtime": None, "exact": None, "pats": None}


def default_lang():
    v = get("language", "en")
    return v if v in SUPPORTED else "en"


def from_cookie(cookie):
    m = re.search(r"(?:^|;\s*)kitlang=(en|pt)\b", cookie or "")
    return m.group(1) if m else default_lang()


def cookie_header(lang):
    return "kitlang=%s; Path=/; Max-Age=31536000; SameSite=Lax" % lang


def _load():
    try:
        mt = os.path.getmtime(DICT_PATH)
    except OSError:
        return None, None
    if _cache["mtime"] == mt:
        return _cache["exact"], _cache["pats"]
    d = json.load(open(DICT_PATH, encoding="utf-8")).get("web", {})
    exact, pats = {}, []
    for k, v in d.items():
        if not v or v.strip() == k.strip():
            continue
        if _PH.search(k):
            parts, toks = _PH.split(k), _PH.findall(k)
            tokmap, pieces = {}, []
            for i, p in enumerate(parts):
                pieces.append(re.escape(p).replace(r"\ ", r"\s+"))
                if i < len(parts) - 1:
                    tokmap.setdefault(toks[i], i)
                    pieces.append(r"(?P<g%d>[^<>\n]{0,120}?)" % i)
            pats.append((re.compile("".join(pieces)), v, tokmap))
        else:
            exact[re.sub(r"\s+", " ", k).strip()] = v
    # alternancia unica, chaves mais longas primeiro
    keys = sorted(exact, key=len, reverse=True)
    if keys:
        alts = []
        for k in keys:
            rx = r"\s+".join(re.escape(w) for w in k.split(" "))
            if " " not in k and len(k) < 12:      # palavras soltas: so traduzem quando sao o texto inteiro (nunca dentro de frases)
                pre, post = r"(?<=[>\"'`])", r"(?=[<\"'`])"
            else:
                pre = r"(?<![\w])" if re.match(r"\w", k) else ""
                post = r"(?![\w])" if re.search(r"\w$", k) else ""
            alts.append(pre + rx + post)
        big = re.compile("|".join(alts))
    else:
        big = None
    _cache.update(mtime=mt, exact=(big, exact), pats=pats)
    return _cache["exact"], _cache["pats"]


def _esc(s, mode):
    if mode == "json":
        return json.dumps(s, ensure_ascii=False)[1:-1]
    if mode == "js":
        return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", "\\n")
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _tr_chunk(text, big_exact, pats, mode):
    big, exact = big_exact if big_exact else (None, {})
    for rx, v, tokmap in pats:
        def rep(m, v=v, tokmap=tokmap):
            res = _PH.sub(lambda t: m.group("g%d" % tokmap[t.group(0)]) if t.group(0) in tokmap else "", v)
            return _esc(res, mode)
        text = rx.sub(rep, text)
    if big:
        def rep2(m):
            key = re.sub(r"\s+", " ", m.group(0)).strip()
            return _esc(exact.get(key, m.group(0)), mode) if key in exact else m.group(0)
        text = big.sub(rep2, text)
    return text


_SCRIPT = re.compile(r"(<script\b[^>]*>)(.*?)(</script>)", re.S | re.I)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.S | re.I)


def translate(text, lang, mode="html"):
    if lang == SOURCE or not text:
        return text
    try:
        be, pats = _load()
    except Exception:
        return text
    if be is None:
        return text
    if mode == "json":
        return _tr_chunk(text, be, pats, "json")
    out, pos = [], 0
    for m in _SCRIPT.finditer(text):
        out.append(_tr_html_nostyle(text[pos:m.start()], be, pats))
        out.append(m.group(1) + _tr_chunk(m.group(2), be, pats, "js") + m.group(3))
        pos = m.end()
    out.append(_tr_html_nostyle(text[pos:], be, pats))
    res = "".join(out)
    return res.replace('<html lang="pt"', '<html lang="%s"' % lang)


def _tr_html_nostyle(text, be, pats):
    out, pos = [], 0
    for m in _STYLE.finditer(text):
        out.append(_tr_chunk(text[pos:m.start()], be, pats, "html")); out.append(m.group(0)); pos = m.end()
    out.append(_tr_chunk(text[pos:], be, pats, "html"))
    return "".join(out)
