"""Foco (ADHD/autismo): uma coisa agora, temporizador, lista curta, despejo de ideias, barra do dia. Dados por conta."""
import os, json, re, time, uuid, html
HERE = os.path.dirname(os.path.abspath(__file__))
E = html.escape


def T(lang, pt, en): return en if lang == "en" else pt


def _p(u): return os.path.join(HERE, "focus-%s.json" % re.sub(r"[^a-z0-9_-]", "", str(u).lower()))


def load(u):
    try: d = json.load(open(_p(u)))
    except (OSError, ValueError): d = {}
    d.setdefault("now", ""); d.setdefault("tasks", []); d.setdefault("dump", [])
    return d


def save(u, d):
    p = _p(u); tmp = p + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def post(u, path, f, inbox_ok=False):
    d = load(u); a = path.rstrip("/").split("/")[-1]; i = (f.get("id") or "")[:12]; t = (f.get("t") or "").strip()[:200]
    if a == "add" and t and len(d["tasks"]) < 100: d["tasks"].append({"id": uuid.uuid4().hex[:8], "t": t})
    elif a == "now":
        tk = next((x for x in d["tasks"] if x["id"] == i), None)
        if tk: d["now"] = tk["t"]
        elif t: d["now"] = t
    elif a == "done":
        if i == "now": d["now"] = ""
        else:
            tk = next((x for x in d["tasks"] if x["id"] == i), None)
            if tk:
                d["tasks"].remove(tk)
                if d["now"] == tk["t"]: d["now"] = ""
        d["done_today"] = d.get("done_today", 0) + 1 if d.get("done_day") == time.strftime("%Y-%m-%d") else 1
        d["done_day"] = time.strftime("%Y-%m-%d")
    elif a == "del": d["tasks"] = [x for x in d["tasks"] if x["id"] != i]
    elif a == "dump" and t and len(d["dump"]) < 300: d["dump"].insert(0, {"id": uuid.uuid4().hex[:8], "t": t, "ts": int(time.time())})
    elif a == "dumpdel": d["dump"] = [x for x in d["dump"] if x["id"] != i]
    elif a == "dumptask":
        x = next((x for x in d["dump"] if x["id"] == i), None)
        if x and len(d["tasks"]) < 100:
            d["tasks"].append({"id": uuid.uuid4().hex[:8], "t": x["t"][:200]}); d["dump"].remove(x)
    elif a == "inboxnow" and inbox_ok:
        import inbox
        it = next((x for x in inbox._load()["items"] if x.get("id") == i and not x.get("done")), None)
        if it: d["now"] = it["title"][:200]
    elif a == "dumpinbox" and inbox_ok:
        import inbox
        x = next((x for x in d["dump"] if x["id"] == i), None)
        if x:
            ib = inbox._load()
            ib["items"].append({"id": uuid.uuid4().hex[:12], "ts": time.time(), "author": u, "title": x["t"][:90], "category": "ideia",
                                "priority": "média", "details": x["t"], "images": [], "done": False})
            inbox._save(ib); d["dump"].remove(x)
    else: return ""
    save(u, d); return ""


def render(u, lang, inbox_ok=False):
    d = load(u); L = lambda pt, en: E(T(lang, pt, en))
    done = d.get("done_today", 0) if d.get("done_day") == time.strftime("%Y-%m-%d") else 0
    now = (f'<div class="now">{E(d["now"])}</div><form method="post" action="/finance/focus/done"><input type="hidden" name="id" value="now">'
           f'<button class="big">✔ {L("Feito", "Done")}</button></form>') if d["now"] else f'<div class="now dim">{L("Nada escolhido. Escolhe uma coisa pequena da lista.", "Nothing chosen. Pick one small thing from the list.")}</div>'
    tasks = "".join(f'<li><span>{E(x["t"])}</span><form method="post" action="/finance/focus/now"><input type="hidden" name="id" value="{x["id"]}"><button title="{L("Fazer agora", "Do now")}">▶</button></form>'
                    f'<form method="post" action="/finance/focus/del"><input type="hidden" name="id" value="{x["id"]}"><button class="g" title="{L("Apagar", "Delete")}">✕</button></form></li>' for x in d["tasks"])
    dump = "".join(f'<li><span>{E(x["t"])}</span><form method="post" action="/finance/focus/dumptask"><input type="hidden" name="id" value="{x["id"]}"><button title="{L("Passar para a lista", "Move to list")}">＋</button></form>'
                   + (f'<form method="post" action="/finance/focus/dumpinbox"><input type="hidden" name="id" value="{x["id"]}"><button class="g" title="{L("Enviar para a Caixa de ideias", "Send to Ideas box")}">📥</button></form>' if inbox_ok else "") +
                   f'<form method="post" action="/finance/focus/dumpdel"><input type="hidden" name="id" value="{x["id"]}"><button class="g" title="{L("Apagar", "Delete")}">✕</button></form></li>' for x in d["dump"][:30])
    ibx = ""
    if inbox_ok:
        import inbox
        pend = [x for x in inbox._load()["items"] if not x.get("done")][:8]
        ibx = (f'<h2>📥 {L("Da Caixa de ideias", "From the Ideas box")}</h2><ul>' + "".join(
            f'<li><span>{E(x["title"])}</span><form method="post" action="/finance/focus/inboxnow"><input type="hidden" name="id" value="{E(x["id"])}">'
            f'<button class="g" title="{L("Fazer agora", "Do now")}">▶</button></form></li>' for x in pend) + "</ul>") if pend else ""
    return f"""<style>.fo{{max-width:560px;margin:auto}}.now{{font-size:1.6em;font-weight:600;text-align:center;padding:22px 12px;background:#262a31;border-radius:14px;margin:8px 0}}
.now.dim{{font-size:1em;font-weight:400;color:#9aa3b2}}.big{{display:block;width:100%;padding:14px;font-size:1.1em}}.fo ul{{list-style:none;padding:0}}.fo li{{display:flex;gap:6px;align-items:center;padding:6px 0;border-bottom:1px solid #333}}
.fo li span{{flex:1;word-break:break-word}}.fo li form{{margin:0}}.g{{background:#3a3f48}}.tm{{text-align:center;font-size:2.4em;font-variant-numeric:tabular-nums;margin:6px 0}}
.bar{{height:10px;background:#2a2e36;border-radius:6px;overflow:hidden}}.bar i{{display:block;height:100%;background:#4a7bd0;width:0}}.row{{display:flex;gap:4px;justify-content:center;flex-wrap:wrap}}
.fo input[type=text]{{flex:1;min-width:0}}.add{{display:flex}}small.d{{color:#7d8594}}</style>
<div class="fo"><h1>🎯 {L("Foco", "Focus")}</h1>
<h2>{L("Uma coisa agora", "One thing now")}</h2>{now}
<div class="box"><div class="tm" id="tm">25:00</div><div class="row"><button class="g" data-m="10">10</button><button class="g" data-m="25">25</button><button class="g" data-m="45">45</button>
<button id="st">{L("Começar", "Start")}</button><button class="g" id="sp">{L("Parar", "Stop")}</button></div><small class="d" id="tmn"></small></div>
<small class="d">{L("Hoje feito", "Done today")}: {done}</small>
<h2>{L("Lista curta", "Short list")}</h2><form class="add" method="post" action="/finance/focus/add"><input type="text" name="t" maxlength="200" placeholder="{L("Tarefa pequena...", "Small task...")}" required><button>＋</button></form><ul>{tasks}</ul>
<h2>🧠 {L("Despejo de ideias", "Brain dump")}</h2><small class="d">{L("Escreve já o que te vem à cabeça e volta ao que estavas a fazer.", "Write down what pops up and get back to what you were doing.")}</small>
<form class="add" method="post" action="/finance/focus/dump"><input type="text" name="t" maxlength="200" placeholder="..." required><button>＋</button></form><ul>{dump}</ul>
{ibx}<h2>{L("O teu dia", "Your day")}</h2><div class="bar"><i id="dy"></i></div><small class="d" id="dyt"></small></div>
<script>(function(){{var K='focusEnd',tm=document.getElementById('tm'),n=document.getElementById('tmn'),mins=25,iv;
var pt={1 if lang!='en' else 0};
function f(s){{s=Math.max(0,s);return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}}
function tick(){{var e=+localStorage.getItem(K)||0;if(!e){{tm.textContent=f(mins*60);return}}var s=Math.round((e-Date.now())/1000);tm.textContent=f(s);
if(s<=0){{clearInterval(iv);localStorage.removeItem(K);n.textContent=pt?'Tempo! Faz uma pausa curta.':'Time! Take a short break.';try{{var c=new AudioContext(),o=c.createOscillator(),g=c.createGain();o.connect(g);g.connect(c.destination);g.gain.value=.05;o.frequency.value=440;o.start();o.stop(c.currentTime+.4)}}catch(x){{}}}}}}
document.querySelectorAll('[data-m]').forEach(function(b){{b.onclick=function(){{mins=+b.dataset.m;localStorage.removeItem(K);clearInterval(iv);tick()}}}});
document.getElementById('st').onclick=function(){{localStorage.setItem(K,Date.now()+mins*60000);n.textContent='';clearInterval(iv);iv=setInterval(tick,1000);tick()}};
document.getElementById('sp').onclick=function(){{localStorage.removeItem(K);clearInterval(iv);n.textContent='';tick()}};
if(localStorage.getItem(K)){{iv=setInterval(tick,1000)}};tick();
var h=new Date(),m=h.getHours()*60+h.getMinutes(),a=420,b=1380,p=Math.min(100,Math.max(0,(m-a)/(b-a)*100));document.getElementById('dy').style.width=p+'%';
var l=b-m;document.getElementById('dyt').textContent=l>0?(pt?'Faltam ':'')+Math.floor(l/60)+'h'+String(l%60).padStart(2,'0')+(pt?' até às 23:00':' left until 23:00'):(pt?'O dia acabou. Descansa.':'The day is over. Rest.')}})();</script>"""
