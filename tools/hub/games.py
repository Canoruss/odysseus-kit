"""Jogos grátis: ofertas ativas (GamerPower: Epic, Steam, GOG, itch, Prime...) + próximos grátis da Epic. Cache 30 min."""
import os, json, time, html, re, urllib.request, urllib.parse, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "games-cache.json")
E = html.escape
TTL = 1800
FILTERS = [("", "Todos", "All"), ("epic", "Epic", "Epic"), ("steam", "Steam", "Steam"), ("gog", "GOG", "GOG"),
           ("itch", "itch.io", "itch.io"), ("prime", "Prime", "Prime"), ("android", "Android", "Android")]


ALERTS = os.path.join(HERE, "games-alerts.json")
STORES = ("epic", "steam", "gog", "itch", "prime")


def alerts_load():
    try: return json.load(open(ALERTS))
    except (OSError, ValueError): return {}


def alerts_set(u, on, lang):
    d = alerts_load(); u = re.sub(r"[^a-z0-9_-]", "", str(u).lower())
    d[u] = {"on": bool(on), "lang": "en" if lang == "en" else "pt"}
    tmp = ALERTS + ".tmp"; fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(d, f)
    os.replace(tmp, ALERTS)


def T(lang, pt, en): return en if lang == "en" else pt


def _get(url):
    r = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (KIT free-games)"})
    return json.load(urllib.request.urlopen(r, timeout=15))


def fetch():
    try:
        c = json.load(open(CACHE))
        if time.time() - c.get("ts", 0) < TTL: return c
    except (OSError, ValueError): c = {}
    out = {"ts": time.time(), "now": c.get("now", []), "next": c.get("next", [])}
    try:
        out["now"] = [{k: g.get(k, "") for k in ("title", "worth", "platforms", "end_date", "thumbnail", "open_giveaway_url", "type")}
                      for g in _get("https://www.gamerpower.com/api/giveaways?type=game&sort-by=popularity")]
    except Exception: pass
    try:
        el = _get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=en-US&country=PT&allowCountries=PT")["data"]["Catalog"]["searchStore"]["elements"]
        nx = []
        for e in el:
            for blk in ((e.get("promotions") or {}).get("upcomingPromotionalOffers") or []):
                for o in blk.get("promotionalOffers", []):
                    if o.get("discountSetting", {}).get("discountPercentage") == 0:
                        slug = e.get("productSlug") or e.get("urlSlug") or ""
                        nx.append({"title": e["title"], "start": o["startDate"][:10], "slug": slug.split("/")[0]})
        out["next"] = sorted(nx, key=lambda x: x["start"])
    except Exception: pass
    try:
        tmp = CACHE + ".tmp"; json.dump(out, open(tmp, "w")); os.replace(tmp, CACHE)
    except OSError: pass
    return out


def _ok(u): return u if re.match(r"https://", u or "") else "#"


def render(flt, lang, user=""):
    d = fetch(); on = alerts_load().get(re.sub(r"[^a-z0-9_-]", "", str(user).lower()), {}).get("on", False); flt = flt if flt in [f[0] for f in FILTERS] else ""
    rows = []
    for g in d["now"]:
        pl = (g.get("platforms") or "")
        if flt and flt not in pl.lower() and flt not in (g.get("title") or "").lower(): continue
        end = g.get("end_date") or ""
        endt = T(lang, "sem data de fim", "no end date") if end in ("", "N/A") else T(lang, "até ", "until ") + end[:10]
        worth = g.get("worth") or ""
        th = _ok(g.get("thumbnail"))
        rows.append(f'<a class="gm" href="{E(_ok(g.get("open_giveaway_url")))}" target="_blank" rel="noopener noreferrer">'
                    f'<img src="{E(th)}" alt="" loading="lazy"><div><b>{E(re.sub(r" ?\(.*?\) Giveaway| Giveaway", "", g.get("title") or ""))}</b>'
                    f'<small>{E(pl[:50])}</small><small>{E(endt)}{" · " + E(worth) if worth and worth != "N/A" else ""}</small></div></a>')
    chips = "".join(f'<a class="ch{" on" if k == flt else ""}" href="?p={k}">{E(T(lang, a, b))}</a>' for k, a, b in FILTERS)
    nxt = "".join(f'<li><b>{E(n["title"])}</b> — {E(T(lang, "a partir de ", "from "))}{E(n["start"])}</li>' for n in d["next"][:8])
    age = int((time.time() - d["ts"]) / 60)
    empty = "" if rows else f'<p>{E(T(lang, "Nada encontrado agora.", "Nothing found right now."))}</p>'
    return f"""<style>.gms{{max-width:720px;margin:auto}}.gm{{display:flex;gap:12px;align-items:center;background:#262a31;border-radius:10px;padding:8px;margin:8px 0;color:#eee;text-decoration:none}}
.gm img{{width:120px;height:68px;object-fit:cover;border-radius:6px;background:#1d2026}}.gm div{{display:flex;flex-direction:column;gap:2px}}.gm small{{color:#9aa3b2}}
.ch{{display:inline-block;padding:6px 12px;border-radius:16px;background:#2a2e36;color:#ccc;text-decoration:none;margin:2px}}.ch.on{{background:#4a7bd0;color:#fff}}</style>
<div class="gms"><h1>🎮 {E(T(lang, "Jogos grátis", "Free games"))}</h1><form method="post" action="/finance/games/alerts" style="margin:6px 0"><input type="hidden" name="on" value="{0 if on else 1}"><button>{"🔔 " + E(T(lang, "Avisos ligados (desligar)", "Alerts on (turn off)")) if on else "🔕 " + E(T(lang, "Avisar-me de jogos grátis novos (Epic, Steam, GOG, itch.io, Prime)", "Alert me about new free games (Epic, Steam, GOG, itch.io, Prime)"))}</button></form><div>{chips}</div>{"".join(rows)}{empty}
<h2>{E(T(lang, "Próximos grátis na Epic", "Coming next on Epic"))}</h2><ul>{nxt or "<li>—</li>"}</ul>
<small style="color:#7d8594">{E(T(lang, f"Atualizado há {age} min · fonte: GamerPower e Epic", f"Updated {age} min ago · source: GamerPower and Epic"))}</small></div>"""
