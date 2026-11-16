"""Ciclo (interface HTML). Usa o núcleo em period.py."""
import calendar, datetime, html
import period as P
E = html.escape
MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
WD = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
LABEL_EN = {"Cólicas": "Cramps", "Dor de cabeça": "Headache", "Seios sensíveis": "Breast tenderness", "Acne": "Acne", "Inchaço": "Bloating",
            "Cansaço": "Fatigue", "Irritabilidade": "Irritability", "Dor nas costas": "Back pain", "Mais apetite": "Increased appetite",
            "Náuseas": "Nausea", "Insónias": "Insomnia", "Desejo de doces": "Sugar cravings", "Tonturas": "Dizziness",
            "Dores musculares": "Muscle aches", "Libido alta": "High libido", "Feliz": "Happy", "Calma": "Calm", "Energética": "Energetic",
            "Ansiosa": "Anxious", "Triste": "Sad", "Irritada": "Irritable", "Sensível": "Sensitive", "Cansada": "Tired",
            "Manchas": "Spotting", "Leve": "Light", "Média": "Medium", "Intensa": "Heavy", "Negativo": "Negative", "Positivo": "Positive",
            "Sim": "Yes", "Sim, protegido": "Yes, protected"}
PHASES_EN = {
    "menstrual": ("Menstrual", "The body is renewing itself; energy is usually lower.",
                  ["Food: iron (legumes, leafy greens) and plenty of water.", "Movement: gentle walks and stretching.",
                   "Daily life: rest more; warmth on the belly helps with cramps."]),
    "folicular": ("Follicular", "Energy rises gradually and mood improves.",
                  ["Food: protein and fibre, colourful meals.", "Movement: a good time for tougher workouts or something new.",
                   "Daily life: a good phase to plan and start projects."]),
    "ovulatoria": ("Ovulatory", "Peak energy and fertility; skin and mood are often at their best.",
                   ["Food: light meals with antioxidants (berries, vegetables).", "Movement: intense or group workouts.",
                    "Daily life: great days for conversations and meeting people."]),
    "lutea": ("Luteal", "Progesterone rises; you may feel more tired, hungry and sensitive, especially near the end.",
              ["Food: complex carbs and magnesium (nuts, dark cocoa) help with hunger.", "Movement: yoga, pilates, walks.",
               "Daily life: cut back on commitments, sleep well, be kind to yourself."]),
}


def lab(x, lang):
    return LABEL_EN.get(x, x) if lang == "en" else x


def T(lang, pt, en):
    return en if lang == "en" else pt

CSS = """<style>
.cy{max-width:640px;margin:auto}
.cy .hd{display:flex;justify-content:space-between;align-items:center;margin:6px 0}
.cy .hd a,.cy .lnk{color:#8ab4f8;text-decoration:none;padding:6px 12px;border-radius:8px;background:#2a2e36;display:inline-block;margin:2px}
.cy .cards{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}
.cy .card{background:#262a31;border-radius:10px;padding:10px}
.cy .card.big{grid-column:1/-1;background:#2d2a45}
.cy .card b{display:block;font-size:1.05em;margin-top:4px}
.cy .mut{color:#999;font-size:.85em}
.cy table.cal{width:100%;border-collapse:separate;border-spacing:3px;table-layout:fixed}
.cy table.cal th{font-weight:500;color:#999;font-size:.8em;padding:4px 0}
.cy td.c{height:40px;text-align:center;border-radius:8px;background:#23272e}
.cy td.c a{display:block;color:#eee;text-decoration:none;padding:9px 0;font-size:.95em}
.cy td.out a{color:#555}.cy td.today{outline:2px solid #8ab4f8}.cy td.sel{box-shadow:0 0 0 2px #fff inset}
.cy td.fert{background:#1f4a35}.cy td.pms{background:#3d2c4f}.cy td.ov{background:#1e3f6b}
.cy td.pred{background:#3a1f22;border:1px dashed #d46a6a}.cy td.per{background:#c0392b}
.cy td.c .dot{display:block;height:4px;margin-top:-6px;font-size:0}
.cy td.has a{text-decoration:underline dotted}
.cy .leg{font-size:.8em;color:#aaa;margin:8px 0;display:flex;flex-wrap:wrap;gap:10px}
.cy .leg i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:middle}
.cy form.box label{display:block;margin:6px 0}
.cy .syms{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:6px 0}
.cy .syms label{font-size:.9em}
.cy .row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.cy input[type=text],.cy input[type=date],.cy input[type=number],.cy input[type=password],.cy select{width:100%;box-sizing:border-box}
.cy details{background:#262a31;border-radius:10px;padding:8px 12px;margin:10px 0}
.cy summary{cursor:pointer;font-weight:600}
.cy .tips li{margin:4px 0}
.cy .bars{display:flex;align-items:flex-end;gap:4px;height:90px;margin:6px 0}
.cy .bars div{flex:1;background:#4a7bd0;border-radius:3px 3px 0 0;position:relative;min-width:8px}
.cy .bars span{position:absolute;top:-16px;left:0;right:0;text-align:center;font-size:.7em;color:#bbb}
.cy .aviso{font-size:.8em;color:#aaa;margin-top:12px}
.cy .hero{display:flex;gap:14px;align-items:center;border-radius:18px;padding:14px 16px;margin:8px 0 12px;position:relative;overflow:hidden;background:linear-gradient(135deg,var(--g1),var(--g2))}
.cy .hero .art{position:absolute;right:-18px;top:-18px;width:150px;height:150px;opacity:.22;pointer-events:none}
.cy .hero .rg{flex:none;width:132px;height:132px}.cy .hero .tx{position:relative;z-index:1;min-width:0}
.cy .hero .tx small{color:#ffffffb0;font-size:.8em}.cy .hero .tx b{display:block;font-size:1.25em;margin:2px 0 4px;color:#fff}
.cy .hero .tx p{margin:0;color:#ffffffd0;font-size:.85em;line-height:1.35}
.cy .pic{width:44px;height:44px;flex:none}.cy details summary .pic{vertical-align:middle;margin-right:8px;width:30px;height:30px}
.cy .syms label{background:#23272e;border-radius:10px;padding:7px 9px}
.cy .chip{display:inline-block;margin-top:8px;padding:3px 11px;border-radius:12px;background:#ffffff26;color:#fff;font-size:.78em;font-weight:600}
.cy .lg4{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin:-4px 0 12px;font-size:.78em;color:#aab}
.cy .lg4 i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
.cy .cards .card{border-left:4px solid var(--c,#4a7bd0);display:flex;flex-direction:column;gap:2px}
.cy .cards .card .ic{font-size:1.25em;line-height:1}
.cy .hero:before{content:"";position:absolute;left:-30px;bottom:-40px;width:130px;height:130px;border-radius:50%;background:#ffffff14}
</style>"""


def _pt(dt, lang="pt"):
    return "%s %d" % (MONTHS_EN[dt.month - 1], dt.day) if lang == "en" else "%d de %s" % (dt.day, MONTHS[dt.month - 1])


def lock_page(msg=""):
    return (CSS + '<div class="cy"><h2>Ciclo</h2>' + ('<p class="red">%s</p>' % E(msg) if msg else "")
            + '<form method="post" action="/finance/period/unlock" class="box"><p>Esta área está protegida por PIN.</p>'
              '<input type="password" name="pin" inputmode="numeric" placeholder="PIN" autofocus required>'
              '<button>Entrar</button></form></div>')


def _tags(dt, days, info):
    t = set()
    if days.get(dt.isoformat(), {}).get("flow"):
        t.add("per")
    else:
        for s in info["starts"]:
            if s <= dt < s + datetime.timedelta(days=info["period"]):
                t.add("pred")
    if info["ov"] == dt:
        t.add("ov")
    if info["fert"] and info["fert"][0] <= dt <= info["fert"][1]:
        t.add("fert")
    if info["pms"] and info["pms"][0] <= dt <= info["pms"][1]:
        t.add("pms")
    return t


PH_COL = {"menstrual": ("#7a1f2e", "#c0392b", "#ff8a80"), "folicular": ("#1d4d3a", "#2e8b57", "#9be3b4"),
          "ovulatoria": ("#7a5a12", "#d99a1f", "#ffe08a"), "lutea": ("#2d2a5e", "#6a5acd", "#c3bcff")}
SYM_EMO = {"Cólicas": "🌀", "Dor de cabeça": "🤕", "Seios sensíveis": "🌸", "Acne": "✨", "Inchaço": "🎈", "Cansaço": "😴",
           "Irritabilidade": "⚡", "Dor nas costas": "🦴", "Mais apetite": "🍽️", "Náuseas": "🤢", "Insónias": "🌙",
           "Desejo de doces": "🍫", "Tonturas": "💫", "Dores musculares": "💪", "Libido alta": "🔥"}


def _icon(ph, size=44):
    """Ilustração SVG da fase (gota, rebento, flor, lua). Sem ficheiros externos."""
    c = PH_COL.get(ph, PH_COL["folicular"])[2]
    g = {"menstrual": '<path d="M32 6C32 6 14 28 14 40a18 18 0 0 0 36 0C50 28 32 6 32 6z" fill="%s"/><path d="M24 40a8 8 0 0 0 8 8" stroke="#fff" stroke-opacity=".6" stroke-width="3" fill="none" stroke-linecap="round"/>' % c,
         "folicular": '<path d="M32 58V30" stroke="%s" stroke-width="4" stroke-linecap="round"/><path d="M32 34C32 20 20 14 10 16c0 12 10 20 22 18z" fill="%s"/><path d="M32 28C32 16 42 8 54 10c0 12-10 20-22 18z" fill="%s" fill-opacity=".8"/>' % (c, c, c),
         "ovulatoria": '<circle cx="32" cy="32" r="9" fill="%s"/>%s' % (c, "".join('<ellipse cx="32" cy="12" rx="6" ry="10" fill="%s" fill-opacity=".85" transform="rotate(%d 32 32)"/>' % (c, a) for a in range(0, 360, 45))),
         "lutea": '<path d="M44 8a24 24 0 1 0 12 40A20 20 0 0 1 44 8z" fill="%s"/><circle cx="50" cy="14" r="2.5" fill="%s"/><circle cx="56" cy="26" r="1.8" fill="%s"/>' % (c, c, c)}.get(ph, "")
    return '<svg class="pic" width="%d" height="%d" viewBox="0 0 64 64" aria-hidden="true">%s</svg>' % (size, size, g)


def _ring(info, ph, day):
    """Anel do ciclo: 4 fases coloridas e um marcador no dia de hoje."""
    import math
    n = max(21, min(45, int(info.get("cycle") or 28))); per = max(2, min(9, int(info.get("period") or 5)))
    ov = max(per + 3, n - 14)
    segs = [("menstrual", 0, per), ("folicular", per, ov - 1), ("ovulatoria", ov - 1, ov + 2), ("lutea", ov + 2, n)]
    R, cx = 52, 66
    def pt(a, r=R):
        t = a / n * 2 * math.pi - math.pi / 2
        return cx + r * math.cos(t), cx + r * math.sin(t)
    out = []
    for k, a, b in segs:
        x1, y1 = pt(a); x2, y2 = pt(b)
        out.append('<path d="M%.1f %.1f A%d %d 0 %d 1 %.1f %.1f" stroke="%s" stroke-width="12" fill="none" stroke-linecap="butt" stroke-opacity="%s"/>'
                   % (x1, y1, R, R, 1 if (b - a) / n > .5 else 0, x2, y2, PH_COL[k][2], "1" if k == ph else ".5"))
    mk = ""
    if day:
        x, y = pt(((day - 1) % n) + .5)
        mk = '<circle cx="%.1f" cy="%.1f" r="9" fill="#fff"/><circle cx="%.1f" cy="%.1f" r="4" fill="%s"/>' % (x, y, x, y, PH_COL.get(ph, PH_COL["folicular"])[1])
    mid = ('<text x="66" y="68" text-anchor="middle" font-size="30" font-weight="700" fill="#fff">%d</text><text x="66" y="86" text-anchor="middle" font-size="10" fill="#ffffffb0">dia</text>' % day) if day else ""
    return '<svg class="rg" viewBox="0 0 132 132" aria-hidden="true">%s%s%s</svg>' % ("".join(out), mk, mid)


def _bars_icon():
    return '<svg class="pic" width="28" height="28" viewBox="0 0 64 64" aria-hidden="true"><rect x="10" y="34" width="10" height="20" rx="3" fill="#c3bcff"/><rect x="27" y="20" width="10" height="34" rx="3" fill="#c3bcff"/><rect x="44" y="8" width="10" height="46" rx="3" fill="#c3bcff"/></svg>'


def _legend(lang):
    nm = {"menstrual": T(lang, "Menstrual", "Menstrual"), "folicular": T(lang, "Folicular", "Follicular"),
          "ovulatoria": T(lang, "Ovulatória", "Ovulatory"), "lutea": T(lang, "Lútea", "Luteal")}
    return '<div class="lg4">%s</div>' % "".join('<span><i style="background:%s"></i>%s</span>' % (PH_COL[k][2], nm[k]) for k in nm)


def _hero(info, ph, lang, ch=""):
    if not ph[0]:
        return ""
    g1, g2, _ = PH_COL[ph[0]]
    pn = (PHASES_EN if lang == "en" else P.PHASES)[ph[0]]
    art = _icon(ph[0], 150).replace('class="pic"', 'class="art"')
    return ('<div class="hero" style="--g1:%s;--g2:%s">%s%s<div class="tx"><small>%s</small><b>%s</b><p>%s</p>%s</div></div>%s'
            % (g1, g2, art, _ring(info, ph[0], ph[1]), T(lang, "Fase atual", "Current phase"), E(pn[0]), E(pn[1]),
               ('<span class="chip">%s</span>' % E(T(lang, "Probabilidade de gravidez: %s", "Chance of pregnancy: %s") % ch)) if ch else "", _legend(lang)))


def _summary(info, goal, today, ph, lang="pt"):
    if info["ongoing"]:
        prox = T(lang, "Período em curso (dia %d)", "Period in progress (day %d)") % info["ongoing"]
    elif info["late"]:
        prox = (T(lang, "Atrasado %d dia%s", "%d day%s late") % (info["late"], "s" if info["late"] > 1 else ""))
    elif info["next"]:
        n = (info["next"] - today).days
        prox = T(lang, "Hoje", "Today") if n == 0 else T(lang, "Amanhã", "Tomorrow") if n == 1 else T(lang, "Em %d dias (%s)", "In %d days (%s)") % (n, _pt(info["next"], lang))
    else:
        prox = T(lang, "Sem registos ainda", "No records yet")
    ch = T(lang, P.chance(info, today), {"alta": "high", "média": "medium", "baixa": "low"}[P.chance(info, today)])
    fert = ("%s %s %s" % (_pt(info["fert"][0], lang), T(lang, "a", "to"), _pt(info["fert"][1], lang))) if info["fert"] else "—"
    ov = _pt(info["ov"], lang) if info["ov"] else "—"
    c_period = '<div class="card" style="--c:#e57373"><span class="ic">' + _icon("menstrual", 28) + '</span>%s<b>%s</b></div>' % (T(lang, "Próxima menstruação", "Next period"), E(prox))
    c_ov = '<div class="card" style="--c:#ffd54f"><span class="ic">' + _icon("ovulatoria", 28) + '</span>%s<b>%s</b></div>' % (T(lang, "Ovulação estimada", "Estimated ovulation"), E(ov))
    c_fert = '<div class="card" style="--c:#81c784"><span class="ic">' + _icon("folicular", 28) + '</span>%s<b>%s</b></div>' % (T(lang, "Janela fértil", "Fertile window"), E(fert))
    c_avg = ('<div class="card" style="--c:#9575cd"><span class="ic">' + _bars_icon() + '</span>%s<b>%s</b><span class="mut">%s</span></div>' % (
        T(lang, "Ciclo / duração médios", "Average cycle / period length"),
        T(lang, "%d dias · %d dias", "%d days · %d days") % (info["cycle"], info["period"]),
        T(lang, "%d período(s) registado(s)", "%d period(s) logged") % info["n"]
        + ("" if info["known"] else T(lang, " · valores das definições", " · values from settings"))))
    pn = (PHASES_EN if lang == "en" else P.PHASES).get(ph[0]) if ph[0] else None
    big = ""
    extra = ""
    if goal == "engravidar":
        if info["late"] >= 1:
            extra = '<div class="card big">Período atrasado<b>Já podes fazer um teste de gravidez.</b><span class="mut">Se der negativo e a menstruação não vier, repete passados uns dias ou fala com o teu médico.</span></div>'
        return big + extra + c_fert + c_ov + c_period + c_avg
    return big + c_period + c_ov + c_fert + c_avg


def _tips(ph, today, lang="pt"):
    if not ph[0]:
        return ""
    name, resumo, tips = (PHASES_EN if lang == "en" else P.PHASES)[ph[0]]
    i = today.timetuple().tm_yday % len(tips)
    return ('<details open><summary>' + _icon(ph[0]) + '%s</summary><p><b>%s</b></p>'
            '<details><summary>%s</summary><ul class="tips">%s</ul></details></details>'
            % (T(lang, "Dica de hoje · fase %s", "Tip of the day · %s phase") % E(name.lower()), E(tips[i]),
               T(lang, "Todas as dicas desta fase", "All tips for this phase"), "".join("<li>%s</li>" % E(t) for t in tips)))

def _calendar(d, info, y, m, sel, today, lang="pt"):
    prev = datetime.date(y, m, 1) - datetime.timedelta(days=1)
    nxt = (datetime.date(y, m, 28) + datetime.timedelta(days=5)).replace(day=1)
    head = "".join("<th>%s</th>" % w for w in WD)
    rows = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(y, m):
        cells = []
        for dt in week:
            cls = set(_tags(dt, d["days"], info))
            if dt.month != m:
                cls.add("out")
            if dt == today:
                cls.add("today")
            if dt == sel:
                cls.add("sel")
            if dt.isoformat() in d["days"]:
                cls.add("has")
            q = "/finance/period?ym=%04d-%02d&day=%s" % (dt.year, dt.month, dt.isoformat())
            cells.append('<td class="c %s"><a href="%s">%d</a></td>' % (" ".join(sorted(cls)), q, dt.day))
        rows.append("<tr>%s</tr>" % "".join(cells))
    out = ('<div class="hd"><a href="/finance/period?ym=%04d-%02d">‹</a><b>%s %d</b><a href="/finance/period?ym=%04d-%02d">›</a></div>'
           % (prev.year, prev.month, (MONTHS_EN if lang == "en" else MONTHS)[m - 1].capitalize(), y, nxt.year, nxt.month))
    out += '<table class="cal"><tr>%s</tr>%s</table>' % (head, "".join(rows))
    out += ('<div class="leg"><span><i style="background:#c0392b"></i>Período</span>'
            '<span><i style="background:#3a1f22;border:1px dashed #d46a6a"></i>Previsto</span>'
            '<span><i style="background:#1e3f6b"></i>Ovulação</span><span><i style="background:#1f4a35"></i>Fértil</span>'
            '<span><i style="background:#3d2c4f"></i>TPM</span></div>')
    return out


def _form(d, sel, today, lang="pt"):
    e = d["days"].get(sel.isoformat(), {})
    sel_opt = lambda items, cur: "".join('<option value="%s"%s>%s</option>' % (v, " selected" if cur == v else "", lab(l, lang)) for v, l in items)
    mood = "".join('<option value="%s"%s>%s</option>' % (v, " selected" if e.get("mood", "") == v else "", lab(v, lang) if v else "—") for v in P.MOODS)
    syms = "".join('<label><input type="checkbox" name="s%d" value="1"%s> %s</label>' % (
        i, " checked" if s in e.get("sym", []) else "", (SYM_EMO.get(s, "") + " " + E(lab(s, lang))).strip()) for i, s in enumerate(P.SYMPTOMS))
    f = ('<form method="post" action="/finance/period/log" class="box">'
         '<label><span>Dia</span> <input type="date" name="date" value="%s" max="%s" required></label>'
         '<div class="row"><label><span>Fluxo</span> <select name="flow">%s</select></label><label><span>Humor</span> <select name="mood">%s</select></label></div>'
         '<div class="mut">Sintomas</div><div class="syms">%s</div>'
         '<div class="row"><label>Temperatura basal (°C) <input type="number" step="0.01" min="34" max="42" name="temp" value="%s"></label>'
         '<label>Teste de ovulação <select name="ov">%s</select></label></div>'
         '<label><span>Relações</span> <select name="sex">%s</select></label>'
         '<label><span>Nota</span> <input type="text" name="note" maxlength="300" value="%s"></label><button>Guardar</button></form>'
         % (sel.isoformat(), today.isoformat(), sel_opt(P.FLOW, e.get("flow", "")), mood, syms, E(str(e.get("temp", ""))),
            sel_opt(P.OVTEST, e.get("ov", "")), sel_opt(P.SEX, e.get("sex", "")), E(e.get("note", ""))))
    if e:
        f += ('<form method="post" action="/finance/period/del" style="margin:0"><input type="hidden" name="date" value="%s">'
              '<button style="background:#7a3030">Apagar este dia</button></form>' % sel.isoformat())
    return f


def _bars(vals, unit=""):
    if not vals:
        return '<p class="mut">Sem dados ainda.</p>'
    mx = max(vals)
    return '<div class="bars">%s</div>' % "".join(
        '<div style="height:%d%%"><span>%d</span></div>' % (max(8, int(v * 100 / mx)), v) for v in vals)


def _stats(d, today, lang="pt"):
    s = P.stats(d["days"], today)
    if not s["logged"]:
        return ""
    if s["avg"]:
        avg = T(lang, "%s dias (entre %d e %d)%s", "%s days (between %d and %d)%s") % (
            s["avg"], s["min"], s["max"],
            T(lang, " · ciclos regulares", " · regular cycles") if s["regular"] else T(lang, " · ciclos variáveis", " · variable cycles"))
    else:
        avg = T(lang, "precisas de pelo menos 2 períodos", "you need at least 2 periods")
    sym = ", ".join("%s (%d)" % (E(lab(k, lang)), v) for k, v in s["sym"]) or "—"
    mood = ", ".join("%s (%d)" % (E(lab(k, lang)), v) for k, v in s["mood"]) or "—"
    st = s["streak"]
    return ('<details><summary>%s</summary><p>%s <b>%s</b></p>'
            '<div class="mut">%s</div>%s<div class="mut">%s</div>%s'
            '<p>%s %s<br>%s %s<br>%s <b>%d %s</b> · %s %d</p></details>'
            % (T(lang, "Estatísticas", "Statistics"), T(lang, "Duração média do ciclo:", "Average cycle length:"), avg,
               T(lang, "Duração dos últimos ciclos (dias)", "Length of recent cycles (days)"), _bars(s["cycles"]),
               T(lang, "Duração dos últimos períodos (dias)", "Length of recent periods (days)"), _bars(s["lens"]),
               T(lang, "Sintomas mais frequentes:", "Most frequent symptoms:"), sym,
               T(lang, "Humor mais frequente:", "Most frequent mood:"), mood,
               T(lang, "Sequência de registo:", "Logging streak:"), st, T(lang, "dia" if st == 1 else "dias", "day" if st == 1 else "days"),
               T(lang, "dias registados:", "days logged:"), s["logged"]))

def _settings(d, lang="pt"):
    st, r = d["settings"], d["settings"]["remind"]
    ck = lambda v: " checked" if v else ""
    goal = "".join('<option value="%s"%s>%s</option>' % (v, " selected" if st["goal"] == v else "", l)
                   for v, l in (("acompanhar", "Só acompanhar o ciclo"), ("engravidar", "Tentar engravidar")))
    pin = ('<form method="post" action="/finance/period/pin" class="box"><b>PIN %s</b>'
           '%s<input type="password" name="pin" inputmode="numeric" placeholder="Novo PIN (4 a 8 dígitos)">'
           '<button>%s</button></form>' % ("ativo" if P.has_pin(d) else "(não definido)",
                                          '<input type="password" name="old" inputmode="numeric" placeholder="PIN atual">' if P.has_pin(d) else "",
                                          "Alterar PIN" if P.has_pin(d) else "Definir PIN"))
    if P.has_pin(d):
        pin += ('<form method="post" action="/finance/period/pin" class="box"><input type="hidden" name="remove" value="1">'
                '<input type="password" name="old" inputmode="numeric" placeholder="PIN atual" required><button style="background:#7a3030">Remover PIN</button></form>')
    out = ('<details><summary>Definições, lembretes e dados</summary>'
            '<form method="post" action="/finance/period/settings" class="box">'
            '<label>Objetivo <select name="goal">%s</select></label>'
            '<div class="row"><label>Ciclo habitual (dias) <input type="number" name="cycle" min="21" max="45" value="%d"></label>'
            '<label>Período habitual (dias) <input type="number" name="period" min="2" max="10" value="%d"></label></div>'
            '<div class="mut">Usados enquanto não houver 2 períodos registados.</div>'
            '<label><input type="checkbox" name="r_period" value="1"%s> Lembrete da menstruação</label>'
            '<label>Avisar quantos dias antes <input type="number" name="before" min="0" max="7" value="%d"></label>'
            '<label><input type="checkbox" name="r_ov" value="1"%s> Lembrete da janela fértil / ovulação</label>'
            '<label><input type="checkbox" name="r_late" value="1"%s> Avisar se a menstruação atrasar</label>'
            '<button>Guardar</button></form>%s'
            '<p><a class="lnk" href="/finance/period/export?fmt=csv">Exportar CSV</a> <a class="lnk" href="/finance/period/export?fmt=json">Exportar JSON</a>%s</p>'
            '<form method="post" action="/finance/period/wipe" class="box"><b>Apagar todos os registos</b>'
            '<input type="text" name="confirm" placeholder="Escreve APAGAR"><button style="background:#7a3030">Apagar tudo</button></form></details>'
            % (goal, st["cycle"], st["period"], ck(r["period"]), r["before"], ck(r["ovulation"]), ck(r["late"]), pin,
               ' <form method="post" action="/finance/period/lock" style="display:inline"><button>Bloquear agora</button></form>' if P.has_pin(d) else ""))
    return out.replace("<label>Objetivo <select", "<label>Goal <select") if lang == "en" else out


def render(user, msg="", ym="", day="", cookie="", lang="pt"):
    d = P.load(user)
    if not P.unlocked(user, d, cookie):
        return lock_page(msg)
    today = datetime.date.today()
    try:
        y, m = (int(x) for x in ym.split("-"))
        if not 1 <= m <= 12:
            raise ValueError
    except Exception:
        y, m = today.year, today.month
    sel = min(P._d(day) or today, today)
    info = P.predict(d["days"], today, d["settings"])
    ph = P.phase(info, today)
    hist = ""
    if info["runs"]:
        hist = "<details><summary>Histórico de períodos</summary><table><tr><th>Início</th><th>Fim</th><th>Dias</th></tr>%s</table></details>" % "".join(
            "<tr><td>%s</td><td>%s</td><td>%d</td></tr>" % (_pt(a, lang), _pt(b, lang), (b - a).days + 1) for a, b in info["runs"])
    return (CSS + '<div class="cy"><h2>Ciclo</h2>' + ('<p class="green">%s</p>' % E(msg) if msg else "")
            + _hero(info, ph, lang, T(lang, P.chance(info, today), {"alta": "high", "média": "medium", "baixa": "low"}[P.chance(info, today)])) + '<div class="cards">%s</div>' % _summary(info, d["settings"]["goal"], today, ph, lang)
            + _tips(ph, today, lang) + '<div class="box">%s</div>' % _calendar(d, info, y, m, sel, today, lang)
            + '<h3>%s</h3>%s' % (T(lang, "Registar · %s", "Log · %s") % _pt(sel, lang), _form(d, sel, today, lang)) + _stats(d, today, lang) + hist + _settings(d, lang)
            + '<p class="aviso">Estimativas com base nos teus registos (ou nos valores das definições). '
              'Não é um método contracetivo. Em caso de dúvida, fala com o teu médico.</p></div>')
