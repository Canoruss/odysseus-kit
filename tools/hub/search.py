"""Pesquisa global: procura nos dados da propria conta (Ideias, Sonhos, Foco, Estudo, Contas, Financas). So le ficheiros do utilizador."""
import os, json, re, html
HERE = os.path.dirname(os.path.abspath(__file__))
E = html.escape
SKIP = {"seen", "id", "ids", "password", "pw", "token", "hash", "salt", "ts", "t_id"}


def _u(u): return re.sub(r"[^a-z0-9_-]", "", str(u).lower())


def _sources(u, owner, mlike):
    u = _u(u); s = []
    s.append(("🎯 Foco / Focus", "/finance/focus", "focus-%s.json" % u))
    s.append(("💭 Sonhos / Dreams", "/finance/dreams", "dreams-%s.json" % u))
    s.append(("🎓 Estudo / Study", "/finance/study", "study-%s.json" % u))
    s.append(("🧾 Contas / Bills", "/finance/bills", "bills-%s.json" % u))
    if owner:
        s.append(("💡 Ideias / Ideas", "/finance/inbox", "inbox.json"))
        s.append(("💶 Finanças / Finance", "/finance/", "data.json"))
    elif mlike:
        s.append(("💶 Finanças / Finance", "/finance/m/home", "data-%s.json" % u))
    return s


def _walk(o, q, out, ctx=None):
    if isinstance(o, dict):
        txt = [str(v) for k, v in o.items() if k not in SKIP and isinstance(v, (str, int, float)) and str(v).strip()]
        hit = [t for t in txt if q in t.lower()]
        if hit:
            out.append(" · ".join(txt)[:220])
        for k, v in o.items():
            if k in SKIP: continue
            if isinstance(v, (dict, list)): _walk(v, q, out)
    elif isinstance(o, list):
        for v in o:
            if isinstance(v, (dict, list)): _walk(v, q, out)
            elif isinstance(v, str) and q in v.lower(): out.append(v[:220])


def find(u, q, owner, mlike):
    q = (q or "").strip().lower()[:60]
    res = []
    if len(q) < 2: return res
    for label, link, f in _sources(u, owner, mlike):
        try: d = json.load(open(os.path.join(HERE, f)))
        except (OSError, ValueError): continue
        out = []; _walk(d, q, out)
        seen = []
        for x in out:
            if x not in seen: seen.append(x)
        if seen: res.append((label, link, seen[:8]))
    return res


def render(u, q, lang, owner, mlike):
    en = lang == "en"; L = lambda pt, e: e if en else pt
    res = find(u, q, owner, mlike)
    body = ""
    for label, link, items in res:
        li = "".join("<li>%s</li>" % re.sub("(?i)(%s)" % re.escape(E(q)), r"<mark>\1</mark>", E(x)) for x in items)
        body += f'<h3><a href="{link}">{label}</a></h3><ul>{li}</ul>'
    if q and not res: body = "<p>%s</p>" % E(L("Nada encontrado.", "Nothing found."))
    return (f'<div style="max-width:640px;margin:auto"><h1>🔎 {E(L("Pesquisa", "Search"))}</h1><form method="get" action="/finance/search"><input name="q" value="{E(q or "")}" placeholder="{E(L("Pesquisar em todas as abas…", "Search all tabs…"))}" autofocus style="width:75%;padding:8px"> <button>{E(L("Procurar", "Search"))}</button></form>{body}</div>')
