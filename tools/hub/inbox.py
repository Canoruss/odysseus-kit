"""Caixa de ideias e problemas partilhada (administrador + membro): texto + fotos, organizado por IA em tarefas, com checklist."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import os, json, time, uuid, base64, html, re, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.environ.get("INBOX_DATA", os.path.join(HERE, "inbox.json"))
IMGDIR = os.environ.get("INBOX_IMG", os.path.join(HERE, "inbox-img"))
OWNER = OWNER
NAMES = {OWNER: "administrador", MEMBER: "membro", TESTER: "Conta de teste"}
PRIO = {"alta": 0, "média": 1, "media": 1, "baixa": 2}
CATS = {"bug": "🐞 Problema", "ideia": "💡 Ideia", "pergunta": "❓ Pergunta"}


def _load():
    try:
        return json.load(open(FILE))
    except (OSError, ValueError):
        return {"items": []}


def _save(d):
    tmp = FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, FILE)


def _gemini_key():
    for line in open(secret_file("gemini")):
        if line.startswith("GEMINI_API_KEY="):
            return line.strip().split("=", 1)[1]
    raise RuntimeError("sem chave Gemini")


def organize(text, images_b64):
    """Devolve lista de tarefas [{title, category, priority, details}]."""
    prompt = ("Organizas feedback sobre uma app e um servidor pessoal (Odysseus, Finanças, Gym, Tradução, Canva, app Android). "
              "Recebes a mensagem de uma utilizadora em texto livre (pode ter várias ideias ou problemas) e, às vezes, fotos (capturas de ecrã). "
              "Divide em tarefas separadas, uma por assunto. Responde só com um JSON array de objetos "
              '{"title": "título curto e claro em português de Portugal (máx. 70 caracteres)", '
              '"category": "bug" ou "ideia" ou "pergunta", "priority": "alta" ou "média" ou "baixa", '
              '"details": "o que a pessoa disse, resumido e sem inventar; refere o que se vê nas fotos"}. '
              "Não inventes factos. Se só houver fotos, descreve o que mostram.\n\nMensagem:\n" + (text or "(sem texto)"))
    parts = [{"text": prompt}] + [{"inline_data": {"mime_type": "image/jpeg", "data": b}} for b in images_b64[:6]]
    key = _gemini_key()
    last = None
    try:  # Groq primeiro; se falhar, Gemini
        import groqv
        o = json.loads(groqv.vision_multi(prompt + "\nResponde com um objeto JSON {\"tarefas\": [ ... ]}.", images_b64[:6], json_out=True))
        if isinstance(o, dict): o = o.get("tarefas") or o.get("tasks") or [o]
        out = []
        for t in o[:12]:
            title = str(t.get("title") or "").strip()[:90]
            if title:
                out.append({"title": title, "category": t.get("category") if t.get("category") in CATS else "ideia",
                            "priority": t.get("priority") if t.get("priority") in PRIO else "média",
                            "details": str(t.get("details") or "")[:1500]})
        if out: return out
    except Exception as e:
        last = e
    for m in ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"):
        body = json.dumps({"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json"}}).encode()
        rq = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", body,
                                    {"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            r = json.load(urllib.request.urlopen(rq, timeout=90))
            o = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
            if isinstance(o, dict):
                o = [o]
            out = []
            for t in o[:12]:
                title = str(t.get("title") or "").strip()[:90]
                if not title:
                    continue
                out.append({"title": title, "category": t.get("category") if t.get("category") in CATS else "ideia",
                            "priority": t.get("priority") if t.get("priority") in PRIO else "média",
                            "details": str(t.get("details") or "")[:1500]})
            if out:
                return out
        except Exception as e:
            last = e
    return [{"title": (text or "Mensagem com fotos").strip().split("\n")[0][:70], "category": "ideia", "priority": "média",
             "details": (text or "")[:1500] + ("\n(organização automática indisponível)" if last else "")}]


PAGE_CSS = """<style>
:root{--bg:#0f1115;--card:#181b22;--line:#2a2f3a;--txt:#e8eaf0;--mut:#8b93a5;--ac:#3ddc97}
*{box-sizing:border-box}body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--txt);margin:0;padding:14px;max-width:760px;margin:auto}
h1{font-size:22px;margin:4px 0 4px}h2{font-size:15px;color:var(--mut);margin:18px 0 8px;font-weight:600}
.sub{color:var(--mut);font-size:13px;margin-bottom:12px}
.box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin:10px 0}
textarea{width:100%;min-height:110px;background:#0c0e12;border:1px solid var(--line);color:var(--txt);border-radius:10px;padding:10px;font-size:16px;font-family:inherit}
button{background:var(--ac);color:#06210f;border:0;border-radius:10px;padding:11px 16px;font-size:16px;font-weight:600;cursor:pointer}
button.alt{background:#0c0e12;border:1px solid var(--line);color:var(--txt);font-size:14px;padding:7px 11px}
.thumbs{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.thumbs img{height:70px;border-radius:8px;border:1px solid var(--line)}
.task{display:flex;gap:10px;align-items:flex-start;padding:12px;border-bottom:1px solid var(--line)}.task:last-child{border:0}
.task .b{flex:1}.task .t{font-weight:600;font-size:15px}.task .d{color:#b8c0cf;font-size:13.5px;margin-top:3px;white-space:pre-wrap}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:20px;background:#0c0e12;border:1px solid var(--line);color:var(--mut);margin-right:5px}
.alta{color:#ff8b8b;border-color:#5a2f2f}.done .t{text-decoration:line-through;color:var(--mut)}
.chk{width:22px;height:22px;accent-color:var(--ac);margin-top:2px}.msg{color:var(--ac);font-size:14px;margin-top:8px;min-height:20px}
.timg img{height:64px;border-radius:8px;margin:6px 6px 0 0;border:1px solid var(--line)}
</style>"""

JS = r"""<script>
const BASE='/finance/inbox';let files=[];
const $=id=>document.getElementById(id);
$('ph').addEventListener('change',async e=>{
  for(const f of e.target.files){try{const bm=await createImageBitmap(f);const k=Math.min(1,1280/Math.max(bm.width,bm.height));
    const c=document.createElement('canvas');c.width=bm.width*k;c.height=bm.height*k;c.getContext('2d').drawImage(bm,0,0,c.width,c.height);
    const u=c.toDataURL('image/jpeg',0.8);files.push(u.split(',')[1]);const im=new Image();im.src=u;$('th').appendChild(im);}catch(_){}}
  e.target.value='';});
$('send').onclick=async()=>{
  const t=$('tx').value.trim();if(!t&&!files.length){$('ms').textContent='Escreve algo ou junta uma foto.';return}
  $('send').disabled=true;$('ms').textContent='A enviar e a organizar…';
  try{const r=await fetch(BASE+'/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,images:files})});
    const j=await r.json();if(!r.ok||j.error)throw new Error(j.error||('HTTP '+r.status));location.reload();}
  catch(e){$('ms').textContent='Erro: '+e.message;$('send').disabled=false}};
async function act(a,id){await fetch(BASE+'/'+a,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});location.reload()}
</script>"""


def _task_html(it, owner, who):
    imgs = "".join(f'<a href="/finance/inbox/img/{html.escape(n)}" target="_blank"><img src="/finance/inbox/img/{html.escape(n)}"></a>' for n in it.get("images", []))
    who_tag = f'<span class="tag">{NAMES.get(it["author"], it["author"])}</span>' if owner else ""
    pr = it.get("priority", "média")
    chk = (f'<input class="chk" type="checkbox" {"checked" if it["done"] else ""} onchange="act(\'toggle\',\'{it["id"]}\')">' if owner
           else f'<span style="font-size:20px">{"✅" if it["done"] else "⬜"}</span>')
    dele = f'<button class="alt" onclick="if(confirm(\'Apagar?\'))act(\'del\',\'{it["id"]}\')">Apagar</button>' if owner else ""
    return (f'<div class="task {"done" if it["done"] else ""}">{chk}<div class="b"><div class="t">{html.escape(it["title"])}</div>'
            f'<div>{who_tag}<span class="tag">{CATS.get(it.get("category"), "💡 Ideia")}</span><span class="tag {"alta" if pr=="alta" else ""}">{html.escape(pr)}</span>'
            f'<span class="tag">{time.strftime("%d/%m", time.localtime(_num(it.get("ts"))))}</span></div>'
            f'<div class="d">{html.escape(it.get("details", ""))}</div><div class="timg">{imgs}</div></div>{dele}</div>')


def _num(x):
    try: return float(x or 0)
    except (TypeError, ValueError): return 0.0


def render(user):
    owner = user == OWNER
    items = [i for i in _load()["items"] if owner or i["author"] == user]
    open_ = sorted([i for i in items if not i["done"]], key=lambda i: (PRIO.get(i.get("priority"), 1), -_num(i.get("ts"))))
    done = sorted([i for i in items if i["done"]], key=lambda i: -_num(i.get("done_ts")))
    sub = ("Tudo o que o membro e tu enviam. Marca como feito quando estiver corrigido." if owner
           else "Escreve aqui ideias, problemas ou dúvidas sobre a app e o servidor, com fotos se ajudar. O administrador vê tudo organizado e o que ficar resolvido aparece na lista de feitos.")
    o_html = "".join(_task_html(i, owner, user) for i in open_) or '<div style="color:#8b93a5;padding:8px">Nada pendente. 🎉</div>'
    d_html = "".join(_task_html(i, owner, user) for i in done) or '<div style="color:#8b93a5;padding:8px">Ainda nada concluído.</div>'
    return (f'<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Caixa de ideias</title>{PAGE_CSS}</head><body>'
            f'<h1>📥 Caixa de ideias e problemas</h1><div class="sub">{sub}</div>'
            '<div class="box"><textarea id="tx" placeholder="Escreve tudo o que queres dizer: ideias, erros, o que não percebes… podes pôr vários assuntos na mesma mensagem."></textarea>'
            '<div class="thumbs" id="th"></div><input type="file" id="ph" accept="image/*" multiple style="display:none">'
            '<div style="display:flex;gap:8px;margin-top:8px"><button class="alt" onclick="document.getElementById(\'ph\').click()">📷 Juntar fotos</button><button id="send">Enviar</button></div>'
            f'<div class="msg" id="ms"></div></div><h2>Pendentes ({len(open_)})</h2><div class="box" style="padding:4px">{o_html}</div>'
            f'<h2>Feitos ✓ ({len(done)})</h2><div class="box" style="padding:4px">{d_html}</div>{JS}</body></html>')


def _json(h, code, obj):
    b = json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, dict) and "error" in obj:   # mensagens de erro seguem o idioma escolhido
        import i18n
        b = i18n.translate(b, i18n.from_cookie(h.headers.get("Cookie", "")), "json")
    b = b.encode()
    h.send_response(code); h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Content-Length", str(len(b))); h.send_header("Cache-Control", "no-store"); h.end_headers(); h.wfile.write(b)


def get(h, user):
    p = h.path.split("?")[0].rstrip("/")
    m = re.match(r"^/inbox/img/([a-f0-9]{16,40}\.jpg)$", p)
    if m:
        data = _load()
        if user != OWNER and not any(m.group(1) in i.get("images", []) and i["author"] == user for i in data["items"]):
            return h.send(403, "Sem acesso.")
        try:
            b = open(os.path.join(IMGDIR, m.group(1)), "rb").read()
        except OSError:
            return h.send(404, "não encontrado")
        h.send_response(200); h.send_header("Content-Type", "image/jpeg"); h.send_header("Content-Length", str(len(b)))
        h.send_header("Cache-Control", "private, max-age=3600"); h.end_headers(); h.wfile.write(b)
        return
    if p == "/inbox":
        return h.send(200, render(user))
    return h.send(404, "não encontrado")


def post(h, user):
    p = h.path.split("?")[0].rstrip("/")
    n = int(h.headers.get("Content-Length", 0) or 0)
    if n > 14_000_000:
        return _json(h, 413, {"error": "mensagem demasiado grande"})
    try:
        j = json.loads(h.rfile.read(n).decode())
    except ValueError:
        return _json(h, 400, {"error": "pedido inválido"})
    if p == "/inbox/add":
        text = str(j.get("text") or "")[:5000].strip()
        imgs = [b for b in (j.get("images") or [])[:6] if isinstance(b, str) and len(b) < 3_000_000]
        if not text and not imgs:
            return _json(h, 400, {"error": "mensagem vazia"})
        names = []
        os.makedirs(IMGDIR, mode=0o700, exist_ok=True)
        for b in imgs:
            try:
                raw = base64.b64decode(b, validate=True)
            except Exception:
                continue
            if raw[:3] != b"\xff\xd8\xff":
                continue
            nm = uuid.uuid4().hex[:24] + ".jpg"
            with open(os.path.join(IMGDIR, nm), "wb") as f:
                f.write(raw)
            os.chmod(os.path.join(IMGDIR, nm), 0o600); names.append(nm)
        tasks = organize(text, imgs)
        d = _load(); now = time.time()
        for t in tasks:
            d["items"].append({"id": uuid.uuid4().hex[:12], "ts": now, "author": user, "title": t["title"], "category": t["category"],
                               "priority": t["priority"], "details": t["details"], "images": names, "done": False, "done_ts": None})
        _save(d)
        return _json(h, 200, {"ok": True, "tasks": len(tasks)})
    if p in ("/inbox/toggle", "/inbox/del"):
        if user != OWNER:
            return _json(h, 403, {"error": "só o administrador"})
        d = _load(); iid = str(j.get("id") or "")
        for it in d["items"]:
            if it["id"] == iid:
                if p.endswith("toggle"):
                    it["done"] = not it["done"]; it["done_ts"] = time.time() if it["done"] else None
        if p.endswith("del"):
            d["items"] = [i for i in d["items"] if i["id"] != iid]
        _save(d)
        return _json(h, 200, {"ok": True})
    return _json(h, 404, {"error": "não encontrado"})
