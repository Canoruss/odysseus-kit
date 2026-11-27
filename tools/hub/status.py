"""Aba Estado: uso dos modelos (todos) + estado do servidor e atividade recente (só admin). PT-PT / EN. Auto-refresh 30 s."""
import html, subprocess
import usage

def _sh(c):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=8).stdout.strip()
    except Exception: return ""

def render(lang="pt", admin=False):
    en = lang == "en"
    T = (lambda p, e: e if en else p)
    e = html.escape
    out = ["<meta http-equiv='refresh' content='30'><style>.bar{height:6px;background:#3a3f48;border-radius:3px;overflow:hidden}.bar i{display:block;height:100%;background:#6ea5cf}.bar i.hi{background:#d9a441}.bar i.cr{background:#d9534f}.r{display:flex;justify-content:space-between;font-size:13px;margin-top:6px}small{opacity:.65}pre{white-space:pre-wrap;font-size:12px;margin:4px 0}</style>"]
    try: d = usage.get()
    except Exception: d = {"items": [], "updated": "?"}
    out.append(f"<h2>{T('Uso dos modelos','Model usage')} <small>{T('atualizado','updated')} {e(str(d.get('updated','')))}</small></h2>")
    for it in d.get("items", []):
        out.append(f"<div class='box'><b>{e(it['name'])}</b>")
        for r in it.get("rows", []):
            p = max(0, min(100, int(r.get("pct", 0)))); c = "cr" if p >= 90 else "hi" if p >= 70 else ""
            out.append(f"<div class='r'><span>{e(r['label'])}</span><span>{p}% · <small>{e(str(r.get('reset','')))}</small></span></div><div class='bar'><i class='{c}' style='width:{p}%'></i></div>")
        if it.get("note"): out.append(f"<div><small>{e(it['note'])}</small></div>")
        out.append("</div>")
    if admin:
        disk = _sh("df -h / | tail -1 | awk '{print $3\" / \"$2\" (\"$5\")\"}'")
        mem = _sh("free -m | awk '/Mem/{printf \"%.1fG / %.1fG (%d%%)\", $3/1024, $2/1024, $3*100/$2}'")
        swap = _sh("free -m | awk '/Swap/{if($2>0)printf \"%.1fG / %.1fG (%d%%)\", $3/1024, $2/1024, $3*100/$2; else print \"0\"}'")
        cpu = _sh("a=$(awk '/^cpu /{print $2+$3+$4+$7+$8, $2+$3+$4+$5+$6+$7+$8}' /proc/stat); sleep 0.5; b=$(awk '/^cpu /{print $2+$3+$4+$7+$8, $2+$3+$4+$5+$6+$7+$8}' /proc/stat); echo $a $b | awk '{d=$4-$2; if(d>0)printf \"%d%%\", ($3-$1)*100/d; else print \"0%\"}'") + f" · {_sh('nproc')} cores"
        load = _sh("cut -d' ' -f1-3 /proc/loadavg")
        ctrs = _sh("docker ps --format '{{.Names}}|{{.Status}}' | sort")
        rows = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in (l.split("|", 1) for l in ctrs.splitlines() if "|" in l))
        out.append(f"<h2>{T('Servidor','Server')}</h2><div class='box'><b>{T('Disco','Disk')}:</b> {e(disk)}<br><b>RAM:</b> {e(mem)}<br><b>Swap:</b> {e(swap)}<br><b>CPU:</b> {e(cpu)}<br><b>{T('Carga','Load')}:</b> {e(load)}</div>")
        out.append(f"<div class='box'><b>{T('Contentores','Containers')}</b><table>{rows}</table></div>")
        out.append(f"<h2>{T('Atividade recente','Recent activity')}</h2><div class='box'><b>{T('Verificações','Checks')}</b><pre>{e(_sh('tail -6 ~/health-check.log'))}</pre><b>{T('Pós-deploy','Post-deploy')}</b><pre>{e(_sh('tail -3 ~/post-deploy.log'))}</pre><b>{T('Guarda de serviços','Service guard')}</b><pre>{e(_sh('tail -4 ~/guard-services.log'))}</pre></div>")
        bk = _sh("ls -lh --time-style=long-iso ~/backups/images/*.tar.gz 2>/dev/null | awk '{print $6\" \"$7\"  \"$5\"  \"$8}'")
        out.append(f"<div class='box'><b>{T('Backup da imagem','Image backup')}</b> ({e(_sh('cat ~/backups/images/.last-save'))})<pre>{e(bk)}</pre><small>{T('Restaurar','Restore')}: gunzip -c ficheiro.tar.gz | docker load</small></div>")
    return "".join(out)
