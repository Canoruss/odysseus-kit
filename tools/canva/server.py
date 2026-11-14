#!/usr/bin/env python3
"""Canva (REST API) para o Odysseus: ligar conta, criar designs, listar e exportar. So o utilizador owner."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import i18n
import threading, re, os, json, time, base64, hashlib, secrets, html, urllib.request, urllib.parse, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
H = os.path.expanduser("~")
ENV = {}
try:
    for l in open(secret_file("canva")):
        if "=" in l:
            k, v = l.strip().split("=", 1); ENV[k] = v
except OSError:
    print("AVISO: Canva nao configurado (corre o assistente de configuracao, passo Canva).", flush=True)
CID, CSEC = ENV.get("CANVA_CLIENT_ID", ""), ENV.get("CANVA_CLIENT_SECRET", "")
TOK = os.path.join(CONF_DIR, "canva-token.json")
PREFIX = "/canva"
REDIR = PUBLIC_URL + "/canva/callback"
SCOPES = "design:meta:read design:content:read design:content:write asset:read asset:write profile:read brandtemplate:meta:read brandtemplate:content:read"
OWNER = OWNER
USERS = (OWNER, MEMBER, TESTER)
PEND = {}
API = "https://api.canva.com/rest/v1"

def who(h):
    c = h.get("Cookie", "")
    if not c: return None
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(get("odysseus_url", "http://127.0.0.1:7860") + "/api/auth/status", headers={"Cookie": c}), timeout=3))
        return d.get("username") if d.get("authenticated") else None
    except Exception: return None

CUR = threading.local()
def _tok(u=None, own=False):
    """Ficheiro do token: cada pessoa pode ter o seu. Sem o seu, usa o do administrador (dono)."""
    u = u or getattr(CUR, "u", None) or OWNER
    mine = os.path.join(CONF_DIR, "canva-token-%s.json") % re.sub(r"[^a-z0-9]", "", u)
    if u == OWNER: return TOK
    return mine if (own or os.path.exists(mine)) else TOK
def has_own(u):
    return u == OWNER and os.path.exists(TOK) or u != OWNER and os.path.exists(_tok(u, True)) and _tok(u, True) != TOK
def tload():
    try: return json.load(open(_tok()))
    except Exception: return None
def tsave(t, u=None):
    f = _tok(u, own=True); t["at"] = time.time()
    with open(f + ".tmp", "w") as fh: json.dump(t, fh)
    os.chmod(f + ".tmp", 0o600); os.replace(f + ".tmp", f)

def tokreq(data):
    b = base64.b64encode(f"{CID}:{CSEC}".encode()).decode()
    r = urllib.request.Request(API + "/oauth/token", urllib.parse.urlencode(data).encode(),
        {"Authorization": "Basic " + b, "Content-Type": "application/x-www-form-urlencoded"})
    return json.load(urllib.request.urlopen(r, timeout=20))

def access():
    t = tload()
    if not t: return None
    if time.time() > t["at"] + t.get("expires_in", 14400) - 120:
        try:
            n = tokreq({"grant_type": "refresh_token", "refresh_token": t["refresh_token"]})
            tsave(n, getattr(CUR, 'u', None) if _tok() != TOK or getattr(CUR, 'u', OWNER) == OWNER else OWNER); t = n
        except Exception: return None
    return t["access_token"]

def api(method, path, body=None):
    tk = access()
    if not tk: raise RuntimeError("Canva não ligado")
    r = urllib.request.Request(API + path, json.dumps(body).encode() if body is not None else None,
        {"Authorization": "Bearer " + tk, "Content-Type": "application/json"}, method=method)
    try: return json.load(urllib.request.urlopen(r, timeout=30))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Canva {e.code}: {e.read().decode()[:300]}")

CSS = """
:root{--bg:#0f1115;--card:#181b22;--line:#2a2f3a;--txt:#e8eaf0;--mut:#8b93a5;--ac:#7d5cff;--ac2:#00c4cc}
*{box-sizing:border-box}body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--txt);margin:0;padding:14px;max-width:820px;margin:auto}
a{color:#9db4ff;text-decoration:none}h2{margin:0 0 4px;font-size:22px}h3{margin:18px 0 8px;font-size:16px;color:var(--mut);font-weight:600}
.hero{background:linear-gradient(135deg,#2b1f63,#0c4a55);border-radius:18px;padding:18px;margin-bottom:14px}.hero .sub{color:#c8d3e8;font-size:14px}
.box{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin:10px 0}
input,select{width:100%;font-size:16px;padding:12px;border-radius:10px;border:1px solid var(--line);background:#0c0e12;color:var(--txt);margin:5px 0}
button,.btn{display:inline-block;background:linear-gradient(90deg,var(--ac),var(--ac2));color:#fff;border:0;border-radius:12px;padding:12px 18px;font-size:16px;font-weight:600;cursor:pointer}
.btn.alt{background:#0c0e12;border:1px solid var(--line);color:var(--txt);padding:8px 12px;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}.card .t{height:110px;background:#0c0e12 center/cover no-repeat}
.card .m{padding:10px}.card .n{font-size:14px;font-weight:600;margin-bottom:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.card .a{display:flex;gap:6px}
.msg{background:#1c2a24;border:1px solid #2f5a45;border-radius:12px;padding:10px;margin:10px 0}img{max-width:100%;border-radius:10px}
"""
def page(body): return f"<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'><style>{CSS}</style>{body}".encode()
SIZES = {"instagram_post": "Post Instagram", "instagram_story": "Story Instagram", "doc": "Documento", "presentation": "Apresentação", "whiteboard": "Whiteboard", "poster": "Poster", "flyer": "Flyer"}
CUSTOM = {"instagram_post": (1080, 1080), "instagram_story": (1080, 1920), "poster": (1200, 1800), "flyer": (794, 1123)}
def dtype(kind):
    if kind in CUSTOM: return {"type": "custom", "width": CUSTOM[kind][0], "height": CUSTOM[kind][1]}
    return {"type": "preset", "name": kind}

def _acct_note():
    u = getattr(CUR, "u", OWNER)
    if u == OWNER: return "Conta do Canva ligada: a tua."
    if has_own(u): return "Estás a usar <b>a tua conta</b> do Canva. Os designs ficam nela e o botão Editar funciona com a tua sessão."
    return ("A usar a conta de Canva do administrador (para <b>editar</b>, o browser tem de ter sessão nessa conta; se aparecer \"Erro 403 / conta certa\", é outra conta). "
            f"Preferes a tua? <a href='{PREFIX}/connect' target=_blank>Ligar a minha conta do Canva</a>. A exportação em PNG funciona sempre.")

def main_page(msg=""):
    hero = "<div class=hero><h2>🎨 Canva</h2><div class=sub>Cria designs e exporta-os como imagem.</div></div>"
    m = f"<div class=msg>{msg}</div>" if msg else ""
    hero += "<div style='font-size:12px;color:#9aa;padding:0 4px 8px'>" + _acct_note() + "</div>"
    if not access():
        return page(f"{hero}{m}<div class=box>Ainda não ligado ao Canva.<p><a href='{PREFIX}/connect' target=_blank><button>Ligar ao Canva</button></a></p></div>")
    opts = "".join(f"<option value={k}>{v}</option>" for k, v in SIZES.items())
    out = f"{hero}{m}<div class=box><form method=post action='{PREFIX}/create'><input name=title placeholder='Título do design' required><select name=kind>{opts}</select><button>＋ Criar design</button></form></div><h3>Designs recentes</h3><div class=grid>"
    try:
        for d in api("GET", "/designs?limit=12&sort_by=modified_descending").get("items", []):
            th = (d.get("thumbnail") or {}).get("url", "")
            bg = f" style=\"background-image:url('{html.escape(th)}')\"" if th else ""
            out += f"<div class=card><div class=t{bg}></div><div class=m><div class=n>{html.escape(d.get('title') or 'Sem título')}</div><div class=a><a class='btn alt' href='{html.escape(d['urls']['edit_url'])}' target=_blank>Editar</a><a class='btn alt' href='{PREFIX}/export?id={d['id']}'>PNG</a></div></div></div>"
    except Exception as e: out += html.escape(str(e))
    return page(out + "</div>")

_RYOKU = {"0f1115":"#000000","0c0e12":"#000000","181b22":"#0a0a0a","1d2026":"#0a0a0a","262a31":"#141414","2a2e36":"#141414",
          "2a2f3a":"#3a3631","e8eaf0":"#cdc4ba","cfd5e2":"#cdc4ba","8b93a5":"#958f87","9aa3b2":"#958f87","7d8594":"#958f87",
          "3ddc97":"#ce5e32","7d5cff":"#ce5e32","00c4cc":"#ce5e32","9db4ff":"#cdc4ba","c8d3e8":"#cdc4ba","2b1f63":"#0a0a0a","0c4a55":"#141414","1c2a24":"#0a0a0a","2f5a45":"#3a3631","17352b":"#0a0a0a","16233a":"#141414","4aa3ff":"#ce5e32","4a7bd0":"#ce5e32","06210f":"#000000",
          "70d080":"#6daf8c","5fd08a":"#6daf8c","4aa86b":"#6daf8c"}
_RYOKU_CSS = ("<style>@font-face{font-family:'Space Grotesk Variable';src:url(/static/ryoku/fonts/space-grotesk.woff2) format('woff2');font-weight:300 700}"
              "body,input,select,textarea,button{font-family:'Space Grotesk Variable',system-ui,sans-serif!important}"
              "h1,h2,h3{font-family:'Fraunces Variable',Georgia,serif;font-weight:500}"
              "@font-face{font-family:'Fraunces Variable';src:url(/static/ryoku/fonts/fraunces.woff2) format('woff2');font-weight:100 900}"
              "</style>")
def ryoku_skin(html):
    if html.lstrip()[:1] in "{[": return html   # JSON (AJAX): nao mexer
    import re as _r
    html = _r.sub(r"border-radius:\s*(\d+)px", lambda m: "border-radius:%dpx" % (2 if int(m.group(1)) < 999 else int(m.group(1))), html)
    html = _r.sub(r"linear-gradient\(90deg,\s*var\(--ac\),\s*var\(--ac2\)\)", "var(--ac)", html)
    html = _r.sub(r"#([0-9a-fA-F]{6})\b", lambda m: _RYOKU.get(m.group(1).lower(), m.group(0)), html)
    return html.replace("</head>", _RYOKU_CSS + "</head>", 1) if "</head>" in html else _RYOKU_CSS + html


class Hd(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ct="text/html; charset=utf-8", loc=None):
        if ct.startswith("text/html") and "kittheme=ryoku" in (self.headers.get("Cookie") or ""):
            body = ryoku_skin(body.decode("utf-8", "replace") if isinstance(body, bytes) else body)
        if isinstance(body, str): body = body.encode()
        if ct.startswith("text/html") and isinstance(body, bytes):
            body = i18n.translate(body.decode("utf-8", "replace"), i18n.from_cookie(self.headers.get("Cookie", ""))).encode()
        self.send_response(code); self.send_header("Content-Type", ct)
        if loc: self.send_header("Location", loc)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def go(self):
        u = urllib.parse.urlparse(self.path); p = u.path
        if p.startswith(PREFIX): p = p[len(PREFIX):] or "/"
        q = urllib.parse.parse_qs(u.query)
        u = who(self.headers); CUR.u = u
        if u not in USERS: return self.send(403, page("Sem acesso."))
        try:
            if p == "/": return self.send(200, main_page())
            if p == "/connect":
                ver = secrets.token_urlsafe(64); st = secrets.token_urlsafe(16); PEND[st] = (ver, u)
                ch = base64.urlsafe_b64encode(hashlib.sha256(ver.encode()).digest()).decode().rstrip("=")
                url = "https://www.canva.com/api/oauth/authorize?" + urllib.parse.urlencode({"code_challenge_method": "s256", "response_type": "code", "client_id": CID, "redirect_uri": REDIR, "scope": SCOPES, "code_challenge": ch, "state": st})
                return self.send(302, b"", loc=url)
            if p == "/callback":
                pe = PEND.pop((q.get("state") or [""])[0], None)
                ver = pe[0] if pe and pe[1] == u else None
                if not ver or not q.get("code"): return self.send(400, page("Ligação inválida: " + html.escape(str(q.get("error", ""))) + f" <a href='{PREFIX}/'>voltar</a>"))
                tsave(tokreq({"grant_type": "authorization_code", "code": q["code"][0], "code_verifier": ver, "redirect_uri": REDIR}), u)
                return self.send(302, b"", loc=PREFIX + "/")
            if p == "/create" and self.command == "POST":
                n = int(self.headers.get("Content-Length", 0)); f = urllib.parse.parse_qs(self.rfile.read(n).decode())
                kind = (f.get("kind") or ["instagram_post"])[0]
                if kind not in SIZES: kind = "instagram_post"
                d = api("POST", "/designs", {"design_type": dtype(kind), "title": (f.get("title") or ["Odysseus"])[0][:250]})["design"]
                return self.send(200, main_page(f"Criado: <a href='{html.escape(d['urls']['edit_url'])}' target=_blank>abrir no Canva</a>"))
            if p == "/export":
                did = (q.get("id") or [""])[0]
                job = api("POST", "/exports", {"design_id": did, "format": {"type": "png"}})["job"]
                for _ in range(20):
                    if job["status"] != "in_progress": break
                    time.sleep(1.5); job = api("GET", "/exports/" + job["id"])["job"]
                if job["status"] != "success": return self.send(200, main_page("Exportação falhou: " + html.escape(json.dumps(job.get("error", job["status"])))))
                imgs = "".join(f"<p><img src='{html.escape(u)}'></p>" for u in job["urls"])
                return self.send(200, page(f"<h2>Exportado</h2>{imgs}<p><a class='btn alt' href='{PREFIX}/'>← voltar</a> <span style='color:#8b93a5;font-size:13px'>as ligações expiram em 24 h</span></p>"))
            return self.send(404, page("Não encontrado."))
        except Exception as e:
            return self.send(200, main_page("Erro: " + html.escape(str(e))))
    do_GET = go; do_POST = go

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(get("canva_port", 8793))), Hd).serve_forever()
