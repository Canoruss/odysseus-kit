"""Glicose: leituras (LibreLinkUp ou manuais), media de 2 dias, calculadora de dose (SUGESTAO) e hidratos por foto."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import json, os, time, hashlib, datetime, urllib.request, urllib.error, html, threading, base64

HERE = HUB
GFILE = os.environ.get("GLUCOSE_DATA", os.path.join(HERE, "glucose.json"))
CRED = secret_file("librelinkup")
LOCK = threading.Lock()

# --- regras de dose: NAO ha valores por omissao. Cada pessoa define os do seu medico em
# ~/.config/odysseus-kit/config.json -> "glucose": {"fiasp_start":..,"fiasp_base":..,"fiasp_step":..,"carb_per_unit":..,
#   "max_dose":..,"basal_high_avg":..,"basal_low_avg":..,"basal_step":..,"basal_default":..}
# Sem estes valores a calculadora fica desativada e so mostra leituras e historico.
import kitconfig as _kc
_G = _kc._conf.get("glucose", {}) if isinstance(_kc._conf.get("glucose", {}), dict) else {}
FIASP_START = _G.get("fiasp_start")
FIASP_BASE = _G.get("fiasp_base")
FIASP_STEP = _G.get("fiasp_step")
CARB_PER_UNIT = _G.get("carb_per_unit")
MAX_DOSE = _G.get("max_dose")
HYPO = _G.get("hypo", 70)               # limiar de hipoglicemia (mg/dL)
BASAL_HIGH_AVG = _G.get("basal_high_avg")
BASAL_STEP = _G.get("basal_step")
BASAL_LOW_AVG = _G.get("basal_low_avg")
CALC_READY = None not in (FIASP_START, FIASP_BASE, FIASP_STEP, CARB_PER_UNIT, MAX_DOSE)
BASAL_READY = None not in (BASAL_HIGH_AVG, BASAL_STEP, BASAL_LOW_AVG)

def load():
    try:
        d = json.load(open(GFILE))
    except (OSError, ValueError):
        d = {}
    d.setdefault("readings", []); d.setdefault("basal", _G.get("basal_default", 0)); d.setdefault("log", [])
    return d

def save(d):
    d["readings"] = d["readings"][-6000:]
    tmp = GFILE + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f)
    os.chmod(tmp, 0o600); os.replace(tmp, GFILE)

def half(x): return round(x * 2) / 2

def dose(glucose, carbs):
    """Devolve dict com a sugestao de Fiasp e o detalhe do calculo."""
    out = {"warnings": []}
    if not CALC_READY:
        out.update(total=0, corr=0, meal=0, capped=False)
        out["warnings"].append("Calculadora desativada: define os valores do teu médico em config.json (secção 'glucose'). Isto é só uma ferramenta de apoio e não substitui o médico.")
        return out
    carbs = max(0.0, float(carbs or 0))
    if glucose is not None and glucose < HYPO:
        out.update(total=0, corr=0, meal=0, capped=False)
        out["warnings"].append(f"Glicose abaixo de {HYPO}: não tomes insulina. Trata a hipoglicemia e segue as indicações do teu médico.")
        return out
    corr = 0.0
    if glucose is not None and glucose >= FIASP_START:
        corr = half(FIASP_BASE + (glucose - FIASP_START) / FIASP_STEP)
    meal = half(carbs / CARB_PER_UNIT)
    total = corr + meal
    capped = total > MAX_DOSE
    if capped:
        out["warnings"].append(f"O cálculo dá {total:g} U, acima do limite de {MAX_DOSE:g} U. Mostro o limite; não excedas sem falar com o médico.")
    out.update(corr=corr, meal=meal, total=min(total, MAX_DOSE), raw=total, capped=capped)
    return out

def stats(d, now=None):
    now = now or time.time()
    r = [x for x in d["readings"] if x["t"] >= now - 48 * 3600]
    last = d["readings"][-1] if d["readings"] else None
    avg = None; enough = False
    if r:
        avg = sum(x["v"] for x in r) / len(r)
        enough = (r[-1]["t"] - r[0]["t"]) >= 36 * 3600 and len(r) >= 24
    return {"last": last, "avg2d": avg, "enough": enough, "n": len(r)}

def basal_suggestion(d, st):
    b = d["basal"]
    if not BASAL_READY:
        return {"msg": "Sugestões de dose basal desativadas (define os valores do teu médico em config.json).", "new": None}
    if not st["enough"]:
        return {"msg": "Ainda não há histórico suficiente (preciso de cerca de 2 dias de leituras) para sugerir alteração do Tresiba.", "new": None}
    if st["avg2d"] > BASAL_HIGH_AVG:
        return {"msg": f"Média dos últimos 2 dias: {st['avg2d']:.0f} mg/dL (acima de {BASAL_HIGH_AVG}). Sugestão: subir o Tresiba de {b:g} para {b + BASAL_STEP:g} U à noite.", "new": b + BASAL_STEP}
    if st["avg2d"] < BASAL_LOW_AVG and b - BASAL_STEP > 0:
        return {"msg": f"Média dos últimos 2 dias: {st['avg2d']:.0f} mg/dL (abaixo de {BASAL_LOW_AVG}). Sugestão: descer o Tresiba de {b:g} para {b - BASAL_STEP:g} U à noite.", "new": b - BASAL_STEP}
    return {"msg": f"Média dos últimos 2 dias: {st['avg2d']:.0f} mg/dL. Sem sugestão de alteração do Tresiba ({b:g} U).", "new": None}

# --- LibreLinkUp (acesso nao oficial; pode deixar de funcionar) ---
HDR = {"product": "llu.android", "version": "4.16.0", "Content-Type": "application/json", "Accept": "application/json", "cache-control": "no-cache"}
_tok = {"token": None, "base": "https://api.libreview.io", "acct": None, "exp": 0}

def _req(url, body=None, token=None, acct=None):
    h = dict(HDR)
    if token: h["Authorization"] = "Bearer " + token
    if acct: h["Account-Id"] = acct
    rq = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None, h)
    return json.load(urllib.request.urlopen(rq, timeout=25))

def have_cred(): return os.path.exists(CRED)

def _login():
    c = {}
    for line in open(CRED):
        if "=" in line: k, v = line.rstrip("\n").split("=", 1); c[k] = v
    base = _tok["base"]
    r = _req(base + "/llu/auth/login", {"email": c["LLU_EMAIL"], "password": c["LLU_PASSWORD"]})
    if r.get("data", {}).get("redirect"):
        base = f"https://api-{r['data']['region']}.libreview.io"
        r = _req(base + "/llu/auth/login", {"email": c["LLU_EMAIL"], "password": c["LLU_PASSWORD"]})
    dat = r["data"]
    _tok.update(token=dat["authTicket"]["token"], base=base, acct=hashlib.sha256(dat["user"]["id"].encode()).hexdigest(),
                exp=dat["authTicket"].get("expires", time.time() + 3000))

def fetch_llu():
    if not _tok["token"] or time.time() > _tok["exp"] - 60:
        _login()
    try:
        con = _req(_tok["base"] + "/llu/connections", token=_tok["token"], acct=_tok["acct"])
    except urllib.error.HTTPError as e:
        if e.code in (401, 403): _tok["token"] = None; _login(); con = _req(_tok["base"] + "/llu/connections", token=_tok["token"], acct=_tok["acct"])
        else: raise
    pid = con["data"][0]["patientId"]
    g = _req(f"{_tok['base']}/llu/connections/{pid}/graph", token=_tok["token"], acct=_tok["acct"])["data"]
    items = list(g.get("graphData", []))
    if g.get("connection", {}).get("glucoseMeasurement"): items.append(g["connection"]["glucoseMeasurement"])
    out = []
    for x in items:
        ts = x.get("FactoryTimestamp") or x.get("Timestamp")
        try: t = datetime.datetime.strptime(ts, "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=datetime.timezone.utc).timestamp()
        except (ValueError, TypeError): continue
        out.append({"t": t, "v": float(x["ValueInMgPerDl"])})
    return out

def merge(new):
    with LOCK:
        d = load(); seen = {int(x["t"]) // 60 for x in d["readings"]}
        add = [x for x in new if int(x["t"]) // 60 not in seen]
        d["readings"] = sorted(d["readings"] + add, key=lambda x: x["t"]); save(d)
        return len(add)

STATUS = {"ok": None, "err": ""}
def poll_loop():
    while True:
        if have_cred():
            try:
                n = merge(fetch_llu()); STATUS.update(ok=time.time(), err="")
            except Exception as e:
                STATUS["err"] = str(e)[:150]
        time.sleep(120)

def start_poller():
    threading.Thread(target=poll_loop, daemon=True).start()

# --- hidratos por foto (Gemini) ---
def read_meal(b64):
    key = None
    for line in open(secret_file("gemini")):
        if line.startswith("GEMINI_API_KEY="): key = line.strip().split("=", 1)[1]
    prompt = ('Estás a ajudar uma pessoa com diabetes a estimar hidratos de carbono de uma refeição na foto. Responde só com JSON: '
              '{"items":[{"name":"alimento em português de Portugal","grams":peso estimado em gramas,"carbs_g":hidratos estimados em gramas}], "notes":"incertezas, p.ex. molhos ou porções difíceis de ver"}. '
              'Sê realista, indica um valor por alimento visível e não inventes o que não se vê. Se não houver comida, devolve items vazio.')
    last = None
    for m in ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"):
        body = json.dumps({"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64}}]}],
                           "generationConfig": {"responseMimeType": "application/json"}}).encode()
        rq = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", body,
                                    {"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            r = json.load(urllib.request.urlopen(rq, timeout=60))
            o = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
            if isinstance(o, list): o = {"items": o}
            items = [{"name": str(i.get("name", ""))[:60], "grams": round(float(i.get("grams") or 0)), "carbs_g": round(float(i.get("carbs_g") or 0), 1)} for i in o.get("items", [])][:20]
            return {"items": items, "notes": str(o.get("notes", ""))[:300]}
        except Exception as e:
            last = e
    raise RuntimeError(last)

def add_log(kind, units, glucose=None, carbs=None, items=None):
    with LOCK:
        d = load()
        d["log"].append({"t": time.time(), "kind": kind, "units": units, "glucose": glucose, "carbs": carbs,
                         "items": [{"name": str(i.get("name", ""))[:60], "carbs_g": i.get("carbs_g")} for i in (items or [])][:20]})
        d["log"] = d["log"][-2000:]; save(d)

def _tz():
    try:
        import zoneinfo; return zoneinfo.ZoneInfo(__import__("kitconfig").get("timezone", "UTC"))
    except Exception: return datetime.timezone.utc

def parse_when(txt, days=30):
    """'YYYY-MM-DDTHH:MM' (hora de Lisboa) -> timestamp. Recusa futuro e mais de `days` dias."""
    t = datetime.datetime.fromisoformat(str(txt)[:16]).replace(tzinfo=_tz()).timestamp()
    now = time.time()
    if t > now + 300 or t < now - days * 86400: raise ValueError("data fora do intervalo")
    return t

def reading_near(ts, window=20 * 60):
    """Leitura do sensor mais proxima de ts (ate 20 min), ou None."""
    best = None
    for x in load()["readings"]:
        dt = abs(x["t"] - ts)
        if dt <= window and (best is None or dt < best[0]): best = (dt, x)
    return best[1] if best else None

def add_manual(kind, units, ts, glucose=None, carbs=None, note=""):
    with LOCK:
        d = load()
        d["log"].append({"t": ts, "kind": kind, "units": units, "glucose": glucose, "carbs": carbs, "manual": True,
                         "items": [{"name": str(note)[:60], "carbs_g": None}] if note else []})
        d["log"] = sorted(d["log"], key=lambda e: e["t"])[-2000:]; save(d)

def edit_log(old_t, kind, units, ts, glucose, carbs, note):
    """Substitui um registo (mantem a lista de alimentos se a nota nao mudou)."""
    with LOCK:
        d = load(); e = next((x for x in d["log"] if abs(x["t"] - float(old_t)) <= 0.001), None)
        if not e: return False
        orig = ", ".join(i.get("name", "") for i in e.get("items", []))
        e["t"], e["kind"], e["units"], e["glucose"], e["carbs"] = ts, kind, units, glucose, carbs
        if str(note) != orig: e["items"] = [{"name": str(note)[:60], "carbs_g": None}] if note else []
        e["edited"] = True
        d["log"] = sorted(d["log"], key=lambda x: x["t"]); save(d); return True

def del_log(ts):
    with LOCK:
        d = load(); n = len(d["log"])
        d["log"] = [e for e in d["log"] if abs(e["t"] - float(ts)) > 0.001]; save(d)
        return n - len(d["log"])

def now_json():
    d = load(); l = d["readings"][-1] if d["readings"] else None
    return {"v": l["v"] if l else None, "age": int(time.time() - l["t"]) if l else None}

def history_html(d, limit=40, edit=False):
    rows = ""
    for e in reversed(d["log"][-limit:]):
        t = datetime.datetime.fromtimestamp(e["t"], datetime.timezone(datetime.timedelta(0))).strftime("%d/%m %H:%M")
        try:
            import zoneinfo; t = datetime.datetime.fromtimestamp(e["t"], zoneinfo.ZoneInfo(__import__("kitconfig").get("timezone", "UTC"))).strftime("%d/%m %H:%M")
        except Exception: pass
        food = ", ".join(html.escape(i["name"]) + (f" ({i['carbs_g']} g)" if i.get("carbs_g") is not None else "") for i in e.get("items", []))
        meal = e["kind"] == "refeicao"
        what = ("Refeição pré-treino (sem insulina)" if meal else ("Fiasp" if e["kind"] == "fiasp" else "Tresiba")) + (" <small style='color:#8ab'>(manual)</small>" if e.get("manual") else "") + (" <small style='color:#ca8'>(editado)</small>" if e.get("edited") else "")
        units = "" if meal else f" <b>{e['units']:g} U</b>"
        gl = f'{e["glucose"]:.0f}' if e.get("glucose") else "—"
        ch = f'{e["carbs"]:g} g' if e.get("carbs") else "—"
        tid = repr(e["t"])
        ed = html.escape(json.dumps({"t": e["t"], "kind": e["kind"], "units": e["units"], "glucose": e.get("glucose"), "carbs": e.get("carbs"),
            "note": ", ".join(i.get("name", "") for i in e.get("items", [])),
            "when": datetime.datetime.fromtimestamp(e["t"], _tz()).strftime("%Y-%m-%dT%H:%M")}), quote=True)
        # refeições pré-treino so se apagam (a edição do formulário é só para insulina)
        dele = ("<td style='white-space:nowrap'>" + ("" if meal else "<button type='button' data-e=\"" + ed + "\" style='background:#3a5a8a;color:#fff;border:0;border-radius:6px;padding:3px 8px;margin-right:4px' onclick=\"editLog(this)\">editar</button>") + "<button type='button' style='background:#6a3a3a;color:#fff;border:0;border-radius:6px;padding:3px 8px' onclick=\"delLog(" + tid + ")\">apagar</button></td>") if edit else ""
        rows += f"<tr><td>{t}</td><td>{what}{units}</td><td>{gl}</td><td>{ch}</td><td>{food or '—'}</td>{dele}</tr>"
    if not rows: return '<p style="color:#aaa">Ainda sem registos.</p>'
    return f'<div style="overflow-x:auto"><table><tr><th>Quando</th><th>Insulina</th><th>Glicose</th><th>Hidratos</th><th>O que comeu</th>{"<th></th>" if edit else ""}</tr>{rows}</table></div>'

def render_history(page):
    d = load(); st = stats(d); last = st["last"]
    cur = (f'<div class="big">{last["v"]:.0f} <small>mg/dL</small></div><div style="color:#aaa">há {int((time.time()-last["t"])/60)} min</div>' if last else "")
    body = f'<h1>Glicose do administrador (só leitura)</h1><div class="box">{cur}{chart_svg(d)}</div><div class="box"><h2>Insulina e refeições</h2>{history_html(d, 60)}</div><style>.big{{font-size:36px;font-weight:700}} small{{font-size:14px;color:#aaa}}</style>'
    return page(body, "Glicose")

MANUAL_BOX = """<div class="box" id="mbox"><h2 id="mh">Registo manual</h2><div style="color:#aaa;margin-bottom:6px">Esqueceste-te de registar? Indica quando tomaste. A glicose dessa hora vem do sensor.</div>
<div><select id="mk"><option value="fiasp">Fiasp</option><option value="tresiba">Tresiba</option></select> <input id="mu" size="4" inputmode="decimal" placeholder="U"> U &nbsp; <input type="datetime-local" id="mw"></div>
<div style="margin-top:6px">Glicose: <input id="mg2" size="4" inputmode="decimal" placeholder="mg/dL"> <span id="mgi" style="color:#aaa;font-size:13px"></span></div>
<div style="margin-top:6px">Hidratos (g, opcional): <input id="mc" size="4" inputmode="decimal"> &nbsp; Nota: <input id="mn" placeholder="ex: jantar" style="min-width:140px"></div>
<div style="margin-top:8px"><button type="button" id="msv" onclick="saveManual()">Guardar registo</button> <button type="button" id="mcx" onclick="cancelEdit()" style="display:none;background:#555">Cancelar</button> <span id="mm"></span></div></div>"""

# --- pagina ---
PAGE_JS = r"""
const $=id=>document.getElementById(id);
function fmt(x){return (Math.round(x*10)/10).toString().replace('.',',')}
async function calc(){
  const g=$('gv').value===''?null:parseFloat($('gv').value.replace(',','.'));
  let c=0; document.querySelectorAll('.cb').forEach(i=>{c+=parseFloat(i.value.replace(',','.'))||0});
  const extra=parseFloat($('cx').value.replace(',','.'))||0; c+=extra;
  $('ct').textContent=fmt(c);
  const r=await (await fetch('/finance/glucose/dose',{method:'POST',body:JSON.stringify({glucose:g,carbs:c}),credentials:'same-origin'})).json();
  let h='<div class="big">'+fmt(r.total)+' U Fiasp</div><div>Correção: '+fmt(r.corr)+' U · Refeição: '+fmt(r.meal)+' U ('+fmt(c)+' g)</div>';
  r.warnings.forEach(w=>{h+='<div class="red">'+w+'</div>'});
  h+='<div style="color:#aaa;margin-top:6px">Sugestão para confirmares com o teu esquema. Não substitui o teu juízo nem o médico.</div>';
  $('res').innerHTML=h; if(document.activeElement!==$('du'))$('du').value=r.total;
}
$('mg').addEventListener('change',e=>{const f=e.target.files[0];if(!f)return;const dt=new DataTransfer();dt.items.add(f);$('mf').files=dt.files;$('mf').dispatchEvent(new Event('change'));e.target.value=''});
$('mf').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;const st=$('ms');st.textContent='A analisar a refeição…';
 try{const bm=await createImageBitmap(f);const k=Math.min(1,1400/Math.max(bm.width,bm.height));const c=document.createElement('canvas');c.width=bm.width*k;c.height=bm.height*k;c.getContext('2d').drawImage(bm,0,0,c.width,c.height);
 const b64=c.toDataURL('image/jpeg',0.85).split(',')[1];
 const o=await (await fetch('/finance/glucose/meal',{method:'POST',body:JSON.stringify({image:b64}),credentials:'same-origin'})).json();
 if(o.error){st.textContent=o.error;return}
 let h='<table><tr><th>Alimento</th><th>g</th><th>Hidratos (g)</th></tr>';
 o.items.forEach(i=>{h+='<tr><td>'+i.name.replace(/</g,'&lt;')+'</td><td>'+i.grams+'</td><td><input class="cb" value="'+i.carbs_g+'" size="4" inputmode="decimal" oninput="calc()"></td></tr>'});
 h+='</table>'+(o.notes?'<div style="color:#aaa">'+o.notes.replace(/</g,'&lt;')+'</div>':'');
 $('items').innerHTML=h; st.textContent='Estimativa: corrige os valores se for preciso e confirma.'; calc();
 }catch(x){st.textContent='Erro: '+x}});
let manual=false, lastR=null;
$('gv').addEventListener('input',()=>{manual=true;calc()});
async function live(){try{const r=await (await fetch('/finance/glucose/now',{credentials:'same-origin'})).json();
 if(r.v!=null){$('cur').textContent=Math.round(r.v);$('age').textContent='há '+Math.round(r.age/60)+' min';
  if(!manual&&r.age<1800&&String(r.v)!==lastR){lastR=String(r.v);$('gv').value=Math.round(r.v);calc();}}}catch(e){}}
setInterval(live,20000); live();
let lastItems=[];
function curItems(){const items=[];document.querySelectorAll('#items tr').forEach(tr=>{const td=tr.querySelectorAll('td');if(td.length==3)items.push({name:td[0].textContent,carbs_g:parseFloat(td[2].querySelector('input').value.replace(',','.'))||0})});return items}
async function logDose(){const u=parseFloat($('du').value.replace(',','.'));if(!(u>=0)){$('lm').textContent='Indica a dose.';return}
 const g=$('gv').value===''?null:parseFloat($('gv').value.replace(',','.'));let c=parseFloat($('ct').textContent.replace(',','.'))||0;
 const r=await (await fetch('/finance/glucose/log',{method:'POST',body:JSON.stringify({kind:'fiasp',units:u,glucose:g,carbs:c,items:curItems()}),credentials:'same-origin'})).json();
 $('lm').textContent=r.ok?'Registado.':'Erro.';if(r.ok)setTimeout(()=>location.reload(),600);}
async function logMeal(){const g=$('gv').value===''?null:parseFloat($('gv').value.replace(',','.'));let c=parseFloat($('ct').textContent.replace(',','.'))||0;
 if(!(c>0)){$('lmt').textContent='Indica os hidratos (foto ou campo "Hidratos extra").';return}
 const r=await (await fetch('/finance/glucose/log',{method:'POST',body:JSON.stringify({kind:'refeicao',units:0,glucose:g,carbs:c,items:curItems()}),credentials:'same-origin'})).json();
 $('lmt').textContent=r.ok?'Refeição pré-treino registada (sem insulina).':'Erro.';if(r.ok)setTimeout(()=>location.reload(),900);}
$('cx').addEventListener('input',calc); calc();
function pad(n){return String(n).padStart(2,'0')}
function nowLocal(){const d=new Date();return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+'T'+pad(d.getHours())+':'+pad(d.getMinutes())}
if($('mw')){$('mw').value=nowLocal();$('mw').max=nowLocal();
 async function lookup(){const w=$('mw').value;if(!w)return;try{const r=await (await fetch('/finance/glucose/at?when='+encodeURIComponent(w),{credentials:'same-origin'})).json();
  if(r.v!=null){$('mg2').value=Math.round(r.v);$('mgi').textContent='leitura do sensor às '+r.hm+' ('+r.dmin+' min de diferença)'}else{$('mgi').textContent='sem leitura do sensor nessa hora: escreve o valor, se o souberes'}}catch(e){}}
 $('mw').addEventListener('change',lookup);lookup();
 let editT=null;
 window.saveManual=async function(){const u=parseFloat($('mu').value.replace(',','.'));if(!(u>0)){$('mm').textContent='Indica as unidades.';return}
  const g=$('mg2').value.trim()===''?null:parseFloat($('mg2').value.replace(',','.'));const c=$('mc').value.trim()===''?null:parseFloat($('mc').value.replace(',','.'));
  const body={kind:$('mk').value,units:u,when:$('mw').value,glucose:g,carbs:c,note:$('mn').value};if(editT!==null)body.t=editT;
  const r=await (await fetch(editT!==null?'/finance/glucose/log_edit':'/finance/glucose/log_manual',{method:'POST',credentials:'same-origin',body:JSON.stringify(body)})).json();
  $('mm').textContent=r.ok?'Guardado.':(r.error||'Erro.');if(r.ok)setTimeout(()=>location.reload(),600)};
 window.editLog=function(b){const e=JSON.parse(b.dataset.e);editT=e.t;$('mk').value=e.kind;$('mu').value=String(e.units).replace('.',',');$('mw').removeAttribute('max');$('mw').value=e.when;
  $('mg2').value=e.glucose==null?'':Math.round(e.glucose);$('mc').value=e.carbs==null?'':String(e.carbs).replace('.',',');$('mn').value=e.note||'';
  $('mh').textContent='Editar registo';$('msv').textContent='Guardar alterações';$('mcx').style.display='';$('mgi').textContent='';$('mm').textContent='';$('mbox').scrollIntoView({behavior:'smooth'})};
 window.cancelEdit=function(){location.reload()}}
async function delLog(t){if(!confirm('Apagar este registo?'))return;const r=await (await fetch('/finance/glucose/log_del',{method:'POST',credentials:'same-origin',body:JSON.stringify({t:t})})).json();if(r.ok)location.reload();else alert(r.error||'Erro')}
"""

def chart_svg(d):
    now = time.time(); pts = [x for x in d["readings"] if x["t"] >= now - 24 * 3600]
    if len(pts) < 2: return '<p style="color:#aaa">Sem leituras nas últimas 24 h.</p>'
    W, Hh = 600, 160; lo, hi = 40, 350
    def X(t): return (t - (now - 24 * 3600)) / (24 * 3600) * W
    def Y(v): return Hh - (min(max(v, lo), hi) - lo) / (hi - lo) * Hh
    path = " ".join(f"{X(p['t']):.1f},{Y(p['v']):.1f}" for p in pts)
    band = f'<rect x="0" y="{Y(180):.1f}" width="{W}" height="{Y(70)-Y(180):.1f}" fill="#70d080" opacity=".12"/>'
    return f'<svg viewBox="0 0 {W} {Hh}" width="100%" style="background:#1d2026;border-radius:8px">{band}<polyline fill="none" stroke="#6aa0ff" stroke-width="2" points="{path}"/></svg>'

def render(page):
    d = load(); st = stats(d); bs = basal_suggestion(d, st)
    last = st["last"]
    if last:
        mins = int((time.time() - last["t"]) / 60)
        cur = f'<div class="big"><span id="cur">{last["v"]:.0f}</span> <small>mg/dL</small></div><div style="color:#aaa" id="age">há {mins} min</div>'
        pre = f'value="{last["v"]:.0f}"' if mins <= 20 else ""
    else:
        cur = '<div style="color:#aaa">Sem leituras ainda.</div>'; pre = ""
    if have_cred():
        src = ('<span class="green">LibreLinkUp ligado</span>' if STATUS["ok"] else '<span class="red">LibreLinkUp: ainda sem leitura</span>')
        if STATUS["err"]: src += f'<div class="red">{html.escape(STATUS["err"])}</div>'
    else:
        src = '<span class="red">LibreLinkUp não configurado: introduz a glicose à mão.</span>'
    basal = f'''<div class="box"><h2>Tresiba</h2><div>Dose atual: <b>{d["basal"]:g} U</b> (à noite)</div><div>{html.escape(bs["msg"])}</div>'''
    if bs["new"]:
        basal += f'<form method="post" action="/finance/glucose/basal"><input type="hidden" name="v" value="{bs["new"]:g}"><button>Confirmar: passar a {bs["new"]:g} U</button></form>'
    basal += '<form method="post" action="/finance/glucose/basal" style="margin-top:6px"><input name="v" size="4" placeholder="U" inputmode="decimal"><button>Definir dose manualmente</button></form></div>'
    body = f'''<h1>Glicose</h1>
<div class="box">{cur}<div>{src}</div>{chart_svg(d)}
<div style="color:#aaa">Média 48 h: {"%.0f mg/dL" % st["avg2d"] if st["avg2d"] else "—"} ({st["n"]} leituras)</div>
<form method="post" action="/finance/glucose/add" style="margin-top:6px"><input name="v" size="5" placeholder="mg/dL" inputmode="numeric" required><button>Guardar leitura manual</button></form></div>
<div class="box"><h2>Refeição e dose de Fiasp</h2>
<div>Glicose atual: <input id="gv" size="5" inputmode="numeric" {pre} placeholder="mg/dL"> mg/dL</div>
<div style="margin:8px 0">Foto da refeição: <label class="btn" style="display:inline-block;padding:6px 12px;border-radius:8px;background:#2f6fd0;color:#fff;cursor:pointer;margin:0 4px">📷 Câmara<input type="file" id="mf" accept="image/*" capture="environment" style="display:none" onclick="try{{parent.postMessage('fin-keep','*')}}catch(e){{}}"></label><label class="btn" style="display:inline-block;padding:6px 12px;border-radius:8px;background:#444;color:#fff;cursor:pointer;margin:0 4px">🖼 Galeria<input type="file" id="mg" accept="image/*" style="display:none" onclick="try{{parent.postMessage('fin-keep','*')}}catch(e){{}}"></label> <span id="ms"></span></div>
<div id="items"></div>
<div>Hidratos extra (g): <input id="cx" size="4" inputmode="decimal" placeholder="0"> · Total: <b><span id="ct">0</span> g</b></div>
<div id="res" class="box"></div>
<div>Dose tomada: <input id="du" size="4" inputmode="decimal"> U Fiasp <button type="button" onclick="logDose()">Registar dose tomada</button> <span id="lm"></span></div>
<div style="margin-top:8px">Refeição antes do treino (sem insulina): <button type="button" onclick="logMeal()">Registar hidratos pré-treino</button> <span id="lmt"></span></div></div>
{MANUAL_BOX}<div class="box"><h2>Histórico (insulina e refeições)</h2>{history_html(d, 40, True)}</div>
{basal}
<div class="box" style="color:#aaa;font-size:13px">Regras usadas: Fiasp abaixo de 150 mg/dL só hidratos (1 U por 10 g); a partir de 150, correção de 6 U + 1 U por cada 50 mg/dL acima (arredondada a 0,5), somada aos hidratos. Limite {MAX_DOSE:g} U. Abaixo de {HYPO} mg/dL não sugere insulina. Tresiba: sugere +{BASAL_STEP} U se a média de 2 dias passar de {BASAL_HIGH_AVG}. São sugestões; confirma sempre com o médico.</div>
<style>.big{{font-size:36px;font-weight:700}} small{{font-size:14px;color:#aaa}}</style><script>{PAGE_JS}</script>'''
    return page(body, "Glicose")
