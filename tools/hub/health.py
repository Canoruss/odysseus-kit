"""Saude do relogio (Health Connect do Android) -> cartao no Gym. Dados por conta em health-<user>.json."""
import os, re, json, time, html, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
E = html.escape


def T(lang, pt, en): return en if lang == "en" else pt


def _p(u): return os.path.join(HERE, "health-%s.json" % re.sub(r"[^a-z0-9_-]", "", str(u).lower()))


def load(u):
    try: d = json.load(open(_p(u)))
    except (OSError, ValueError): d = {}
    d.setdefault("days", {}); d.setdefault("workouts", [])
    return d


def _save(u, d):
    p = _p(u); tmp = p + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _num(v, lo, hi):
    try: x = float(v)
    except (TypeError, ValueError): return None
    return round(x, 1) if lo <= x <= hi else None


def ingest(u, j):
    """j = {days:[{date,steps,kcal,hr_min,hr_avg,hr_max,hr_rest,sleep_min,spo2_avg,spo2_min}], workouts:[{start,end,type,kcal,hr_avg,hr_max}]}"""
    d = load(u); n = 0
    if j.get("diag"): d["diag"] = re.sub(r"[^\w ,:/.()-]", "", str(j["diag"]))[:200]; d["diag_at"] = int(time.time())
    if isinstance(j.get("sources"), list):
        d["sources"] = sorted({re.sub(r"[^a-zA-Z0-9._]", "", str(x))[:80] for x in j["sources"][:20]} - {""})
    for r in (j.get("days") or [])[:60]:
        try: dt = datetime.date.fromisoformat(str(r.get("date")))
        except ValueError: continue
        row = {k: _num(r.get(k), lo, hi) for k, lo, hi in (("steps", 0, 200000), ("kcal", 0, 20000), ("hr_min", 20, 250),
               ("hr_avg", 20, 250), ("hr_max", 20, 250), ("hr_rest", 20, 200), ("sleep_min", 0, 1440), ("spo2_avg", 50, 100), ("spo2_min", 50, 100))}
        d["days"][dt.isoformat()] = {k: v for k, v in row.items() if v is not None}; n += 1
    seen = {w.get("start") for w in d["workouts"]}
    for w in (j.get("workouts") or [])[:100]:
        s = str(w.get("start") or "")[:25]
        if not s or s in seen: continue
        d["workouts"].append({"start": s, "end": str(w.get("end") or "")[:25], "type": re.sub(r"[^\w .-]", "", str(w.get("type") or ""))[:40],
                              "kcal": _num(w.get("kcal"), 0, 20000), "hr_avg": _num(w.get("hr_avg"), 20, 250), "hr_max": _num(w.get("hr_max"), 20, 250)})
        seen.add(s); n += 1
    d["workouts"] = sorted(d["workouts"], key=lambda w: w["start"])[-200:]
    d["days"] = dict(sorted(d["days"].items())[-120:]); d["updated"] = int(time.time())
    _save(u, d)
    return {"ok": True, "n": n}


CSS = """<style>
.hw{--r:#e0262d;display:grid;gap:10px}.hw .c{background:#1c1c1e;border-radius:18px;padding:14px;color:#eee}
.hw h3{margin:0 0 8px;font-size:13px;font-weight:600;color:#bbb}.hw .g2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.hw .big{font-size:26px;font-weight:700;letter-spacing:1px}.hw .sm{font-size:11px;color:#999}
.hw .ring{display:flex;align-items:center;gap:14px}.hw .leg div{display:flex;justify-content:space-between;gap:14px;font-size:13px;margin:3px 0}
.hw .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px}
.hw .bars{display:flex;align-items:flex-end;gap:6px;height:64px;margin-top:8px}.hw .bars i{flex:1;background:#eee;border-radius:3px;min-height:2px;display:block}
.hw .bars i.t{background:var(--r)}.hw .bl{display:flex;gap:6px;font-size:10px;color:#888;margin-top:3px}.hw .bl span{flex:1;text-align:center}
.hw .row{display:flex;justify-content:space-between;padding:7px 10px;margin-top:5px;background:#262628;border-radius:10px;font-size:13px}
.hw .wk{display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid #2c2c2e;font-size:13px}
</style>"""


def _ring(parts, size=96):
    """parts = [(fraction 0..1, color)] aneis concentricos."""
    import math
    out = ['<svg width="%d" height="%d" viewBox="0 0 100 100">' % (size, size)]
    for n, (fr, col) in enumerate(parts):
        r = 44 - n * 10; c = 2 * math.pi * r; fr = max(0.0, min(1.0, fr or 0))
        out.append('<circle cx="50" cy="50" r="%d" fill="none" stroke="#333" stroke-width="7"/>' % r)
        out.append('<circle cx="50" cy="50" r="%d" fill="none" stroke="%s" stroke-width="7" stroke-linecap="round" '
                   'stroke-dasharray="%.1f %.1f" transform="rotate(-90 50 50)"/>' % (r, col, c * fr, c))
    return "".join(out) + "</svg>"


def _bars(days, key, lang, fmt=None):
    vals = [v.get(key) for _, v in days]; mx = max([x for x in vals if x] or [1])
    bs = "".join('<i%s style="height:%d%%" title="%s"></i>' % (' class="t"' if n == len(days) - 1 else "", max(3, int(100 * (x or 0) / mx)),
                 ("%g" % x) if x else "–") for n, x in enumerate(vals))
    wd = (["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"], ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])[lang == "en"]
    ls = "".join("<span>%s</span>" % wd[datetime.date.fromisoformat(k).weekday()] for k, _ in days)
    return '<div class="bars">%s</div><div class="bl">%s</div>' % (bs, ls)

APPS = [  # (package prefix, name, how to enable sync with Health Connect: pt, en)
    ("com.nothing", "Nothing X", "Definições › Health Connect › ligar", "Settings › Health Connect › turn on"),
    ("com.sec.android.app.shealth", "Samsung Health", "Definições › Health Connect › ligar partilha", "Settings › Health Connect › turn on sharing"),
    ("com.google.android.apps.fitness", "Google Fit", "Perfil › Definições › Health Connect", "Profile › Settings › Health Connect"),
    ("com.fitbit", "Fitbit", "Hoje › Perfil › Definições da app › Health Connect", "Today › Profile › App settings › Health Connect"),
    ("com.garmin", "Garmin Connect", "Mais › Definições › Apps ligadas › Health Connect", "More › Settings › Connected apps › Health Connect"),
    ("com.huami", "Zepp (Amazfit)", "Perfil › Adicionar contas › Health Connect", "Profile › Add accounts › Health Connect"),
    ("com.xiaomi", "Mi Fitness (Xiaomi)", "Perfil › Definições › Health Connect", "Profile › Settings › Health Connect"),
    ("com.ouraring", "Oura", "Definições › Health Connect", "Settings › Health Connect"),
    ("com.withings", "Withings", "Definições › Health Connect", "Settings › Health Connect"),
    ("fi.polar", "Polar Flow", "Definições › Health Connect", "Settings › Health Connect"),
    ("com.whoop", "WHOOP", "Definições › Health Connect", "Settings › Health Connect"),
]


def _src_name(pkg):
    for p, n, _a, _b in APPS:
        if pkg.startswith(p): return n
    return pkg


def _apps_html(lang):
    rows = "".join('<div class="row"><b>%s</b><span class="sm">%s</span></div>' % (E(n), E(T(lang, a, b))) for _p, n, a, b in APPS)
    return ('<div class="c"><h3>%s</h3><div class="sm">%s</div>%s<div class="sm" style="margin-top:8px">%s</div></div>' % (
        T(lang, "Apps compatíveis", "Compatible apps"),
        T(lang, "Qualquer app de saúde que escreva no Health Connect funciona. Ativa a sincronização na app do teu relógio:",
          "Any health app that writes to Health Connect works. Turn on syncing in your watch's app:"),
        rows,
        T(lang, "Huawei Health não suporta o Health Connect. Apple Health só existe no iPhone.",
          "Huawei Health does not support Health Connect. Apple Health only exists on iPhone.")))


def _btn(lang):
    return ('<p><button onclick="var n=window.OdysseusNative||(window.parent&&window.parent.OdysseusNative);'
            'if(n&&n.healthSync)n.healthSync();else alert(this.dataset.m)" data-m="%s" '
            'style="padding:10px 16px;border-radius:10px;border:0;background:#d71921;color:#fff;font-size:15px">%s</button></p>') % (
        E(T(lang, "Abre a app Android do Odysseus (versão mais recente).", "Open the Odysseus Android app (latest version).")),
        T(lang, "Sincronizar relógio agora", "Sync watch now"))


def box(u, lang="pt"):
    d = load(u)
    if not d["days"]:
        msg = T(lang, "Ainda sem dados. Na app Android, abre as Definições do Odysseus e ativa «Ligar Health Connect».",
                "No data yet. In the Android app, open Odysseus Settings and enable “Connect Health Connect”.")
        if d.get("diag"): msg += '<br><small>%s: %s</small>' % (T(lang, "Último estado da app", "Last app status"), E(d["diag"]))
        if d.get("sources"): msg += '<br><small>%s: %s</small>' % (T(lang, "Dados de", "Data from"), E(", ".join(_src_name(x) for x in d["sources"])))
        btn = _btn(lang)
        return '<div class="box"><h2>⌚ %s</h2><p style="color:#aaa">%s</p>%s<div class="hw">%s%s</div></div>' % (
            T(lang, "Relógio", "Watch"), msg, btn, CSS, _apps_html(lang))
    days = sorted(d["days"].items())[-7:]
    last_d, last = days[-1]
    def f(v, s=""): return ("%g%s" % (v, s)) if v is not None else "–"
    steps, kcal = last.get("steps"), last.get("kcal")
    sl = last.get("sleep_min")
    sleep = ("%dh%02d" % (sl // 60, sl % 60)) if sl else "–"
    today_wk = [w for w in d["workouts"] if w["start"][:10] == last_d]
    ex_min = 0
    for w in today_wk:
        try: ex_min += int((datetime.datetime.fromisoformat(w["end"][:19]) - datetime.datetime.fromisoformat(w["start"][:19])).total_seconds() // 60)
        except ValueError: pass
    ring = _ring([((kcal or 0) / 400, "#e0262d"), (ex_min / 30, "#fff"), ((steps or 0) / 5000, "#888")])
    leg = ('<div><span><i class="dot" style="background:#e0262d"></i>%s</span><b>%s/400</b></div>'
           '<div><span><i class="dot" style="background:#fff"></i>%s</span><b>%s/30</b></div>'
           '<div><span><i class="dot" style="background:#888"></i>%s</span><b>%s/5000</b></div>') % (
        T(lang, "Calorias (kcal)", "Calories (kcal)"), f(kcal), T(lang, "Exercício (min)", "Exercise (min)"), ex_min, T(lang, "Passos", "Steps"), f(steps))
    wk = "".join('<div class="wk"><span>%s · %s</span><span>%s · %s</span></div>' % (
        E(w["start"][5:16].replace("T", " ")), E(w.get("type") or "–"),
        ("♥ %s" % f(w.get("hr_avg"))) if w.get("hr_avg") else "", ("%s kcal" % f(w.get("kcal"))) if w.get("kcal") else "") for w in reversed(d["workouts"][-5:]))
    upd = time.strftime("%d/%m %H:%M", time.localtime(d.get("updated", 0)))
    return ('<div class="box"><h2>⌚ %s</h2>%s<div class="hw">'
            '<div class="c"><h3>%s</h3><div class="ring">%s<div class="leg" style="flex:1">%s</div></div></div>'
            '<div class="g2"><div class="c"><h3>♥ %s</h3><div class="big">%s <span class="sm">bpm</span></div>'
            '<div class="sm">%s %s · %s %s</div></div>'
            '<div class="c"><h3>🌙 %s</h3><div class="big">%s</div><div class="sm">%s</div></div></div>'
            '<div class="c"><h3>🫁 %s</h3><div class="big">%s <span class="sm">%%</span></div><div class="sm">%s %s%%</div></div>'
            '<div class="c"><h3>%s</h3><div class="big">%s</div>%s</div>'
            '<div class="c"><h3>♥ %s</h3>%s'
            '<div class="row"><span>%s</span><b>%s bpm</b></div><div class="row"><span>%s</span><b>%s bpm</b></div><div class="row"><span>%s</span><b>%s bpm</b></div></div>'
            '%s%s</div><p class="sm" style="margin-top:8px">%s %s · via Health Connect%s</p>%s</div>') % (
        T(lang, "Relógio", "Watch"), CSS,
        T(lang, "Atividade de hoje", "Today's activity"), ring, leg,
        T(lang, "Frequência cardíaca", "Heart rate"), f(last.get("hr_avg")),
        T(lang, "Repouso", "Resting"), f(last.get("hr_rest")), T(lang, "Máx.", "Max"), f(last.get("hr_max")),
        T(lang, "Sono", "Sleep"), sleep, T(lang, "Sem dados", "No data") if not sl else last_d[5:],
        T(lang, "Oxigénio no sangue (SpO2)", "Blood oxygen (SpO2)"), f(last.get("spo2_avg")), T(lang, "Mínimo", "Minimum"), f(last.get("spo2_min")),
        T(lang, "Passos (7 dias)", "Steps (7 days)"), f(steps), _bars(days, "steps", lang),
        T(lang, "BPM médio (7 dias)", "Avg BPM (7 days)"), _bars(days, "hr_avg", lang),
        T(lang, "Repouso", "Resting"), f(last.get("hr_rest")), T(lang, "Mais alto", "Highest"), f(last.get("hr_max")),
        T(lang, "Mais baixo", "Lowest"), f(last.get("hr_min")),
        ('<div class="c"><h3>%s</h3>%s</div>' % (T(lang, "Treinos recentes", "Recent workouts"), wk)) if wk else "",
        ('<details class="c"><summary class="sm">%s</summary>%s</details>' % (T(lang, "Apps compatíveis", "Compatible apps"), _apps_html(lang))),
        T(lang, "Atualizado", "Updated"), upd,
        (" · %s: %s" % (T(lang, "Dados de", "Data from"), E(", ".join(_src_name(x) for x in d["sources"])))) if d.get("sources") else "", _btn(lang))
