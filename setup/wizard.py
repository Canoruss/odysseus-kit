#!/usr/bin/env python3
"""Odysseus KIT: assistente de configuracao (passo a passo).
Arranque:  python3 -I setup/wizard.py   -> abre http://127.0.0.1:8790
Cada passo explica o que e, onde obter as chaves, tem um botao Testar, um interruptor Ativar e o botao Saltar.
O que saltares fica desativado mas NAO se perde: podes voltar e ativar, e o que ja escreveste fica guardado.
Escreve:  ~/.config/odysseus-kit/config.json  (funcionalidades + nomes)   e   ~/.config/odysseus-kit/<nome>.env (chaves, modo 600)."""
import base64, imaplib, json, os, smtplib, ssl, sys, urllib.error, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import i18n

CONF_DIR = os.environ.get("KIT_CONF_DIR", os.path.join(os.path.expanduser("~"), ".config", "odysseus-kit"))
CONF = os.path.join(CONF_DIR, "config.json")
PORT = int(os.environ.get("KIT_WIZARD_PORT", "8790"))
os.makedirs(CONF_DIR, mode=0o700, exist_ok=True)
TOKEN_FILE = os.path.join(CONF_DIR, "wizard.token")   # segredo partilhado com o hub: so o hub (apos validar o administrador) o conhece
if not os.path.exists(TOKEN_FILE):
    import secrets as _sec
    _fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(_fd, "w") as _f:
        _f.write(_sec.token_urlsafe(32))
TOKEN = open(TOKEN_FILE).read().strip()

# field = (chave, rotulo, tipo)   tipo: text | secret | number
# file  = ficheiro .env onde os campos 'secret'/'env' vao; 'cfg' = vao para config.json
STEPS = [
    {"id": "server", "title": "1. O teu servidor", "core": True, "default": True,
     "why": "Dados básicos: o endereço público do teu Odysseus e os nomes dos utilizadores. Sem isto as ligações e os avisos não sabem para onde apontar.",
     "how": ["Endereço público: o que usas para abrir o Odysseus no telemóvel (ex.: https://o-teu-servidor.tuarede.ts.net).",
             "Utilizador administrador: o nome de utilizador que criaste no Odysseus.",
             "Fuso horário: nome IANA, ex. Europe/Lisbon, America/Sao_Paulo, UTC."],
     "fields": [("public_url", "Endereço público do servidor", "cfg"), ("owner", "Utilizador administrador", "cfg"),
                ("owner_name", "Nome a mostrar", "cfg"), ("timezone", "Fuso horário", "cfg"),
                ("member", "Segundo utilizador (opcional)", "cfg"), ("member_name", "Nome do segundo utilizador", "cfg")]},
    {"id": "ai_groq", "title": "2. IA rápida e grátis: Groq", "default": True, "test": "groq", "file": "groq",
     "why": "Ditado por voz, sugestões de resposta, tradução por foto e leitura de recibos em menos de 1 segundo. Plano gratuito, sem cartão.",
     "how": ["Abre https://console.groq.com/keys e cria conta.", "Carrega em 'Create API Key', dá-lhe um nome e copia a chave (começa por gsk_).", "Cola-a abaixo e carrega em Testar."],
     "fields": [("GROQ_API_KEY", "Chave Groq", "secret")]},
    {"id": "ai_gemini", "title": "3. IA da Google: Gemini (opcional)", "default": False, "test": "gemini", "file": "gemini",
     "why": "Modelo de reserva e leitura de fotos de refeições e relatórios. O plano gratuito tem limites e pode ficar sobrecarregado.",
     "how": ["Abre https://aistudio.google.com/apikey e inicia sessão.", "Carrega em 'Create API key' e copia a chave (começa por AIza).", "Não gera imagens no plano gratuito."],
     "fields": [("GEMINI_API_KEY", "Chave Gemini", "secret")]},
    {"id": "translate", "title": "4. Tradução: DeepL", "default": True, "test": "deepl", "file": "deepl",
     "why": "Tradução muito rápida e de boa qualidade (cerca de 0,4 s). O plano gratuito dá 500 000 caracteres por mês.",
     "how": ["Abre https://www.deepl.com/pro-api e cria uma conta 'DeepL API Free'.", "Em Conta → Chaves, copia a 'Authentication Key' (acaba em :fx).", "Sem DeepL a tradução usa o Groq ou o Gemini."],
     "fields": [("DEEPL_API_KEY", "Chave DeepL", "secret")]},
    {"id": "bridge", "title": "5. Modelo compatível OpenAI (opcional)", "default": False, "file": "bridge",
     "why": "Se tens um servidor compatível com a API da OpenAI (por exemplo um bridge para o Claude Code), é usado como motor de reserva.",
     "how": ["Indica a chave que o teu servidor aceita. O endereço por omissão é http://127.0.0.1:8787/v1/chat/completions."],
     "fields": [("BRIDGE_API_KEY", "Chave do bridge", "secret")]},
    {"id": "finance", "title": "6. Finanças", "default": True, "file": "finance",
     "why": "Movimentos, dívidas com avisos de vencimento, metas, leitura de recibos por foto e despesas mensais. Protegido por palavra-passe própria.",
     "how": ["Escolhe uma palavra-passe forte (diferente da do Odysseus). Pede-a sempre que abres as Finanças."],
     "fields": [("FINANCE_PASSWORD", "Palavra-passe das Finanças", "secret")]},
    {"id": "gym", "title": "7. Gym e Treino+", "default": True,
     "why": "Plano de treino, registo de séries e peso, fotos de progresso e análise de técnica por IA. Não precisa de chaves além da IA.",
     "how": ["Define o teu peso inicial e a meta; podes mudar depois.", "O plano de exemplo é editável (GYM_PLAN em tools/hub/server.py) ou gerado pelo questionário."],
     "fields": [("gym_start_kg", "Peso inicial (kg)", "cfg"), ("gym_goal_kg", "Meta (kg)", "cfg")]},
    {"id": "study", "title": "8. Estudo (trabalhos e pesquisa)", "default": True,
     "why": "Trabalhos com etapas e prazos, biblioteca de fontes com citações APA, notas por cadeira e ajuda da IA para resumir e rever. Não escreve o trabalho por ti.",
     "how": ["Não precisa de chaves além da IA (Groq)."], "fields": []},
    {"id": "news", "title": "9. Notícias personalizadas", "default": True,
     "why": "Feed com as fontes e os temas que escolhes, sem algoritmos de terceiros, e um resumo do dia que cita as fontes.",
     "how": ["As fontes e os temas escolhem-se dentro da página Notícias."], "fields": []},
    {"id": "compose", "title": "10. Compor email e WhatsApp", "default": True,
     "why": "A IA escreve o rascunho e tu escolhes a app (Gmail, Outlook, Proton, WhatsApp...) para enviar.",
     "how": ["Não precisa de chaves além da IA."], "fields": []},
    {"id": "flights", "title": "11. Voos (opcional)", "default": False, "file": "airlabs",
     "why": "Guarda voos e abre-os no Flightradar24. Com uma chave AirLabs mostra também o estado e os atrasos, e avisa 3 h e 1 h antes da partida se houver atraso, cancelamento ou mudança de porta. O plano grátis tem um limite de consultas, por isso o Kit só consulta quando carregas em Atualizar estado e nessas duas janelas.",
     "how": ["Abre https://airlabs.co e cria conta gratuita (o registo pede um endereço de website: serve o do teu perfil ou projeto).", "Copia a API key do painel.", "Para os avisos automáticos, agenda em cron: */10 * * * * python3 -I tools/jobs/flight_watch.py (não gasta consultas quando não há nada a verificar)."],
     "fields": [("AIRLABS_API_KEY", "Chave AirLabs", "secret")]},
    {"id": "glucose", "title": "12. Glicose (opcional, saúde)", "default": False, "file": "librelinkup",
     "why": "Lê o sensor FreeStyle Libre através do LibreLinkUp e mostra gráfico e histórico. A calculadora de insulina NÃO vem com valores: só funciona se definires os do teu médico.",
     "how": ["Na app LibreLink, cria uma conta de seguidor (LibreLinkUp) e convida-a.", "Usa o email e a palavra-passe dessa conta de seguidor.",
             "Para ativar a calculadora, define os valores do teu médico em config.json, secção 'glucose' (ver docs/GLUCOSE.md).",
             "É uma ferramenta de apoio. Não substitui o médico."],
     "fields": [("LLU_EMAIL", "Email da conta LibreLinkUp", "secret"), ("LLU_PASSWORD", "Palavra-passe LibreLinkUp", "secret")]},
    {"id": "canva", "title": "13. Canva (opcional)", "default": False, "file": "canva",
     "why": "Cria designs e exporta para PNG a partir do Odysseus.",
     "how": ["Abre https://www.canva.com/developers e cria uma integração.", "Em 'Scopes' ativa leitura e escrita de designs e assets.",
             "Em 'Redirect URLs' acrescenta o teu endereço público + /canva/callback.", "Copia o Client ID e gera o Client secret."],
     "fields": [("CANVA_CLIENT_ID", "Client ID", "secret"), ("CANVA_CLIENT_SECRET", "Client secret", "secret")]},
    {"id": "email", "title": "14. Emails (opcional)", "default": False, "test": "imap",
     "why": "Liga as tuas caixas de correio ao Odysseus por IMAP/SMTP.",
     "how": ["Gmail: ativa a verificação em dois passos e cria uma palavra-passe de aplicação em https://myaccount.google.com/apppasswords (IMAP imap.gmail.com:993, SMTP smtp.gmail.com:587).",
             "Outlook/Microsoft 365: muitas contas só permitem OAuth; se a palavra-passe falhar, usa o reencaminhamento para outra caixa.",
             "Outros: pergunta ao teu fornecedor pelos servidores IMAP/SMTP.",
             "As contas adicionam-se depois na página Emails do Odysseus; aqui podes só testar o login."],
     "fields": [("imap_host", "Servidor IMAP", "text"), ("imap_port", "Porta IMAP (993)", "text"), ("imap_user", "Utilizador", "text"), ("imap_pass", "Palavra-passe (não é guardada)", "secret")]},
    {"id": "clickup", "title": "15. ClickUp (opcional)", "default": False, "file": "clickup",
     "why": "Uma lista diária das tuas tarefas abertas como lembrete no Odysseus.",
     "how": ["No ClickUp: Definições → Apps → 'API Token' → Gerar.", "O id da equipa vê-se no URL: app.clickup.com/<ID>/..."],
     "fields": [("CLICKUP_API_TOKEN", "Token ClickUp", "secret"), ("clickup_team", "ID da equipa", "cfg"), ("clickup_assignee", "O teu nome ou email no ClickUp", "cfg")]},
    {"id": "telegram", "title": "16. Telegram (opcional)", "default": False, "test": "telegram", "file": "telegram",
     "why": "Avisos para o telemóvel quando o servidor precisa de ti.",
     "how": ["No Telegram fala com @BotFather, envia /newbot e segue os passos.", "Copia o token (123456:ABC...). Envia uma mensagem ao teu bot e o chat id obtém-se em https://api.telegram.org/bot<TOKEN>/getUpdates."],
     "fields": [("TELEGRAM_BOT_TOKEN", "Token do bot", "secret"), ("TELEGRAM_CHAT_ID", "Chat id", "secret")]},
    {"id": "gallery", "title": "17. Galeria a partir de uma pasta (opcional)", "default": False,
     "why": "Importa para a galeria do Odysseus as fotos de uma pasta (por exemplo do Nextcloud), sem duplicados, todos os dias.",
     "how": ["Indica o caminho completo da pasta no servidor.", "Cria o ficheiro owner.env com ODY_USER e ODY_PASSWORD do administrador do Odysseus (ver docs/INSTALL.md)."],
     "fields": [("gallery_src", "Pasta com as fotos", "cfg")]},
    {"id": "android", "title": "18. App Android", "default": True,
     "why": "A app abre o teu Odysseus em ecrã inteiro e acrescenta widgets, lembretes, tradutor e leitura de SMS de consultas.",
     "how": ["Segue docs/APK.md para compilar e instalar a APK com o endereço do passo 1.", "Se preferires, usa o Odysseus como PWA: abre o endereço no Chrome e escolhe 'Instalar'."],
     "fields": []},
]
BYID = {s["id"]: s for s in STEPS}


def load():
    try:
        return json.load(open(CONF, encoding="utf-8"))
    except Exception:
        return {}


def save(c):
    tmp = CONF + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, ensure_ascii=False)
    os.chmod(tmp, 0o600)
    os.replace(tmp, CONF)


def read_env(name):
    d = {}
    try:
        for l in open(os.path.join(CONF_DIR, name + ".env"), encoding="utf-8"):
            if "=" in l and not l.startswith("#"):
                k, v = l.rstrip("\n").split("=", 1)
                d[k] = v
    except OSError:
        pass
    return d


def write_env(name, d):
    p = os.path.join(CONF_DIR, name + ".env")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for k, v in d.items():
            f.write(f"{k}={v}\n")


def mask(v):
    return "" if not v else ("•" * 6 + v[-4:] if len(v) > 8 else "•" * len(v))


def state():
    c = load()
    out = []
    for s in STEPS:
        cfg = c.get("features", {})
        enabled = cfg.get(s["id"], s["default"])
        env = read_env(s["file"]) if s.get("file") else {}
        vals = {}
        for k, label, t in s["fields"]:
            if t == "secret":
                v = env.get(k, "")
                vals[k] = {"set": bool(v), "mask": mask(v)}
            else:
                vals[k] = {"value": c.get(k, "")}
        out.append({"id": s["id"], "title": s["title"], "why": s["why"], "how": s["how"], "core": s.get("core", False),
                    "enabled": enabled, "visited": s["id"] in c.get("visited", []), "test": bool(s.get("test")),
                    "fields": [{"key": k, "label": l, "type": t} for k, l, t in s["fields"]], "values": vals})
    return out


def _get(url, headers=None, data=None, timeout=12):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def run_test(kind, v):
    try:
        if kind == "groq":
            st, _ = _get("https://api.groq.com/openai/v1/models", {"Authorization": "Bearer " + v["GROQ_API_KEY"], "User-Agent": "odysseus-kit"})
            return True, "Chave válida."
        if kind == "gemini":
            st, _ = _get("https://generativelanguage.googleapis.com/v1beta/models?key=" + urllib.parse.quote(v["GEMINI_API_KEY"]))
            return True, "Chave válida."
        if kind == "deepl":
            k = v["DEEPL_API_KEY"]
            host = "api-free.deepl.com" if k.endswith(":fx") else "api.deepl.com"
            st, b = _get(f"https://{host}/v2/usage", {"Authorization": "DeepL-Auth-Key " + k})
            u = json.loads(b)
            return True, f"Chave válida. Uso: {u.get('character_count', 0)} de {u.get('character_limit', 0)} caracteres."
        if kind == "telegram":
            st, b = _get(f"https://api.telegram.org/bot{v['TELEGRAM_BOT_TOKEN']}/getMe")
            return True, "Bot: @" + json.loads(b)["result"]["username"]
        if kind == "imap":
            m = imaplib.IMAP4_SSL(v["imap_host"], int(v.get("imap_port") or 993), timeout=12)
            m.login(v["imap_user"], v["imap_pass"])
            n = m.select("INBOX", readonly=True)[1][0].decode()
            m.logout()
            return True, f"Login OK. Caixa de entrada com {n} mensagens."
    except urllib.error.HTTPError as e:
        return False, f"Recusado pelo serviço (HTTP {e.code}). Confirma a chave."
    except imaplib.IMAP4.error as e:
        return False, "Login recusado: " + str(e)[:120] + ". No Gmail usa uma palavra-passe de aplicação."
    except Exception as e:
        return False, "Falhou: " + str(e)[:140]
    return False, "Sem teste para este passo."


def apply(sid, body):
    s = BYID[sid]
    c = load()
    feats = c.setdefault("features", {})
    feats[sid] = bool(body.get("enabled"))
    vis = c.setdefault("visited", [])
    if sid not in vis:
        vis.append(sid)
    env = read_env(s["file"]) if s.get("file") else {}
    for k, label, t in s["fields"]:
        if k not in body.get("values", {}):
            continue
        val = str(body["values"][k]).strip()
        if t == "secret":
            if sid == "email":
                continue   # a palavra-passe de email nunca e guardada pelo assistente
            if val:
                env[k] = val          # vazio = mantem o que ja estava
        elif val != "":
            c[k] = val
    if s.get("file"):
        write_env(s["file"], env)
    save(c)
    # ficheiro para o front-end do Odysseus (window.KIT_CONFIG)
    try:
        pub = {"owner": c.get("owner", "owner"), "member": c.get("member", "member"), "features": feats}
        with open(os.path.join(CONF_DIR, "kit-config.js"), "w", encoding="utf-8") as f:
            f.write("window.KIT_CONFIG = " + json.dumps(pub) + ";\n")
    except OSError:
        pass


PAGE = r"""<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Odysseus KIT: configuração</title><style>
:root{color-scheme:dark}body{margin:0;font-family:system-ui,sans-serif;background:#14161b;color:#e8e8ea}
.wrap{max-width:720px;margin:0 auto;padding:18px}h1{font-size:22px;margin:6px 0 2px}.sub{color:#9aa3b2;font-size:14px;margin-bottom:14px}
.bar{height:6px;background:#262a33;border-radius:9px;overflow:hidden;margin:10px 0 16px}.bar i{display:block;height:100%;background:#4cc38a;width:0}
.card{background:#1d2027;border:1px solid #2b303a;border-radius:14px;padding:16px;margin-bottom:12px}
h2{margin:0 0 6px;font-size:18px}.why{color:#c3c8d2;font-size:14px;margin:0 0 10px}
ol{margin:6px 0 12px 18px;padding:0;color:#aeb5c2;font-size:13.5px}li{margin:3px 0}
label{display:block;font-size:13px;color:#9aa3b2;margin:10px 0 3px}input[type=text],input[type=password]{width:100%;box-sizing:border-box;padding:10px;border-radius:9px;border:1px solid #333a47;background:#12141a;color:#fff;font-size:15px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;align-items:center}button{border:0;border-radius:10px;padding:10px 16px;font-size:14px;cursor:pointer;background:#2e3442;color:#fff}
button.pri{background:#2a8f63}button.ghost{background:transparent;border:1px solid #333a47;color:#9aa3b2}.msg{font-size:13px;margin-top:8px;min-height:18px}
.ok{color:#4cc38a}.bad{color:#ef6b6b}.tag{font-size:11px;padding:2px 8px;border-radius:99px;background:#262a33;color:#9aa3b2;margin-left:6px}
.sw{display:flex;align-items:center;gap:8px;margin:8px 0;font-size:14px}.nav{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.nav button{padding:5px 10px;font-size:12px;background:#222630}.nav button.cur{background:#2a8f63}.nav button.off{opacity:.55}
</style></head><body><div class="wrap"><h1>Odysseus KIT</h1><div style="float:right;font-size:13px"><a href="lang?l=en" style="color:#9aa3b2">English</a> · <a href="lang?l=pt" style="color:#9aa3b2">Portugu&ecirc;s</a></div><div class="sub">Configuração passo a passo. Podes saltar o que não precisas e voltar mais tarde; nada do que escreveres se perde.</div>
<div class="bar"><i id="pb"></i></div><div class="nav" id="nav"></div><div id="box"></div></div>
<script>
let S=[],cur=0;const $=s=>document.querySelector(s);
async function load(){S=await (await fetch('api/state')).json();render()}
function render(){
 $('#pb').style.width=(100*S.filter(s=>s.visited).length/S.length)+'%';
 $('#nav').innerHTML=S.map((s,i)=>`<button class="${i==cur?'cur':''} ${s.enabled?'':'off'}" onclick="cur=${i};render()">${i+1}</button>`).join('');
 const s=S[cur];
 let f=s.fields.map(x=>{const v=s.values[x.key]||{};
  if(x.type==='secret')return `<label>${x.label}${v.set?` <span class="tag">guardado ${v.mask}</span>`:''}</label><input type="password" id="f_${x.key}" placeholder="${v.set?'deixa vazio para manter':''}" autocomplete="off">`;
  return `<label>${x.label}</label><input type="text" id="f_${x.key}" value="${(v.value||'').replace(/"/g,'&quot;')}">`}).join('');
 $('#box').innerHTML=`<div class="card"><h2>${s.title}${s.core?'<span class="tag">essencial</span>':''}</h2><p class="why">${s.why}</p>
 <ol>${s.how.map(h=>`<li>${h}</li>`).join('')}</ol>
 ${s.core?'':`<div class="sw"><input type="checkbox" id="en" ${s.enabled?'checked':''}><label for="en" style="margin:0;color:#e8e8ea">Ativar esta funcionalidade</label></div>`}
 ${f}<div class="msg" id="msg"></div>
 <div class="row"><button class="ghost" onclick="go(-1)">← Anterior</button>
 ${s.test?'<button onclick="test()">Testar</button>':''}
 ${s.core?'':'<button class="ghost" onclick="skip()">Saltar (desativar)</button>'}
 <button class="pri" onclick="save()">Guardar e continuar →</button></div></div>`;
}
function vals(){const o={};S[cur].fields.forEach(x=>{o[x.key]=document.getElementById('f_'+x.key).value});return o}
async function post(u,b){return (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json()}
async function save(skipped){const s=S[cur];const en=s.core?true:(skipped===true?false:document.getElementById('en').checked);
 await post('api/save',{id:s.id,enabled:en,values:vals()});await load();cur=Math.min(cur+1,S.length-1);render()}
async function skip(){const s=S[cur];await post('api/save',{id:s.id,enabled:false,values:{}});await load();cur=Math.min(cur+1,S.length-1);render()}
function go(d){cur=Math.max(0,Math.min(S.length-1,cur+d));render()}
async function test(){$('#msg').className='msg';$('#msg').textContent='A testar...';const r=await post('api/test',{id:S[cur].id,values:vals()});$('#msg').className='msg '+(r.ok?'ok':'bad');$('#msg').textContent=r.msg}
load();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json", extra=None):
        import hmac as _h
        direct = not _h.compare_digest(self.headers.get("X-Kit-Setup-Token", ""), TOKEN)    # acesso direto (nao via hub): traduzir aqui
        lang = i18n.from_cookie(self.headers.get("Cookie", ""))
        if direct and lang != i18n.SOURCE and isinstance(body, str) and self.path.split("?")[0] != "/status":
            body = i18n.translate(body, lang, "json" if ctype == "application/json" else "html")
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.split("?")[0] == "/lang":      # /lang?l=en|pt  -> guarda o idioma e volta ao assistente
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query); l = (q.get("l") or ["en"])[0]
            l = l if l in ("en", "pt") else "en"
            self.send_response(302); self.send_header("Set-Cookie", i18n.cookie_header(l)); self.send_header("Location", "/"); self.send_header("Content-Length", "0"); self.end_headers()
            return
        if self.path.split("?")[0] == "/status":
            return self._send(200, json.dumps({"done": "android" in load().get("visited", [])}))
        if self.path == "/":
            return self._send(200, PAGE, "text/html")
        if self.path == "/api/state":
            return self._send(200, json.dumps(state(), ensure_ascii=False))
        self._send(404, "{}")

    def do_POST(self):
        # so aceita pedidos feitos a partir desta mesma pagina (protecao contra CSRF de outros sites)
        origin = self.headers.get("Origin", "")
        import hmac as _hm
        via_hub = _hm.compare_digest(self.headers.get("X-Kit-Setup-Token", ""), TOKEN)   # pedido validado pelo hub (administrador)
        if not via_hub and origin and urllib.parse.urlparse(origin).netloc not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
            return self._send(403, '{"error":"origem recusada"}')
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", "0")), 200000)) or b"{}")
        except ValueError:
            return self._send(400, "{}")
        if self.path == "/api/save" and body.get("id") in BYID:
            apply(body["id"], body)
            return self._send(200, '{"ok":true}')
        if self.path == "/api/test" and body.get("id") in BYID:
            s = BYID[body["id"]]
            v = dict(body.get("values") or {})
            env = read_env(s["file"]) if s.get("file") else {}
            for k, _, t in s["fields"]:      # campo vazio = usa a chave guardada
                if t == "secret" and not v.get(k):
                    v[k] = env.get(k, "")
            ok, msg = run_test(s.get("test", ""), v)
            return self._send(200, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))
        self._send(404, "{}")


if __name__ == "__main__":
    print(f"Assistente de configuração: http://127.0.0.1:{PORT}   (Ctrl+C para sair)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
