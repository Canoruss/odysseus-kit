#!/usr/bin/env python3
"""Financas pessoais: login por palavra-passe, movimentos (gastos/ganhos), dividas e grafico. Escuta so em 127.0.0.1:8792."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import i18n
GYM_START = float(get('gym_start_kg', 70)); GYM_GOAL = float(get('gym_goal_kg', 75))
import hashlib, hmac, html, json, os, secrets, datetime, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = HUB
DATA = os.path.join(HERE, "data.json")
PREFIX = "/finance"
CATS = ["casa", "contas", "comida", "restaurantes", "transportes", "combustivel", "saude", "farmacia", "roupa", "lazer", "ginasio", "educacao", "tecnologia", "viagens", "prestacoes", "presentes", "trabalho", "salario", "outros"]
import time, base64, re
import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glucose
import inbox
import routine
import study, extras, usage
import reports, media
IDLE = 180
LAST = [0.0]

def env(path):
    d = {}
    for line in open(path):
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1); d[k] = v
    return d

try: SECRET = env(secret_file("finance"))["FINANCE_PASSWORD"]
except Exception:
    SECRET = secrets.token_urlsafe(24)   # sem palavra-passe configurada: ninguem entra nas Financas ate correres o assistente (setup/)
    print("AVISO: FINANCE_PASSWORD nao definida (corre o assistente de configuracao).", flush=True)
KEY = hashlib.sha256(("finance-session:" + SECRET).encode()).hexdigest()
TOKEN = hmac.new(KEY.encode(), b"ok", "sha256").hexdigest()
SBX = TESTER   # conta de teste: Financas/Gym completos mas com dados, palavra-passe e sessao proprios
try: SBX_SECRET = env(os.path.expanduser("~/.config/odysseus-kit/finance-sandbox.env"))["FINANCE_SANDBOX_PASSWORD"]
except Exception: SBX_SECRET = secrets.token_urlsafe(16)
SBX_TOKEN = hmac.new(KEY.encode(), ("sbx:" + SBX_SECRET).encode(), "sha256").hexdigest()
SBX_DATA = os.path.join(HERE, "data-sandbox-main.json")
LAST_SBX = [0.0]
def _is_sbx(): return getattr(CUR, "u", None) == SBX
def _L(): return LAST_SBX if _is_sbx() else LAST
def _secret(): return SBX_SECRET if _is_sbx() else SECRET
def _token(): return SBX_TOKEN if _is_sbx() else TOKEN


import urllib.request, threading, secrets
MLIKE = (MEMBER, TESTER)   # contas com o espaço tipo membro (dados separados por conta)
CUR = threading.local()
def _mfile():
    u = getattr(CUR, "u", None) or MEMBER
    return os.path.join(HERE, "data-member.json" if u == MEMBER else "data-%s.json" % re.sub(r"[^a-z0-9]", "", u))

def who(headers):
    """Utilizador do Odysseus dono do cookie reencaminhado (ou None)."""
    cookie = headers.get("Cookie", "")
    if not cookie:
        return None
    try:
        req = urllib.request.Request(get("odysseus_url", "http://127.0.0.1:7860") + "/api/auth/status", headers={"Cookie": cookie})
        d = json.load(urllib.request.urlopen(req, timeout=3))
        return d.get("username") if d.get("authenticated") else None
    except Exception:
        return None

def mload():
    try: return json.load(open(_mfile()))
    except FileNotFoundError: return {"movements": [], "debts": [], "goals": [], "weights": [], "workouts": []}

def msave(d):
    MFILE = _mfile(); tmp = MFILE + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600); os.replace(tmp, MFILE)

def m_token(d):
    return hmac.new(KEY.encode(), ("m:" + d["pw"]["hash"]).encode(), "sha256").hexdigest()

def m_hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200000).hex()

def load():
    try: d = json.load(open(SBX_DATA if _is_sbx() else DATA))
    except FileNotFoundError: d = {"movements": [], "debts": [], "goals": []} if _is_sbx() else {"movements": []}
    if "debts" not in d:
        d.update(json.load(open(os.path.join(HERE, "debts.json"))))
    return d

def save(d):
    DT = SBX_DATA if _is_sbx() else DATA; tmp = DT + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600); os.replace(tmp, DT)

def page(body, title="Financas"):
    return f"""<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
body{{font-family:system-ui,sans-serif;background:#1d2026;color:#eee;margin:0;padding:16px;max-width:900px;margin:auto}}
h1,h2{{font-weight:600}} table{{width:100%;border-collapse:collapse;margin:8px 0}} td,th{{padding:6px;border-bottom:1px solid #333;text-align:left}}
input,select,button{{padding:8px;border-radius:6px;border:1px solid #444;background:#2a2e36;color:#eee;margin:3px}}
button{{background:#4a7bd0;border:0;cursor:pointer}} .red{{color:#f07070}} .green{{color:#70d080}} .box{{background:#262a31;padding:12px;border-radius:10px;margin:10px 0}}
</style></head><body>{body}</body></html>"""

def eur(v): return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

def chart(d):
    now = datetime.date.today()
    months = [(now.replace(day=1) - datetime.timedelta(days=30 * i)).strftime("%Y-%m") for i in range(5, -1, -1)]
    gastos = {m: 0.0 for m in months}; ganhos = {m: 0.0 for m in months}
    for m in d["movements"]:
        k = m["date"][:7]
        if k in gastos:
            (gastos if m["type"] == "gasto" else ganhos)[k] += float(m["amount"])
    top = max([1.0] + list(gastos.values()) + list(ganhos.values()))
    step = 10 ** (len(str(int(top))) - 1); top = ((int(top) // step) + 1) * step
    W, H, pl, pb, pt = 600, 210, 44, 26, 12
    ph = H - pb - pt; gw = (W - pl - 8) / 6; bw = 15
    MES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    out = []
    for k in range(3):
        y = pt + ph - ph * k / 2; v = top * k / 2
        out.append(f'<line x1="{pl}" y1="{y:.1f}" x2="{W-8}" y2="{y:.1f}" stroke="#2f343d" stroke-width="1"/>'
                   f'<text x="{pl-6}" y="{y+4:.1f}" font-size="11" fill="#7d8594" text-anchor="end">{v:,.0f}</text>'.replace(",", " "))
    for i, mth in enumerate(months):
        cx = pl + gw * i + gw / 2
        for j, (val, col) in enumerate(((gastos[mth], "#f07070"), (ganhos[mth], "#5fd08a"))):
            h = val / top * ph; x = cx - bw - 1 + j * (bw + 2)
            if h > 0:
                out.append(f'<rect x="{x:.1f}" y="{pt+ph-h:.1f}" width="{bw}" height="{max(h,2):.1f}" rx="4" fill="{col}"><title>{eur(val)}</title></rect>')
        cur = ' font-weight="700" fill="#e8eaf0"' if i == 5 else ' fill="#7d8594"'
        out.append(f'<text x="{cx:.1f}" y="{H-8}" font-size="12" text-anchor="middle"{cur}>{MES[int(mth[5:])-1]}</text>')
    svg = f'<svg viewBox="0 0 {W} {H}" width="100%" style="display:block">{"".join(out)}</svg>'
    legend = ('<div style="display:flex;gap:16px;font-size:12px;color:#9aa3b2;margin-top:6px">'
              '<span><span style="color:#f07070">●</span> Gastos</span><span><span style="color:#5fd08a">●</span> Ganhos</span></div>')
    return f'<div class="box"><h2 style="margin:0 0 8px;font-size:16px">Últimos 6 meses</h2>{svg}{legend}</div>'


def dash(d, pre="/finance"):
    now = datetime.date.today()
    months = [(now.replace(day=1) - datetime.timedelta(days=30 * i)).strftime("%Y-%m") for i in range(5, -1, -1)]
    g = {m: 0.0 for m in months}; r = {m: 0.0 for m in months}
    for m in d["movements"]:
        k = m["date"][:7]
        if k in g: (g if m["type"] == "gasto" else r)[k] += float(m["amount"])
    cur = months[-1]; prev = months[-2]
    def spark(vals, col):
        top = max([1.0] + vals); w = 100 / len(vals)
        bars = "".join(f'<rect x="{i*w+2:.1f}" y="{40-v/top*38:.1f}" width="{w-4:.1f}" height="{max(v/top*38,1):.1f}" rx="2" fill="{col}"/>' for i, v in enumerate(vals))
        return f'<svg viewBox="0 0 100 40" width="110" height="44">{bars}</svg>'
    def card(title, val, sub, svg, cls=""):
        return f'<div class="dc"><div class="dt">{title}</div><div class="dv {cls}">{val}</div><div class="ds">{sub}</div>{svg}</div>'
    def delta(a, b, good_up):
        x = a - b
        if abs(x) < 0.005: return "sem variação"
        up = x > 0
        c = "green" if up == good_up else "red"
        return f'<span class="{c}">{"▲" if up else "▼"} {eur(abs(x))} vs mês anterior</span>'
    net = [r[m] - g[m] for m in months]
    cards = (card("Gasto (este mês)", eur(g[cur]), delta(g[cur], g[prev], False) if g[cur] or g[prev] else "Ainda sem gastos", spark([g[m] for m in months], "#f07070"))
             + card("Rendimento", eur(r[cur]), delta(r[cur], r[prev], True) if r[cur] or r[prev] else "Ainda sem rendimentos", spark([r[m] for m in months], "#70d080"))
             + card("Fluxo líquido", ("+" if net[-1] >= 0 else "") + eur(net[-1]),
                    f'<span class="green">⊕ {eur(r[cur])}</span> &nbsp; <span class="red">⊖ {eur(g[cur])}</span>', spark([max(x, 0) for x in net], "#70d080"), "green" if net[-1] >= 0 else "red"))
    debts = d["debts"]; total = sum(float(x["amount"]) for x in debts)
    pal = ["#4a7bd0", "#f07070", "#70d080", "#e0b050", "#a070e0", "#50c0c0", "#e07090", "#909090"]
    circ = 2 * 3.14159 * 40; off = 0; arcs = []; leg = []
    for i, x in enumerate(debts):
        a = float(x["amount"]); frac = a / total if total else 0
        arcs.append(f'<circle r="40" cx="60" cy="60" fill="none" stroke="{pal[i%8]}" stroke-width="16" stroke-dasharray="{frac*circ:.2f} {circ:.2f}" stroke-dashoffset="{-off:.2f}" transform="rotate(-90 60 60)"/>')
        off += frac * circ
        leg.append(f'<div><span style="color:{pal[i%8]}">■</span> {html.escape(x["name"])} · {eur(a)}</div>')
    donut = f'<svg viewBox="0 0 120 120" width="120" height="120">{"".join(arcs) or "<circle r=40 cx=60 cy=60 fill=none stroke=#333 stroke-width=16 />"}</svg>'
    goals = d.get("goals", [])
    grows = "".join(f"<tr><td>{html.escape(x['name'])}</td><td>{eur(float(x['target']))}</td><td>{html.escape(x.get('deadline',''))}</td>"
                    f"<td><form method='post' action='/finance/goal/del' style='margin:0'><input type='hidden' name='i' value='{i}'><button>apagar</button></form></td></tr>"
                    for i, x in enumerate(goals))
    return f"""<style>.dcs{{display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x mandatory;padding:4px 0}}
.dc{{flex:0 0 78%;max-width:300px;scroll-snap-align:start;background:#262a31;border-radius:14px;padding:14px;position:relative}}
.dt{{color:#aaa;font-size:13px}}.dv{{font-size:28px;font-weight:700;margin:4px 0}}.ds{{font-size:12px;color:#aaa}}.dc svg{{position:absolute;right:12px;top:14px}}
.don{{display:flex;gap:14px;align-items:center;flex-wrap:wrap}}</style>
<div class="dcs">{cards}</div>
<div class="box"><h2>Total em dívida</h2><div class="don">{donut}<div><div class="dv red">{eur(total)}</div><div class="ds">{"".join(leg)}</div></div></div></div>
<div class="box"><h2>Metas e poupança</h2><table>{grows or "<tr><td>Ainda sem metas.</td></tr>"}</table>
<form method="post" action="/finance/goal/add"><input name="name" placeholder="Meta" required><input type="number" step="0.01" name="target" placeholder="Valor €" required><input type="date" name="deadline"><button>Adicionar</button></form></div>
""".replace("/finance/goal/", pre + "/goal/")


GYM_PLAN = """
<div class="box"><h2>Plano de exemplo</h2><p>Este é um <b>plano de exemplo</b> (3 treinos por semana, corpo inteiro). Edita-o em <code>GYM_PLAN</code> ou deixa que o questionário gere um plano personalizado.</p>
<p class="red"><b>Antes de começar:</b> confirma o plano com um profissional de saúde, sobretudo se tens alguma condição médica ou tomas medicação.</p></div>
<div class="box"><h2>Treino A: pernas e glúteos</h2><ul><li>Agachamento goblet: 3 x 10</li><li>Hip thrust: 4 x 8 a 10</li><li>Afundos: 3 x 10 por perna</li><li>Prancha: 3 x 30 a 45 s</li></ul></div>
<div class="box"><h2>Treino B: peito, costas e ombros</h2><ul><li>Supino com halteres: 4 x 8 a 10</li><li>Remada sentada: 3 x 10</li><li>Puxada à frente: 3 x 10</li><li>Elevação lateral: 3 x 12</li></ul></div>
<div class="box"><h2>Treino C: posterior e abdominais</h2><ul><li>Peso morto romeno: 3 x 8 a 10</li><li>Coice de glúteo na polia: 3 x 12</li><li>Flexões: 3 x máximo</li><li>Roda abdominal ou dead bug: 3 x 10</li></ul></div>
"""

GYM_RULES = ("És o assistente de metas do Gym do utilizador. A tua ÚNICA função é registar as metas dele e as alterações ao plano de treino que ele comunica, e confirmar de forma curta. "
 "NÃO respondas a mais nada (conversa geral, finanças, glicose, doses de insulina, medicação, diagnósticos): nesse caso diz 'Só posso registar metas e alterações do Gym.' e não alteres nada. "
 "NÃO uses ferramentas nem pesquisas. Escreve em português de Portugal. Se a alteração envolver glicose, jejum ou medicação, acrescenta 'valida com o teu médico'. "
 'Responde APENAS com JSON: {"reply": "confirmação curta", "goals": "texto completo e atualizado das metas (ou o atual se nada mudou)", "adjustments": ["lista completa e atualizada de alterações ao plano, curtas"]}.')

def gym_chat(d, msg, person="owner"):
    key = _bridge_key()
    if not key: raise RuntimeError("bridge indisponível")
    hist = d.get("gym_chat", [])[-6:]
    rules = GYM_RULES
    prompt = (rules + "\n\nMETAS ATUAIS: " + (d.get("gym_goals") or "(nenhuma)") +
              "\nALTERAÇÕES ATUAIS: " + json.dumps(d.get("gym_adjust", []), ensure_ascii=False) +
              "\nCONVERSA RECENTE: " + json.dumps(hist, ensure_ascii=False) +
              "\n\nNOVA MENSAGEM DO UTILIZADOR: " + json.dumps(msg, ensure_ascii=False))
    body = json.dumps({"model": "claude-code-haiku", "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(BRIDGE_URL, data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    out = json.load(urllib.request.urlopen(req, timeout=120))
    text = out["choices"][0]["message"]["content"]
    j = json.loads(text[text.index("{"): text.rindex("}") + 1])
    reply = str(j["reply"])[:500]
    goals = str(j.get("goals", ""))[:800]
    adj = [str(a)[:200] for a in j.get("adjustments", [])][:15]
    return reply, goals, adj

GYM_CHAT_JS = r"""<script>
async function gsend(){const i=document.getElementById('gm');const m=i.value.trim();if(!m)return;const l=document.getElementById('gl');
 l.insertAdjacentHTML('beforeend','<div><b>Tu:</b> '+m.replace(/</g,'&lt;')+'</div><div id="gw" style="color:#aaa">A pensar…</div>');i.value='';
 try{const r=await (await fetch(GYM_CHAT_URL,{method:'POST',body:JSON.stringify({message:m}),credentials:'same-origin'})).json();
  document.getElementById('gw').remove();
  if(r.error){l.insertAdjacentHTML('beforeend','<div class="red">'+r.error+'</div>');return}
  l.insertAdjacentHTML('beforeend','<div><b>Assistente:</b> '+r.reply.replace(/</g,'&lt;')+'</div>');
  document.getElementById('gg').textContent=r.goals||'(nenhuma)';
  document.getElementById('ga').innerHTML=r.adjustments.map(a=>'<li>'+a.replace(/</g,'&lt;')+'</li>').join('')||'<li style="color:#aaa">nenhuma</li>';
 }catch(e){document.getElementById('gw').textContent='Erro: '+e}}
document.getElementById('gm').addEventListener('keydown',e=>{if(e.key==='Enter')gsend()});
</script>"""

def gym_chat_box(d, url="/finance/gym/chat"):
    adj = "".join(f"<li>{html.escape(a)}</li>" for a in d.get("gym_adjust", [])) or '<li style="color:#aaa">nenhuma</li>'
    log = "".join(f"<div><b>{'Tu' if m['r']=='u' else 'Assistente'}:</b> {html.escape(m['t'])}</div>" for m in d.get("gym_chat", [])[-6:])
    return ('<div class="box"><h2>Metas e alterações</h2>'
            f'<div><b>Metas:</b> <span id="gg">{html.escape(d.get("gym_goals") or "(nenhuma)")}</span></div>'
            f'<div><b>Alterações ao plano:</b><ul id="ga">{adj}</ul></div>'
            f'<div id="gl" style="margin:8px 0">{log}</div>'
            '<input id="gm" placeholder="Diz as tuas metas ou alterações ao treino…" style="width:75%" maxlength="800"><button type="button" onclick="gsend()">Enviar</button>'
            '<div style="color:#aaa;font-size:12px">Este chat só regista metas e alterações do Gym.</div></div><script>const GYM_CHAT_URL=' + json.dumps(url) + ';</script>' + GYM_CHAT_JS)


def _plans_from_gym():
    """Treinos A/B/C a partir do plano real do Gym (GYM_PLAN), sem as series/repeticoes."""
    out = {}
    for h2, body in re.findall(r"<h2>(Treino [A-Z] \(.*?)</h2>(.*?)</div>", GYM_PLAN, flags=re.S):
        flat = []
        for li in re.findall(r"<li>(.*?)</li>", body, flags=re.S):
            t = re.sub(r"<[^>]+>", "", li); ab = t.startswith("Abdominais:")
            t = re.sub(r"^Abdominais:\s*", "", t)
            for x in (t.split(" e ") if ab else [t]):
                x = re.sub(r"\s*:\s*\d.*$", "", x); x = re.sub(r"\s+\d.*$", "", x).strip()
                if x: flat.append(x[0].upper() + x[1:60])
        if flat: out[re.sub(r"<[^>]+>", "", h2)] = flat[:10]
    return out

def _plans_from_m(m):
    out = {}
    for t in (m.get("plan") or {}).get("treinos", []):
        ex = [re.sub(r"\s*:\s*\d.*$", "", e).strip()[:60] for e in t.get("exercicios", [])]
        if ex: out[str(t["nome"])[:50]] = [e for e in ex if e]
    return out

def tp_html(api, plans=None):
    plans = plans or {"Treino livre": ["Agachamento", "Supino", "Remada", "Press de ombros", "Prancha (s)"]}
    return open(os.path.join(HERE, "treino.html"), encoding="utf-8").read().replace("__API__", api).replace("__PLANS__", json.dumps(plans, ensure_ascii=False))

def tp_get(st):
    t = st.get("tplus", {})
    return {"sets": t.get("sets", []), "goal": t.get("goal"),
            "weights": [{"d": w["date"], "w": w["kg"]} for w in st.get("weights", []) if "date" in w and "kg" in w]}

def tp_put(st, j):
    sets = []
    for x in (j.get("sets") or [])[:5000]:
        try:
            datetime.date.fromisoformat(str(x["d"]))
            sets.append({"d": str(x["d"]), "t": int(x["t"]), "plan": str(x.get("plan", ""))[:60], "ex": str(x.get("ex", ""))[:60],
                         "kg": max(0.0, min(float(x.get("kg") or 0), 1000)), "reps": max(0, min(int(x["reps"]), 1000)),
                         "rpe": (max(1, min(int(x["rpe"]), 10)) if x.get("rpe") else None)})
        except (KeyError, ValueError, TypeError):
            continue
    ws = {}
    for x in (j.get("weights") or [])[:3000]:
        try:
            dd = datetime.date.fromisoformat(str(x["d"])).isoformat(); kg = round(float(x["w"]), 1)
            if 20 <= kg <= 250: ws[dd] = kg
        except (KeyError, ValueError, TypeError):
            continue
    try:
        goal = float(j["goal"]) if j.get("goal") else None
        if goal is not None and not 20 <= goal <= 250: goal = None
    except (ValueError, TypeError):
        goal = None
    st["tplus"] = {"sets": sets, "goal": goal}
    st["weights"] = [{"date": k, "kg": v} for k, v in sorted(ws.items())]

def rp_body(h):
    n = int(h.headers.get("Content-Length", 0) or 0)
    if n > 12_000_000: return None
    try: return json.loads(h.rfile.read(n).decode())
    except ValueError: return None

def md_post(h, store, saver, rel, back):
    """Fotos de progresso e tecnica (Gym). rel = photo | del | cmp | tech."""
    if rel == "del" or rel == "cmp":
        f = h.form()
        try: i = int(f.get("i", "-1"))
        except ValueError: i = -1
        if rel == "del":
            try: del store.get("photos", [])[i]
            except IndexError: pass
        else:
            try: media.compare(store, i)
            except Exception: pass
        saver(store); return h.redirect(back)
    j = rp_body(h)
    if not isinstance(j, dict): return h.send(400, json.dumps({"error": "pedido inválido"}))
    if rel == "photo":
        d = str(j.get("date", ""))
        try: datetime.date.fromisoformat(d)
        except ValueError: return h.send(400, json.dumps({"error": "data inválida"}))
        img = j.get("img")
        if not isinstance(img, str) or len(img) > 400000: return h.send(400, json.dumps({"error": "imagem inválida"}))
        media.add_photo(store, img, d, str(j.get("note", ""))); saver(store)
        return h.send(200, json.dumps({"ok": True}))
    if rel == "tech":
        mime = j.get("mime"); data = j.get("data")
        if mime not in ("image/jpeg", "video/mp4", "video/quicktime", "video/webm") or not isinstance(data, str):
            return h.send(400, json.dumps({"error": "ficheiro inválido (foto ou vídeo curto)"}))
        try: txt = media.technique(data, mime, str(j.get("exercise", ""))[:60])
        except Exception: return h.send(502, json.dumps({"error": "não consegui analisar, tenta outra foto"}))
        return h.send(200, json.dumps({"text": txt}))
    return h.send(404, "")

def rp_run(h, store, saver, ctx=""):
    j = rp_body(h)
    ok_mime = ("image/jpeg", "image/png", "image/webp", "application/pdf")
    if not j or j.get("mime") not in ok_mime or not isinstance(j.get("data"), str):
        return h.send(400, json.dumps({"error": "ficheiro inválido (usa foto ou PDF)"}))
    try:
        reports.put(store, reports.analyze(j["mime"], j["data"], ctx))
    except Exception as e:
        return h.send(502, json.dumps({"error": "não consegui ler o relatório, tenta outra foto"}))
    saver(store)
    return h.send(200, json.dumps({"ok": True}))

def tp_body(h):
    n = int(h.headers.get("Content-Length", 0) or 0)
    if n > 2_000_000: return None
    try: return json.loads(h.rfile.read(n).decode())
    except ValueError: return None


GYM_CSS = """<style>
body{background:#0f1115!important;max-width:760px!important}
.hero{background:linear-gradient(135deg,#17352b,#16233a);border-radius:18px;padding:18px;margin:6px 0 14px}
.hero h1{margin:0 0 4px;font-size:24px}.hero .sub{color:#9fb3c8;font-size:14px}
.stats3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}
.stat3{background:#0f1115aa;border-radius:12px;padding:10px;text-align:center}.stat3 span{display:block;color:#8b93a5;font-size:12px}.stat3 b{font-size:21px;color:#3ddc97}
.bar{height:10px;background:#0f1115;border-radius:8px;margin-top:12px;overflow:hidden}.bar i{display:block;height:100%;background:linear-gradient(90deg,#3ddc97,#4aa3ff)}
.cta{display:block;text-align:center;background:#3ddc97;color:#06210f;padding:14px;border-radius:14px;text-decoration:none;font-weight:700;font-size:17px;margin-bottom:14px}
details.box{background:#181b22;border:1px solid #2a2f3a;border-radius:14px;padding:0;margin:8px 0}
details.box>summary{cursor:pointer;padding:14px 16px;font-weight:600;font-size:16px;list-style:none;display:flex;justify-content:space-between}
details.box>summary:after{content:"▾";color:#8b93a5}details.box[open]>summary:after{content:"▴"}
details.box>.in{padding:0 16px 14px;color:#cfd5e2;line-height:1.5;font-size:14.5px}details.box ul{padding-left:20px}details.box li{margin:4px 0}
.box{background:#181b22!important;border:1px solid #2a2f3a;border-radius:14px!important;padding:14px!important}
.box h2{margin:0 0 10px;font-size:17px;color:#3ddc97}
table{font-size:14px}th{color:#8b93a5;font-weight:500}
input,select{background:#0c0e12!important;border:1px solid #2a2f3a!important;border-radius:10px!important;padding:10px!important}
button{background:#3ddc97!important;color:#06210f!important;font-weight:600;border-radius:10px!important;padding:10px 14px!important}
.green{color:#3ddc97}
</style>"""

def gym_plan_cards(html_):
    out=[];n=[0]
    def rep(m):
        n[0]+=1; op=" open" if n[0]<=2 else ""
        return f'<details class="box"{op}><summary>{m.group(1)}</summary><div class="in">{m.group(2)}</div></details>'
    return re.sub(r'<div class="box"><h2>(.*?)</h2>(.*?)</div>', rep, html_, flags=re.S)

def gym_page(d):
    today = datetime.date.today().isoformat()
    done_today = any(w["date"] == today for w in d.get("workouts", []))
    weights = sorted(d.get("weights", []), key=lambda w: w["date"], reverse=True)[:12]
    wrows = "".join(f"<tr><td>{w['date']}</td><td>{float(w['kg']):.1f} kg</td></tr>" for w in weights)
    last = weights[0]["kg"] if weights else None
    n_week = sum(1 for w in d.get("workouts", []) if (datetime.date.today() - datetime.date.fromisoformat(w["date"])).days < 7)
    status = ('<p class="green">Treino de hoje registado.</p>' if done_today else
              '<form method="post" action="/finance/gym/done"><button>Marcar treino de hoje como feito</button></form>')
    wk = float(last) if last else GYM_START
    prog = max(0, min(100, int((wk - GYM_START) / max(1.0, GYM_GOAL - GYM_START) * 100)))
    return page(GYM_CSS + f"""<div class="hero"><h1>💪 Gym</h1><div class="sub">Objetivo: de {GYM_START:.0f} para {GYM_GOAL:.0f} kg</div>
<div class="stats3"><div class="stat3"><span>Peso</span><b>{('%.1f kg' % last) if last else '–'}</b></div><div class="stat3"><span>Meta</span><b>{GYM_GOAL:.0f} kg</b></div><div class="stat3"><span>Treinos / semana</span><b>{n_week}/3</b></div></div>
<div class="bar"><i style="width:{prog}%"></i></div></div>
<a class="cta" href="/finance/gym/treino">▶ Abrir Treino+ (séries, descanso, peso)</a>
<div class="box"><h2>Registo de hoje</h2>{status}
<form method="post" action="/finance/gym/weight" style="margin-top:8px"><input type="number" step="0.1" name="kg" placeholder="peso em kg" required>
<input type="date" name="date" value="{today}" required><button>Registar peso</button></form>
<table><tr><th>Data</th><th>Peso</th></tr>{wrows}</table></div>
{reports.box(d, '/finance/gym/report')}{media.box(d, '/finance/gym', True)}
{gym_chat_box(d)}
<h2 style="margin:18px 0 4px">Plano</h2>{gym_plan_cards(GYM_PLAN)}""", "Gym")


def rec_box(d):
    rows = "".join(f"<tr><td>{html.escape(x['name'])}</td><td class='red'>{eur(float(x['amount']))}</td><td>dia {x['day']}</td>"
                   f"<td><form method='post' action='/finance/recurring/del' style='margin:0'><input type='hidden' name='i' value='{i}'><button>apagar</button></form></td></tr>"
                   for i, x in enumerate(d.get("recurring", [])))
    ropts = "".join(f"<option>{c}</option>" for c in CATS)
    return (f"""<div class="box"><h2>Despesas mensais</h2><table><tr><th>Despesa</th><th>Valor</th><th>Quando</th><th></th></tr>{rows}</table>
<form method="post" action="/finance/recurring/add"><input name="name" placeholder="Despesa (ex.: renda)" required><input type="number" step="0.01" name="amount" placeholder="Valor €" required><input type="number" name="day" min="1" max="31" placeholder="dia do mês" required><select name="category">{ropts}</select><button>Adicionar</button></form>
<div style="color:#aaa;font-size:12px">Todos os meses, nesse dia, recebes um aviso no Odysseus (3 dias antes, 1 dia antes e no próprio dia).</div></div>""")

def m_banner(m, mode):
    css = '<style>.lg{max-width:340px;margin:12vh auto 0}.lg h1{font-size:20px;margin:0 0 12px;text-align:center}.lg .box{padding:18px}.lg input{width:100%;box-sizing:border-box;margin:4px 0}.lg button{width:100%;margin:8px 0 0;padding:11px}</style>'
    if "pw" not in m:
        return (css + '<div class="lg"><h1>Cria a tua palavra-passe</h1><div class="box"><p style="color:#9aa3b2;font-size:13px;margin:0 0 6px">Esta área é só tua. Ninguém mais a vê, nem o administrador.</p>'
                '<form method="post" action="/finance/m/setpw"><input type="password" name="pw" placeholder="Nova palavra-passe (mín. 8)" minlength="8" required autofocus>'
                '<input type="password" name="pw2" placeholder="Repete a palavra-passe" minlength="8" required><button>Guardar</button></form></div></div>')
    return (css + '<div class="lg"><h1>🔒 Finanças</h1><div class="box"><form method="post" action="/finance/m/login">'
            '<input type="password" name="pw" placeholder="Palavra-passe" required autofocus><button>Entrar</button></form></div></div>')

def m_page(m, body, title):
    return page(f'<h1>{title} <a href="/finance/logout" style="font-size:14px;color:#aaa">sair</a></h1>' + body, title)


EX_GYM = ["Leg press", "Supino com halteres", "Puxada à frente", "Remada sentada", "Desenvolvimento com halteres",
          "Prancha", "Elevação pélvica", "Peso morto romeno (carga leve)", "Bicicleta", "Caminhada inclinada"]
EX_HOME = ["Agachamento com peso corporal", "Flexões (inclinadas se preciso)", "Remada com garrafas ou elástico",
           "Afundos", "Ponte de glúteos", "Prancha", "Elevação lateral com garrafas", "Peso morto com garrafas", "Caminhada rápida"]

def gen_plan(q):
    obj = q.get("objetivo", "saude"); nivel = q.get("nivel", "iniciante")
    dias = max(2, min(4, int(q.get("dias", "3") or 3)))
    dur = q.get("duracao", "45")
    ex = EX_GYM if q.get("equipamento") == "ginasio" else EX_HOME
    series, reps = {"massa": (3, "8-12"), "perder": (3, "12-15"), "saude": (2, "10-12"), "ansiedade": (2, "10-12")}.get(obj, (3, "10-12"))
    if nivel == "iniciante": series = max(2, series - 1)
    if nivel == "avancado": series += 1
    def pick(i, n):  # rotação de exercícios por treino
        return [ex[(i * 3 + k) % len(ex)] for k in range(n)]
    if dias == 2:
        nomes = ["Treino A (corpo inteiro)", "Treino B (corpo inteiro)"]
        grupos = [pick(0, 5), pick(1, 5)]
    elif dias == 3:
        nomes = ["Treino A (corpo inteiro)", "Treino B (corpo inteiro)", "Treino C (corpo inteiro)"]
        grupos = [pick(0, 5), pick(1, 5), pick(2, 5)]
    else:
        nomes = ["Superior (A)", "Inferior (A)", "Superior (B)", "Inferior (B)"]
        grupos = [pick(0, 5), pick(1, 5), pick(2, 5), pick(3, 5)]
    treinos = [{"nome": n, "exercicios": [f"{e}: {series} x {reps}" for e in g]} for n, g in zip(nomes, grupos)]
    notas = [f"Duração alvo: {dur} minutos por sessão. Aquece 5 minutos antes."]
    if obj == "perder": notas.append("Acrescenta 10 a 15 minutos de caminhada depois de cada treino.")
    if obj == "ansiedade": notas.append("Faz as séries com respiração calma e descanso de 60 a 90 segundos. Caminhada leve nos dias sem treino.")
    if obj == "massa": notas.append("Quando conseguires fazer todas as séries no topo do intervalo com boa técnica, aumenta a carga 2 a 5%.")
    if q.get("lesoes", "").strip(): notas.append("Tens limitações registadas: evita cargas máximas na zona afetada e mostra este plano a um profissional antes de começar.")
    if q.get("saude", "").strip(): notas.append("Tens condições de saúde ou medicação registadas: confirma o plano com o teu médico antes de começar.")
    resumo = f"{dias} treinos por semana, nível {nivel}, objetivo: {obj}."
    return {"resumo": resumo, "treinos": treinos, "notas": notas, "gerado": datetime.date.today().isoformat()}

def m_finance(m):
    total = sum(float(x["amount"]) for x in m["debts"])
    drows = "".join(f"<tr><td>{html.escape(x['name'])}</td><td class='red'>{eur(float(x['amount']))}</td>"
                    f"<td><form method='post' action='/finance/m/debt/del'><input type='hidden' name='i' value='{i}'><button>apagar</button></form></td></tr>"
                    for i, x in enumerate(m["debts"]))
    grows = "".join(f"<tr><td>{html.escape(x['name'])}</td><td>{eur(float(x['target']))}</td><td>{html.escape(x.get('deadline',''))}</td>"
                    f"<td><form method='post' action='/finance/m/goal/del'><input type='hidden' name='i' value='{i}'><button>apagar</button></form></td></tr>"
                    for i, x in enumerate(m["goals"]))
    mv = sorted(m["movements"], key=lambda x: x["date"], reverse=True)[:30]
    mrows = "".join(f"<tr><td>{x['date']}</td><td>{x['type']}</td><td>{html.escape(x['category'])}</td>"
                    f"<td class='{'red' if x['type']=='gasto' else 'green'}'>{eur(float(x['amount']))}</td><td>{html.escape(x.get('note',''))}</td></tr>" for x in mv)
    opts = "".join(f"<option>{c}</option>" for c in CATS)
    today = datetime.date.today().isoformat()
    rrows = "".join(f"<tr><td>{html.escape(x['name'])}</td><td class='red'>{eur(float(x['amount']))}</td><td>dia {x['day']}</td>"
                    f"<td><form method='post' action='/finance/m/recurring/del'><input type='hidden' name='i' value='{i}'><button>apagar</button></form></td></tr>"
                    for i, x in enumerate(m.get("recurring", [])))
    ropts = "".join(f"<option>{c}</option>" for c in CATS)
    return dash(m, "/finance/m") + f"""<div class="box"><h2>Despesas mensais</h2><table><tr><th>Despesa</th><th>Valor</th><th>Quando</th><th></th></tr>{rrows}</table>
<form method="post" action="/finance/m/recurring/add"><input name="name" placeholder="Despesa (ex.: renda)" required><input type="number" step="0.01" name="amount" placeholder="Valor €" required><input type="number" name="day" min="1" max="31" placeholder="dia do mês" required><select name="category">{ropts}</select><button>Adicionar</button></form>
<div style="color:#aaa;font-size:12px">Todos os meses, nesse dia, recebes um aviso no Odysseus (3 dias antes, 1 dia antes e no próprio dia).</div></div>
{RC_UI.replace("/finance/receipt", "/finance/m/receipt")}
<div class="box"><h2>Dívidas: <span class="red">{eur(total)}</span></h2><table>{drows}</table>
<form method="post" action="/finance/m/debt/add"><input name="name" placeholder="Nome" required><input type="number" step="0.01" name="amount" placeholder="Valor €" required><button>Adicionar dívida</button></form></div>
{chart(m)}
<div class="box"><h2>Novo movimento</h2><form id="nm" method="post" action="/finance/m/add">
<select name="type"><option value="gasto">gasto</option><option value="ganho">ganho</option></select>
<input type="number" step="0.01" name="amount" placeholder="valor €" required><select name="category">{opts}</select>
<input type="date" name="date" value="{today}" required><input name="note" placeholder="nota" maxlength="120"><button>Guardar</button></form></div>
<div class="box"><h2>Últimos movimentos</h2><table>{mrows}</table></div>"""

def m_gym_page(m):
    """Gym do membro: mesma estrutura do teu (cabecalho, registo de peso/treino, relatorios, fotos, chat, plano), sem glicose."""
    today = datetime.date.today().isoformat()
    ws = sorted(m.get("weights", []), key=lambda w: w["date"], reverse=True)[:12]
    wrows = "".join(f"<tr><td>{w['date']}</td><td>{float(w['kg']):.1f} kg</td></tr>" for w in ws)
    last = ws[0]["kg"] if ws else None
    goal = (m.get("tplus") or {}).get("goal")
    q = m.get("quiz") or {}
    dias = int(q.get("dias", 3) or 3)
    n_week = sum(1 for w in m.get("workouts", []) if (datetime.date.today() - datetime.date.fromisoformat(w["date"])).days < 7)
    done_today = any(w["date"] == today for w in m.get("workouts", []))
    status = ('<p class="green">Treino de hoje registado.</p>' if done_today else
              '<form method="post" action="/finance/m/gym/done"><button>Marcar treino de hoje como feito</button></form>')
    obj = {"massa": "Ganhar massa", "perder": "Perder peso", "saude": "Saúde geral", "ansiedade": "Reduzir ansiedade"}.get(q.get("objetivo"), "Define o teu objetivo no questionário")
    try: gv = float(goal) if goal else None
    except (TypeError, ValueError): gv = None
    prog = 0
    if last and gv and ws:
        first = float(sorted(m.get("weights", []), key=lambda w: w["date"])[0]["kg"])
        if gv != first: prog = max(0, min(100, int((float(last) - first) / (gv - first) * 100)))
    hero = (GYM_CSS + f"""<div class="hero"><h1>💪 Gym</h1><div class="sub">{obj}</div>
<div class="stats3"><div class="stat3"><span>Peso</span><b>{('%.1f kg' % last) if last else '–'}</b></div><div class="stat3"><span>Meta</span><b>{('%g kg' % gv) if gv else '–'}</b></div><div class="stat3"><span>Treinos / semana</span><b>{n_week}/{dias}</b></div></div>
<div class="bar"><i style="width:{prog}%"></i></div></div>
<div class="box"><h2>Registo de hoje</h2>{status}
<form method="post" action="/finance/m/gym/weight" style="margin-top:8px"><input type="number" step="0.1" name="kg" placeholder="peso em kg" required>
<input type="date" name="date" value="{today}" required><button>Registar peso</button></form>
<table><tr><th>Data</th><th>Peso</th></tr>{wrows}</table></div>""")
    cta = '<a class="cta" href="/finance/m/gym/treino">▶ Abrir Treino+ (séries, descanso, peso)</a>'
    plan_html, quiz_html = m_gym(m)
    return page(hero.replace('<div class="box"><h2>Registo de hoje</h2>', cta + '<div class="box"><h2>Registo de hoje</h2>', 1)
                + reports.box(m, "/finance/m/gym/report") + media.box(m, "/finance/m/gym")
                + gym_chat_box(m, "/finance/m/gym/chat") + plan_html + quiz_html, "Gym")

def m_gym(m):
    """Devolve (plano, questionario) no mesmo estilo do Gym do administrador."""
    q = m.get("quiz") or {}
    plan = m.get("plan")
    sel = lambda name, opts: f"<select name='{name}'>" + "".join(f"<option value='{v}'{' selected' if q.get(name)==v else ''}>{t}</option>" for v, t in opts) + "</select>"
    quiz = f"""<details class="box"{'' if plan else ' open'}><summary>{'Refazer questionário' if plan else 'Questionário'}</summary><div class="in"><form method="post" action="/finance/m/quiz">
<p>Objetivo: {sel('objetivo', [('massa','Ganhar massa'),('perder','Perder peso'),('saude','Saúde geral'),('ansiedade','Reduzir ansiedade')])}</p>
<p>Dias por semana: {sel('dias', [('2','2'),('3','3'),('4','4')])}</p>
<p>Nível: {sel('nivel', [('iniciante','Nunca treinei ou pouco'),('intermedio','Algum tempo'),('avancado','Treino há anos')])}</p>
<p>Onde treinas: {sel('equipamento', [('ginasio','Ginásio'),('casa','Em casa')])}</p>
<p>Duração por sessão: {sel('duracao', [('30','30 min'),('45','45 min'),('60','60 min')])}</p>
<p>Limitações físicas (lesões, dores): <br><textarea name="lesoes" rows="2" style="width:100%">{html.escape(q.get('lesoes',''))}</textarea></p>
<p>Condições de saúde ou medicação (opcional): <br><textarea name="saude" rows="2" style="width:100%">{html.escape(q.get('saude',''))}</textarea></p>
<button>Gerar plano</button></form></div></details>"""
    if not plan:
        return '<div class="box"><p>Responde ao questionário para gerar o teu plano.</p></div>', quiz
    cards = f'<div class="box"><h2>Resumo</h2><p>{html.escape(plan["resumo"])}</p><p style="color:#9aa3b2;font-size:12px">Gerado em {plan["gerado"]} · fonte: {html.escape(plan.get("fonte","regras"))}</p></div>'
    for t in plan["treinos"]:
        cards += f'<div class="box"><h2>{html.escape(t["nome"])}</h2><ul>' + "".join(f"<li>{html.escape(e)}</li>" for e in t["exercicios"]) + "</ul></div>"
    cards += '<div class="box"><h2>Notas</h2><ul>' + "".join(f"<li>{html.escape(n)}</li>" for n in plan["notas"]) + "</ul></div>"
    return '<h2 style="margin:18px 0 4px">Plano</h2>' + gym_plan_cards(cards), quiz


BRIDGE_URL = "http://127.0.0.1:8787/v1/chat/completions"
def _bridge_key():
    try:
        for line in open(secret_file("bridge")):
            if line.startswith("BRIDGE_API_KEY="):
                return line.strip().split("=", 1)[1].strip().strip('"')
    except FileNotFoundError:
        pass
    return ""

def ai_plan(q):
    """Plano gerado pelo Claude Haiku (via bridge), com pesquisa na web. Devolve None se falhar."""
    key = _bridge_key()
    if not key:
        return None
    dias = max(2, min(4, int(q.get("dias", "3") or 3)))
    prompt = (
        "Cria um plano de treino semanal personalizado em português de Portugal. "
        "Pesquisa na web boas práticas atuais para este perfil antes de escrever o plano. "
        f"Perfil: objetivo={q.get('objetivo')}, dias por semana={dias}, nível={q.get('nivel')}, "
        f"treina em={'ginásio' if q.get('equipamento')=='ginasio' else 'casa'}, duração por sessão={q.get('duracao')} minutos, "
        f"limitações físicas={q.get('lesoes') or 'nenhuma indicada'}, condições de saúde ou medicação={q.get('saude') or 'nenhuma indicada'}. "
        "Responde APENAS com JSON neste formato: "
        '{"resumo": "frase curta", "treinos": [{"nome": "Treino A", "exercicios": ["Exercício: 3 x 10-12", "..."]}], '
        '"notas": ["nota de segurança ou progressão", "..."]}. '
        "Usa entre 3 e 6 exercícios por treino. Se houver limitações ou condições de saúde, inclui nas notas que o plano deve ser validado com um profissional ou com o médico. "
        "Não inventes diagnósticos nem dosagens de medicação."
    )
    body = json.dumps({"model": "claude-code-haiku", "messages": [
        {"role": "system", "content": "És um treinador pessoal cauteloso. Respondes só com JSON válido."},
        {"role": "user", "content": prompt}]}).encode()
    try:
        req = urllib.request.Request(BRIDGE_URL, data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        out = json.load(urllib.request.urlopen(req, timeout=240))
        text = out["choices"][0]["message"]["content"]
        plan = json.loads(text[text.index("{"): text.rindex("}") + 1])
        treinos = [{"nome": str(t["nome"])[:80], "exercicios": [str(e)[:160] for e in t["exercicios"]][:8]} for t in plan["treinos"]]
        if not treinos or len(treinos) > 5:
            return None
        return {"resumo": str(plan.get("resumo", ""))[:300], "treinos": treinos,
                "notas": [str(n)[:300] for n in plan.get("notas", [])][:10], "gerado": datetime.date.today().isoformat(), "fonte": "Claude Haiku"}
    except Exception:
        return None

def read_receipt(b64):
    key = env(secret_file("gemini"))["GEMINI_API_KEY"]
    prompt = ("Lê este recibo/fatura. Responde só com JSON: "
      '{"amount": total pago em euros (número), "date": "AAAA-MM-DD" ou null, "merchant": "nome do estabelecimento", '
      '"category": uma de ' + json.dumps(CATS) + ', "note": "resumo curto em português de Portugal"}. '
      "Categorias: supermercado/mercearia=comida, café/restaurante=restaurantes, gasolina=combustivel, vestuário/calçado=roupa, "
      "luz/água/gás/internet=contas, farmácia=farmacia, consulta/exames=saude. Se não for legível, usa amount null.")
    def finish(o):
        if isinstance(o, list): o = o[0]
        amt = o.get("amount")
        if amt is None: return {"error": "Não encontrei o valor no recibo. Tenta outra foto."}
        cat = o.get("category") if o.get("category") in CATS else "outros"
        try: datetime.date.fromisoformat(o.get("date") or ""); dt = o["date"]
        except ValueError: dt = datetime.date.today().isoformat()
        note = (str(o.get("merchant") or "") + (" - " + str(o.get("note")) if o.get("note") else ""))[:120]
        return {"amount": round(float(amt), 2), "date": dt, "category": cat, "note": note}
    try:  # Groq primeiro (~0,6 s); o utilizador confirma sempre antes de guardar
        import groqv
        r = finish(json.loads(groqv.vision_json(prompt, b64)))
        if "amount" in r: return r
    except Exception:
        pass
    last = None
    for m in ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"):
        body = json.dumps({"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64}}]}],
                           "generationConfig": {"responseMimeType": "application/json"}}).encode()
        rq = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", body,
                                    {"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            r = json.load(urllib.request.urlopen(rq, timeout=60))
            return finish(json.loads(r["candidates"][0]["content"]["parts"][0]["text"]))
        except Exception as e:
            last = e
    raise RuntimeError(last)

RC_UI = r"""<div class="box"><h2>Foto do recibo</h2><input type="file" id="rc" accept="image/*" capture="environment" onclick="try{parent.postMessage('fin-keep','*')}catch(e){}"> <span id="rs"></span></div>
<script>
document.getElementById('rc').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;const st=document.getElementById('rs');st.textContent='A ler o recibo…';
try{const bm=await createImageBitmap(f);const k=Math.min(1,1600/Math.max(bm.width,bm.height));const c=document.createElement('canvas');c.width=bm.width*k;c.height=bm.height*k;c.getContext('2d').drawImage(bm,0,0,c.width,c.height);
const b64=c.toDataURL('image/jpeg',0.85).split(',')[1];const r=await fetch('/finance/receipt',{method:'POST',body:JSON.stringify({image:b64}),credentials:'same-origin'});const o=await r.json();
if(o.error){st.textContent=o.error;return}
const F=document.getElementById('nm');F.elements.type.value='gasto';F.elements.amount.value=o.amount;F.elements.category.value=o.category;F.elements.date.value=o.date;F.elements.note.value=o.note;st.textContent='Lido: confirma e carrega em Guardar.';}
catch(x){st.textContent='Erro: '+x}});</script>
"""

_RYOKU = {"0f1115":"#000000","0c0e12":"#000000","181b22":"#0a0a0a","1d2026":"#0a0a0a","262a31":"#141414","2a2e36":"#141414",
          "2a2f3a":"#3a3631","e8eaf0":"#cdc4ba","cfd5e2":"#cdc4ba","8b93a5":"#958f87","9aa3b2":"#958f87","7d8594":"#958f87",
          "3ddc97":"#ce5e32","17352b":"#0a0a0a","16233a":"#141414","4aa3ff":"#ce5e32","4a7bd0":"#ce5e32","06210f":"#000000",
          "70d080":"#6daf8c","5fd08a":"#6daf8c","4aa86b":"#6daf8c"}
_RYOKU_CSS = ("<style>@font-face{font-family:'Space Grotesk Variable';src:url(/static/ryoku/fonts/space-grotesk.woff2) format('woff2');font-weight:300 700}"
              "body,input,select,textarea,button{font-family:'Space Grotesk Variable',system-ui,sans-serif!important}"
              "h1,h2,h3{font-family:'Fraunces Variable',Georgia,serif;font-weight:500}"
              "@font-face{font-family:'Fraunces Variable';src:url(/static/ryoku/fonts/fraunces.woff2) format('woff2');font-weight:100 900}"
              "</style>")
def ryoku_skin(html):
    head = html[:300].lower()
    if "<!doctype" not in head and "<html" not in head: return html   # so documentos HTML (nao JSON, texto ou fragmentos AJAX)
    import re as _r
    html = _r.sub(r"border-radius:\s*(\d+)px", lambda m: "border-radius:%dpx" % (2 if int(m.group(1)) < 999 else int(m.group(1))), html)
    html = _r.sub(r"#([0-9a-fA-F]{6})\b", lambda m: _RYOKU.get(m.group(1).lower(), m.group(0)), html)
    if "</head>" in html: return html.replace("</head>", _RYOKU_CSS + "</head>", 1)
    m = _r.match(r"\s*<!doctype[^>]*>", html, _r.I)
    return html[:m.end()] + _RYOKU_CSS + html[m.end():] if m else _RYOKU_CSS + html


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def authed(self):
        c = self.headers.get("Cookie", "")
        for part in c.split(";"):
            if part.strip().startswith("fin="):
                ok = hmac.compare_digest(part.strip()[4:], _token()) and time.time() - _L()[0] < IDLE
                if ok:
                    _L()[0] = time.time()
                return ok
        return False

    def send(self, code, body, headers=None):
        _lang = i18n.from_cookie(self.headers.get("Cookie", ""))
        CUR.lang = _lang
        if "kittheme=ryoku" in (self.headers.get("Cookie") or "") and isinstance(body, str) and body[:1] not in "{[": body = ryoku_skin(body)
        if isinstance(body, str) and _lang != i18n.SOURCE:
            body = i18n.translate(body, _lang, "json" if body[:1] in "{[" else "html")
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)

    def setup_proxy(self, method):
        """Assistente de configuracao dentro do Odysseus: /setup/* -> wizard (127.0.0.1). So o administrador."""
        u = getattr(CUR, "u", None)
        if u != OWNER:
            return self.send(403, "Sem acesso." if method == "GET" else json.dumps({"error": "sem acesso"}))
        path = self.path.split("?", 1)[0]
        sub = path[len("/setup"):] or "/"
        if sub == "/" and path == "/setup":
            return self.redirect("/finance/setup/")
        try: tok = open(os.path.join(CONF_DIR, "wizard.token")).read().strip()
        except OSError: tok = ""
        n = int(self.headers.get("Content-Length") or 0)
        data = self.rfile.read(min(n, 200000)) if method == "POST" else None
        req = urllib.request.Request("http://127.0.0.1:%s%s" % (get("wizard_port", "8790"), sub), data=data, method=method,
                                     headers={"X-Kit-Setup-Token": tok, "Content-Type": self.headers.get("Content-Type", "application/json")})
        try:
            r = urllib.request.urlopen(req, timeout=20); body, code, ct = r.read(), r.status, r.headers.get("Content-Type", "text/html")
        except urllib.error.HTTPError as e:
            body, code, ct = e.read(), e.code, e.headers.get("Content-Type", "application/json")
        except Exception:
            return self.send(502, "O assistente nao esta a correr. No servidor: bash scripts/start.sh")
        if "text/html" in ct:
            body = i18n.translate(body.decode("utf-8", "replace"), i18n.from_cookie(self.headers.get("Cookie", ""))).encode()
        elif "json" in ct and sub != "/status":
            body = i18n.translate(body.decode("utf-8", "replace"), i18n.from_cookie(self.headers.get("Cookie", "")), "json").encode()
        self.send_response(code); self.send_header("Content-Type", ct); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def redirect(self, to, headers=None):
        self.send_response(303); self.send_header("Location", to)
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.send_header("Content-Length", "0"); self.end_headers()

    def form(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        return {k: v[0] for k, v in urllib.parse.parse_qs(self.rfile.read(min(n, 10000)).decode()).items()}

    def norm(self):
        p = self.path
        if p == PREFIX or p.startswith(PREFIX + "/"):
            p = p[len(PREFIX):] or "/"
        self.path = p


    def files_delete(self, user):
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            fid = os.path.basename(str(json.loads(self.rfile.read(min(n, 1000)))["id"]))
            d = os.path.join(SHARE_DIR, user); ip = os.path.join(d, "index.json")
            items = json.load(open(ip))
            keep = [it for it in items if it.get("id") != fid]
            if len(keep) == len(items): return self.send(200, json.dumps({"error": "Ficheiro não encontrado."}))
            try: os.remove(os.path.join(d, os.path.basename([it for it in items if it.get("id") == fid][0]["file"])))
            except FileNotFoundError: pass
            tmp = ip + ".tmp"; json.dump(keep, open(tmp, "w"), ensure_ascii=False, indent=1); os.replace(tmp, ip)
            return self.send(200, json.dumps({"ok": True}))
        except Exception as e:
            return self.send(200, json.dumps({"error": "Não consegui apagar (" + str(e)[:50] + ")."}))

    def m_gym_chat(self):
        m = mload()
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            msg = str(json.loads(self.rfile.read(min(n, 4000)))["message"]).strip()[:800]
            if not msg: raise ValueError
        except Exception:
            return self.send(200, json.dumps({"error": "Mensagem inválida."}))
        try:
            reply, goals, adj = gym_chat(m, msg, "member")
        except Exception as e:
            return self.send(200, json.dumps({"error": "Não consegui responder agora (" + str(e)[:60] + ")."}))
        m["gym_goals"] = goals; m["gym_adjust"] = adj
        m.setdefault("gym_chat", []).extend([{"r": "u", "t": msg}, {"r": "a", "t": reply}]); m["gym_chat"] = m["gym_chat"][-40:]
        msave(m)
        return self.send(200, json.dumps({"reply": reply, "goals": goals, "adjustments": adj}))

    def m_cookie_ok(self, m):
        c = self.headers.get("Cookie", "")
        for part in c.split(";"):
            if part.strip().startswith("finm="):
                return "pw" in m and hmac.compare_digest(part.strip()[5:], m_token(m))
        return False

    def m_get(self):
        m = mload(); p = self.path.rstrip("/")
        if p.startswith("/logout"):
            return self.redirect("/finance/", {"Set-Cookie": "finm=; Path=/finance; Max-Age=0; HttpOnly; Secure; SameSite=Strict"})
        if p == "/m/gym/treino":
            return self.send(200, tp_html(PREFIX + "/m/gym/treino/api", _plans_from_m(m)))
        if p == "/m/gym/treino/api":
            return self.send(200, json.dumps(tp_get(m)))
        if p in ("/m/gym", "/gym"):
            return self.send(200, m_gym_page(m))
        if "pw" not in m or not self.m_cookie_ok(m):
            return self.send(200, m_page(m, m_banner(m, "setup" if "pw" not in m else "login"), "membro"))
        if p == "/m/home" or p == "":
            return self.send(200, m_page(m, m_finance(m), "Finanças"))
        return self.send(404, page("não encontrado"))

    def m_post(self):
        m = mload(); f = self.form()
        back = "/finance/m/gym" if urllib.parse.urlsplit(self.headers.get("Referer", "")).path.rstrip("/").endswith("/gym") else "/finance/m/home"
        if self.path == "/m/setpw":
            if "pw" in m: return self.send(403, page("Já tens palavra-passe definida."))
            pw = f.get("pw", ""); pw2 = f.get("pw2", "")
            if len(pw) < 8 or pw != pw2:
                return self.send(200, m_page(m, '<p class="red">Palavras-passe diferentes ou com menos de 8 caracteres.</p><a href="/finance/m/home">voltar</a>', "membro"))
            salt = secrets.token_hex(16)
            m["pw"] = {"salt": salt, "hash": m_hash(pw, salt)}; msave(m)
            return self.redirect(back, {"Set-Cookie": f"finm={m_token(m)}; Path=/finance; Max-Age=600; HttpOnly; Secure; SameSite=Strict"})
        if self.path == "/m/login":
            if "pw" not in m: return self.redirect("/finance/m/home")
            if hmac.compare_digest(m_hash(f.get("pw", ""), m["pw"]["salt"]), m["pw"]["hash"]):
                return self.redirect(back, {"Set-Cookie": f"finm={m_token(m)}; Path=/finance; Max-Age=600; HttpOnly; Secure; SameSite=Strict"})
            return self.send(200, m_page(m, '<p class="red">Palavra-passe errada.</p><a href="/finance/m/home">voltar</a>', "membro"))
        if self.path == "/m/quiz":
            q = {k: f.get(k, "")[:500] for k in ("objetivo", "dias", "nivel", "equipamento", "duracao", "lesoes", "saude")}
            if q["objetivo"] not in ("massa", "perder", "saude", "ansiedade") or q["equipamento"] not in ("ginasio", "casa"):
                return self.send(200, m_page(m, '<p class="red">Respostas inválidas.</p>', "Gym"))
            m["quiz"] = q
            plan = ai_plan(q)
            if plan is None:
                plan = gen_plan(q); plan["fonte"] = "regras (IA indisponível)"
            m["plan"] = plan; msave(m)
            return self.redirect("/finance/m/gym")
        if not self.m_cookie_ok(m):
            return self.redirect("/finance/m/home")
        if self.path == "/m/recurring/add":
            try:
                day = int(f["day"]); amt = round(float(f["amount"].replace(",", ".")), 2)
                if not 1 <= day <= 31 or amt <= 0 or not f["name"].strip(): raise ValueError
            except (KeyError, ValueError): return self.send(200, m_page(m, '<p class="red">Dados inválidos.</p>', "Finanças"))
            m.setdefault("recurring", []).append({"name": f["name"].strip()[:60], "amount": amt, "day": day, "category": f.get("category") if f.get("category") in CATS else "outros"})
            msave(m); return self.redirect("/finance/m/home")
        if self.path == "/m/recurring/del":
            try: del m.setdefault("recurring", [])[int(f["i"])]
            except (KeyError, ValueError, IndexError): pass
            msave(m); return self.redirect("/finance/m/home")
        if self.path == "/m/debt/add":
            try: m["debts"].append({"name": f["name"][:60], "amount": round(float(f["amount"].replace(",", ".")), 2)})
            except (KeyError, ValueError): return self.send(200, m_page(m, '<p class="red">Dados inválidos.</p>', "Finanças"))
            msave(m); return self.redirect("/finance/m/home")
        if self.path == "/m/debt/del":
            try: del m["debts"][int(f["i"])]
            except (KeyError, ValueError, IndexError): pass
            msave(m); return self.redirect("/finance/m/home")
        if self.path == "/m/goal/add":
            try: m["goals"].append({"name": f["name"][:60], "target": round(float(f["target"].replace(",", ".")), 2), "deadline": f.get("deadline", "")})
            except (KeyError, ValueError): return self.send(200, m_page(m, '<p class="red">Dados inválidos.</p>', "Finanças"))
            msave(m); return self.redirect("/finance/m/home")
        if self.path == "/m/goal/del":
            try: del m["goals"][int(f["i"])]
            except (KeyError, ValueError, IndexError): pass
            msave(m); return self.redirect("/finance/m/home")
        if self.path == "/m/add":
            try:
                amount = round(float(f["amount"].replace(",", ".")), 2); date = datetime.date.fromisoformat(f["date"]).isoformat()
            except (KeyError, ValueError): return self.send(200, m_page(m, '<p class="red">Dados inválidos.</p>', "Finanças"))
            if amount <= 0 or f.get("type") not in ("gasto", "ganho") or f.get("category") not in CATS:
                return self.send(200, m_page(m, '<p class="red">Dados inválidos.</p>', "Finanças"))
            m["movements"].append({"date": date, "type": f["type"], "category": f["category"], "amount": amount, "note": f.get("note", "")[:120]})
            msave(m); return self.redirect("/finance/m/home")
        return self.send(404, page("não encontrado"))

    def read_json(self, limit):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n > limit: raise ValueError("demasiado grande")
        return json.loads(self.rfile.read(n) or b"{}")

    def glucose_post(self):
        p = self.path
        try:
            if p == "/glucose/dose":
                j = self.read_json(2000); g = j.get("glucose")
                return self.send(200, json.dumps(glucose.dose(None if g is None else float(g), float(j.get("carbs") or 0))))
            if p == "/glucose/log":
                j = self.read_json(20000); u = float(j["units"])
                if not 0 <= u <= 100: raise ValueError
                g = j.get("glucose"); c = j.get("carbs")
                kind = j.get("kind") if j.get("kind") in ("fiasp", "tresiba", "refeicao") else "fiasp"
                if kind == "refeicao": u = 0.0  # refeição pré-treino: sem insulina
                glucose.add_log(kind, u,
                                None if g is None else float(g), None if c is None else float(c), j.get("items") or [])
                return self.send(200, json.dumps({"ok": True}))
            if p == "/glucose/log_manual":
                j = self.read_json(3000)
                kind = j.get("kind") if j.get("kind") in ("fiasp", "tresiba") else "fiasp"
                u = float(j["units"])
                if not 0 < u <= (150 if kind == "tresiba" else 100): raise ValueError
                ts = glucose.parse_when(j["when"])
                g = j.get("glucose"); g = None if g in (None, "") else float(g)
                if g is None:
                    r = glucose.reading_near(ts); g = r["v"] if r else None
                if g is not None and not 20 <= g <= 600: raise ValueError
                c = j.get("carbs"); c = None if c in (None, "") else float(c)
                if c is not None and not 0 <= c <= 500: raise ValueError
                glucose.add_manual(kind, u, ts, g, c, str(j.get("note") or "")[:60])
                return self.send(200, json.dumps({"ok": True}))
            if p == "/glucose/log_edit":
                j = self.read_json(3000)
                kind = j.get("kind") if j.get("kind") in ("fiasp", "tresiba") else "fiasp"
                u = float(j["units"])
                if not 0 < u <= (150 if kind == "tresiba" else 100): raise ValueError
                ts = glucose.parse_when(j["when"], 400)
                g = j.get("glucose"); g = None if g in (None, "") else float(g)
                if g is not None and not 20 <= g <= 600: raise ValueError
                c = j.get("carbs"); c = None if c in (None, "") else float(c)
                if c is not None and not 0 <= c <= 500: raise ValueError
                ok = glucose.edit_log(float(j["t"]), kind, u, ts, g, c, str(j.get("note") or "")[:60])
                return self.send(200, json.dumps({"ok": True} if ok else {"error": "Registo não encontrado."}))
            if p == "/glucose/log_del":
                j = self.read_json(500)
                return self.send(200, json.dumps({"ok": True} if glucose.del_log(float(j["t"])) else {"error": "Registo não encontrado."}))
            if p == "/glucose/meal":
                j = self.read_json(6_000_000); base64.b64decode(j["image"], validate=True)
                try: return self.send(200, json.dumps(glucose.read_meal(j["image"])))
                except Exception as e: return self.send(200, json.dumps({"error": "Não consegui analisar a foto: " + str(e)[:100]}))
            f = self.form()
            if p == "/glucose/add":
                v = float(f["v"].replace(",", "."))
                if not 20 <= v <= 600: raise ValueError
                glucose.merge([{"t": time.time(), "v": v}])
            elif p == "/glucose/basal":
                v = float(f["v"].replace(",", "."))
                if not 0 < v <= 150: raise ValueError
                with glucose.LOCK:
                    d = glucose.load(); d["basal"] = v; glucose.save(d)
                glucose.add_log("tresiba", v)
            else:
                return self.send(404, page("não encontrado"))
        except (ValueError, KeyError, TypeError):
            if p in ("/glucose/log_manual", "/glucose/log_edit", "/glucose/log_del", "/glucose/log"):
                return self.send(200, json.dumps({"error": "Valores inválidos: confirma a hora (até 30 dias atrás), as unidades e a glicose."}))
            return self.send(200, page('<p class="red">Valor inválido.</p><a href="/finance/glucose">voltar</a>'))
        return self.redirect("/finance/glucose")

    def do_GET(self):
        self.norm()
        u = who(self.headers); CUR.u = u
        if self.path.split("?")[0].rstrip("/") == "/prefs":
            if not u: return self.send(403, json.dumps({"error": "sem acesso"}))
            return self.send(200, json.dumps(extras.prefs_get(HUB, u), ensure_ascii=False))
        if self.path.split("?")[0].rstrip("/") == "/usage":          # barra de uso (todos os utilizadores com sessao)
            if not u: return self.send(403, json.dumps({"error": "sem acesso"}))
            return self.send(200, json.dumps(usage.get(), ensure_ascii=False))
        if self.path.split("?")[0].startswith("/setup"):
            return self.setup_proxy("GET")
        if self.path.split("?")[0].rstrip("/") == "/i18n.json":     # dicionario para o front-end (publico, sem dados pessoais)
            try: d = json.load(open(i18n.DICT_PATH, encoding="utf-8"))
            except Exception: d = {}
            b = json.dumps({"web": d.get("web", {})}, ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=300"); self.send_header("Content-Length", str(len(b))); self.end_headers()
            return self.wfile.write(b)
        if self.path.split("?")[0].rstrip("/") == "/lang":      # /lang?l=en|pt&next=/caminho  (define o idioma das paginas)
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            l = (q.get("l") or [""])[0]; nxt = (q.get("next") or ["/"])[0]
            if l not in i18n.SUPPORTED: return self.send(400, json.dumps({"error": "idioma invalido"}))
            if not nxt.startswith("/") or nxt.startswith("//"): nxt = "/"
            return self.redirect(nxt, {"Set-Cookie": i18n.cookie_header(l)})
        if self.path.startswith("/inbox") and u in (OWNER,) + MLIKE:
            return inbox.get(self, u)
        if u in (OWNER,) + MLIKE and self.path.split("?")[0].rstrip("/") in ("/news", "/compose", "/flight", "/emails", "/prompt"):
            pth = self.path.split("?")[0].rstrip("/"); qq = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if pth == "/news": return self.send(200, page(extras.news_page(u, qq), "Notícias"))
            if pth == "/emails":
                sug = () if u == MEMBER else ()
                return self.send(200, page(extras.emails_page(self.headers.get("Cookie", ""), sug), "Emails"))
            if pth == "/compose": return self.send(200, page(study.CSS + extras.COMPOSE, "Compor"))
            if pth == "/prompt": return self.send(200, page(study.CSS + extras.PROMPT, "Prompts"))
            fq = re.sub(r"\s", "", (qq.get("q") or [""])[0]).upper()
            if fq and extras.FN.match(fq): return self.redirect(extras.flight_links(fq)[0][1])
            return self.send(200, page(extras.flight_page(u, "Número de voo inválido (ex: TP1234)." if fq else (qq.get("m") or [""])[0][:100]), "Voos"))
        if u in (OWNER,) + MLIKE and self.path.split("?")[0].rstrip("/") == "/study/apa.docx":
            return study.apa_docx(self, u)
        if u in (OWNER,) + MLIKE and self.path.split("?")[0].rstrip("/") == "/study":
            return study.get(self, u, page)
        if u in (OWNER,) + MLIKE and self.path.split("?")[0].rstrip("/") == "/routine":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self.send(200, page(study.nav("plan") + routine.render(u, (q.get("m") or [""])[0][:200]), "Rotina"))
        if u in MLIKE and self.path.rstrip("/") in ("/glucose", "/glucose/history"):
            return self.send(200, glucose.render_history(page))
        if u == MEMBER or self.path.startswith("/m/"):
            if u not in MLIKE:
                return self.send(200, page('<p class="red">Abre esta área com a tua conta do Odysseus.</p>'))
            return self.m_get()
        if u not in (OWNER, SBX):
            return self.send(200, page('<p class="red">Abre as Finanças ou o Gym a partir do Odysseus, com a tua conta.</p>'))
        if self.path.startswith("/logout"):
            _L()[0] = 0
            return self.redirect("/finance/", {"Set-Cookie": "fin=; Path=/finance; Max-Age=0; HttpOnly; Secure; SameSite=Strict"})
        if self.path.rstrip('/') == '/gym/treino':
            return self.send(200, tp_html(PREFIX + "/gym/treino/api", _plans_from_gym()))
        if self.path.rstrip('/') == '/gym/treino/api':
            return self.send(200, json.dumps(tp_get(load())))
        if self.path.rstrip('/') == '/gym':
            return self.send(200, gym_page(load()))
        if self.path.split("?")[0].rstrip('/') == '/glucose/at':
            try:
                w = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("when", [""])[0]
                ts = glucose.parse_when(w); r = glucose.reading_near(ts)
                if not r: return self.send(200, json.dumps({"v": None}))
                hm = datetime.datetime.fromtimestamp(r["t"], glucose._tz()).strftime("%H:%M")
                return self.send(200, json.dumps({"v": r["v"], "hm": hm, "dmin": int(abs(r["t"] - ts) / 60)}))
            except (ValueError, KeyError):
                return self.send(200, json.dumps({"v": None}))
        if self.path.rstrip('/') == '/glucose/now':
            return self.send(200, json.dumps(glucose.now_json()))
        if self.path.rstrip('/') == '/glucose':
            return self.send(200, glucose.render(page))
        if not self.authed():
            return self.send(200, page(f"""<style>.lg{{max-width:340px;margin:12vh auto 0}}.lg h1{{font-size:20px;margin:0 0 12px;text-align:center}}.lg .box{{padding:18px}}.lg input{{width:100%;box-sizing:border-box;margin:4px 0}}.lg button{{width:100%;margin:8px 0 0;padding:11px}}</style><div class="lg"><h1>🔒 Finanças</h1><form method="post" action="/finance/login" class="box">
<input type="password" name="pw" placeholder="Palavra-passe" autofocus required><button>Entrar</button></form></div>"""))
        d = load(); today = datetime.date.today().isoformat()
        debts = d["debts"]; total = sum(float(x["amount"]) for x in debts)
        rows = "".join(f"<tr><td>{html.escape(x['name'])}</td><td class='red'>{eur(float(x['amount']))}</td>"
                       f"<td><form method='post' action='/finance/debt/due' style='margin:0'><input type='hidden' name='i' value='{i}'>"
                       f"<input name='day' size='2' inputmode='numeric' placeholder='dia' value='{html.escape(str(x.get('due_day') or ''))}' title='Dia do mês do vencimento (1-31), vazio = sem aviso'><button>OK</button></form></td></tr>"
                       for i, x in enumerate(debts))
        mv = sorted(d["movements"], key=lambda m: m["date"], reverse=True)[:30]
        mrows = "".join(f"<tr><td>{m['date']}</td><td>{m['type']}</td><td>{html.escape(m['category'])}</td>"
                        f"<td class='{'red' if m['type']=='gasto' else 'green'}'>{eur(float(m['amount']))}</td>"
                        f"<td>{html.escape(m.get('note',''))}</td></tr>" for m in mv)
        opts = "".join(f"<option>{c}</option>" for c in CATS)
        body = f"""<h1>Finanças <a href="/finance/logout" style="font-size:14px;color:#aaa">sair</a></h1>
{dash(d)}
<div class="box"><h2>Dívidas: <span class="red">{eur(total)}</span></h2><table><tr><th>Nome</th><th>Valor</th><th>Vence dia</th></tr>{rows}</table><div style="color:#aaa;font-size:12px">Indica o dia do vencimento para receberes avisos 3 dias, 1 dia e no próprio dia.</div></div>
{rec_box(d)}
{chart(d)}
{RC_UI}
<div class="box"><h2>Novo movimento</h2><form id="nm" method="post" action="/finance/add">
<select name="type"><option value="gasto">gasto</option><option value="ganho">ganho</option></select>
<input type="number" step="0.01" name="amount" placeholder="valor €" required>
<select name="category">{opts}</select>
<input type="date" name="date" value="{today}" required>
<input name="note" placeholder="nota (opcional)" maxlength="120"><button>Guardar</button></form></div>
<div class="box"><h2>Últimos movimentos</h2><table><tr><th>Data</th><th>Tipo</th><th>Categoria</th><th>Valor</th><th>Nota</th></tr>{mrows}</table></div>"""
        self.send(200, page(body))

    def do_POST(self):
        self.norm()
        u = who(self.headers); CUR.u = u
        if self.path.split("?")[0].rstrip("/") == "/prefs":
            if not u: return self.send(403, json.dumps({"error": "sem acesso"}))
            try: body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 20000)) or b"{}")
            except ValueError: return self.send(400, json.dumps({"error": "pedido invalido"}))
            return self.send(200, json.dumps(extras.prefs_set(HUB, u, body if isinstance(body, dict) else {}), ensure_ascii=False))
        if self.path.split("?")[0].startswith("/setup"):
            return self.setup_proxy("POST")
        if self.path.startswith("/inbox") and u in (OWNER,) + MLIKE:
            return inbox.post(self, u)
        if u in (OWNER,) + MLIKE and self.path.split("?")[0] in ("/news/save", "/news/digest", "/compose/draft", "/prompt/gen", "/flight/add", "/flight/del", "/flight/status", "/emails/add", "/emails/del"):
            pth = self.path.split("?")[0]
            try:
                if pth in ("/emails/add", "/emails/del"):
                    j = self.read_json(4000); ck = self.headers.get("Cookie", "")
                    return self.send(200, json.dumps(extras.emails_add(ck, j) if pth == "/emails/add" else extras.emails_del(ck, j)))
                if pth == "/prompt/gen":
                    return self.send(200, json.dumps(extras.prompt_gen(self.read_json(6000)), ensure_ascii=False))
                if pth in ("/news/digest", "/compose/draft"):
                    j = self.read_json(4000)
                    return self.send(200, json.dumps(extras.news_digest(u) if pth == "/news/digest" else extras.compose_draft(j)))
                n = int(self.headers.get("Content-Length", 0) or 0)
                f = urllib.parse.parse_qs(self.rfile.read(min(n, 20000)).decode())
                if pth == "/news/save": extras.news_save(u, f); return self.redirect(PREFIX + "/news")
                msg = extras.flight_add(u, f) if pth == "/flight/add" else (extras.flight_refresh(u, f) if pth == "/flight/status" else extras.flight_del(u, f))
                return self.redirect(PREFIX + "/flight" + ("?m=" + urllib.parse.quote(msg) if msg else ""))
            except ValueError as e:
                return self.send(200, json.dumps({"error": str(e)[:150]}))
            except Exception as e:
                return self.send(200, json.dumps({"error": "A IA não respondeu (%s). Tenta outra vez." % str(e)[:60]}))
        if self.path == "/files/delete" and u:
            return self.files_delete(re.sub(r"[^a-z0-9_-]", "", str(u).lower()))
        if u in (OWNER,) + MLIKE and self.path.startswith("/study/"):
            return study.post(self, u)
        if u in (OWNER,) + MLIKE and self.path.startswith("/routine/"):
            msg = routine.post(u, self.path.split("?")[0], self.form())
            return self.redirect("/finance/routine" + ("?m=" + urllib.parse.quote(msg) if msg else ""))
        if u == MEMBER or self.path.startswith("/m/"):
            if u not in MLIKE:
                return self.send(403, page("Sem acesso."))
            if self.path == "/m/gym/chat":
                return self.m_gym_chat()
            if self.path == "/m/gym/done":
                m = mload(); today = datetime.date.today().isoformat()
                if not any(w["date"] == today for w in m.setdefault("workouts", [])):
                    m["workouts"].append({"date": today, "done": True}); msave(m)
                return self.redirect("/finance/m/gym")
            if self.path == "/m/gym/weight":
                f = self.form()
                try:
                    kg = round(float(f["kg"].replace(",", ".")), 1); date = datetime.date.fromisoformat(f["date"]).isoformat()
                    if not 20 <= kg <= 250: raise ValueError
                except (KeyError, ValueError):
                    return self.send(200, page('<p class="red">Peso inválido.</p><a href="/finance/m/gym">voltar</a>'))
                m = mload(); m.setdefault("weights", []).append({"date": date, "kg": kg}); msave(m)
                return self.redirect("/finance/m/gym")
            if self.path in ("/m/gym/photo", "/m/gym/photo/del", "/m/gym/photo/cmp", "/m/gym/tech"):
                m = mload(); return md_post(self, m, msave, self.path.rsplit("/", 1)[1], "/finance/m/gym")
            if self.path == "/m/gym/report":
                m = mload(); return rp_run(self, m, msave)
            if self.path == "/m/gym/report/del":
                m = mload(); f = self.form()
                try: del m.get("reports", [])[int(f.get("i", "-1"))]
                except (ValueError, IndexError): pass
                msave(m); return self.redirect("/finance/m/gym")
            if self.path == "/m/gym/treino/api":
                j = tp_body(self)
                if j is None: return self.send(400, json.dumps({"error": "pedido inválido"}))
                m = mload(); tp_put(m, j); msave(m)
                return self.send(200, json.dumps({"ok": True}))
            if self.path == "/m/receipt":
                if not self.m_cookie_ok(mload()):
                    return self.send(403, json.dumps({"error": "sessão expirada"}))
                n = int(self.headers.get("Content-Length", 0) or 0)
                if n > 6_000_000: return self.send(413, json.dumps({"error": "imagem demasiado grande"}))
                try:
                    img = json.loads(self.rfile.read(n))["image"]; base64.b64decode(img, validate=True)
                    return self.send(200, json.dumps(read_receipt(img)))
                except Exception as e:
                    return self.send(200, json.dumps({"error": "Não consegui ler o recibo: " + str(e)[:120]}))
            if self.path == "/files/delete":
                return self.files_delete(u)
            return self.m_post()
        if u not in (OWNER, SBX) and self.path != "/login":
            return self.send(403, page("Sem acesso."))
        if u == SBX and self.path.startswith("/glucose"):
            return self.send(403, page("A conta de teste não escreve na glicose real."))
        if self.path == "/login":
            f = self.form()
            if hmac.compare_digest(f.get("pw", ""), _secret()):
                _L()[0] = time.time()
                return self.redirect("/finance/", {"Set-Cookie": f"fin={_token()}; Path=/finance; Max-Age=600; HttpOnly; Secure; SameSite=Strict"})
            return self.send(200, page('<p class="red">Palavra-passe errada.</p><p><a href="/" style="color:#aaa">voltar</a></p>'))
        if self.path == "/quick":
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                j = json.loads(self.rfile.read(min(n, 3000)))
                amount = round(float(str(j["amount"]).replace(",", ".")), 2)
                cat = j.get("category") if j.get("category") in CATS else "outros"
                if not 0 < amount < 100000: raise ValueError
            except Exception:
                return self.send(200, json.dumps({"error": "Valor inválido."}))
            try: dq = datetime.date.fromisoformat(str(j.get("date") or "")).isoformat()
            except ValueError: dq = datetime.date.today().isoformat()
            d = load(); d["movements"].append({"date": dq, "type": "gasto", "category": cat,
                                               "amount": amount, "note": str(j.get("note", ""))[:120]}); save(d)
            return self.send(200, json.dumps({"ok": True, "amount": amount, "category": cat}))
        if self.path == "/quick/read":
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                if n > 6_000_000: return self.send(413, json.dumps({"error": "imagem demasiado grande"}))
                img = json.loads(self.rfile.read(n))["image"]
                base64.b64decode(img, validate=True)
                return self.send(200, json.dumps(read_receipt(img)))
            except Exception as e:
                return self.send(200, json.dumps({"error": "Não consegui ler o talão: " + str(e)[:120]}))
        if self.path == "/files/delete":
            return self.files_delete(OWNER)
        if self.path.startswith("/glucose/"):
            return self.glucose_post()
        if self.path in ("/gym/photo", "/gym/photo/del", "/gym/photo/cmp", "/gym/tech"):
            if u != OWNER: return self.send(403, json.dumps({"error": "sem acesso"}))
            d = load(); return md_post(self, d, save, self.path.rsplit("/", 1)[1], "/finance/gym")
        if self.path == "/gym/report":
            if u != OWNER: return self.send(403, json.dumps({"error": "sem acesso"}))
            d = load(); return rp_run(self, d, save, "Tem diabetes e quer ganhar massa magra de forma saudável.")
        if self.path == "/gym/report/del":
            if u != OWNER: return self.send(403, "Sem acesso.")
            d = load(); f = self.form()
            try: del d.get("reports", [])[int(f.get("i", "-1"))]
            except (ValueError, IndexError): pass
            save(d); return self.redirect("/finance/gym")
        if self.path == "/gym/treino/api":
            if u != OWNER: return self.send(403, json.dumps({"error": "sem acesso"}))
            j = tp_body(self)
            if j is None: return self.send(400, json.dumps({"error": "pedido inválido"}))
            d = load(); tp_put(d, j); save(d)
            return self.send(200, json.dumps({"ok": True}))
        if not self.authed() and not self.path.startswith("/gym/"):
            return self.redirect("/finance/")
        if self.path == "/gym/chat":
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                msg = str(json.loads(self.rfile.read(min(n, 4000)))["message"]).strip()[:800]
                if not msg: raise ValueError
            except Exception:
                return self.send(200, json.dumps({"error": "Mensagem inválida."}))
            d = load()
            try:
                reply, goals, adj = gym_chat(d, msg)
            except Exception as e:
                return self.send(200, json.dumps({"error": "Não consegui responder agora (" + str(e)[:60] + ")."}))
            d["gym_goals"] = goals; d["gym_adjust"] = adj
            d.setdefault("gym_chat", []).extend([{"r": "u", "t": msg}, {"r": "a", "t": reply}]); d["gym_chat"] = d["gym_chat"][-40:]
            save(d)
            return self.send(200, json.dumps({"reply": reply, "goals": goals, "adjustments": adj}))
        if self.path == "/debt/due":
            f = self.form()
            try:
                i = int(f["i"]); day = f.get("day", "").strip()
                d = load()
                if day == "": d["debts"][i].pop("due_day", None)
                else:
                    day = int(day)
                    if not 1 <= day <= 31: raise ValueError
                    d["debts"][i]["due_day"] = day
                save(d)
            except (KeyError, ValueError, IndexError):
                return self.send(200, page('<p class="red">Dia inválido.</p><a href="/finance/">voltar</a>'))
            return self.redirect("/finance/")
        if self.path == "/recurring/add":
            f = self.form()
            try:
                day = int(f["day"]); amt = round(float(f["amount"].replace(",", ".")), 2)
                if not 1 <= day <= 31 or amt <= 0 or not f["name"].strip(): raise ValueError
            except (KeyError, ValueError):
                return self.send(200, page('<p class="red">Dados inválidos.</p><a href="/finance/">voltar</a>'))
            d = load(); d.setdefault("recurring", []).append({"name": f["name"].strip()[:60], "amount": amt, "day": day,
                                                              "category": f.get("category") if f.get("category") in CATS else "outros"})
            save(d); return self.redirect("/finance/")
        if self.path == "/recurring/del":
            f = self.form()
            try:
                d = load(); del d.setdefault("recurring", [])[int(f["i"])]; save(d)
            except (KeyError, ValueError, IndexError): pass
            return self.redirect("/finance/")
        if self.path == "/gym/done":
            d = load(); today = datetime.date.today().isoformat()
            if not any(w["date"] == today for w in d.setdefault("workouts", [])):
                d["workouts"].append({"date": today, "done": True}); save(d)
            return self.redirect("/finance/gym")
        if self.path == "/gym/weight":
            f = self.form()
            try:
                kg = round(float(f["kg"].replace(",", ".")), 1); date = datetime.date.fromisoformat(f["date"]).isoformat()
            except (KeyError, ValueError):
                return self.send(200, page('<p class="red">Peso inválido.</p><a href="/finance/gym">voltar</a>'))
            if not 20 <= kg <= 250:
                return self.send(200, page('<p class="red">Peso fora do intervalo.</p><a href="/finance/gym">voltar</a>'))
            d = load(); d.setdefault("weights", []).append({"date": date, "kg": kg}); save(d)
            return self.redirect("/finance/gym")
        if self.path == "/receipt":
            if not self.authed():
                return self.send(403, json.dumps({"error": "sessão expirada"}))
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n > 6_000_000:
                return self.send(413, json.dumps({"error": "imagem demasiado grande"}))
            try:
                img = json.loads(self.rfile.read(n))["image"]
                base64.b64decode(img, validate=True)
                out = read_receipt(img)
            except Exception as e:
                return self.send(200, json.dumps({"error": "Não consegui ler o recibo: " + str(e)[:120]}))
            return self.send(200, json.dumps(out))
        if self.path in ("/goal/add", "/goal/del"):
            f = self.form(); d = load(); d.setdefault("goals", [])
            try:
                if self.path == "/goal/add":
                    d["goals"].append({"name": f["name"][:60], "target": round(float(f["target"].replace(",", ".")), 2), "deadline": f.get("deadline", "")})
                else: del d["goals"][int(f["i"])]
            except (KeyError, ValueError, IndexError): pass
            save(d); return self.redirect("/finance/")
        if self.path == "/add":
            f = self.form()
            try:
                amount = round(float(f["amount"].replace(",", ".")), 2)
                date = datetime.date.fromisoformat(f["date"]).isoformat()
            except (KeyError, ValueError):
                return self.send(200, page('<p class="red">Dados inválidos.</p><a href="/">voltar</a>'))
            if amount <= 0 or f.get("type") not in ("gasto", "ganho") or f.get("category") not in CATS:
                return self.send(200, page('<p class="red">Dados inválidos.</p><a href="/">voltar</a>'))
            d = load()
            d["movements"].append({"date": date, "type": f["type"], "category": f["category"],
                                   "amount": amount, "note": f.get("note", "")[:120]})
            save(d)
            return self.redirect("/finance/")
        self.send(404, page("não encontrado"))

if __name__ == "__main__":
    glucose.start_poller()
    ThreadingHTTPServer(("127.0.0.1", int(get("hub_port", 8792))), H).serve_forever()
