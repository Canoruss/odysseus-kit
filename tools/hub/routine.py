"""Rotina de estudo/trabalho: metas, planeador anti-burnout e sincronização com o Canvas LMS. Dados por utilizador."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import datetime, html, json, os, re, threading, urllib.request, urllib.parse
DIR = os.path.dirname(os.path.abspath(__file__))
LOCK = threading.Lock()
WD = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
DEFAULT = {"items": [], "avail": [120, 120, 120, 120, 120, 180, 0], "block": 50, "daycap": 240, "canvas": {}}

def _f(user): return os.path.join(DIR, "routine-%s.json" % re.sub(r"[^a-z0-9]", "", user))
def load(user):
    try: d = json.load(open(_f(user)))
    except Exception: d = {}
    for k, v in DEFAULT.items(): d.setdefault(k, json.loads(json.dumps(v)))
    return d
def save(user, d):
    tmp = _f(user) + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600); os.replace(tmp, _f(user))

def _date(s):
    try: return datetime.date.fromisoformat(s)
    except Exception: return None

def schedule(d, today=None, days=14):
    """Distribui o trabalho em blocos nos próximos dias, respeitando horas/dia, bloco máximo e pausas.
    Devolve (dias, avisos). Dias de 0 minutos (descanso) ficam vazios. Itens semanais/mensais repetem-se."""
    today = today or datetime.date.today()
    block = max(15, int(d["block"])); cap = max(30, int(d["daycap"]))
    jobs = []
    for it in d["items"]:
        if it.get("done"): continue
        rem = max(0, int(it["minutes"]) - int(it.get("spent", 0)))
        dl = _date(it.get("deadline") or "")
        rep = it.get("repeat", "")
        if rep in ("semanal", "mensal") and rem > 0:
            # meta recorrente: horas por semana/mês, gera uma ocorrência por período no horizonte
            step = 7 if rep == "semanal" else 30
            for k in range(0, days, step):
                jobs.append({"title": it["title"], "type": it.get("type", ""), "left": rem, "dl": today + datetime.timedelta(days=min(days - 1, k + step - 1)), "start": today + datetime.timedelta(days=k), "pri": it.get("priority", 2)})
        elif rem > 0:
            jobs.append({"title": it["title"], "type": it.get("type", ""), "left": rem, "dl": dl, "start": today, "pri": it.get("priority", 2)})
    plan = []; warns = []
    horizon = [today + datetime.timedelta(days=i) for i in range(days)]
    for day in horizon:
        avail = min(cap, int(d["avail"][day.weekday()]))
        avail = int(avail * 0.85)  # 15% de folga para imprevistos
        blocks = []
        live = [j for j in jobs if j["left"] > 0 and j["start"] <= day]
        live.sort(key=lambda j: ((j["dl"] or datetime.date.max) - day, j["pri"]))
        # urgência: quanto menos dias restam face ao trabalho em falta, mais cedo entra
        while avail >= 15 and live:
            progressed = False
            for j in list(live):
                if avail < 15: break
                dl = j["dl"]
                if dl and dl < day: continue
                left_days = max(1, (dl - day).days + 1) if dl else 99
                share = j["left"] / left_days if dl else min(j["left"], block)
                want = min(j["left"], block, max(15, int(round(share / 5.0)) * 5), avail)
                if want < 15 and j["left"] >= 15: continue
                blocks.append({"title": j["title"], "type": j["type"], "min": int(want)})
                j["left"] -= want; avail -= want; progressed = True
                if j["left"] <= 0: live.remove(j)
            if not progressed: break
        plan.append({"date": day, "blocks": blocks})
    for j in jobs:
        if j["left"] > 0:
            if j["dl"] and j["dl"] <= horizon[-1]:
                warns.append(f"«{j['title']}»: faltam {j['left']//60}h{j['left']%60:02d} que não cabem até {j['dl'].isoformat()}. Aumenta as horas livres, adia o prazo ou reduz a tarefa.")
            else:
                warns.append(f"«{j['title']}»: ainda faltam {j['left']//60}h{j['left']%60:02d} depois dos próximos {days} dias.")
    return plan, warns

def _api(base, token, path):
    r = urllib.request.Request(base.rstrip("/") + path, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(r, timeout=30) as x:
        link = x.headers.get("Link", ""); return json.loads(x.read()), link

def canvas_sync(d):
    cv = d.get("canvas") or {}
    base, token = cv.get("url", ""), cv.get("token", "")
    if not base or not token: return "Indica o endereço do Canvas e o token."
    courses, _ = _api(base, token, "/api/v1/courses?enrollment_state=active&per_page=50")
    n = 0; known = {it.get("canvas_id") for it in d["items"] if it.get("canvas_id")}
    now = datetime.datetime.now(datetime.timezone.utc)
    for c in courses:
        if not isinstance(c, dict) or "id" not in c: continue
        try: ass, _ = _api(base, token, f"/api/v1/courses/{c['id']}/assignments?bucket=upcoming&include[]=submission&per_page=50")
        except Exception: continue
        for a in ass:
            cid = f"{c['id']}-{a['id']}"
            if cid in known: continue
            sub = (a.get("submission") or {}).get("workflow_state")
            if sub in ("submitted", "graded"): continue
            due = (a.get("due_at") or "")[:10]
            d["items"].append({"title": f"{c.get('name','curso')[:40]}: {a.get('name','trabalho')[:70]}", "type": "estudar", "minutes": 120,
                               "spent": 0, "deadline": due, "repeat": "", "priority": 1, "canvas_id": cid, "url": a.get("html_url", "")})
            n += 1
    d["canvas"]["last_sync"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"Sincronizado: {n} tarefas novas dos teus cursos."

def hm(m): return f"{m//60}h{m%60:02d}" if m >= 60 else f"{m} min"

def render(user, msg=""):
    d = load(user)
    E = html.escape
    plan, warns = schedule(d)
    rows = ""
    for i, it in enumerate(d["items"]):
        left = max(0, int(it["minutes"]) - int(it.get("spent", 0)))
        ck = " style='opacity:.5'" if it.get("done") else ""
        link = f" <a href='{E(it['url'])}' target='_blank' style='color:#aaa'>↗</a>" if it.get("url") else ""
        rows += (f"<tr{ck}><td>{E(it['title'])}{link}</td><td>{E(it.get('type',''))}</td><td>{hm(int(it['minutes']))}</td><td>{hm(int(it.get('spent',0)))}</td>"
                 f"<td>{E(it.get('deadline') or '—')}</td><td>{E(it.get('repeat') or '')}</td>"
                 f"<td><form method='post' action='/finance/routine/spent' style='display:inline'><input type='hidden' name='i' value='{i}'><button name='m' value='30'>+30 min</button></form> "
                 f"<form method='post' action='/finance/routine/done' style='display:inline'><input type='hidden' name='i' value='{i}'><button>{'reabrir' if it.get('done') else 'feito'}</button></form> "
                 f"<form method='post' action='/finance/routine/del' style='display:inline'><input type='hidden' name='i' value='{i}'><button>apagar</button></form></td></tr>")
    days = ""
    for p in plan:
        tot = sum(b["min"] for b in p["blocks"])
        body = "".join(f"<li>{E(b['title'])} <span style='color:#aaa'>({hm(b['min'])}{', '+E(b['type']) if b['type'] else ''})</span></li>" for b in p["blocks"]) or "<li style='color:#aaa'>descanso</li>"
        days += f"<div class='box' style='margin:6px 0'><b>{WD[p['date'].weekday()]} {p['date'].strftime('%d/%m')}</b> <span style='color:#aaa'>· {hm(tot) if tot else 'livre'}</span><ul>{body}</ul></div>"
    wl = "".join(f"<li class='red'>{E(w)}</li>" for w in warns)
    av = "".join(f"<label style='display:inline-block;margin:3px'>{WD[i][:3]} <input name='a{i}' type='number' min='0' max='1440' step='15' value='{d['avail'][i]}' style='width:70px'></label>" for i in range(7))
    cv = d["canvas"]
    return f"""<h1>Rotina <span style="font-size:14px;color:#aaa">estudo e trabalho</span></h1>{('<p>'+E(msg)+'</p>') if msg else ''}
<div class="box"><h2>Tempo disponível (minutos por dia)</h2><form method="post" action="/finance/routine/settings">{av}<br>
<label>Bloco máx. <input name="block" type="number" min="15" max="180" step="5" value="{d['block']}" style="width:70px"> min</label>
<label>Limite diário <input name="daycap" type="number" min="30" max="600" step="15" value="{d['daycap']}" style="width:70px"> min</label>
<button>Guardar</button></form>
<div style="color:#aaa;font-size:12px">O plano guarda 15% de folga por dia, limita as horas diárias e deixa descansar nos dias a 0, para evitares burnout.</div></div>
<div class="box"><h2>Nova meta ou tarefa</h2><form method="post" action="/finance/routine/add">
<input name="title" placeholder="O que tens de fazer / estudar / ler" required style="min-width:220px">
<select name="type"><option>estudar</option><option>ler</option><option>trabalho</option><option>outro</option></select>
<input name="hours" type="number" step="0.25" min="0.25" placeholder="horas totais" required style="width:110px">
<input name="deadline" type="date" title="Prazo (opcional)">
<select name="repeat"><option value="">única</option><option value="semanal">todas as semanas</option><option value="mensal">todos os meses</option></select>
<button>Adicionar</button></form>
<div style="color:#aaa;font-size:12px">Em «todas as semanas/meses», as horas são o total a fazer em cada semana/mês.</div></div>
{('<div class="box"><h2>Avisos do plano</h2><ul>'+wl+'</ul></div>') if wl else ''}
<div class="box"><h2>Tarefas</h2><table><tr><th>Tarefa</th><th>Tipo</th><th>Total</th><th>Feito</th><th>Prazo</th><th>Repete</th><th></th></tr>{rows}</table></div>
<h2>Plano dos próximos 14 dias</h2>{days}"""

def post(user, path, f):
    d = load(user); msg = ""
    try:
        if path == "/routine/settings":
            d["avail"] = [max(0, min(1440, int(f.get("a%d" % i, 0) or 0))) for i in range(7)]
            d["block"] = max(15, min(180, int(f.get("block", 50)))); d["daycap"] = max(30, min(600, int(f.get("daycap", 240))))
        elif path == "/routine/add":
            h = float(f["hours"].replace(",", "."))
            if not 0.25 <= h <= 1000 or not f["title"].strip(): raise ValueError
            dl = f.get("deadline") or ""
            if dl and not _date(dl): raise ValueError
            d["items"].append({"title": f["title"].strip()[:100], "type": f.get("type", "estudar")[:20], "minutes": int(round(h * 60)), "spent": 0,
                               "deadline": dl, "repeat": f.get("repeat") if f.get("repeat") in ("semanal", "mensal") else "", "priority": 2})
        elif path in ("/routine/spent", "/routine/done", "/routine/del"):
            i = int(f["i"]); it = d["items"][i]
            if path == "/routine/spent": it["spent"] = int(it.get("spent", 0)) + int(f.get("m", 30))
            elif path == "/routine/done": it["done"] = not it.get("done")
            else: del d["items"][i]
        elif path == "/routine/canvas":
            u = f.get("url", "").strip().rstrip("/")
            if u and not re.match(r"^https://[\w.-]+(:\d+)?$", u): return "O endereço deve ser tipo https://escola.instructure.com"
            d["canvas"]["url"] = u
            if f.get("token", "").strip(): d["canvas"]["token"] = f["token"].strip()
            msg = "Canvas guardado."
        elif path == "/routine/sync":
            msg = canvas_sync(d)
    except (KeyError, ValueError, IndexError):
        return "Dados inválidos."
    except Exception as e:
        msg = "Não consegui falar com o Canvas: " + str(e)[:100]
    with LOCK: save(user, d)
    return msg
