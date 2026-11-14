"""Estudo: ferramenta para trabalhos e pesquisa universitaria (so membro).
Cadeiras, trabalhos com etapas, fontes com citacao APA, notas, pomodoro, notas/medias e ajuda da IA (estruturar, resumir, citar, rever).
A IA ajuda a organizar e a entender; nao escreve o trabalho por ti."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import datetime, html, json, os, re, threading, time, urllib.error, urllib.parse, urllib.request, uuid
DIR = os.path.dirname(os.path.abspath(__file__))
LOCK = threading.Lock()
E = html.escape
STATUS = ["por começar", "pesquisa", "escrita", "revisão", "entregue"]
TYPES = ["trabalho", "relatório", "ensaio", "apresentação", "ficha", "exame", "leitura", "projeto"]
STYPES = ["artigo", "livro", "site", "capítulo", "outro"]
COLORS = ["#4a7bd0", "#d0714a", "#4aa86b", "#a04ad0", "#d0b84a", "#d04a7b", "#4ab8d0"]
PFX = "/finance"

import email.parser, email.policy, ipaddress, socket, subprocess
MAXUP = 15 * 1024 * 1024

def _safe_host(host):
    try:
        for fam, _, _, _, sa in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(sa[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip in ipaddress.ip_network("100.64.0.0/10"):
                return False
        return True
    except Exception:
        return False

class _NoPriv(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        u = urllib.parse.urlparse(newurl)
        if u.scheme not in ("http", "https") or not _safe_host(u.hostname or ""): raise ValueError("redirecionamento bloqueado")
        return super().redirect_request(req, fp, code, msg, hdrs, newurl)

def _ocr_pdf(b, pages=15):
    """PDF digitalizado: converte as primeiras paginas em imagem e le-as com o tesseract (pt+en)."""
    import tempfile, glob
    with tempfile.TemporaryDirectory() as td:
        pdf = os.path.join(td, "in.pdf"); open(pdf, "wb").write(b)
        subprocess.run(["pdftoppm", "-r", "170", "-l", str(pages), "-gray", "-png", pdf, os.path.join(td, "p")], capture_output=True, timeout=90)
        langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
        lang = "por+eng" if "por" in langs.split() else "eng"
        out = []
        for img in sorted(glob.glob(os.path.join(td, "p*.png"))):
            r = subprocess.run(["tesseract", img, "-", "-l", lang], capture_output=True, timeout=60)
            out.append(r.stdout.decode("utf-8", "replace"))
        return "\n\n".join(out)

def pdf_text(b):
    r = subprocess.run(["pdftotext", "-layout", "-l", "40", "-", "-"], input=b, capture_output=True, timeout=30)
    t = r.stdout.decode("utf-8", "replace")
    if len(t.strip()) < 50:                      # sem texto: provavelmente digitalizado
        try: t = _ocr_pdf(b)
        except Exception: pass
    return t

def clean_html(raw):
    raw = re.sub(r"(?is)<(script|style|nav|footer|header|noscript|svg)[^>]*>.*?</\1>", " ", raw)
    t = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    body = re.sub(r"(?s)<[^>]+>", " ", raw)
    body = re.sub(r"\s+", " ", html.unescape(body)).strip()
    return ((html.unescape(t.group(1)).strip() + "\n\n") if t else "") + body

def fetch_url(url):
    """Le um link (pagina ou PDF). Bloqueia enderecos internos."""
    u = urllib.parse.urlparse(url.strip())
    if u.scheme not in ("http", "https") or not u.hostname or not _safe_host(u.hostname): raise ValueError("link não permitido")
    req = urllib.request.Request(url.strip(), headers={"User-Agent": "Mozilla/5.0 (EstudoBot)"})
    with urllib.request.build_opener(_NoPriv).open(req, timeout=15) as r:
        data = r.read(MAXUP + 1)
        ct = (r.headers.get("Content-Type") or "").lower()
    if len(data) > MAXUP: raise ValueError("ficheiro demasiado grande")
    if "pdf" in ct or data[:4] == b"%PDF": return pdf_text(data)
    return clean_html(data.decode("utf-8", "replace"))

def read_form(h):
    """Devolve (campos, ficheiros) para urlencoded ou multipart."""
    n = int(h.headers.get("Content-Length", 0) or 0)
    ct = h.headers.get("Content-Type", "")
    if ct.startswith("multipart/form-data"):
        if n > MAXUP + 100000: raise ValueError("ficheiro demasiado grande (máx 15 MB)")
        raw = h.rfile.read(n)
        msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(b"Content-Type: " + ct.encode() + b"\r\n\r\n" + raw)
        f, files = {}, {}
        for part in msg.iter_parts():
            nm = part.get_param("name", header="content-disposition")
            fn = part.get_filename()
            if fn: files[nm] = part.get_payload(decode=True) or b""
            elif nm: f[nm] = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        return f, files
    return {k: v[0] for k, v in urllib.parse.parse_qs(h.rfile.read(min(n, 200000)).decode()).items()}, {}

def source_text(f, files):
    """Texto a partir de: ficheiro PDF/txt, link ou texto colado."""
    b = files.get("file")
    if b:
        t = pdf_text(b) if b[:4] == b"%PDF" else b.decode("utf-8", "replace")
        if len(t.strip()) < 50: raise ValueError("não consegui ler texto do ficheiro (PDF digitalizado?)")
        return t
    x = (f.get("text") or "").strip()
    if re.match(r"https?://\S+$", x): return fetch_url(x)
    if not x: raise ValueError("falta o texto, o link ou o PDF")
    return x

def _f(u): return os.path.join(DIR, "study-%s.json" % re.sub(r"[^a-z0-9]", "", u))
def load(u):
    try: d = json.load(open(_f(u)))
    except Exception: d = {}
    for k in ("courses", "tasks", "sources"): d.setdefault(k, [])
    return d
def save(u, d):
    t = _f(u) + ".tmp"
    with open(t, "w") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.chmod(t, 0o600); os.replace(t, _f(u))
def nid(): return uuid.uuid4().hex[:8]
def _date(s):
    try: return datetime.date.fromisoformat(s)
    except Exception: return None
def find(lst, i): return next((x for x in lst if x["id"] == i), None)

# ---------- IA (Groq, gratis e rapido) ----------
def _key():
    for l in open(secret_file("groq")):
        if l.startswith("GROQ_API_KEY="): return l.strip().split("=", 1)[1]
    raise RuntimeError("sem chave")
def ai(system, user, js=False, timeout=45):
    body = {"model": "qwen/qwen3.8-27b", "temperature": 0.3, "max_tokens": 1800,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user[:14000]}]}
    if js: body["response_format"] = {"type": "json_object"}
    rq = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", json.dumps(body).encode(),
        {"Content-Type": "application/json", "Authorization": "Bearer " + _key(), "User-Agent": "finance-tool/1.0"})
    for k in range(3):
        try: return json.load(urllib.request.urlopen(rq, timeout=timeout))["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or k == 2: raise
            time.sleep(3 + 4 * k)
PT = "Responde sempre em português de Portugal, de forma clara e curta. "

# ---------- Exportar APA para Word ----------
def _docx_bytes(refs):
    import zipfile, io
    X = lambda t: html.escape(t, quote=False)
    paras = ['<w:p><w:pPr><w:pStyle w:val="Title"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/></w:rPr><w:t>Referências</w:t></w:r></w:p>']
    for r in refs:
        runs = ""
        for i, part in enumerate(re.split(r"</?i>", r)):
            if not part: continue
            runs += "<w:r><w:rPr>%s</w:rPr><w:t xml:space=\"preserve\">%s</w:t></w:r>" % ("<w:i/>" if i % 2 else "", X(html.unescape(part)))
        paras.append('<w:p><w:pPr><w:spacing w:after="120" w:line="480" w:lineRule="auto"/><w:ind w:left="720" w:hanging="720"/></w:pPr>%s</w:p>' % runs)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           + "".join(paras) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults>'
              '<w:style w:type="paragraph" w:styleId="Title" w:name="Title"><w:rPr><w:sz w:val="28"/></w:rPr></w:style></w:styles>')
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/_rels/document.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr("word/document.xml", doc); z.writestr("word/styles.xml", styles)
    return bio.getvalue()

def apa_docx(h, u):
    with LOCK: d = load(u)
    srcs = sorted(d["sources"], key=lambda s: (s.get("authors") or s.get("title") or "").lower())
    if not srcs: return h.redirect(PFX + "/study?tab=sources&m=" + urllib.parse.quote("Ainda não há fontes para exportar."))
    b = _docx_bytes([apa(s) for s in srcs])
    h.send_response(200)
    h.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    h.send_header("Content-Disposition", 'attachment; filename="referencias-apa.docx"')
    h.send_header("Content-Length", str(len(b))); h.send_header("Cache-Control", "no-store"); h.end_headers(); h.wfile.write(b)

# ---------- APA ----------
def apa(s):
    names = []
    for a in [x.strip() for x in re.split(r";|\n", s.get("authors", "")) if x.strip()]:
        if "," in a:
            ln, fn = [p.strip() for p in a.split(",", 1)]
            ini = " ".join(w[0].upper() + "." for w in re.split(r"[\s-]+", fn) if w)
            names.append(f"{ln}, {ini}".strip(", "))
        else: names.append(a)
    au = names[0] if len(names) == 1 else (", ".join(names[:-1]) + ", & " + names[-1]) if names else ""
    yr = f"({s.get('year') or 's.d.'})"
    t, c, dt, url = s.get("title", ""), s.get("container", ""), s.get("details", ""), s.get("url", "")
    if s.get("type") == "artigo": core = f"{t}. <i>{E(c)}</i>" + (f", {E(dt)}" if dt else "") + "."
    elif s.get("type") in ("livro", "outro"): core = f"<i>{E(t)}</i>" + (f" ({E(dt)})" if dt else "") + "." + (f" {E(c)}." if c else "")
    elif s.get("type") == "capítulo": core = f"{E(t)}. In <i>{E(c)}</i>" + (f" ({E(dt)})" if dt else "") + "."
    else: core = f"<i>{E(t)}</i>." + (f" {E(c)}." if c else "")
    if s.get("type") in ("artigo",): core = E(t) + ". <i>" + E(c) + "</i>" + (f", {E(dt)}" if dt else "") + "."
    out = (f"{E(au)} " if au else "") + f"{yr}. {core}"
    if url: out += f" {E(url)}"
    return out

# ---------- paginas ----------
CSS = """<style>.nav{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px}.nav a{padding:7px 14px;border-radius:20px;background:#2a2e36;color:#ccc;text-decoration:none;font-size:14px}
.nav a.on{background:#4a7bd0;color:#fff}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
.card{background:#262a31;border-radius:12px;padding:12px;border-left:4px solid var(--c,#4a7bd0)}.mut{color:#9aa;font-size:12px}
.pill{display:inline-block;padding:2px 9px;border-radius:12px;background:#333;font-size:12px;margin:1px}.bar{height:6px;background:#333;border-radius:4px;overflow:hidden;margin:6px 0}
.bar i{display:block;height:100%;background:#4aa86b}.urg{color:#f07070}.warn{color:#e0b050}.pre{white-space:pre-wrap;background:#1d2026;padding:10px;border-radius:8px;font-size:14px;line-height:1.5}
textarea{width:100%;box-sizing:border-box;padding:8px;border-radius:6px;border:1px solid #444;background:#2a2e36;color:#eee;min-height:90px;font-family:inherit}
details summary{cursor:pointer;font-weight:600;margin:6px 0}.xs{padding:3px 8px;font-size:12px}.in{min-width:140px}</style>"""
def nav(tab):
    items = [("", "Painel"), ("tasks", "Trabalhos"), ("sources", "Fontes"), ("courses", "Cadeiras"), ("plan", "Planeador")]
    return CSS + "<div class='nav'>" + "".join(
        f"<a class='{'on' if tab == k else ''}' href='{PFX}/{'routine' if k == 'plan' else 'study' + ('?tab=' + k if k else '')}'>{n}</a>" for k, n in items) + "</div>"

def days_left(t):
    dl = _date(t.get("due", ""))
    return (dl - datetime.date.today()).days if dl else None
def due_html(t):
    n = days_left(t)
    if n is None: return "<span class='mut'>sem prazo</span>"
    cls = "urg" if n <= 2 else "warn" if n <= 7 else "mut"
    txt = "atrasado %d d" % -n if n < 0 else "hoje" if n == 0 else "amanhã" if n == 1 else "em %d dias" % n
    return f"<span class='{cls}'>{E(t['due'][8:]+'/'+t['due'][5:7])} · {txt}</span>"
def prog(t):
    st = t.get("steps", [])
    return int(100 * sum(1 for s in st if s["d"]) / len(st)) if st else (100 if t.get("status") == "entregue" else int(100 * STATUS.index(t.get("status", STATUS[0])) / (len(STATUS) - 1)))
def cname(d, cid):
    c = find(d["courses"], cid)
    return (c["name"], c["color"]) if c else ("Sem cadeira", "#666")
def card(d, t):
    n, col = cname(d, t.get("course"))
    return (f"<div class='card' style='--c:{col}'><a href='{PFX}/study?tab=task&t={t['id']}' style='color:#fff;text-decoration:none'><b>{E(t['title'])}</b></a><br>"
            f"<span class='pill'>{E(n)}</span><span class='pill'>{E(t.get('type',''))}</span><span class='pill'>{E(t.get('status',''))}</span><br>{due_html(t)}"
            f"<div class='bar'><i style='width:{prog(t)}%'></i></div></div>")
def fmt_min(m): return f"{m//60}h{m%60:02d}" if m >= 60 else f"{m} min"

def v_dash(d):
    act = sorted([t for t in d["tasks"] if t.get("status") != "entregue"], key=lambda t: (_date(t.get("due", "")) or datetime.date.max))
    spent = sum(int(t.get("spent", 0)) for t in d["tasks"])
    done = sum(1 for t in d["tasks"] if t.get("status") == "entregue")
    week = [t for t in act if (days_left(t) is not None and days_left(t) <= 7)]
    return (f"<h1>Estudo</h1><div class='grid'><div class='card'><b>{len(act)}</b><br><span class='mut'>trabalhos em curso</span></div>"
            f"<div class='card'><b>{len(week)}</b><br><span class='mut'>com prazo nos próximos 7 dias</span></div>"
            f"<div class='card'><b>{done}</b><br><span class='mut'>entregues</span></div>"
            f"<div class='card'><b>{fmt_min(spent)}</b><br><span class='mut'>de estudo registado</span></div></div>"
            f"<h2>Próximos prazos</h2><div class='grid'>{''.join(card(d, t) for t in act[:8]) or '<p class=mut>Sem trabalhos. Cria o primeiro em Trabalhos.</p>'}</div>"
            f"<h2>Fontes por ler</h2>" + ("<ul>" + "".join(f"<li>{apa(s)}</li>" for s in d['sources'] if not s.get('read'))[:3000] + "</ul>" if any(not s.get('read') for s in d['sources']) else "<p class=mut>Nada pendente.</p>"))

def course_opts(d, sel=""):
    return "<option value=''>— cadeira —</option>" + "".join(f"<option value='{c['id']}'{' selected' if c['id']==sel else ''}>{E(c['name'])}</option>" for c in d["courses"])

def v_tasks(d):
    flt = "".join(f"<option>{s}</option>" for s in TYPES)
    rows = ""
    for st in STATUS:
        ts = [t for t in d["tasks"] if t.get("status", STATUS[0]) == st]
        ts.sort(key=lambda t: (_date(t.get("due", "")) or datetime.date.max))
        if ts: rows += f"<h2>{st.capitalize()} <span class='mut'>({len(ts)})</span></h2><div class='grid'>{''.join(card(d, t) for t in ts)}</div>"
    return (f"<h1>Trabalhos</h1><div class='card'><form method='post' action='{PFX}/study/task_add'><input class='in' name='title' placeholder='Título do trabalho' required style='min-width:220px'>"
            f"<select name='course'>{course_opts(d)}</select><select name='type'>{flt}</select><input type='date' name='due'><button>Criar</button></form></div>{rows}")

def v_task(d, t, msg=""):
    n, col = cname(d, t.get("course"))
    srcs = [s for s in d["sources"] if s.get("task") == t["id"]]
    steps = "".join(f"<li><form method='post' action='{PFX}/study/step' style='display:inline'><input type='hidden' name='t' value='{t['id']}'><input type='hidden' name='i' value='{i}'>"
                    f"<button class='xs' style='background:{'#4aa86b' if s['d'] else '#444'}'>{'✓' if s['d'] else '○'}</button></form> "
                    f"<span style='{'opacity:.5;text-decoration:line-through' if s['d'] else ''}'>{E(s['t'])}</span> "
                    f"<form method='post' action='{PFX}/study/step_del' style='display:inline'><input type='hidden' name='t' value='{t['id']}'><input type='hidden' name='i' value='{i}'><button class='xs' style='background:#333'>×</button></form></li>"
                    for i, s in enumerate(t.get("steps", [])))
    stat = "".join(f"<option{' selected' if s == t.get('status') else ''}>{s}</option>" for s in STATUS)
    sl = "".join(f"<div class='card' style='margin:6px 0'>{apa(s)}<br><span class='mut'>{E(s.get('notes',''))}</span></div>" for s in srcs) or "<p class=mut>Sem fontes ligadas. Adiciona em Fontes.</p>"
    sid_opts = "".join(f"<option value='{s['id']}'>{E((s.get('title') or '')[:50])}</option>" for s in d["sources"])
    return (f"<p><a href='{PFX}/study?tab=tasks' style='color:#9ab'>← Trabalhos</a></p>{('<p>'+E(msg)+'</p>') if msg else ''}"
            f"<h1 style='border-left:5px solid {col};padding-left:10px'>{E(t['title'])}</h1><p><span class='pill'>{E(n)}</span><span class='pill'>{E(t.get('type',''))}</span> {due_html(t)} · "
            f"<span class='mut'>estudo registado: {fmt_min(int(t.get('spent',0)))}</span></p>"
            f"<div class='card'><form method='post' action='{PFX}/study/task_set'><input type='hidden' name='t' value='{t['id']}'>"
            f"<select name='status'>{stat}</select><select name='course'>{course_opts(d, t.get('course',''))}</select><input type='date' name='due' value='{E(t.get('due',''))}'>"
            f"<input name='grade' placeholder='nota (0-20)' value='{E(str(t.get('grade','')))}' style='width:110px'><input name='weight' placeholder='peso %' value='{E(str(t.get('weight','')))}' style='width:80px'><button>Guardar</button></form></div>"
            f"<div class='card' style='margin:10px 0'><h2>⏱ Foco (pomodoro)</h2><span id='pt' style='font-size:34px'>25:00</span> "
            f"<button type='button' onclick='pom()'>Iniciar 25 min</button><span class='mut'> no fim soma 25 min ao trabalho</span></div>"
            f"<script>var T=null,S=1500;function pom(){{if(T)return;T=setInterval(function(){{S--;document.getElementById('pt').textContent=String(Math.floor(S/60)).padStart(2,'0')+':'+String(S%60).padStart(2,'0');"
            f"if(S<=0){{clearInterval(T);fetch('{PFX}/study/spent',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:'t={t['id']}&m=25'}}).then(function(){{location.reload()}})}}}},1000)}}</script>"
            f"<h2>Etapas</h2><ul style='list-style:none;padding-left:0'>{steps}</ul><form method='post' action='{PFX}/study/step_add'><input type='hidden' name='t' value='{t['id']}'>"
            f"<input class='in' name='s' placeholder='Nova etapa' required style='min-width:220px'><button>Adicionar</button></form>"
            f"<h2>Estrutura</h2>{('<div class=pre>'+E(t['outline'])+'</div>') if t.get('outline') else '<p class=mut>Ainda sem estrutura.</p>'}"
            f"<h2>Ajuda da IA</h2><p class='mut'>Organiza, resume e revê. Não escreve o trabalho por ti, e convém verificar sempre o que ela diz.</p>"
            f"<div class='card'><form method='post' action='{PFX}/study/ai_outline'><input type='hidden' name='t' value='{t['id']}'><b>Estrutura e etapas</b> "
            f"<input class='in' name='brief' placeholder='o que pede o enunciado (opcional)' style='min-width:240px'><button>Gerar</button></form></div>"
            f"<div class='card' style='margin-top:8px'><form method='post' action='{PFX}/study/ai_summ' enctype='multipart/form-data'><input type='hidden' name='t' value='{t['id']}'><b>Resumir um texto, link ou PDF</b>"
            f"<textarea name='text' placeholder='Cola o texto OU um link (artigo, PDF online)'></textarea><label class='mut'>ou envia um PDF (até 15 MB): <input type='file' name='file' accept='.pdf,.txt'></label><br><select name='src'><option value=''>— guardar nas notas do trabalho —</option>{sid_opts}</select><button>Resumir</button></form></div>"
            f"<div class='card' style='margin-top:8px'><form method='post' action='{PFX}/study/ai_review'><input type='hidden' name='t' value='{t['id']}'><b>Rever o que escreveste</b>"
            f"<textarea name='text' placeholder='Cola o teu texto: dou feedback de clareza, estrutura e argumentos' required></textarea><button>Rever</button></form></div>"
            f"<h2>Notas</h2><form method='post' action='{PFX}/study/notes'><input type='hidden' name='t' value='{t['id']}'><textarea name='notes' style='min-height:200px'>{E(t.get('notes',''))}</textarea><button>Guardar notas</button></form>"
            f"<h2>Fontes deste trabalho</h2>{sl}"
            f"<form method='post' action='{PFX}/study/task_del' onsubmit=\"return confirm('Apagar este trabalho?')\" style='margin-top:20px'><input type='hidden' name='t' value='{t['id']}'><button style='background:#7a3a3a'>Apagar trabalho</button></form>")

def v_sources(d, q="", msg=""):
    ql = q.lower()
    ss = [s for s in d["sources"] if not ql or ql in json.dumps(s, ensure_ascii=False).lower()]
    tasks = "<option value=''>— trabalho —</option>" + "".join(f"<option value='{t['id']}'>{E(t['title'][:40])}</option>" for t in d["tasks"])
    rows = ""
    for s in ss:
        tt = find(d["tasks"], s.get("task", ""))
        rows += (f"<div class='card' style='margin:6px 0'>{apa(s)}<br><span class='mut'>{E(tt['title']) if tt else ''}</span>"
                 f"{('<div class=pre style=margin-top:6px>'+E(s['notes'])+'</div>') if s.get('notes') else ''}"
                 f"<form method='post' action='{PFX}/study/src_read' style='display:inline'><input type='hidden' name='s' value='{s['id']}'><button class='xs'>{'lida ✓' if s.get('read') else 'marcar como lida'}</button></form> "
                 f"<form method='post' action='{PFX}/study/src_del' style='display:inline' onsubmit=\"return confirm('Apagar?')\"><input type='hidden' name='s' value='{s['id']}'><button class='xs' style='background:#7a3a3a'>apagar</button></form></div>")
    allapa = "\n".join(html.unescape(re.sub("<[^>]+>", "", apa(s))) for s in sorted(d["sources"], key=lambda s: (s.get("authors") or s.get("title") or "").lower()))
    st = "".join(f"<option>{x}</option>" for x in STYPES)
    return (f"<h1>Fontes</h1>{('<p>'+E(msg)+'</p>') if msg else ''}"
            f"<div class='card'><form method='post' action='{PFX}/study/ai_cite' enctype='multipart/form-data'><b>Preencher com a IA</b> <span class='mut'>cola um link (lê a página), a referência, ou envia o PDF; confirma sempre os dados</span>"
            f"<textarea name='text' placeholder='ex: https://... ou Silva, A. (2020). Título...' style='min-height:60px'></textarea><label class='mut'>PDF: <input type='file' name='file' accept='.pdf'></label><select name='task'>{tasks}</select><button>Extrair dados</button></form></div>"
            f"<details><summary>+ Adicionar fonte à mão</summary><div class='card'><form method='post' action='{PFX}/study/src_add'>"
            f"<select name='type'>{st}</select><select name='task'>{tasks}</select><input class='in' name='authors' placeholder='Autores: Silva, Ana; Costa, Rui'><input name='year' placeholder='ano' style='width:70px'><br>"
            f"<input class='in' name='title' placeholder='Título' required style='min-width:260px'><input class='in' name='container' placeholder='Revista / editora / site'><input name='details' placeholder='vol(n), págs' style='width:120px'><br>"
            f"<input class='in' name='url' placeholder='Link ou DOI' style='min-width:260px'><textarea name='notes' placeholder='Notas e citações úteis' style='min-height:60px'></textarea><button>Guardar</button></form></div></details>"
            f"<form method='get' action='{PFX}/study'><input type='hidden' name='tab' value='sources'><input name='q' value='{E(q)}' placeholder='Pesquisar nas fontes' class='in'><button>Pesquisar</button></form>"
            f"{rows or '<p class=mut>Sem fontes.</p>'}"
            + (f"<p><a href='{PFX}/study/apa.docx'><button type='button'>Exportar referências para Word (.docx)</button></a></p>" + f"<details><summary>Lista de referências (APA), para copiar</summary><textarea readonly style='min-height:200px'>{E(allapa)}</textarea></details>" if allapa else ""))

def v_courses(d):
    cs = ""
    for c in d["courses"]:
        ts = [t for t in d["tasks"] if t.get("course") == c["id"]]
        gr = [(float(t["grade"]), float(t.get("weight") or 0)) for t in ts if str(t.get("grade", "")).strip()]
        w = sum(x[1] for x in gr)
        avg = (sum(g * p for g, p in gr) / w) if w else (sum(g for g, _ in gr) / len(gr) if gr else None)
        cs += (f"<div class='card' style='--c:{c['color']};margin:6px 0'><b>{E(c['name'])}</b> <span class='mut'>{E(c.get('prof',''))}</span><br>"
               f"{len(ts)} trabalhos, {sum(1 for t in ts if t.get('status')=='entregue')} entregues"
               + (f" · média <b>{avg:.1f}</b>/20" if avg is not None else "")
               + f" · {fmt_min(sum(int(t.get('spent',0)) for t in ts))} de estudo"
               f"<form method='post' action='{PFX}/study/course_del' style='display:inline;float:right' onsubmit=\"return confirm('Apagar a cadeira? Os trabalhos ficam.')\"><input type='hidden' name='c' value='{c['id']}'><button class='xs' style='background:#7a3a3a'>apagar</button></form></div>")
    return (f"<h1>Cadeiras</h1><div class='card'><form method='post' action='{PFX}/study/course_add'><input class='in' name='name' placeholder='Nome da cadeira' required>"
            f"<input class='in' name='prof' placeholder='Professor (opcional)'><button>Adicionar</button></form></div>{cs or '<p class=mut>Sem cadeiras.</p>'}")

def render(d, tab, q, tid, msg):
    if tab == "task" and find(d["tasks"], tid): return nav("tasks") + v_task(d, find(d["tasks"], tid), msg)
    body = {"tasks": v_tasks, "sources": lambda d: v_sources(d, q, msg), "courses": v_courses}.get(tab, v_dash)(d)
    return nav(tab if tab in ("tasks", "sources", "courses") else "") + (f"<p>{E(msg)}</p>" if msg and tab not in ("sources",) else "") + body

# ---------- handlers ----------
def get(h, u, page):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(h.path).query)
    g = lambda k: (q.get(k) or [""])[0]
    with LOCK: d = load(u)
    return h.send(200, page(render(d, g("tab"), g("q")[:100], g("t"), g("m")[:200]), "Estudo"))

def post(h, u):
    try: f, files = read_form(h)
    except ValueError as e: return h.redirect(PFX + "/study?m=" + urllib.parse.quote(str(e)))
    act = h.path.split("?")[0].rstrip("/").split("/")[-1]
    tab, tid, msg, ajax = "", "", "", False
    with LOCK:
        d = load(u)
    try:
        t = find(d["tasks"], f.get("t", ""))
        if t: tab, tid = "task", t["id"]
        elif act.startswith("src") or act == "ai_cite": tab = "sources"
        if act == "course_add":
            nm = f["name"].strip()[:60]
            if nm: d["courses"].append({"id": nid(), "name": nm, "prof": f.get("prof", "")[:60], "color": COLORS[len(d["courses"]) % len(COLORS)]})
            tab = "courses"
        elif act == "course_del":
            d["courses"] = [c for c in d["courses"] if c["id"] != f.get("c")]; tab = "courses"
        elif act == "task_add":
            dl = f.get("due", "")
            nt = {"id": nid(), "title": f["title"].strip()[:120], "course": f.get("course", ""), "type": f.get("type", "trabalho") if f.get("type") in TYPES else "trabalho",
                  "due": dl if _date(dl) else "", "status": STATUS[0], "steps": [], "notes": "", "spent": 0}
            d["tasks"].append(nt); tab, tid = "task", nt["id"]
        elif t and act == "task_set":
            if f.get("status") in STATUS: t["status"] = f["status"]
            t["course"] = f.get("course", "") if find(d["courses"], f.get("course", "")) else ""
            t["due"] = f.get("due", "") if _date(f.get("due", "")) else ""
            for k, hi in (("grade", 20), ("weight", 100)):
                v = f.get(k, "").replace(",", ".").strip()
                t[k] = str(min(float(v), hi)) if v and float(v) >= 0 else ""
            tab, tid = "task", t["id"]
        elif t and act == "task_del":
            d["tasks"] = [x for x in d["tasks"] if x["id"] != t["id"]]; d["sources"] = [s for s in d["sources"] if s.get("task") != t["id"]]; tab = "tasks"
        elif t and act == "step_add":
            if f.get("s", "").strip(): t["steps"].append({"t": f["s"].strip()[:150], "d": False})
            tab, tid = "task", t["id"]
        elif t and act in ("step", "step_del"):
            i = int(f["i"])
            if act == "step": t["steps"][i]["d"] = not t["steps"][i]["d"]
            else: del t["steps"][i]
            tab, tid = "task", t["id"]
        elif t and act == "notes":
            t["notes"] = f.get("notes", "")[:20000]; tab, tid, msg = "task", t["id"], "Notas guardadas."
        elif t and act == "spent":
            t["spent"] = int(t.get("spent", 0)) + max(1, min(180, int(f.get("m", 25)))); ajax = True
        elif t and act == "ai_outline":
            r = json.loads(ai(PT + "És um tutor universitário. Ajudas a organizar trabalhos, sem os escrever. Devolve JSON: {\"estrutura\": [\"secção: o que cobrir\"], \"etapas\": [\"passo concreto\"], \"perguntas\": [\"pergunta de pesquisa\"]}, com 4-8 itens em cada.",
                              f"Trabalho: {t['title']}\nTipo: {t.get('type')}\nCadeira: {cname(d, t.get('course'))[0]}\nEnunciado: {f.get('brief','')}", js=True))
            t["outline"] = "ESTRUTURA\n" + "\n".join("• " + str(x) for x in r.get("estrutura", [])) + "\n\nPERGUNTAS DE PESQUISA\n" + "\n".join("? " + str(x) for x in r.get("perguntas", []))
            for e in r.get("etapas", [])[:10]: t["steps"].append({"t": str(e)[:150], "d": False})
            tab, tid, msg = "task", t["id"], "Estrutura e etapas geradas. Ajusta ao enunciado."
        elif t and act == "ai_summ":
            r = ai(PT + "Resume o texto para estudo universitário: 1) resumo em 5 linhas; 2) ideias-chave em tópicos; 3) termos importantes; 4) 3 perguntas para testar a compreensão. Não inventes nada que não esteja no texto.", source_text(f, files)[:24000])
            s = find(d["sources"], f.get("src", ""))
            block = "\n\n— Resumo (" + datetime.date.today().strftime("%d/%m") + ") —\n" + r
            if s: s["notes"] = (s.get("notes", "") + block)[:20000]
            else: t["notes"] = (t.get("notes", "") + block)[:20000]
            tab, tid, msg = "task", t["id"], "Resumo guardado nas notas" + (" da fonte." if s else " do trabalho.")
        elif t and act == "ai_review":
            r = ai(PT + "Revê o texto de um estudante universitário. Dá feedback em 4 partes: clareza, estrutura, argumentos e língua (erros concretos). Sê construtivo e específico. Não reescrevas o texto todo.", f["text"])
            t["notes"] = (t.get("notes", "") + "\n\n— Revisão (" + datetime.date.today().strftime("%d/%m") + ") —\n" + r)[:20000]
            tab, tid, msg = "task", t["id"], "Feedback acrescentado às notas."
        elif act == "src_add":
            d["sources"].append({"id": nid(), "type": f.get("type") if f.get("type") in STYPES else "outro", "task": f.get("task", ""), "authors": f.get("authors", "")[:300], "year": f.get("year", "")[:6],
                                 "title": f["title"].strip()[:300], "container": f.get("container", "")[:200], "details": f.get("details", "")[:60], "url": f.get("url", "")[:400], "notes": f.get("notes", "")[:5000], "read": False})
            tab = "sources"
        elif act == "ai_cite":
            r = json.loads(ai(PT + "Extrai os dados bibliográficos do texto ou link. Devolve JSON: {\"type\": \"artigo|livro|site|capítulo|outro\", \"authors\": \"Apelido, Nome; Apelido, Nome\", \"year\": \"\", \"title\": \"\", \"container\": \"revista, editora ou site\", \"details\": \"volume(número), páginas\", \"url\": \"\"}. Se um dado não existir, deixa vazio. Nunca inventes autores ou anos.", ((("Link: " + f["text"].strip() + "\n\n") if f["text"].strip().startswith("http") else "") + source_text(f, files))[:12000], js=True))
            d["sources"].append({"id": nid(), "type": r.get("type") if r.get("type") in STYPES else "outro", "task": f.get("task", ""), "authors": str(r.get("authors", ""))[:300], "year": str(r.get("year", ""))[:6],
                                 "title": str(r.get("title", "") or f.get("text", "")[:80] or "Documento")[:300], "container": str(r.get("container", ""))[:200], "details": str(r.get("details", ""))[:60], "url": str(r.get("url", "") or (f.get("text", "") if f.get("text", "").startswith("http") else ""))[:400], "notes": "", "read": False})
            tab, msg = "sources", "Fonte adicionada com os dados extraídos. Confirma autores e ano na fonte original."
        elif act == "src_read":
            s = find(d["sources"], f.get("s", ""));
            if s: s["read"] = not s.get("read")
            tab = "sources"
        elif act == "src_del":
            d["sources"] = [s for s in d["sources"] if s["id"] != f.get("s")]; tab = "sources"
    except (KeyError, ValueError, IndexError):
        msg = "Dados inválidos."
    except Exception as e:
        msg = "A IA não respondeu (%s). Tenta outra vez." % str(e)[:60]
    with LOCK: save(u, d)
    if ajax: return h.send(200, "ok")
    q = "?tab=" + tab + ("&t=" + tid if tid else "") + ("&m=" + urllib.parse.quote(msg) if msg else "")
    return h.redirect(PFX + "/study" + q)
