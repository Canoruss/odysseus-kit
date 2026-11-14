"""Configuracao central do Odysseus KIT. Escrita pelo assistente de configuracao (setup/), lida por todas as ferramentas.
Ordem: variavel de ambiente KIT_<NOME>  >  ~/.config/odysseus-kit/config.json  >  valor por omissao."""
import json, os

HOME = os.path.expanduser("~")
CONF_DIR = os.environ.get("KIT_CONF_DIR", os.path.join(HOME, ".config", "odysseus-kit"))
_TOOLS = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(CONF_DIR, "config.json"), encoding="utf-8") as _f:
        _conf = json.load(_f)
except Exception:
    _conf = {}


def get(key, default=""):
    return os.environ.get("KIT_" + key.upper(), _conf.get(key, default))


def feature(name, default=True):
    """Funcionalidade ativa? (o assistente guarda 'features': {nome: true/false})."""
    v = os.environ.get("KIT_FEATURE_" + name.upper())
    if v is not None:
        return v not in ("0", "false", "no", "")
    return bool(_conf.get("features", {}).get(name, default))


def secret_file(name):
    """Ficheiro com chaves, ex.: secret_file('groq') -> ~/.config/odysseus-kit/groq.env"""
    return os.path.join(CONF_DIR, name + ".env")


OWNER = get("owner", "owner")                  # utilizador administrador do Odysseus
MEMBER = get("member", "member")               # segundo utilizador (opcional)
TESTER = get("tester", "kit-test")             # conta de testes (opcional)
OWNER_NAME = get("owner_name", "Owner")
MEMBER_NAME = get("member_name", "Member")
PUBLIC_URL = get("public_url", "https://YOUR-SERVER.YOUR-TAILNET.ts.net").rstrip("/")
HUB = get("hub_dir", os.path.join(_TOOLS, "hub"))                    # onde ficam os dados das ferramentas
JOBS_STATE = get("jobs_dir", os.path.join(HOME, ".local", "share", "odysseus-kit", "jobs"))
SHARE_DIR = get("share_dir", os.path.join(HOME, ".local", "share", "odysseus-kit", "share"))
os.makedirs(JOBS_STATE, exist_ok=True)
