"""Faturas detetadas no e-mail (Fase 1): procura nas contas ligadas ao Odysseus, extrai com Groq e deixa confirmar/ignorar.
Dados por conta (bills-<user>.json). Nao guarda o corpo dos e-mails: so o ID da mensagem e os campos extraidos."""
import sys as _s, os as _o
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), ".."))
from kitconfig import *
from kitconfig import secret_file
import os, re, json, time, uuid, html, datetime, urllib.request, urllib.parse
import subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
E = html.escape
ODY = "http://127.0.0.1:7860"
KW = re.compile(r"devolu[cç][aã]o|suspens[aã]o|falha no pagamento|pagamento (?:recusado|falhad)|payment (?:failed|declined)|fatura|factura|invoice|vencimento|pagamento|payment|refer[eê]ncia multibanco|d[eé]bito direto|d[eé]bito direct|a pagar|amount due|due date|recibo|bill\b|renda|condom[ií]nio|prestação|prestacao", re.I)
SENDERS = re.compile(r"edp|epal|[aá]guas|vodafone|meo|nos\.pt|nowo|galp|endesa|iberdrola|goldenergy|seguros?|condom|santander|openbank|revolut|klarna|oney|sequra|finan[cç]as|portaldasfinancas|at\.gov", re.I)
MAXREAD, MAXLIST, DAYS = 8, 60, 21


def T(lang, pt, en): return en if lang == "en" else pt


def _p(u): return os.path.join(HERE, "bills-%s.json" % re.sub(r"[^a-z0-9_-]", "", str(u).lower()))


def load(u):
    try: d = json.load(open(_p(u)))
    except (OSError, ValueError): d = {}
    d.setdefault("seen", []); d.setdefault("pending", []); d.setdefault("off", []); d.setdefault("last", 0); d.setdefault("msg", ""); d.setdefault("tracked", []); d.setdefault("rules", {}); d.setdefault("learned", []); d.setdefault("muted", []); d.setdefault("ign", {}); d.setdefault("auto", False)
    return d


def save(u, d):
    p = _p(u); tmp = p + ".tmp"
    d["seen"] = d["seen"][-1500:]
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _ody(cookie, path):
    rq = urllib.request.Request(ODY + path, headers={"Cookie": cookie})
    try:
        with urllib.request.urlopen(rq, timeout=60) as r: return json.loads(r.read().decode() or "{}")
    except Exception as e: return {"error": str(e)[:100]}


class Src:
    """Acesso ao e-mail do utilizador: cookie (pagina), sessao (cron, outros utilizadores) ou API do agente (cron, administrador; sem anexos)."""
    def __init__(self, cookie=None, user=None):
        self.cookie, self.user = cookie, user
        self.codex = bool(user) and user == OWNER

    def raw(self, path):
        if self.cookie is not None:
            rq = urllib.request.Request(ODY + path, headers={"Cookie": self.cookie})
            with urllib.request.urlopen(rq, timeout=60) as r: return r.read()
        sys.path.insert(0, os.path.join(HERE, "..", "jobs")); import users
        with users._session(self.user).open(users.B + path, timeout=90) as r: return r.read()

    def js(self, path):
        if self.codex:
            sys.path.insert(0, os.path.join(HERE, "..", "jobs")); import lib, subprocess
            r = subprocess.run(["python3", "-I", lib.ODY, "GET", path], capture_output=True, text=True, timeout=120, env=lib.ENV)
            try: return json.loads(r.stdout)
            except ValueError: return {"error": (r.stdout or r.stderr)[:100]}
        try: return json.loads(self.raw(path).decode() or "{}")
        except Exception as e: return {"error": str(e)[:100]}

    def accounts(self):
        if self.codex: return [{"id": "", "name": OWNER}]
        return self.js("/api/email/accounts").get("accounts") or []

    def listing(self, aid, since):
        if self.codex:
            fo = "[Gmail]/Todo o correio"
            r = self.js("/api/codex/emails?folder=%s&limit=%d&offset=0" % (urllib.parse.quote(fo), MAXLIST * 2))
            if r.get("error") or not r.get("emails"): fo = "INBOX"; r = self.js("/api/codex/emails?folder=INBOX&limit=%d&offset=0" % (MAXLIST * 2))
            cut = time.mktime(datetime.date.fromisoformat(since).timetuple())
            r["emails"] = [dict(m, folder=fo) for m in r.get("emails") or [] if m.get("date_epoch", 0) >= cut]; return r
        return self.js("/api/email/list?" + urllib.parse.urlencode({"account_id": aid, "limit": MAXLIST, "date_from": since, "refresh": 1}))

    def read(self, m, aid):
        q = {"folder": m.get("folder") or "INBOX", "mark_seen": "false"}
        if aid: q["account_id"] = aid
        base = "/api/codex/emails/%s?" if self.codex else "/api/email/read/%s?"
        return self.js(base % urllib.parse.quote(str(m.get("uid"))) + urllib.parse.urlencode(q))

    def pdf(self, m, aid):
        """Texto dos primeiros PDFs em anexo (so com cookie/sessao; a API do agente nao tem anexos)."""
        if self.codex or not m.get("has_attachments"): return ""
        uid = urllib.parse.quote(str(m.get("uid"))); q = {"folder": m.get("folder") or "INBOX"}
        if aid: q["account_id"] = aid
        qs = urllib.parse.urlencode(q); out = ""
        try:
            for at in (self.js("/api/email/attachments/%s?%s" % (uid, qs)).get("attachments") or [])[:6]:
                if not str(at.get("filename", "")).lower().endswith(".pdf") or (at.get("size") or 0) > 6_000_000: continue
                data = self.raw("/api/email/attachment/%s/%s?%s" % (uid, at.get("index"), qs))
                if data[:4] != b"%PDF": continue
                r = subprocess.run(["pdftotext", "-l", "3", "-layout", "-", "-"], input=data, capture_output=True, timeout=30)
                out += " " + re.sub(r"\s+", " ", r.stdout.decode("utf-8", "ignore"))
                if len(out) > 1500: break
        except Exception: pass
        return out.strip()[:2500]


def _groq(prompt):
    import groqv
    body = {"model": "qwen/qwen3.8-27b", "temperature": 0, "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": prompt}]}
    rq = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", json.dumps(body).encode(),
                                {"Content-Type": "application/json", "Authorization": "Bearer " + groqv._key(), "User-Agent": "finance-tool/1.0"})
    return json.loads(json.load(urllib.request.urlopen(rq, timeout=40))["choices"][0]["message"]["content"])


def _text(body):
    t = re.sub(r"(?is)<(style|script).*?</\1>", " ", body or "")
    t = re.sub(r"<[^>]+>", " ", t); t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()[:3500]


def extract(frm, subj, body, pdf=""):
    p = ("Analisa este e-mail e diz se é uma FATURA/COBRANÇA a pagar (não conta publicidade, newsletters, avisos de segurança, recibos já pagos ou encomendas).\n"
         'Responde só com JSON: {"fatura": true|false, "emissor": "nome curto", "valor": número em euros ou null, "vencimento": "AAAA-MM-DD" ou null, '
         '"referencia": "referência de pagamento ou null", "recorrente": true|false, "descricao": "máx 60 caracteres", "aviso_falha": true|false}\n'
         "aviso_falha=true se for aviso de pagamento falhado/devolvido/recusado, cobrança em atraso ou ameaça de suspensão do serviço.\n"
         "Hoje é %s.\nDe: %s\nAssunto: %s\nTexto: %s%s" % (datetime.date.today().isoformat(), frm[:120], subj[:200], _text(body)[:1800 if pdf else 3500], ("\nPDF em anexo: " + pdf) if pdf else ""))
    return _groq(p)


def _num(v):
    try:
        x = round(float(str(v).replace(",", ".").replace("€", "").strip()), 2)
        return x if 0 < x < 1e6 else None
    except (TypeError, ValueError): return None


def _date(v):
    try: return datetime.date.fromisoformat(str(v)[:10]).isoformat()
    except ValueError: return ""


def _addr(frm):
    m = re.search(r"<([^>]+)>", frm or ""); return (m.group(1) if m else frm or "").strip().lower()[:80]


def scan(u, cookie=None, auto=False):
    """Procura e-mails recentes e acrescenta candidatos a 'pending'. Devolve o numero de faturas novas."""
    d = load(u); src = Src(cookie=cookie, user=u if auto else None)
    acc = src.accounts()
    if not acc:
        d["msg"] = "no-acc"; d["last"] = int(time.time()); save(u, d); return 0
    since = (datetime.date.today() - datetime.timedelta(days=DAYS)).isoformat()
    seen = set(d["seen"]); read = found = 0; err = ""; learned = set(d["learned"]); muted = set(d["muted"])
    for a in acc:
        aid = a.get("id")
        if (aid is None) or aid in d["off"]: continue
        r = src.listing(aid, since)
        if r.get("error") and not r.get("emails"): err = r["error"]; continue
        for m in r.get("emails") or []:
            mid = m.get("message_id") or "%s:%s" % (aid, m.get("uid"))
            if mid in seen: continue
            frm = "%s <%s>" % (m.get("from_name", ""), m.get("from_address", "")); subj = m.get("subject", ""); ad = _addr(frm)
            if ad in muted or not (KW.search(subj) or SENDERS.search(frm) or ad in learned):
                seen.add(mid); d["seen"].append(mid); continue
            if read >= MAXREAD: continue          # fica para a proxima procura
            read += 1; seen.add(mid); d["seen"].append(mid)
            b = src.read(m, aid)
            try: x = extract(frm, subj, b.get("body") or b.get("body_html") or "", src.pdf(m, aid))
            except Exception as e: err = "IA: " + str(e)[:80]; seen.discard(mid); d["seen"].remove(mid); continue
            v = _num(x.get("valor"))
            if x.get("aviso_falha") is True:
                d.setdefault("alerts", []).append({"id": uuid.uuid4().hex[:10], "mid": mid, "from": (m.get("from_name") or m.get("from_address") or "")[:60], "issuer": str(x.get("emissor") or "")[:50], "amount": v, "desc": str(x.get("descricao") or subj)[:80], "date": (m.get("date") or "")[:10]})
                d["alerts"] = d["alerts"][-30:]; found += 1; continue
            if x.get("fatura") is not True or v is None: continue
            d["pending"].append({"id": uuid.uuid4().hex[:10], "mid": mid, "acc": a.get("name") or a.get("imap_user") or "", "from": (m.get("from_name") or m.get("from_address") or "")[:60], "addr": ad,
                                 "issuer": str(x.get("emissor") or m.get("from_name") or "")[:50], "amount": v, "due": _date(x.get("vencimento")),
                                 "ref": str(x.get("referencia") or "")[:40] if x.get("referencia") else "", "rec": bool(x.get("recorrente")),
                                 "desc": str(x.get("descricao") or subj)[:80], "date": (m.get("date") or "")[:10]})
            found += 1
    d["pending"] = d["pending"][-100:]
    d["last"] = int(time.time()); d["msg"] = ("err:" + err) if err and not found else "ok:%d:%d" % (found, read)
    save(u, d); return found


def post(u, path, f, cookie, add_debt, del_debt=None):
    """add_debt(name, amount, due, ref) grava a divida nas Financas e devolve o nome gravado; del_debt(nome) remove-a ao marcar como paga."""
    a = path.rstrip("/").split("/")[-1]; i = (f.get("id") or "")[:12]; d = load(u)
    if a == "scan": scan(u, cookie); return ""
    if a == "alertok":
        d["alerts"] = [x for x in d.get("alerts", []) if x["id"] != i]; save(u, d); return ""
    if a == "auto":
        d["auto"] = not d["auto"]; save(u, d); return ""
    if a == "unlearn":
        ad = (f.get("addr") or "")[:80]
        for k in ("learned", "muted"):
            if ad in d[k]: d[k].remove(ad)
        save(u, d); return ""
    if a == "toggle":
        aid = (f.get("acc") or "")[:80]
        if aid in d["off"]: d["off"].remove(aid)
        elif aid: d["off"].append(aid)
        save(u, d); return ""
    if a in ("paid", "drop", "forget"):
        if a == "forget":
            d["rules"].pop((f.get("rule") or "")[:60], None); save(u, d); return ""
        t = next((t for t in d["tracked"] if t["id"] == i), None)
        if t:
            if a == "paid" and del_debt and t.get("debt"): del_debt(t["debt"])
            d["tracked"].remove(t); save(u, d)
        return ""
    x = next((x for x in d["pending"] if x["id"] == i), None)
    if not x: return ""
    ad = x.get("addr") or ""
    if a == "ok":
        if ad and ad not in d["learned"]: d["learned"].append(ad)
        d["ign"].pop(ad, None)
        if ad in d["muted"]: d["muted"].remove(ad)
        amt = _num(f.get("amount")) or x["amount"]; name = (f.get("issuer") or x["issuer"]).strip()[:50] or "Fatura"
        due = _date(f.get("due")) or x["due"]
        note = add_debt(name, amt, due, x["ref"])
        if due: d["tracked"].append({"id": x["id"], "issuer": name, "amount": amt, "due": due, "ref": x["ref"], "debt": note or "", "sent": []})
        if f.get("rec") and due:
            d["rules"][name.lower()[:60]] = {"issuer": name, "day": int(due[8:10]), "amount": amt, "warned": "", "last_due": due}
    elif a != "ignore": return ""
    else:
        if ad and ad not in d["learned"]:
            d["ign"][ad] = d["ign"].get(ad, 0) + 1
            if d["ign"][ad] >= 2 and ad not in d["muted"]: d["muted"].append(ad)
    d["pending"].remove(x); save(u, d); return ""


def render(u, lang, cookie):
    d = load(u); L = lambda pt, en: E(T(lang, pt, en))
    acc = _ody(cookie, "/api/email/accounts").get("accounts") or []
    m = d["msg"]
    if m.startswith("ok:"):
        _, fo, rd = m.split(":"); st = L("Última procura: %s e-mails analisados, %s faturas novas." % (rd, fo), "Last scan: %s emails analysed, %s new invoices." % (rd, fo))
    elif m == "no-acc": st = L("Não há contas de e-mail ligadas. Liga uma no separador Emails.", "No email accounts linked. Add one in the Emails tab.")
    elif m.startswith("err:"): st = L("A procura falhou: ", "Scan failed: ") + E(m[4:])
    else: st = L("Ainda não procurei faturas.", "No scan yet.")
    when = (" · " + time.strftime("%d/%m %H:%M", time.localtime(d["last"]))) if d["last"] else ""
    rows = ""
    for x in d["pending"]:
        due = x["due"] or ""
        rows += (f'<div class="b"><form method="post" action="/finance/bills/ok"><input type="hidden" name="id" value="{x["id"]}">'
                 f'<div><b>{E(x["issuer"])}</b> <span class="mut">· {E(x["desc"])}</span></div>'
                 f'<div class="mut">{L("Conta", "Account")}: {E(x["acc"])} · {L("De", "From")}: {E(x["from"])} · {E(x["date"])}'
                 f'{" · " + L("recorrente", "recurring") if x["rec"] else ""}{" · ref. " + E(x["ref"]) if x["ref"] else ""}</div>'
                 f'<div class="r"><input name="issuer" value="{E(x["issuer"])}" aria-label="{L("Emissor", "Issuer")}"> <input name="amount" value="{x["amount"]:.2f}" size="8" inputmode="decimal" aria-label="€"> €'
                 f' <input type="date" name="due" value="{E(due)}" aria-label="{L("Vencimento", "Due date")}">'
                 f' <label><input type="checkbox" name="rec" value="1"{" checked" if x["rec"] else ""}> {L("recorrente", "recurring")}</label>'
                 f' <button>✔ {L("Confirmar", "Confirm")}</button>'
                 f'<button class="g" formaction="/finance/bills/ignore">✕ {L("Ignorar", "Ignore")}</button></div></form></div>')
    trk = "".join(f'<div class="t"><span><b>{E(t["issuer"])}</b> · {t["amount"]:.2f} € · {L("vence", "due")} {E(t["due"])}{" · ref. " + E(t["ref"]) if t["ref"] else ""}</span>'
                  f'<form method="post" action="/finance/bills/paid"><input type="hidden" name="id" value="{t["id"]}"><button>✔ {L("Já paguei", "Paid")}</button>'
                  f'<button class="g" formaction="/finance/bills/drop">✕</button></form></div>' for t in sorted(d["tracked"], key=lambda t: t["due"]))
    rls = "".join(f'<form method="post" action="/finance/bills/forget" class="t"><input type="hidden" name="rule" value="{E(k)}"><span>{E(r["issuer"])} · {L("todos os meses, dia", "monthly, day")} {r["day"]} · ~{r["amount"]:.2f} €</span>'
                  f'<button class="g">{L("Parar", "Stop")}</button></form>' for k, r in d["rules"].items())
    accs = "".join(f'<form method="post" action="/finance/bills/toggle" class="t"><input type="hidden" name="acc" value="{E(a.get("id", ""))}">'
                   f'<span>{E(a.get("name") or a.get("imap_user") or "")}</span><button class="g">{L("ligado", "on") if a.get("id") not in d["off"] else L("desligado", "off")}</button></form>' for a in acc)
    auto = (f'<form method="post" action="/finance/bills/auto" class="t"><span>{L("Procura automática diária (08:17) (avisa-me quando houver faturas novas)", "Automatic daily scan (08:17) (notify me about new invoices)")}</span>'
            f'<button class="g">{L("ligada", "on") if d["auto"] else L("desligada", "off")}</button></form>')
    lrn = "".join(f'<form method="post" action="/finance/bills/unlearn" class="t"><input type="hidden" name="addr" value="{E(a)}"><span>{E(a)} · {L("sempre analisado", "always scanned")}</span><button class="g">✕</button></form>' for a in d["learned"]) + \
          "".join(f'<form method="post" action="/finance/bills/unlearn" class="t"><input type="hidden" name="addr" value="{E(a)}"><span>{E(a)} · {L("ignorado", "muted")}</span><button class="g">{L("voltar a analisar", "scan again")}</button></form>' for a in d["muted"])
    css = ("<style>body{background:#1d2026;color:#eee;font-family:system-ui;max-width:900px;margin:auto;padding:16px}.mut{color:#9aa}.b{background:#262a31;border-radius:10px;padding:12px;margin:10px 0}"
           ".r{margin-top:8px}input,button{padding:8px;border-radius:6px;border:1px solid #444;background:#2a2e36;color:#eee;margin:3px}button{background:#4a7bd0;border:0;cursor:pointer}"
           "button.g{background:#444}.t{display:flex;justify-content:space-between;align-items:center;background:#262a31;border-radius:8px;padding:4px 10px;margin:4px 0}"
           ".big{padding:12px 20px;font-size:16px}</style>")
    al = "".join(f'<div class="b" style="border-left:4px solid #d9534f"><b>⚠️ {E(x.get("issuer") or x.get("from"))}</b> {E(x.get("date"))}<br>{E(x.get("desc"))}{(" · %.2f €" % x["amount"]) if x.get("amount") else ""}'
                 f'<form method="post" action="/finance/bills/alertok" class="t"><input type="hidden" name="id" value="{E(x["id"])}"><button class="g">{L("Já vi", "Seen")}</button></form></div>' for x in d.get("alerts", []))
    al = (f'<h2>⚠️ {L("Avisos de pagamento falhado", "Failed-payment alerts")}</h2>' + al) if al else ""
    return (css + al + f'<h1>{L("Faturas detetadas no e-mail", "Invoices found in email")}</h1>'
            f'<p class="mut">{L("Procuro nos últimos %d dias nas contas ligadas. Nada entra nas Finanças sem confirmares. O texto dos e-mails relevantes (e dos PDFs em anexo) é analisado pelo Groq e não é guardado." % DAYS, "I scan the last %d days in your linked accounts. Nothing reaches Finance until you confirm. The text of relevant emails (and attached PDFs) is analysed by Groq and is not stored." % DAYS)}</p>'
            f'<form method="post" action="/finance/bills/scan"><button class="big">🔎 {L("Procurar faturas agora", "Scan for invoices now")}</button></form>'
            f'<p class="mut">{st}{when}</p>'
            f'<h2>{L("Por confirmar", "To confirm")} ({len(d["pending"])})</h2>{rows or "<p class=mut>" + L("Nada por confirmar.", "Nothing to confirm.") + "</p>"}'
            f'<h2>{L("A pagar (lembrete na véspera e no dia)", "To pay (reminder the day before and on the day)")}</h2>{trk or "<p class=mut>" + L("Nada a pagar.", "Nothing to pay.") + "</p>"}'
            f'<h2>{L("Faturas recorrentes", "Recurring invoices")}</h2>{rls or "<p class=mut>" + L("Nenhuma. Marca «recorrente» ao confirmar.", "None. Tick “recurring” when confirming.") + "</p>"}'
            f'<h2>{L("Automático", "Automatic")}</h2>{auto}'
            f'<h2>{L("Remetentes aprendidos", "Learned senders")}</h2>{lrn or "<p class=mut>" + L("Aprendo ao confirmares uma fatura; ao ignorares 2 vezes o mesmo remetente deixo de o analisar.", "I learn when you confirm an invoice; after you ignore the same sender twice I stop scanning it.") + "</p>"}'
            f'<h2>{L("Contas a analisar", "Accounts to scan")}</h2>{accs or "<p class=mut>" + L("Nenhuma conta ligada.", "No accounts linked.") + "</p>"}'
            f'<p><a href="/finance/emails" style="color:#8ab4f8">← Emails</a></p>')
