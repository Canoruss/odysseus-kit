"""Ferramentas extra (por pessoa): Noticias personalizadas, Compor (email/WhatsApp) e Voos.
Cada pessoa escolhe as suas fontes e temas; nao ha curadoria politica do servidor."""
import datetime, email.utils, html, json, os, re, threading, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import study
import airlabs

DIR = os.path.dirname(os.path.abspath(__file__))
E = html.escape
LOCK = threading.Lock()
PFX = "/finance"

# ---------- Noticias ----------
CATALOG = [  # so fontes cujo feed foi verificado a funcionar
    ("rtp", "RTP", "geral", "https://www.rtp.pt/noticias/rss"),
    ("cnnpt", "CNN Portugal", "geral", "https://cnnportugal.iol.pt/rss"),
    ("observador", "Observador", "geral", "https://observador.pt/feed/"),
    ("minuto", "Notícias ao Minuto", "geral", "https://www.noticiasaominuto.com/rss/ultima-hora"),
    ("sapo", "Sapo 24", "geral", "https://24.sapo.pt/rss"),
    ("visao", "Visão", "geral", "https://visao.pt/feed/"),
    ("eco", "ECO", "economia", "https://eco.sapo.pt/feed/"),
    ("cnbc", "CNBC (EN)", "economia", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("euronews", "Euronews PT", "internacional", "https://pt.euronews.com/rss"),
    ("bbc", "BBC World (EN)", "internacional", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("guardian", "The Guardian (EN)", "internacional", "https://www.theguardian.com/world/rss"),
    ("aljazeera", "Al Jazeera (EN)", "internacional", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("fox", "Fox News (EN)", "internacional", "https://moxie.foxnews.com/google-publisher/latest.xml"),
    ("record", "Record", "desporto", "https://www.record.pt/rss"),
    ("teksapo", "Tek Sapo", "tecnologia", "https://tek.sapo.pt/rss"),
    ("hn", "Hacker News (EN)", "tecnologia", "https://hnrss.org/frontpage"),
    ("techcrunch", "TechCrunch (EN)", "tecnologia", "https://techcrunch.com/feed/"),
    ('pcgamer', 'PC Gamer (EN)', 'jogos', 'https://www.pcgamer.com/rss/'),
    ('eurogamer', 'Eurogamer (EN)', 'jogos', 'https://www.eurogamer.net/feed'),
    ('ign', 'IGN (EN)', 'jogos', 'https://feeds.feedburner.com/ign/all'),
    ('rps', 'Rock Paper Shotgun (EN)', 'jogos', 'https://www.rockpapershotgun.com/feed'),
    ('toms', "Tom's Hardware (EN)", 'tecnologia', 'https://www.tomshardware.com/feeds/all'),
    ('ars', 'Ars Technica (EN)', 'tecnologia', 'https://feeds.arstechnica.com/arstechnica/index'),
    ('verge', 'The Verge (EN)', 'tecnologia', 'https://www.theverge.com/rss/index.xml'),
    ('pitchfork', 'Pitchfork (EN)', 'música', 'https://pitchfork.com/feed/feed-news/rss'),
    ('rollingstone', 'Rolling Stone (EN)', 'música', 'https://www.rollingstone.com/music/feed/'),
    ('nme', 'NME (EN)', 'música', 'https://www.nme.com/news/music/feed'),
    ('bbcfoot', 'BBC Sport Futebol (EN)', 'desporto', 'https://feeds.bbci.co.uk/sport/football/rss.xml'),
    ('espnfc', 'ESPN FC (EN)', 'desporto', 'https://www.espn.com/espn/rss/soccer/news'),
    ('maisfut', 'Maisfutebol', 'desporto', 'https://maisfutebol.iol.pt/rss'),
    ('nypost', 'New York Post (EN)', 'opinião', 'https://nypost.com/feed/'),
    ('dailywire', 'The Daily Wire (EN)', 'opinião', 'https://www.dailywire.com/feeds/rss.xml'),
    ('spiked', 'Spiked (EN)', 'opinião', 'https://www.spiked-online.com/feed/'),
    ('dailymail', 'Daily Mail (EN)', 'internacional', 'https://www.dailymail.co.uk/articles.rss'),
    ('washex', 'Washington Examiner (EN)', 'opinião', 'https://www.washingtonexaminer.com/feed'),
    ('gbnews', 'GB News (EN)', 'opinião', 'https://www.gbnews.com/feeds/politics.rss'),
]
CAT = {c[0]: c for c in CATALOG}
DEFAULT_SRC = ["rtp", "eco", "euronews", "bbc"]
CACHE = {}  # id -> (ts, items)
TTL = 15 * 60

def _slug(u): return re.sub(r"[^a-z0-9]", "", str(u).lower())
def _pf(u): return os.path.join(DIR, "news-%s.json" % _slug(u))
def prefs(u):
    try: p = json.load(open(_pf(u)))
    except (OSError, ValueError): p = {}
    p.setdefault("sources", DEFAULT_SRC); p.setdefault("topics", []); p.setdefault("muted", []); p.setdefault("critical_only", [])
    return p
def save_prefs(u, p):
    tmp = _pf(u) + ".tmp"; json.dump(p, open(tmp, "w"), ensure_ascii=False); os.chmod(tmp, 0o600); os.replace(tmp, _pf(u))

def _txt(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", s or ""))).strip()
def _tag(blk, name):
    m = re.search(r"(?is)<%s[^>]*>(.*?)</%s>" % (name, name), blk)
    if not m: return ""
    v = m.group(1).strip()
    c = re.match(r"(?s)<!\[CDATA\[(.*)\]\]>$", v)
    return c.group(1) if c else v

def _cd(t): return re.sub(r"^\s*<!\[CDATA\[\s*|\s*\]\]>\s*$", "", t or "")

def parse_feed(raw, src):
    out = []
    for blk in re.findall(r"(?is)<item[ >].*?</item>|<entry[ >].*?</entry>", raw)[:40]:
        title = _cd(_txt(_tag(blk, "title")))
        link = _tag(blk, "link").strip()
        if not link:
            m = re.search(r'(?i)<link[^>]+href="([^"]+)"', blk); link = m.group(1) if m else ""
        link = html.unescape(link)
        if not title or not re.match(r"https?://", link): continue
        desc = _tag(blk, "description") or _tag(blk, "summary") or _tag(blk, "content")
        ts = 0
        for k in ("pubDate", "published", "updated", "dc:date"):
            v = _tag(blk, k).strip()
            if v:
                try: ts = email.utils.parsedate_to_datetime(v).timestamp(); break
                except Exception:
                    try: ts = datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp(); break
                    except Exception: pass
        img = ""
        m = re.search(r'(?i)<(?:media:thumbnail|media:content|enclosure)[^>]+url="([^"]+)"', blk) or re.search(r'(?i)<img[^>]+src="([^"]+)"', desc or "")
        if m and re.match(r"https?://", html.unescape(m.group(1))): img = html.unescape(m.group(1))
        out.append({"src": src, "title": title[:200], "link": link, "desc": _cd(_txt(desc))[:260], "ts": ts or time.time(), "img": img})
    return out

def _decode_feed(raw):
    try: return raw.decode("utf-8")
    except UnicodeDecodeError: return raw.decode("cp1252", "replace")

def fetch_src(sid):
    now = time.time(); c = CACHE.get(sid)
    if c and now - c[0] < TTL: return c[1]
    try:
        rq = urllib.request.Request(CAT[sid][3], headers={"User-Agent": "Mozilla/5.0 (NewsReader)"})
        raw = _decode_feed(urllib.request.urlopen(rq, timeout=12).read(4_000_000))
        items = [] if "<!ENTITY" in raw else parse_feed(raw, sid)
    except Exception:
        items = c[1] if c else []
    CACHE[sid] = (now, items); return items

def _norm(t): return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", t.lower()))[:70]


_STANCE = {}
def _gkey():
    try: return [l.split("=", 1)[1].strip() for l in open(os.path.expanduser("~/.config/groq.env")) if l.startswith("GROQ_API_KEY=")][0]
    except Exception: return ""
def stance_filter(items, terms):
    """Para itens que mencionam os termos, mantem so os CRITICOS desses temas (IA classifica; sem classificacao => esconde)."""
    if not terms: return items
    rx = re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b", re.I)
    hit = [it for it in items if rx.search(it["title"] + " " + it["desc"])]
    todo = [it for it in hit if it["title"] not in _STANCE]
    key = _gkey()
    for i in range(0, len(todo), 25):
        chunk = todo[i:i + 25]
        if not key: break
        lines = "\n".join("%d. %s | %s" % (n, it["title"], it["desc"][:200]) for n, it in enumerate(chunk))
        prompt = ("Para cada noticia, indica a posicao do artigo sobre " + ", ".join(terms) + ": 'critico' (critica/opoe-se a esse movimento ou ideias), "
                  "'favoravel' (apoia/defende), ou 'neutro' (so informa, sem posicao ou nao e sobre isso). Responde so JSON: {\"r\":[\"critico\",...]} na mesma ordem.\n" + lines)
        for attempt in range(3):
            try:
                body = json.dumps({"model": "qwen/qwen3.8-27b", "messages": [{"role": "user", "content": prompt}], "temperature": 0,
                                   "response_format": {"type": "json_object"}}).encode()
                rq = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", body,
                    {"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "odysseus-news/1.0"})
                r = json.loads(json.loads(urllib.request.urlopen(rq, timeout=25).read())["choices"][0]["message"]["content"])["r"]
                for it, v in zip(chunk, r): _STANCE[it["title"]] = str(v).lower()
                break
            except Exception: time.sleep(2)
    out = []
    for it in items:
        if it in hit and _STANCE.get(it["title"]) != "critico": continue
        out.append(it)
    return out

def build(u, only=None):
    p = prefs(u); ids = [s for s in p["sources"] if s in CAT and (not only or s == only)]
    with ThreadPoolExecutor(8) as ex: lists = list(ex.map(fetch_src, ids))
    now = time.time(); seen, items = set(), []
    topics = [t.lower() for t in p["topics"]]; muted = [m.lower() for m in p["muted"]]
    for it in sum(lists, []):
        blob = (it["title"] + " " + it["desc"]).lower()
        if any(m in blob for m in muted): continue
        k = _norm(it["title"])
        if k in seen: continue
        seen.add(k)
        hits = [t for t in topics if t in blob]
        age_h = max(0, (now - it["ts"]) / 3600)
        it = dict(it, hits=hits, score=3 * len(hits) + max(0, 3 - age_h / 8))
        items.append(it)
    items = stance_filter(items, p.get("critical_only", []))
    items.sort(key=lambda x: -x["score"])
    return p, items

def ago(ts):
    m = int((time.time() - ts) / 60)
    return "agora" if m < 2 else f"há {m} min" if m < 90 else f"há {m // 60} h" if m < 2880 else f"há {m // 1440} d"

CSS = study.CSS + """<style>.nw{display:flex;gap:10px;margin:8px 0;padding:10px;background:#262a31;border-radius:12px}.nw img{width:84px;height:84px;object-fit:cover;border-radius:8px;flex:none}
.nw a.t{color:#e8eefc;font-weight:600;text-decoration:none;line-height:1.3}.nw a.t:hover{text-decoration:underline}.tg{background:#2f4a7a}.chk{display:inline-block;margin:3px 10px 3px 0}</style>"""

def nav_n(on):
    return CSS + "<div class='nav'>" + "".join(f"<a class='{'on' if k == on else ''}' href='{PFX}/news{q}'>{n}</a>" for k, n, q in
        (("feed", "Para ti", ""), ("set", "Fontes e temas", "?tab=set"))) + "</div>"

def news_page(u, query):
    tab = (query.get("tab") or [""])[0]
    if tab == "set":
        p = prefs(u); cats = {}
        for s in CATALOG: cats.setdefault(s[2], []).append(s)
        boxes = "".join(f"<h3 style='margin:12px 0 4px;text-transform:capitalize'>{E(c)}</h3>" + "".join(
            f"<label class='chk'><input type='checkbox' name='s' value='{s[0]}'{' checked' if s[0] in p['sources'] else ''}> {E(s[1])}</label>" for s in L) for c, L in cats.items())
        return (nav_n("set") + f"<h1>Fontes e temas</h1><p class='mut'>Escolhe as fontes que queres ler. O servidor não escolhe nem classifica as fontes por ideologia: cada pessoa monta o seu feed.</p>"
                f"<form method='post' action='{PFX}/news/save' class='card'>{boxes}<h3>Temas que te interessam</h3><p class='mut'>Uma palavra ou expressão por linha. As notícias que as contêm sobem no feed.</p>"
                f"<textarea name='topics' style='min-height:90px'>{E(chr(10).join(p['topics']))}</textarea><h3>Esconder notícias com…</h3><textarea name='muted' style='min-height:60px'>{E(chr(10).join(p['muted']))}</textarea><h3>Só mostrar se forem críticas a…</h3><p class='sub'>Notícias que mencionem estes temas só aparecem se o artigo for crítico (a IA classifica; se não conseguir, fica escondida).</p><textarea name='critical_only' style='min-height:60px'>{E(chr(10).join(p.get('critical_only', [])))}</textarea>"
                f"<p><button>Guardar</button></p></form>")
    only = (query.get("s") or [""])[0]
    p, items = build(u, only if only in CAT else None)
    chips = "".join(f"<a class='pill' style='text-decoration:none;color:#ccc{';background:#4a7bd0;color:#fff' if only == s else ''}' href='{PFX}/news?s={s}'>{E(CAT[s][1])}</a>" for s in p["sources"] if s in CAT)
    allc = f"<a class='pill' style='text-decoration:none;color:#ccc{';background:#4a7bd0;color:#fff' if not only else ''}' href='{PFX}/news'>Todas</a>"
    def card(it):
        img = f"<img src='{E(it['img'])}' loading='lazy' referrerpolicy='no-referrer' onerror='this.remove()'>" if it["img"] else ""
        tg = "".join(f"<span class='pill tg'>{E(t)}</span>" for t in it["hits"][:3])
        return (f"<div class='nw'>{img}<div><a class='t' href='{E(it['link'])}' target='_blank' rel='noopener noreferrer'>{E(it['title'])}</a>"
                f"<div class='mut'>{E(CAT[it['src']][1])} · {ago(it['ts'])} {tg}</div><div style='font-size:13px;color:#bbb;margin-top:3px'>{E(it['desc'])}</div></div></div>")
    mine = [i for i in items if i["hits"]][:15]; rest = [i for i in items if not i["hits"]][:45]
    body = nav_n("feed") + "<h1>Notícias</h1>"
    if not p["sources"]: body += "<p>Escolhe fontes em <a href='?tab=set'>Fontes e temas</a>.</p>"
    body += f"<div>{allc}{chips}</div><div class='card' style='margin:10px 0'><button type='button' onclick='dg(this)'>✨ Resumo do dia</button> <span class='mut'>resumo neutro das principais notícias das tuas fontes</span><div id='dg' class='pre' style='display:none;margin-top:8px'></div></div>"
    if mine: body += "<h2>Sobre os teus temas</h2>" + "".join(card(i) for i in mine)
    body += "<h2>Mais recentes</h2>" + ("".join(card(i) for i in rest) or "<p class='mut'>Sem notícias de momento (as fontes podem estar indisponíveis).</p>")
    body += (f"<script>async function dg(b){{b.disabled=true;const d=document.getElementById('dg');d.style.display='';d.textContent='A preparar…';"
             f"try{{const r=await (await fetch('{PFX}/news/digest',{{method:'POST',credentials:'same-origin',body:'{{}}'}})).json();d.textContent=r.text||r.error||'Erro.'}}catch(e){{d.textContent='Erro.'}}b.disabled=false}}</script>")
    return body

def news_save(u, f):
    p = prefs(u)
    p["sources"] = [s for s in f.get("s", []) if s in CAT]
    lines = lambda k: [x.strip()[:40] for x in re.split(r"[\n,]", f.get(k, [""])[0]) if x.strip()][:40]
    p["topics"], p["muted"] = lines("topics"), lines("muted"); p["critical_only"] = lines("critical_only")
    save_prefs(u, p)

def news_digest(u):
    p, items = build(u)
    top = [i for i in items if i["hits"]][:8] + [i for i in items if not i["hits"]][:14]
    if not top: return {"error": "Sem notícias de momento."}
    lst = "\n".join(f"- [{CAT[i['src']][1]}] {i['title']}. {i['desc'][:140]}" for i in top)
    txt = study.ai(study.PT + "Resume as notícias abaixo para o dia, em 6 a 8 tópicos curtos. Sê neutro e factual, atribui cada afirmação à fonte entre parênteses, "
                   "e quando fontes diferentes tratam o mesmo tema de formas diferentes, di-lo. Não acrescentes factos que não estejam na lista.", lst)
    return {"text": txt}

# ---------- Compor ----------
def compose_draft(j):
    kind = "whatsapp" if j.get("kind") == "whatsapp" else "email"
    tone = {"formal": "formal", "amigavel": "amigável e próximo"}.get(j.get("tone"), "claro e cordial")
    lang = {"pt": "português de Portugal", "en": "inglês", "fr": "francês", "es": "espanhol", "de": "alemão"}.get(j.get("lang"), "português de Portugal")
    what = str(j.get("text") or "").strip()[:2000]
    if not what: raise ValueError("escreve o que queres dizer")
    sysm = (f"Escreve {'um email' if kind == 'email' else 'uma mensagem de WhatsApp curta'} em {lang}, tom {tone}, a partir do pedido. Não inventes factos, datas ou valores: "
            "se faltar algo importante, usa [entre parênteses retos]. Sem assinatura com nome inventado. Devolve JSON: {\"subject\": \"assunto (vazio no WhatsApp)\", \"body\": \"texto\"}.")
    r = json.loads(study.ai(sysm, what, js=True))
    return {"subject": str(r.get("subject", ""))[:150] if kind == "email" else "", "body": str(r.get("body", ""))[:4000]}

COMPOSE = """<h1>Compor</h1><p class='mut'>Diz o que queres e eu escrevo o rascunho. Depois escolhes onde o enviar: abre já preenchido na tua app ou webmail, e és tu que carregas em enviar.</p>
<div class='card'><select id='k'><option value='email'>Email</option><option value='whatsapp'>WhatsApp</option></select>
<select id='tn'><option value=''>tom cordial</option><option value='formal'>formal</option><option value='amigavel'>amigável</option></select>
<select id='lg'><option value='pt'>português</option><option value='en'>inglês</option><option value='fr'>francês</option><option value='es'>espanhol</option><option value='de'>alemão</option></select>
<textarea id='tx' placeholder='ex: pedir ao hóspede do apartamento 3 que confirme a hora de chegada e lembrar o check-in a partir das 15h'></textarea>
<p><button onclick='go(this)'>Escrever rascunho</button> <span id='st' class='mut'></span></p></div>
<div id='out' class='card' style='display:none;margin-top:10px'><div id='sj'><input id='su' class='in' style='width:100%;box-sizing:border-box' placeholder='Assunto'></div>
<textarea id='bd' style='min-height:200px;margin-top:6px'></textarea>
<div id='acts' style='margin-top:8px;display:flex;gap:6px;flex-wrap:wrap'></div><div class='mut' id='note' style='margin-top:6px'></div></div>
<script>
const $=id=>document.getElementById(id);
function enc(s){return encodeURIComponent(s)}
function acts(){const k=$('k').value,su=$('su').value,bd=$('bd').value,a=[];
 const L=(t,h,c)=>a.push('<a class=\"pill\" style=\"padding:8px 14px;text-decoration:none;color:#fff;background:'+(c||'#3a5a8a')+'\" target=\"_blank\" rel=\"noopener\" href=\"'+h+'\">'+t+'</a>');
 if(k==='email'){L('Gmail','https://mail.google.com/mail/?view=cm&fs=1&su='+enc(su)+'&body='+enc(bd));
  L('Outlook','https://outlook.live.com/mail/0/deeplink/compose?subject='+enc(su)+'&body='+enc(bd));
  L('Outlook 365','https://outlook.office.com/mail/deeplink/compose?subject='+enc(su)+'&body='+enc(bd));
  L('Yahoo','https://compose.mail.yahoo.com/?subject='+enc(su)+'&body='+enc(bd));
  L('App de email (Proton, etc.)','mailto:?subject='+enc(su)+'&body='+enc(bd),'#555')}
 else{L('WhatsApp (escolher app e contacto)','https://wa.me/?text='+enc(bd),'#1f8f4e');L('Abrir direto na app','whatsapp://send?text='+enc(bd),'#2a6f45')}
 $('acts').innerHTML=a.join('')+'<button type=\"button\" class=\"xs\" style=\"padding:8px 14px\" onclick=\"cp()\">Copiar</button>'+(navigator.share?'<button type=\"button\" class=\"xs\" style=\"padding:8px 14px\" onclick=\"sh()\">Partilhar…</button>':'');}
async function cp(){const t=($('k').value==='email'&&$('su').value?$('su').value+'\\n\\n':'')+$('bd').value;try{await navigator.clipboard.writeText(t);$('note').textContent='Copiado.'}catch(e){$('bd').select();document.execCommand('copy');$('note').textContent='Copiado.'}}
function sh(){navigator.share({title:$('su').value,text:$('bd').value}).catch(()=>{})}
async function go(b){const t=$('tx').value.trim();if(!t){$('st').textContent='Escreve o que queres dizer.';return}
 b.disabled=true;$('st').textContent='A escrever…';
 try{const r=await (await fetch('"""+PFX+"""/compose/draft',{method:'POST',credentials:'same-origin',body:JSON.stringify({kind:$('k').value,tone:$('tn').value,lang:$('lg').value,text:t})})).json();
  if(r.error){$('st').textContent=r.error}else{$('out').style.display='';$('sj').style.display=$('k').value==='email'?'':'none';$('su').value=r.subject;$('bd').value=r.body;$('st').textContent='';acts();
   $('note').textContent=$('k').value==='email'?'Para o Proton, usa o botão da app de email (mailto) ou Copiar. O Proton não aceita rascunhos por link.':'No WhatsApp escolhes a conta (normal ou Business) e depois o contacto.'}}
 catch(e){$('st').textContent='Erro: tenta outra vez.'}b.disabled=false}
['su','bd','k'].forEach(i=>$(i).addEventListener('input',()=>{if($('out').style.display!=='none')acts()}));
</script>"""

# ---------- Voos ----------
def _ff(u): return os.path.join(DIR, "flights-%s.json" % _slug(u))
def flights(u):
    try: return json.load(open(_ff(u)))
    except (OSError, ValueError): return []
def save_flights(u, L):
    tmp = _ff(u) + ".tmp"; json.dump(L, open(tmp, "w"), ensure_ascii=False); os.chmod(tmp, 0o600); os.replace(tmp, _ff(u))
FN = re.compile(r"^[A-Z0-9]{2}\d{1,4}[A-Z]?$")

def flight_links(n, d=""):
    low = n.lower()
    return [("Flightradar24", f"https://www.flightradar24.com/data/flights/{low}"),
            ("FlightAware", f"https://www.flightaware.com/live/flight/{n}"),
            ("Google", "https://www.google.com/search?q=" + urllib.parse.quote(f"{n} flight status {d}".strip()))]

def flight_page(u, msg=""):
    L = sorted(flights(u), key=lambda f: (f.get("date", ""), f.get("n", "")))
    today = datetime.date.today().isoformat()
    rows = ""
    for i, f in enumerate(L):
        past = f.get("date", "9999") < today
        lk = " · ".join(f"<a href='{E(h)}' target='_blank' rel='noopener noreferrer' style='color:#9bc'>{E(n)}</a>" for n, h in flight_links(f["n"], f.get("date", "")))
        rows += (f"<div class='card' style='margin:6px 0;{'opacity:.55' if past else ''}'><b style='font-size:18px'>{E(f['n'])}</b> <span class='mut'>{E(f.get('date', ''))}</span> {E(f.get('note', ''))}<br>{lk}{_flight_status_html(u, f, i)}"
                 f"<form method='post' action='{PFX}/flight/del' style='display:inline;float:right'><input type='hidden' name='i' value='{i}'><button class='xs' style='background:#6a3a3a;color:#fff;border:0;border-radius:6px'>apagar</button></form></div>")
    return (study.CSS + f"<h1>Voos</h1><p class='mut'>Guarda os voos (os teus ou dos hóspedes) e abre o estado em tempo real no Flightradar24. O estado em tempo real vem do Flightradar24{(' e, com a AirLabs, o estado e os atrasos aparecem aqui (consultas este mês: ' + str(airlabs.usage(DIR)) + ' de ' + str(airlabs.MONTH_CAP) + ')') if airlabs.configured() else ''}.</p>{('<p>' + E(msg) + '</p>') if msg else ''}"
            f"<form method='get' action='{PFX}/flight' class='card'><b>Ver um voo agora</b> <input class='in' name='q' placeholder='ex: TP1234' style='text-transform:uppercase;width:120px'><button>Abrir</button></form>"
            f"<form method='post' action='{PFX}/flight/add' class='card' style='margin-top:10px'><b>Guardar voo</b><br><input class='in' name='n' placeholder='Voo: TP1234' required style='text-transform:uppercase;width:120px'> "
            f"<input type='date' name='date'> <input class='in' name='note' placeholder='Hóspede / nota (ex: Apt 3, chega 22:10)' style='min-width:220px'> <button>Guardar</button></form>"
            f"<h2>Voos guardados</h2>{rows or '<p class=mut>Nenhum voo guardado.</p>'}")

def _flight_status_html(u, f, i):
    if not airlabs.configured(): return ""
    info, t = airlabs.cached_info(DIR, f["n"], f.get("date", ""))
    line = (E(airlabs.describe(info)) + f" <span class='mut'>(atualizado {time.strftime('%H:%M', time.localtime(t))})</span>") if info else "<span class='mut'>Sem estado ainda.</span>"
    btn = "" if f.get("date", "9999") < datetime.date.today().isoformat() else (f"<form method='post' action='{PFX}/flight/status' style='display:inline;margin-left:8px'><input type='hidden' name='i' value='{i}'><button class='xs'>Atualizar estado</button></form>")
    return f"<div style='margin-top:6px;font-size:13px;color:#cfd6e4'>{line}{btn}</div>"

def flight_refresh(u, f):
    L = sorted(flights(u), key=lambda x: (x.get("date", ""), x.get("n", "")))
    try: fl = L[int(f.get("i", ["-1"])[0])]
    except (ValueError, IndexError): return "Voo não encontrado."
    r = airlabs.lookup(DIR, fl["n"], fl.get("date", ""))
    return r["error"] if not r["ok"] else ("Estado de %s (guardado há pouco, sem gastar consulta)." % fl["n"] if r["cached"] else "Estado de %s atualizado." % fl["n"])

def flight_add(u, f):
    n = re.sub(r"\s", "", f.get("n", [""])[0]).upper()
    if not FN.match(n): return "Número de voo inválido (ex: TP1234)."
    d = f.get("date", [""])[0]
    try: d = datetime.date.fromisoformat(d).isoformat() if d else ""
    except ValueError: return "Data inválida."
    L = flights(u); L.append({"n": n, "date": d, "note": f.get("note", [""])[0].strip()[:100]}); save_flights(u, L[-60:]); return ""

def flight_del(u, f):
    L = flights(u)
    try: del L[int(f.get("i", ["-1"])[0])]
    except (ValueError, IndexError): return
    save_flights(u, L)

# ---------- Emails (ligar contas ao Odysseus da propria pessoa, sem passar palavras-passe pelo chat) ----------
ODY = "http://127.0.0.1:7860"
PRESETS = {  # dominio -> (imap, porta, smtp, porta, seguranca)
    "gmail.com": ("imap.gmail.com", 993, "smtp.gmail.com", 465, "ssl"),
    "googlemail.com": ("imap.gmail.com", 993, "smtp.gmail.com", 465, "ssl"),
    "outlook.com": ("outlook.office365.com", 993, "smtp.office365.com", 587, "starttls"),
    "hotmail.com": ("outlook.office365.com", 993, "smtp.office365.com", 587, "starttls"),
    "live.com": ("outlook.office365.com", 993, "smtp.office365.com", 587, "starttls"),
    "yahoo.com": ("imap.mail.yahoo.com", 993, "smtp.mail.yahoo.com", 465, "ssl"),
    "icloud.com": ("imap.mail.me.com", 993, "smtp.mail.me.com", 587, "starttls"),
}

def _ody(cookie, method, path, body=None):
    rq = urllib.request.Request(ODY + path, None if body is None else json.dumps(body).encode(), {"Cookie": cookie, "Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(rq, timeout=60) as r: return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read().decode())
        except Exception: return {"ok": False, "error": "HTTP %s" % e.code}

def emails_page(cookie, suggest=()):
    acc = _ody(cookie, "GET", "/api/email/accounts").get("accounts", [])
    rows = "".join(f"<div class='card' style='margin:6px 0'><b>{E(a.get('name') or a.get('imap_user') or '')}</b> <span class='mut'>{E(a.get('imap_user') or '')}</span>"
                   f"<button class='xs' style='float:right;background:#6a3a3a;color:#fff;border:0;border-radius:6px' onclick=\"del('{E(a['id'])}')\">remover</button></div>" for a in acc)
    sug = "".join(f"<option value='{E(x)}'>" for x in suggest)
    return (study.CSS + f"""<h1>Emails</h1><p class='mut'>Liga as tuas contas ao Odysseus para ler e escrever emails aqui. A palavra-passe vai direta para o teu perfil e não passa pelo chat.</p>
<h2>Contas ligadas</h2>{rows or "<p class='mut'>Nenhuma conta ligada.</p>"}
<h2>Ligar uma conta</h2><div class='card'>
<input id='em' class='in' list='sg' placeholder='email' style='width:100%;box-sizing:border-box' autocomplete='off'><datalist id='sg'>{sug}</datalist>
<input id='pw' class='in' type='password' placeholder='palavra-passe de aplicação' style='width:100%;box-sizing:border-box;margin-top:6px' autocomplete='new-password'>
<details style='margin-top:6px'><summary class='mut'>Como obter a palavra-passe de aplicação (Gmail)</summary><div class='mut' style='line-height:1.6'>1. A conta tem de ter a <b>verificação em dois passos</b> ativa.<br>
2. Abre <a href='https://myaccount.google.com/apppasswords' target='_blank' rel='noopener' style='color:#9bc'>myaccount.google.com/apppasswords</a>, escreve um nome (ex: Odysseus) e cria.<br>3. Copia as 16 letras (sem espaços) e cola acima.</div></details>
<details style='margin-top:6px'><summary class='mut'>Outro fornecedor ou avançado</summary><input id='ih' class='in' placeholder='servidor IMAP (opcional)' style='width:100%;box-sizing:border-box;margin-top:4px'><input id='sh' class='in' placeholder='servidor SMTP (opcional)' style='width:100%;box-sizing:border-box;margin-top:4px'></details>
<p><button onclick='add(this)'>Testar e ligar</button> <span id='st'></span></p></div>
<script>
const $=i=>document.getElementById(i);
async function add(b){{const em=$('em').value.trim(),pw=$('pw').value.replace(/\\s/g,'');if(!em||!pw){{$('st').textContent='Preenche o email e a palavra-passe.';return}}
 b.disabled=true;$('st').textContent='A testar a ligação…';
 try{{const r=await (await fetch('{PFX}/emails/add',{{method:'POST',credentials:'same-origin',body:JSON.stringify({{email:em,password:pw,imap:$('ih').value.trim(),smtp:$('sh').value.trim()}})}})).json();
  $('st').textContent=r.ok?'Ligada!':(r.error||'Erro.');if(r.ok)setTimeout(()=>location.reload(),900)}}catch(e){{$('st').textContent='Erro de rede.'}}b.disabled=false}}
async function del(id){{if(!confirm('Remover esta conta do Odysseus?'))return;await fetch('{PFX}/emails/del',{{method:'POST',credentials:'same-origin',body:JSON.stringify({{id:id}})}});location.reload()}}
</script>""")

def emails_add(cookie, j):
    em = str(j.get("email") or "").strip().lower(); pw = str(j.get("password") or "")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", em): return {"ok": False, "error": "Email inválido."}
    if len(pw) < 6: return {"ok": False, "error": "Palavra-passe inválida."}
    dom = em.split("@")[1]; p = PRESETS.get(dom)
    ih, sh = str(j.get("imap") or "").strip(), str(j.get("smtp") or "").strip()
    if ih or sh:
        if not (ih and sh) or not re.match(r"^[a-z0-9.-]+$", ih + sh): return {"ok": False, "error": "Indica o IMAP e o SMTP (ex: imap.exemplo.com)."}
        p = (ih, 993, sh, 465, "ssl")
    if not p: return {"ok": False, "error": "Fornecedor desconhecido: abre 'Outro fornecedor' e indica os servidores IMAP e SMTP."}
    cfg = {"imap_host": p[0], "imap_port": p[1], "imap_user": em, "imap_password": pw, "smtp_host": p[2], "smtp_port": p[3], "smtp_security": p[4], "smtp_user": em, "smtp_password": pw}
    t = _ody(cookie, "POST", "/api/email/accounts/test", cfg)
    if not (t.get("imap") or {}).get("ok"):
        err = str((t.get("imap") or {}).get("error") or t.get("error") or "")
        hint = ""
        if "AUTHENTICATIONFAILED" in err or "Invalid credentials" in err or "authentication" in err.lower():
            hint = " Confirma que usaste uma palavra-passe de APLICAÇÃO (não a normal) e que a verificação em dois passos está ativa." if dom in ("gmail.com", "googlemail.com") else " A palavra-passe foi recusada; contas da escola/Microsoft podem bloquear apps externas."
        return {"ok": False, "error": "Não consegui ligar ao IMAP: " + err[:120] + hint}
    smtp_ok = bool((t.get("smtp") or {}).get("ok"))
    r = _ody(cookie, "POST", "/api/email/accounts", dict(cfg, name=em, from_address=em, display_name="", imap_starttls=False))
    if not r.get("ok"): return {"ok": False, "error": "Não consegui guardar: " + str(r.get("error") or r)[:100]}
    return {"ok": True, "smtp": smtp_ok}

def emails_del(cookie, j):
    i = re.sub(r"[^a-z0-9]", "", str(j.get("id") or "").lower())
    return _ody(cookie, "DELETE", "/api/email/accounts/" + i) if i else {"ok": False}


# ---- preferencias das abas (Tools) por utilizador: ordem e abas escondidas (PC e app partilham) ----
import json as _j, os as _o, re as _re
def prefs_file(base): return _o.path.join(base, "tools-prefs.json")
def prefs_get(base, u):
    try: d = _j.load(open(prefs_file(base), encoding="utf-8"))
    except Exception: d = {}
    p = d.get(u) or {}
    return {"order": p.get("order") or [], "hidden": p.get("hidden") or {}}
def prefs_set(base, u, body):
    ok = _re.compile(r"^tool-[a-z0-9-]{1,40}$")
    order = [x for x in (body.get("order") or []) if isinstance(x, str) and ok.match(x)][:80]
    hidden = {k: 1 for k in (body.get("hidden") or {}) if isinstance(k, str) and ok.match(k)}
    try: d = _j.load(open(prefs_file(base), encoding="utf-8"))
    except Exception: d = {}
    d[u] = {"order": order, "hidden": hidden}
    t = prefs_file(base) + ".tmp"
    with open(t, "w", encoding="utf-8") as f: _j.dump(d, f)
    _o.chmod(t, 0o600); _o.replace(t, prefs_file(base))
    return {"ok": True, "order": order, "hidden": hidden}

# ---------- Prompts (gerador de prompts em ingles) ----------
PROMPT_KINDS = {
    "chat": "a prompt for a general AI assistant (ChatGPT, Claude, Gemini). Structure it with: role, context, task, constraints, output format. Use clear sections.",
    "image": "a prompt for an image generator (Stable Diffusion XL / Midjourney / Gemini). One dense descriptive paragraph: subject, setting, composition, lighting, style, camera/lens, colour palette, quality tags. Also give a negative prompt.",
    "code": "a prompt for an AI coding assistant (Claude Code, Copilot, Cursor). Include: goal, tech stack, files or inputs, requirements, edge cases, acceptance criteria, what NOT to change.",
    "video": "a prompt for an AI video generator (Veo, Sora, Runway). Describe: subject, action over time, camera movement, shot type, setting, lighting, mood, duration and style.",
    "system": "a system prompt for a custom AI agent or GPT. Include: identity, goals, tone, rules, what to refuse, tools usage, output format, and 2 short example exchanges.",
    "music": "a prompt for an AI music generator (Suno, Udio). Include: genre, mood, tempo/BPM, instruments, vocal style, song structure, and lyrics themes.",
}

def _bridge_key():
    from kitconfig import secret_file
    try:
        for l in open(secret_file("bridge")):
            for k in ("BRIDGE_API_KEY=", "API_KEY=", "BRIDGE_TOKEN="):
                if l.startswith(k): return l.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return ""

def _haiku(system, user, timeout=60):
    msg = (system + "\nDo not use any tools. Answer directly with the JSON only.\n\nUSER REQUEST:\n<<<\n" + user + "\n>>>")
    body = {"model": "claude-code-haiku", "messages": [{"role": "user", "content": msg}]}
    rq = urllib.request.Request("http://127.0.0.1:8787/v1/chat/completions", json.dumps(body).encode(),
                                {"Content-Type": "application/json", "Authorization": "Bearer " + _bridge_key()})
    out = json.load(urllib.request.urlopen(rq, timeout=timeout))["choices"][0]["message"]["content"]
    return out[out.find("{"): out.rfind("}") + 1]

def prompt_gen(j):
    what = str(j.get("text") or "").strip()[:3000]
    if not what: raise ValueError("escreve o que queres")
    kind = j.get("kind") if j.get("kind") in PROMPT_KINDS else "chat"
    detail = "concise (under 120 words)" if j.get("detail") == "short" else "detailed and thorough"
    sysm = ("You are an expert prompt engineer. The user describes, usually in Portuguese, what they want an AI to do. "
            f"Write {PROMPT_KINDS[kind]} The prompt must be in English, {detail}, ready to copy and paste, and must not invent personal facts; "
            "use [placeholders in brackets] for details the user did not give. "
            "Then judge what IMPORTANT information is missing for a good result (audience, goal, format, length, style, platform, key facts...). "
            "Only list things that really change the result; if nothing important is missing, return an empty list. "
            "Reply ONLY with JSON: {\"prompt\": \"the English prompt\", \"negative\": \"negative prompt (only for image/video, else empty)\", "
            "\"missing\": [\"short question in European Portuguese about each important missing detail (max 5)\"], "
            "\"tips\": \"1 short tip in European Portuguese\"}.")
    engine = "Groq"
    try:
        r = json.loads(study.ai(sysm, what, js=True))
    except Exception:
        engine = "Claude Haiku (reserva)"
        r = json.loads(_haiku(sysm, what))
    miss = [str(x).strip()[:200] for x in (r.get("missing") or []) if str(x).strip()][:5]
    return {"prompt": str(r.get("prompt", "")).strip()[:6000], "negative": str(r.get("negative", "")).strip()[:1500] if kind in ("image", "video") else "",
            "missing": miss, "tips": str(r.get("tips", "")).strip()[:500], "engine": engine}

PROMPT = """<h1>Prompts</h1><p class='mut'>Diz o que queres, em português, e eu escrevo um prompt em inglês pronto a colar no ChatGPT, Claude, Gemini, gerador de imagens, vídeo ou música.</p>
<div class='card'><select id='k'><option value='chat'>Assistente (ChatGPT/Claude/Gemini)</option><option value='image'>Imagem</option><option value='code'>Código</option>
<option value='video'>Vídeo</option><option value='music'>Música</option><option value='system'>Agente / system prompt</option></select>
<select id='dt'><option value=''>detalhado</option><option value='short'>curto</option></select>
<textarea id='tx' placeholder='ex: uma imagem de um gato astronauta em Lisboa ao pôr do sol, estilo aguarela'></textarea>
<p><button onclick='go(this)'>Gerar prompt</button> <span id='st' class='mut'></span></p></div>
<div id='out' class='card' style='display:none;margin-top:10px'><b>Prompt</b><textarea id='pr' style='min-height:200px;margin-top:6px'></textarea>
<p><button type='button' onclick='cp("pr",this)'>Copiar</button> <button type='button' onclick='sh()'>Partilhar</button></p>
<div id='ngw' style='display:none'><b>Negative prompt</b><textarea id='ng' style='min-height:70px;margin-top:6px'></textarea><p><button type='button' onclick='cp("ng",this)'>Copiar</button></p></div>
<div id='ms' style='display:none;margin-top:8px;padding:8px 10px;border-left:3px solid #d9a441;background:rgba(217,164,65,.08)'><b>⚠ Falta informação importante</b><ul id='msl' style='margin:6px 0 4px 18px;padding:0'></ul><span class='mut'>Acrescenta estes detalhes ao pedido e gera outra vez, ou preenche os [campos] no prompt.</span></div>
<div class='mut' id='tp'></div></div>
<div id='hw' style='margin-top:14px'></div>
<script>
const $=id=>document.getElementById(id);const HK='kit-prompt-hist';
function hist(){try{return JSON.parse(localStorage.getItem(HK)||'[]')}catch(e){return[]}}
function drawH(){const h=hist();$('hw').innerHTML=h.length?'<h2>Recentes</h2>':'';h.forEach((x,i)=>{const d=document.createElement('div');d.className='card';d.style.margin='6px 0';d.style.cursor='pointer';
d.textContent=x.q.slice(0,90);d.title='abrir';d.onclick=()=>show(x.r,x.k);$('hw').appendChild(d)})}
function show(r,k){$('out').style.display='';$('pr').value=r.prompt||'';$('ng').value=r.negative||'';$('ngw').style.display=r.negative?'':'none';const m=r.missing||[];$('ms').style.display=m.length?'':'none';$('msl').innerHTML='';m.forEach(q=>{const li=document.createElement('li');li.textContent=q;$('msl').appendChild(li)});$('tp').textContent=(r.tips?('Dica: '+r.tips+' '):'')+(r.engine?('· '+r.engine):'')}
async function go(b){const t=$('tx').value.trim();if(!t){$('st').textContent='Escreve o que queres.';return}b.disabled=true;$('st').textContent='A escrever…';
try{const r=await (await fetch('/finance/prompt/gen',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,kind:$('k').value,detail:$('dt').value})})).json();
if(r.error){$('st').textContent=r.error}else{$('st').textContent='';show(r,$('k').value);const h=hist();h.unshift({q:t,k:$('k').value,r:r});localStorage.setItem(HK,JSON.stringify(h.slice(0,12)));drawH()}}
catch(e){$('st').textContent='Erro. Tenta outra vez.'}b.disabled=false}
async function cp(id,b){const v=$(id).value;try{await navigator.clipboard.writeText(v)}catch(e){$(id).select();document.execCommand('copy')}const o=b.textContent;b.textContent='Copiado ✓';setTimeout(()=>b.textContent=o,1500)}
function sh(){const v=$('pr').value;try{if(window.parent&&window.parent.OdysseusNative&&window.parent.OdysseusNative.shareText){window.parent.OdysseusNative.shareText('Prompt',v);return}}catch(e){}
if(navigator.share)navigator.share({text:v}).catch(()=>{});else cp('pr',document.querySelector('[onclick="sh()"]'))}
drawH();
</script>"""
