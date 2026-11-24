"""Lembretes na conta de cada utilizador do Odysseus (todas as funcionalidades sao para todos).
- administrador (OWNER): API do agente (lib.add_todo)
- membro (MEMBER): login com as credenciais em ~/.config/odysseus-kit/member.env e POST /api/notes com due_date
USERS: nome curto usado nos ficheiros das ferramentas (ex.: flights-<nome>.json) -> credenciais."""
import datetime, http.cookiejar, json, os, re, sys, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kitconfig import OWNER, MEMBER, secret_file
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hub")); import quiet
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

B = os.environ.get("ODYSSEUS_LOCAL_URL", "http://127.0.0.1:7860")
slug = lambda n: re.sub(r"[^a-z0-9]", "", str(n).lower())
USERS = {slug(OWNER): None}
if MEMBER and slug(MEMBER) != slug(OWNER) and os.path.exists(secret_file("member")):
    USERS[slug(MEMBER)] = (secret_file("member"), "ODY_USER", "ODY_PASSWORD")
_sessions = {}


def _env(path):
    out = {}
    for l in open(os.path.expanduser(path)):
        if "=" in l and not l.startswith("#"):
            k, v = l.strip().split("=", 1); out[k] = v.strip().strip("'\"")
    return out


def _session(user):
    if user in _sessions: return _sessions[user]
    path, ku, kp = USERS[user]
    e = _env(path)
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    r = urllib.request.Request(B + "/api/auth/login", json.dumps({"username": e[ku], "password": e[kp]}).encode(), {"Content-Type": "application/json"})
    op.open(r, timeout=30)
    _sessions[user] = op
    return op


def add_reminder(user, title, when=None, urgent=False):
    """Cria um lembrete (com notificacao) na conta do utilizador. Devolve (ok, mensagem)."""
    when = when or (lib.now() + datetime.timedelta(minutes=1))
    if not urgent:                       # quiet hours (Focus/Cycle tabs): wait until they end
        try: when = quiet.shift(user, when)
        except Exception: pass
    if user not in USERS: return False, "utilizador desconhecido: " + user
    if USERS[user] is None:
        return lib.add_todo(title, when)
    try:
        due = when.replace(tzinfo=None, microsecond=0).isoformat()
        r = urllib.request.Request(B + "/api/notes", json.dumps({"title": title, "content": "", "due_date": due}).encode(), {"Content-Type": "application/json"})
        st = _session(user).open(r, timeout=30).status
        return st == 200, "HTTP %d" % st
    except Exception as e:
        return False, repr(e)[:120]
