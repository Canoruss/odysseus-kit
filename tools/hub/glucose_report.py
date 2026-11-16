"""Glicose: analise (tempo no alvo, GMI, variabilidade, perfil AGP, padroes). Funcoes puras sobre as leituras."""
import html, json, math, time

LOW, VLOW, HIGH, VHIGH = 70, 54, 180, 250
E = html.escape


def _pct(vals, p):
    if not vals:
        return None
    v = sorted(vals); k = (len(v) - 1) * p / 100.0; f = math.floor(k); c = math.ceil(k)
    return v[int(k)] if f == c else v[f] + (v[c] - v[f]) * (k - f)


def metrics(readings, days, now=None):
    now = now or time.time()
    r = [x for x in readings if x["t"] >= now - days * 86400]
    n = len(r)
    if n < 12:
        return None
    vs = [x["v"] for x in r]
    mean = sum(vs) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in vs) / n)
    c = lambda f: 100.0 * sum(1 for v in vs if f(v)) / n
    expected = days * 96  # uma leitura de 15 em 15 min
    return {"n": n, "days": days, "mean": mean, "sd": sd, "cv": 100 * sd / mean if mean else 0,
            "gmi": 3.31 + 0.02392 * mean, "coverage": min(100.0, 100.0 * n / expected),
            "vlow": c(lambda v: v < VLOW), "low": c(lambda v: VLOW <= v < LOW), "in": c(lambda v: LOW <= v <= HIGH),
            "high": c(lambda v: HIGH < v <= VHIGH), "vhigh": c(lambda v: v > VHIGH), "r": r}


def agp(r):
    """-> lista de 24 (hora, p10, p25, p50, p75, p90) ou None quando faltam dados."""
    by = {h: [] for h in range(24)}
    for x in r:
        by[time.localtime(x["t"]).tm_hour].append(x["v"])
    out = []
    for h in range(24):
        v = by[h]
        out.append((h, *(_pct(v, p) for p in (10, 25, 50, 75, 90))) if len(v) >= 3 else (h, None, None, None, None, None))
    return out if sum(1 for o in out if o[1] is not None) >= 12 else None


def agp_svg(prof):
    if not prof:
        return '<p class="gmut">Ainda há poucas leituras para o perfil diário (precisa de alguns dias).</p>'
    W, H, L, B = 600, 230, 34, 22; lo, hi = 40, 300; pw, ph = W - L - 8, H - B - 8
    X = lambda h: L + (h + .5) / 24 * pw
    Y = lambda v: 8 + ph - (min(max(v, lo), hi) - lo) / (hi - lo) * ph
    pts = [o for o in prof if o[1] is not None]
    def band(i, j, col, op):
        up = " ".join("%.1f,%.1f" % (X(o[0]), Y(o[j])) for o in pts)
        dn = " ".join("%.1f,%.1f" % (X(o[0]), Y(o[i])) for o in reversed(pts))
        return '<polygon points="%s %s" fill="%s" opacity="%s"/>' % (up, dn, col, op)
    g = '<rect x="%d" y="%.1f" width="%d" height="%.1f" fill="#4aa86b" opacity=".10"/>' % (L, Y(HIGH), pw, Y(LOW) - Y(HIGH))
    for v in (VLOW, LOW, HIGH, VHIGH):
        g += '<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#888" stroke-opacity=".35" stroke-dasharray="3 4"/><text x="%d" y="%.1f" font-size="10" fill="#999" text-anchor="end">%d</text>' % (L, L + pw, Y(v), Y(v), L - 4, Y(v) + 3, v)
    for h in range(0, 24, 3):
        g += '<text x="%.1f" y="%d" font-size="10" fill="#999" text-anchor="middle">%02d</text>' % (X(h), H - 6, h)
    med = " ".join("%.1f,%.1f" % (X(o[0]), Y(o[3])) for o in pts)
    return ('<svg viewBox="0 0 %d %d" width="100%%" role="img" aria-label="Perfil diário de glicose">%s%s%s<polyline fill="none" stroke="#4a7bd0" stroke-width="2.5" points="%s"/></svg>'
            % (W, H, g, band(1, 5, "#6aa0ff", ".18"), band(2, 4, "#6aa0ff", ".34"), med))


def patterns(r):
    hrs = {h: [0, 0, 0] for h in range(24)}
    for x in r:
        a = hrs[time.localtime(x["t"]).tm_hour]; a[0] += 1; a[1] += x["v"] < LOW; a[2] += x["v"] > HIGH
    out = []
    for idx, label, thr in ((1, "hipoglicemias (abaixo de %d)" % LOW, 10), (2, "glicose alta (acima de %d)" % HIGH, 35)):
        cand = [h for h, a in hrs.items() if a[0] >= 6 and 100.0 * a[idx] / a[0] >= thr]
        if not cand:
            continue
        runs = [[cand[0]]]
        for h in cand[1:]:
            if h == runs[-1][-1] + 1:
                runs[-1].append(h)
            else:
                runs.append([h])
        best = max(runs, key=lambda run: sum(hrs[h][idx] for h in run) / max(1, sum(hrs[h][0] for h in run)))
        pc = 100.0 * sum(hrs[h][idx] for h in best) / sum(hrs[h][0] for h in best)
        out.append("Mais %s entre as %02d:00 e as %02d:00 (%.0f%% das leituras nessa janela)." % (label, best[0], (best[-1] + 1) % 24, pc))
    return out or ["Sem padrões claros por hora do dia neste período."]


CSS = """<style>
.gr{max-width:640px}.gr .tabs{display:flex;gap:6px;margin:6px 0}.gr .tabs button{background:#2a2e36;border:0;color:#ccc;border-radius:16px;padding:6px 14px;cursor:pointer}.gr .tabs button.on{background:#4a7bd0;color:#fff}
.gr .tir{display:flex;height:26px;border-radius:13px;overflow:hidden;margin:8px 0}.gr .tir i{display:block;height:100%}
.gr .lg{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:#aaa}.gr .lg b{color:#eee}.gr .lg span:before{content:"";display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;background:var(--c);vertical-align:-1px}
.gr .kp{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin:10px 0}.gr .kp div{background:#23272e;border-radius:10px;padding:8px 10px}.gr .kp small{display:block;color:#9aa;font-size:11px}.gr .kp b{font-size:20px}
.gr .gmut{color:#9aa;font-size:12px}.gr ul{margin:6px 0 6px 18px;padding:0}.gr .ok{color:#70d080}.gr .no{color:#e0b050}
@media print{body *{visibility:hidden}.gr,.gr *{visibility:visible}.gr{position:absolute;left:0;top:0;width:100%;color:#000}body{background:#fff!important}.gr .kp div{background:#f2f2f2;color:#000}.gr .tabs,.gr .noprint{display:none}}
</style>"""
COLS = (("vlow", "#a02030", "Muito baixo (&lt;54)"), ("low", "#e0674f", "Baixo (54-69)"), ("in", "#4aa86b", "No alvo (70-180)"), ("high", "#e0b050", "Alto (181-250)"), ("vhigh", "#d97a1f", "Muito alto (&gt;250)"))


def summary_text(m):
    return ("Glicose, últimos %d dias (%d leituras, %.0f%% do tempo com sensor): média %.0f mg/dL, GMI %.1f%%, variabilidade (CV) %.0f%%. "
            "No alvo 70-180: %.0f%%; abaixo de 70: %.0f%% (abaixo de 54: %.0f%%); acima de 180: %.0f%% (acima de 250: %.0f%%)."
            % (m["days"], m["n"], m["coverage"], m["mean"], m["gmi"], m["cv"], m["in"], m["low"] + m["vlow"], m["vlow"], m["high"] + m["vhigh"], m["vhigh"]))


def _panel(m):
    bar = "".join('<i style="width:%.2f%%;background:%s" title="%.0f%%"></i>' % (m[k], c, m[k]) for k, c, _ in COLS if m[k] > 0)
    leg = "".join('<span style="--c:%s">%s <b>%.0f%%</b></span>' % (c, t, m[k]) for k, c, t in COLS)
    cls = lambda ok: "ok" if ok else "no"
    goals = ('<ul class="gmut"><li class="%s">No alvo: %.0f%% (meta internacional: mais de 70%%)</li><li class="%s">Abaixo de 70: %.0f%% (meta: menos de 4%%)</li>'
             '<li class="%s">Abaixo de 54: %.0f%% (meta: menos de 1%%)</li><li class="%s">Variabilidade CV: %.0f%% (meta: até 36%%)</li></ul>'
             % (cls(m["in"] > 70), m["in"], cls(m["low"] + m["vlow"] < 4), m["low"] + m["vlow"], cls(m["vlow"] < 1), m["vlow"], cls(m["cv"] <= 36), m["cv"]))
    kp = ('<div class="kp"><div><small>Média</small><b>%.0f</b> <small style="display:inline">mg/dL</small></div><div><small>GMI (estimativa da HbA1c)</small><b>%.1f%%</b></div>'
          '<div><small>Variabilidade (CV)</small><b>%.0f%%</b></div><div><small>Sensor ativo</small><b>%.0f%%</b></div></div>' % (m["mean"], m["gmi"], m["cv"], m["coverage"]))
    pat = "".join("<li>%s</li>" % E(p) for p in patterns(m["r"]))
    return (kp + '<b>Tempo no alvo</b><div class="tir">%s</div><div class="lg">%s</div>%s<b>Perfil diário (mediana e variação)</b>%s'
            '<div class="gmut">Linha: mediana. Faixa escura: 25-75%%. Faixa clara: 10-90%%. Verde: alvo 70-180.</div><b>Padrões</b><ul>%s</ul>'
            % (bar, leg, goals, agp_svg(agp(m["r"])), pat))


def card(readings, now=None):
    ms = [(d, metrics(readings, d, now)) for d in (7, 14, 30)]
    ms = [(d, m) for d, m in ms if m]
    if not ms:
        return '<div class="box gr"><h2>Análise</h2><p class="gmut">Ainda há poucas leituras para analisar.</p></div>'
    first = 1 if len(ms) > 1 else 0
    tabs = "".join('<button type="button" class="%s" onclick="grT(%d)">%d dias</button>' % ("on" if i == first else "", i, d) for i, (d, _) in enumerate(ms))
    panels = "".join('<div class="grp" style="display:%s">%s<div class="noprint" style="margin-top:10px"><button type="button" onclick="window.print()">Imprimir / guardar PDF</button> '
                     '<button type="button" onclick="grC(%s,this)">Copiar resumo</button></div></div>' % ("" if i == first else "none", _panel(m), E(json.dumps(summary_text(m), ensure_ascii=False), quote=True))
                     for i, (_, m) in enumerate(ms))
    js = ("<script>function grT(i){document.querySelectorAll('.gr .grp').forEach((e,k)=>e.style.display=k==i?'':'none');"
          "document.querySelectorAll('.gr .tabs button').forEach((e,k)=>e.className=k==i?'on':'')}"
          "function grC(t,b){navigator.clipboard.writeText(t).then(()=>{b.textContent='Copiado'})}</script>")
    return CSS + '<div class="box gr"><h2>Análise da glicose</h2><div class="tabs">%s</div>%s%s<p class="gmut">Estimativas a partir do sensor; não substituem a consulta. O GMI não é igual à análise de laboratório.</p></div>' % (tabs, panels, js)
