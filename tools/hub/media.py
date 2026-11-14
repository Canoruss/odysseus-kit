"""Gym: fotos de progresso (com comparacao pela IA), analise de tecnica por foto/video e glicose antes do treino."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import json, os, html, datetime, time, urllib.request

def _key():
    for l in open(secret_file("gemini")):
        if l.startswith("GEMINI_API_KEY="): return l.strip().split("=", 1)[1]
    raise RuntimeError("sem chave")

def _gem(parts, prompt, json_out=False):
    last = None
    for m in ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"):
        gc = {"responseMimeType": "application/json"} if json_out else {}
        body = json.dumps({"contents": [{"parts": [{"text": prompt}] + parts}], "generationConfig": gc}).encode()
        rq = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", body,
                                    {"Content-Type": "application/json", "x-goog-api-key": _key()})
        try:
            r = json.load(urllib.request.urlopen(rq, timeout=150))
            return r["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            last = e
    raise RuntimeError(last)

def add_photo(store, b64, date, note=""):
    ph = store.setdefault("photos", [])
    ph.insert(0, {"date": date, "img": b64, "note": note[:120], "cmp": ""})
    ph.sort(key=lambda p: p["date"], reverse=True); del ph[24:]

def compare(store, i):
    ph = store.get("photos", [])
    if i < 0 or i >= len(ph) - 1: raise ValueError("sem foto anterior")
    new, old = ph[i], ph[i + 1]
    txt = _gem([{"inline_data": {"mime_type": "image/jpeg", "data": old["img"]}}, {"inline_data": {"mime_type": "image/jpeg", "data": new["img"]}}],
        f"A primeira foto é de {old['date']} e a segunda de {new['date']}, da mesma pessoa em treino de ginásio (objetivo: ganhar massa magra, com foco em glúteos, abdominais e peito). "
        "Descreve em português de Portugal, em 3 a 5 frases simples e encorajadoras, o que parece ter mudado (volume, postura, definição). "
        "Não estimes percentagem de gordura nem peso, não faças diagnósticos, e diz que a luz e a pose afetam a comparação. Se as fotos não forem comparáveis, diz isso.")
    new["cmp"] = txt.strip()[:900]

def technique(b64, mime, exercise):
    return _gem([{"inline_data": {"mime_type": mime, "data": b64}}],
        f"Vês uma foto ou vídeo curto de alguém a fazer o exercício: {exercise or 'exercício de ginásio'}. Responde em português de Portugal, em lista curta: "
        "o que está bem, 2 a 4 correções de postura (costas, joelhos, amplitude, ritmo) e uma dica de segurança. "
        "Se não perceberes o exercício ou a imagem não ajudar, diz isso. Não diagnostiques lesões nem dores; se houver dor, aconselha parar e falar com um profissional.").strip()[:1800]

def _fmt_age(s):
    return "agora" if s < 90 else f"há {s // 60} min" if s < 5400 else f"há {s // 3600} h"

def glucose_box():
    try:
        import glucose
        d = glucose.load(); st = glucose.stats(d); last = st["last"]
    except Exception:
        return ""
    if not last: return ""
    v = last["v"]; age = int(time.time() - last["t"])
    if age > 3 * 3600: tip, cls = "A última leitura é antiga. Mede a glicose antes de treinar.", "#e0b84a"
    elif v < 70: tip, cls = "Glicose baixa: trata primeiro a hipoglicemia (hidratos rápidos) e não treines agora. Confirma depois com nova leitura.", "#ff6b6b"
    elif v < 100: tip, cls = "Glicose a ficar baixa para treinar: come cerca de 15 a 30 g de hidratos antes e volta a medir. Leva hidratos rápidos para o ginásio.", "#e0b84a"
    elif v <= 250: tip, cls = "Dentro da zona geralmente aceitável para treino ligeiro a moderado. Leva hidratos rápidos e volta a medir ao fim.", "#3ddc97"
    else: tip, cls = "Glicose alta: convém adiar o treino intenso e falar com a equipa da diabetes sobre o que fazer nesta situação.", "#ff6b6b"
    avg = f"{st['avg2d']:.0f} mg/dL" if st["avg2d"] else "—"
    meals = [x for x in d.get("log", []) if x.get("kind") == "fiasp" and x.get("carbs") is not None][-3:]
    ml = "".join(f"<li>{html.escape(datetime.datetime.fromtimestamp(x['t']).strftime('%d/%m %H:%M'))}: {x['carbs']:.0f} g de hidratos, {x['units']} U</li>" for x in reversed(meals) if "t" in x)
    return (f"<div class='box'><h2>Glicose e treino</h2><div style='font-size:28px;font-weight:700;color:{cls}'>{v:.0f} <span style='font-size:14px;color:#8b93a5'>mg/dL · {_fmt_age(age)} · média 2 dias {avg}</span></div>"
            f"<p style='margin:8px 0'>{tip}</p>"
            + (f"<div style='color:#9aa3b2;font-size:13px'>Últimas refeições registadas:</div><ul style='margin:4px 0 0 18px'>{ml}</ul>" if ml else "")
            + "<div style='color:#8b93a5;font-size:12px;margin-top:8px'>Orientação geral, não substitui o teu médico nem altera insulina. Combina com a consulta de diabetes os limites que usas para treinar.</div></div>")

def box(store, url, glucose=False):
    esc = html.escape
    ph = store.get("photos", [])
    cards = ""
    for i, p in enumerate(ph[:12]):
        cmp_ = f"<div style='font-size:13px;color:#cfd5e2;margin-top:6px'>{esc(p['cmp'])}</div>" if p.get("cmp") else ""
        btn = (f"<form method='post' action='{url}/cmp' style='display:inline'><input type='hidden' name='i' value='{i}'><button>Comparar com a anterior</button></form> "
               if i < len(ph) - 1 and not p.get("cmp") else "")
        cards += (f"<div class='box' style='margin:8px 0'><img src='data:image/jpeg;base64,{p['img']}' style='width:100%;max-height:340px;object-fit:contain;border-radius:10px;background:#0c0e12'>"
                  f"<div style='margin-top:6px'><b>{esc(p['date'])}</b> <span style='color:#8b93a5'>{esc(p.get('note',''))}</span></div>{cmp_}"
                  f"<div style='margin-top:6px'>{btn}<form method='post' action='{url}/del' style='display:inline'><input type='hidden' name='i' value='{i}'><button>Apagar</button></form></div></div>")
    js = """<script>
function rs(f,max,q){return new Promise((ok,no)=>{const u=URL.createObjectURL(f),im=new Image();im.onload=()=>{const s=Math.min(1,max/Math.max(im.width,im.height)),c=document.createElement('canvas');c.width=im.width*s;c.height=im.height*s;c.getContext('2d').drawImage(im,0,0,c.width,c.height);ok(c.toDataURL('image/jpeg',q).split(',')[1])};im.onerror=()=>no(new Error('imagem inválida'));im.src=u})}
function b64(f){return new Promise(o=>{const r=new FileReader();r.onload=()=>o(String(r.result).split(',')[1]);r.readAsDataURL(f)})}
async function post(u,b,s){try{const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});const j=await r.json();if(!r.ok||j.error)throw new Error(j.error||r.status);return j}catch(e){s.textContent='Erro: '+e.message;return null}}
async function psend(){const f=document.getElementById('pf').files[0],s=document.getElementById('ps');if(!f){s.textContent='Escolhe uma foto.';return}s.textContent='A guardar…';
const d=document.getElementById('pd').value;const j=await post('URL/photo',{img:await rs(f,900,0.7),date:d,note:document.getElementById('pn').value},s);if(j)location.reload()}
async function tsend(){const f=document.getElementById('tf').files[0],s=document.getElementById('ts'),o=document.getElementById('to');if(!f){s.textContent='Escolhe uma foto ou vídeo.';return}
if(f.size>8e6&&f.type.startsWith('video')){s.textContent='Vídeo demasiado grande (máx. 8 MB, uns 10 s).';return}
s.textContent='A analisar… pode demorar 1 minuto.';const data=f.type.startsWith('image')?await rs(f,1200,0.8):await b64(f);const mime=f.type.startsWith('image')?'image/jpeg':f.type;
const j=await post('URL/tech',{data,mime,exercise:document.getElementById('te').value},s);if(j){s.textContent='';o.textContent=j.text}}
</script>""".replace("URL", url)
    today = datetime.date.today().isoformat()
    return ((glucose_box() if glucose else "")
        + "<div class='box'><h2>Fotos de progresso</h2><div style='color:#9aa3b2;font-size:13px;margin-bottom:8px'>Uma por mês, com a mesma luz, pose e hora. A IA compara com a anterior, sem estimar gordura. Fica guardada só no servidor.</div>"
        f"<input type='file' id='pf' accept='image/*'> <input type='date' id='pd' value='{today}'> <input id='pn' placeholder='nota (opcional)' maxlength='120'> <button type='button' onclick='psend()'>Guardar foto</button> <span id='ps' style='color:#9aa3b2'></span></div>"
        + cards
        + "<div class='box'><h2>Técnica do exercício</h2><div style='color:#9aa3b2;font-size:13px;margin-bottom:8px'>Envia uma foto ou um vídeo curto (até 8 MB) e recebes dicas de postura. Não é guardado. Não diagnostica lesões.</div>"
        "<input id='te' placeholder='exercício (ex.: hip thrust)' maxlength='60'> <input type='file' id='tf' accept='image/*,video/*'> <button type='button' onclick='tsend()'>Analisar</button> <span id='ts' style='color:#9aa3b2'></span>"
        "<pre id='to' style='white-space:pre-wrap;font-family:inherit;color:#cfd5e2;margin-top:8px'></pre></div>" + js)
