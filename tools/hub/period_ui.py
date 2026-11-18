"""Ciclo (interface HTML). Usa o núcleo em period.py."""
import calendar, datetime, html
import period as P
import period_care as PC
import period_pg as PG
E = html.escape
MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
WD_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WD = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
LABEL_EN = {"Cólicas": "Cramps", "Dor de cabeça": "Headache", "Seios sensíveis": "Breast tenderness", "Acne": "Acne", "Inchaço": "Bloating",
            "Cansaço": "Fatigue", "Irritabilidade": "Irritability", "Dor nas costas": "Back pain", "Mais apetite": "Increased appetite",
            "Náuseas": "Nausea", "Insónias": "Insomnia", "Desejo de doces": "Sugar cravings", "Tonturas": "Dizziness",
            "Dores musculares": "Muscle aches", "Libido alta": "High libido", "Feliz": "Happy", "Calma": "Calm", "Energética": "Energetic",
            "Ansiosa": "Anxious", "Triste": "Sad", "Irritada": "Irritable", "Sensível": "Sensitive", "Cansada": "Tired",
            "Manchas": "Spotting", "Leve": "Light", "Média": "Medium", "Intensa": "Heavy", "Negativo": "Negative", "Positivo": "Positive",
            "Sim": "Yes", "Sim, protegido": "Yes, protected", "Incerto": "Uncertain",
            "Diarreia": "Diarrhea", "Gases": "Colic gas", "Obstipação": "Constipation", "Calafrios": "Chills", "Febre": "Fever",
            "Cólicas musculares": "Muscle cramps", "Suores noturnos": "Night sweats", "Afrontamentos": "Hot flashes",
            "Secura vaginal": "Vaginal dryness", "Comichão vaginal": "Vaginal itching", "Ardor vaginal": "Vaginal burning",
            "Urinar com frequência": "Frequent urination", "Erupção na pele": "Skin rash", "Inchaço nas pernas": "Leg swelling",
            "Inchaço facial": "Facial swelling", "Dor na ovulação (esq.)": "Left ovulation pain", "Dor na ovulação (dir.)": "Right ovulation pain",
            "Dor lombar baixa": "Lower back pain", "Dor no baixo-ventre": "Lower abdominal pulling", "Enxaqueca": "Migraine",
            "Dor nas relações": "Painful sex", "Tudo bem": "Everything is fine", "Indiferente": "Indifferent", "Zangada": "Angry",
            "Entusiasmada": "Excited", "Em pânico": "Panicking", "Inspirada": "Inspired", "Melancólica": "Melancholy", "Neutra": "Neutral",
            "Instável": "Changeable", "Stress": "Stress", "Sexo": "Sex", "Sexo com proteção": "Sex with protection",
            "Sexo sem proteção": "Sex without protection", "Libido alta": "High sex drive", "Masturbação": "Masturbation", "Orgasmo": "Orgasm",
            "Sem corrimento": "No discharge", "Pegajoso": "Sticky", "Cremoso": "Creamy", "Clara de ovo": "Egg-white", "Aquoso": "Watery",
            "Atípico": "Atypical", "Mau cheiro": "Bad odor", "Tomei a pílula": "Pill taken", "Pílula de ontem": "Yesterday's pill"}
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
.cy .chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0}
.cy .chip{margin:0!important;display:block}.cy .chip input{position:absolute;opacity:0;pointer-events:none}
.cy .chip span{display:flex;flex-direction:column;align-items:center;gap:2px;min-width:68px;max-width:84px;padding:7px 6px;border-radius:12px;background:#2a2e36;border:2px solid transparent;font-size:1.3em;text-align:center;cursor:pointer}
.cy .chip small{font-size:.5em;color:#bbb;line-height:1.15}
.cy .chip input:checked+span{border-color:#8a7cff;background:#34305a}
.cy .sec{background:#262a31;border-radius:12px;padding:8px 10px;margin:10px 0}.cy .st{font-weight:600;margin-bottom:2px}
.cy .week{display:flex;gap:4px;margin:6px 0 10px}
.cy .wk{flex:1;text-align:center;border-radius:20px;padding:6px 0;background:#23272e;color:#eee;text-decoration:none;display:block;border:2px solid transparent}
.cy .wk small{display:block;color:#999;font-size:.7em}.cy .wk.today{border-color:#fff}.cy .wk.per{background:#c0392b}.cy .wk.pred{border:2px dashed #d46a6a}
.cy .wk.fert{background:#1f4a35}.cy .wk.ov{background:#1e3f6b}.cy .wk.pms{background:#3d2c4f}
.cy .daypanel{display:flex;justify-content:space-between;align-items:center;gap:8px;background:#262a31;border-radius:12px;padding:10px 12px;margin:10px 0}
.cy .eg{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}.cy .eg i{display:block}
.cy .eg .ed{padding:9px 0;border-radius:50%;border:2px solid #d46a6a;background:transparent;color:#eee}.cy .eg .ed.on{background:#c0392b}.cy .eg .ed:disabled{opacity:.3;border-color:#555}
.cy .mh{font-weight:600;margin:10px 0 4px}
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

.cy td.c{height:44px;border-radius:12px;transition:transform .1s}.cy td.c:hover{transform:scale(1.06)}
.cy td.per{background:linear-gradient(#e57373,#c0392b)}.cy td.per a{color:#fff;font-weight:700}
.cy td.ov a,.cy td.per a,.cy td.pred a{position:relative}
.cy td.ov a:after{content:"";position:absolute;left:50%;bottom:3px;width:6px;height:6px;margin-left:-3px;border-radius:50%;background:#ffd54f}
.cy td.per a:after{content:"";position:absolute;left:50%;bottom:3px;width:5px;height:7px;margin-left:-2px;border-radius:50% 50% 50% 50%/60% 60% 40% 40%;background:#ffffffcc}
.cy td.fert{background:#1f4a35;box-shadow:inset 0 0 0 1px #2e8b5766}.cy td.today a{font-weight:800}
.cy td.today{outline:2px solid #8ab4f8;outline-offset:-2px}
.cy .bars{height:120px;gap:8px;padding-top:22px;box-sizing:border-box;justify-content:flex-start}.cy .bars div{flex:0 0 34px;background:linear-gradient(#9fb8ff,#4a7bd0);border-radius:8px 8px 0 0;min-width:0}.cy .bars span{top:-18px;font-weight:600}
.cy .hb{display:flex;align-items:center;gap:8px;margin:5px 0;background:#23272e;border-radius:10px;padding:5px 9px;position:relative;overflow:hidden}
.cy .hb i{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,#c3bcff55,#c3bcff22)}.cy .hb span{position:relative;font-size:.88em}.cy .hb b{position:relative;margin-left:auto}
.cy .rg path{stroke-dasharray:1;stroke-dashoffset:1;animation:cyd .9s ease-out forwards}
.cy .rg path:nth-of-type(2){animation-delay:.15s}.cy .rg path:nth-of-type(3){animation-delay:.3s}.cy .rg path:nth-of-type(4){animation-delay:.45s}
.cy .rg .pl{fill:none;stroke:#fff;stroke-width:2;transform-box:fill-box;transform-origin:center;animation:cyp 2.4s ease-out infinite}
@keyframes cyd{to{stroke-dashoffset:0}}@keyframes cyp{0%{transform:scale(1);opacity:.8}100%{transform:scale(2.1);opacity:0}}
@media (prefers-reduced-motion:reduce){.cy .rg path{animation:none;stroke-dashoffset:0}.cy .rg .pl{animation:none;opacity:0}}
.cy.pal-rosa .hero{background:linear-gradient(135deg,#7b2d55,#d4608f)!important}
.cy.pal-oceano .hero{background:linear-gradient(135deg,#12395e,#2a8fbd)!important}
.cy.pal-lavanda .hero{background:linear-gradient(135deg,#3b2d6b,#8f7be0)!important}
body:has(.cy.th-claro){background:#f6f1f4!important;color:#2b2030!important}
@media (prefers-color-scheme:light){body:has(.cy.th-auto){background:#f6f1f4!important;color:#2b2030!important}}
.cy.th-claro{color:#2b2030}
.cy.th-claro .card,.cy.th-claro details,.cy.th-claro .syms label,.cy.th-claro td.c,.cy.th-claro .hd a,.cy.th-claro .lnk,.cy.th-claro .box{background:#fff;color:#2b2030;box-shadow:0 1px 3px #0001}
.cy.th-claro .mut,.cy.th-claro .leg,.cy.th-claro .aviso,.cy.th-claro .lg4,.cy.th-claro table.cal th{color:#6d6272}.cy.th-claro td.c a{color:#2b2030}.cy.th-claro td.out a{color:#bbb}
.cy.th-claro td.per{background:linear-gradient(#ef9a9a,#e57373)}.cy.th-claro td.per a{color:#fff}.cy.th-claro td.fert{background:#d6f1de}.cy.th-claro td.pms{background:#e6def8}.cy.th-claro td.ov{background:#ffe9a8}.cy.th-claro td.pred{background:#fde6e6;border-color:#e57373}
.cy.th-claro input,.cy.th-claro select,.cy.th-claro textarea{background:#fff;color:#222;border:1px solid #cfc6d2}.cy.th-claro .bars div{background:linear-gradient(#b39ddb,#7e57c2)}.cy.th-claro .hb{background:#eee6f3}
@media (prefers-color-scheme:light){.cy.th-auto{color:#2b2030}
.cy.th-auto .card,.cy.th-auto details,.cy.th-auto .syms label,.cy.th-auto td.c,.cy.th-auto .hd a,.cy.th-auto .lnk,.cy.th-auto .box{background:#fff;color:#2b2030;box-shadow:0 1px 3px #0001}
.cy.th-auto .mut,.cy.th-auto .leg,.cy.th-auto .aviso,.cy.th-auto .lg4,.cy.th-auto table.cal th{color:#6d6272}.cy.th-auto td.c a{color:#2b2030}.cy.th-auto td.out a{color:#bbb}
.cy.th-auto td.per{background:linear-gradient(#ef9a9a,#e57373)}.cy.th-auto td.per a{color:#fff}.cy.th-auto td.fert{background:#d6f1de}.cy.th-auto td.pms{background:#e6def8}.cy.th-auto td.ov{background:#ffe9a8}.cy.th-auto td.pred{background:#fde6e6;border-color:#e57373}
.cy.th-auto input,.cy.th-auto select,.cy.th-auto textarea{background:#fff;color:#222;border:1px solid #cfc6d2}.cy.th-auto .bars div{background:linear-gradient(#b39ddb,#7e57c2)}.cy.th-auto .hb{background:#eee6f3}
}</style>"""


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
           "Desejo de doces": "🍫", "Tonturas": "💫", "Dores musculares": "💪", "Libido alta": "🔥",
           "Diarreia": "🚽", "Gases": "💨", "Obstipação": "🧻", "Calafrios": "🥶", "Febre": "🌡️", "Cólicas musculares": "⚡", "Suores noturnos": "🌙",
           "Afrontamentos": "♨️", "Secura vaginal": "🏜️", "Comichão vaginal": "🔸", "Ardor vaginal": "🔥", "Urinar com frequência": "🚻",
           "Erupção na pele": "🔴", "Inchaço nas pernas": "🦵", "Inchaço facial": "🙂", "Dor na ovulação (esq.)": "◀️", "Dor na ovulação (dir.)": "▶️",
           "Dor lombar baixa": "🦴", "Dor no baixo-ventre": "🌀", "Enxaqueca": "🤯", "Dor nas relações": "💔", "Tudo bem": "👍",
           "Feliz": "😄", "Calma": "😌", "Energética": "⚡", "Ansiosa": "😟", "Triste": "😢", "Irritada": "😠", "Sensível": "🥺", "Cansada": "😪",
           "Indiferente": "😑", "Zangada": "😡", "Entusiasmada": "🤩", "Em pânico": "😱", "Inspirada": "💡", "Melancólica": "😔", "Neutra": "😐",
           "Instável": "🎭", "Stress": "😰", "Sexo": "❤️", "Sexo com proteção": "🛡️", "Sexo sem proteção": "💗", "Masturbação": "✋", "Orgasmo": "💫",
           "Sem corrimento": "⭕", "Manchas": "🩸", "Pegajoso": "🍯", "Cremoso": "🥛", "Clara de ovo": "🥚", "Aquoso": "💧", "Atípico": "❓",
           "Mau cheiro": "☣️", "Tomei a pílula": "💊", "Pílula de ontem": "⏪"}


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
        out.append('<path pathLength="1" d="M%.1f %.1f A%d %d 0 %d 1 %.1f %.1f" stroke="%s" stroke-width="12" fill="none" stroke-linecap="butt" stroke-opacity="%s"/>'
                   % (x1, y1, R, R, 1 if (b - a) / n > .5 else 0, x2, y2, PH_COL[k][2], "1" if k == ph else ".5"))
    mk = ""
    if day:
        x, y = pt(((day - 1) % n) + .5)
        mk = '<circle class="pl" cx="%.1f" cy="%.1f" r="9"/><circle cx="%.1f" cy="%.1f" r="9" fill="#fff"/><circle cx="%.1f" cy="%.1f" r="4" fill="%s"/>' % (x, y, x, y, x, y, PH_COL.get(ph, PH_COL["folicular"])[1])
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


def _chips(pre, items, cur, lang):
    return '<div class="chips">%s</div>' % "".join(
        '<label class="chip"><input type="checkbox" name="%s%d" value="1"%s><span>%s<small>%s</small></span></label>' % (
            pre, i, " checked" if s in cur else "", SYM_EMO.get(s, "•"), E(lab(s, lang))) for i, s in enumerate(items))


def _sec(title, body):
    return '<div class="sec"><div class="st">%s</div>%s</div>' % (title, body)


def _form(d, sel, today, lang="pt", info=None):
    e = d["days"].get(sel.isoformat(), {})
    sel_opt = lambda items, cur: "".join('<option value="%s"%s>%s</option>' % (v, " selected" if cur == v else "", lab(l, lang)) for v, l in items)
    moods = e.get("moods") or ([e["mood"]] if e.get("mood") else [])
    flow = "".join('<label class="chip"><input type="radio" name="flow" value="%s"%s><span>%s<small>%s</small></span></label>' % (
        v, " checked" if e.get("flow", "") == v else "", ic, E(lab(l, lang))) for (v, l), ic in zip(P.FLOW, ["⚪", "🩸", "💧", "🩸", "🔴"]))
    sex = e.get("sx") or ([{"sim": "Sexo", "prot": "Sexo com proteção"}[e["sex"]]] if e.get("sex") in ("sim", "prot") else [])
    tst = lambda name, cur: "".join('<label class="chip"><input type="radio" name="%s" value="%s"%s><span>%s<small>%s</small></span></label>' % (
        name, v, " checked" if cur == v else "", ic, E(lab(l, lang))) for (v, l), ic in zip(P.OVTEST, ["⚪", "➖", "➕", "❔"]) if v or True)
    f = ('<form method="post" action="/finance/period/log" class="box">'
         '<label><span>%s</span> <input type="date" name="date" value="%s" max="%s" required></label>' % (T(lang, "Dia", "Day"), sel.isoformat(), today.isoformat())
         + _sec(T(lang, "Fluxo menstrual", "Menstruation flow"), '<div class="chips">%s</div>' % flow)
         + _sec(T(lang, "Sintomas", "Symptoms"), _chips("s", P.SYMPTOMS, e.get("sym", []), lang))
         + _sec(T(lang, "Humor", "Mood"), _chips("m", P.MOODS[1:], moods, lang))
         + _sec(T(lang, "Sexo", "Sex"), _chips("x", P.SEXO, sex, lang))
         + _sec(T(lang, "Corrimento vaginal", "Vaginal discharge"), _chips("d", P.DISCH, e.get("disch", []), lang))
         + (_sec(T(lang, "Contracetivo oral", "Oral contraceptives"), _chips("p", P.PILL, e.get("pill", []), lang)) if d["settings"].get("takes_pill") else "")
         + _sec(T(lang, "Teste de gravidez", "Pregnancy test"), '<div class="chips">%s</div>' % tst("preg", e.get("preg", "")))
         + _sec(T(lang, "Teste de ovulação", "Ovulation test"), '<div class="chips">%s</div>' % tst("ov", e.get("ov", "")))
         + '<div class="row"><label>%s <input type="number" step="0.01" min="34" max="42" name="temp" value="%s"></label>'
           '<label>%s <input type="number" step="0.1" min="25" max="300" name="weight" value="%s"></label></div>'
           % (T(lang, "Temperatura basal (°C)", "Basal temperature (°C)"), E(str(e.get("temp", ""))), T(lang, "Peso (kg)", "Weight (kg)"), E(str(e.get("weight", ""))))
         + '<label><span>%s</span> <input type="text" name="note" maxlength="300" value="%s"></label><button>%s</button></form>'
           % (T(lang, "Nota", "Note"), E(e.get("note", "")), T(lang, "Guardar", "Save")))
    if e:
        f += ('<form method="post" action="/finance/period/del" style="margin:0"><input type="hidden" name="date" value="%s">'
              '<button style="background:#7a3030">Apagar este dia</button></form>' % sel.isoformat())
    return f


def _week(d, info, today, lang):
    out = []
    wd = WD_EN if lang == "en" else WD
    for k in range(-3, 4):
        dt = today + datetime.timedelta(days=k)
        cls = " ".join(sorted(_tags(dt, d["days"], info) | ({"today"} if k == 0 else set())))
        inner = '<small>%s</small><b>%d</b>' % (wd[dt.weekday()][:1], dt.day)
        out.append('<a class="wk %s" href="/finance/period?ym=%04d-%02d&day=%s">%s</a>' % (cls, dt.year, dt.month, dt.isoformat(), inner) if dt <= today
                   else '<span class="wk %s">%s</span>' % (cls, inner))
    return '<div class="week">%s</div>' % "".join(out)


def _daypanel(info, sel, today, ph, lang, edit_href):
    day = (sel - info["last"]).days + 1 if info["last"] and sel >= info["last"] else None
    ch = {"alta": T(lang, "alta", "high"), "média": T(lang, "média", "medium"), "baixa": T(lang, "baixa", "low")}[P.chance(info, sel)]
    return ('<div class="daypanel"><div><b>%s</b><div class="mut">%s %s</div><div class="mut">%s</div></div><a class="lnk" href="%s">%s</a></div>' % (
        _pt(sel, lang), T(lang, "Probabilidade de gravidez:", "Chance of getting pregnant:"), ch,
        (T(lang, "Dia %d do ciclo", "Day %d of cycle") % day) if day else "", edit_href, T(lang, "Editar datas do período", "Edit period dates")))


def _edit(d, today, lang):
    lo = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    lo = (lo - datetime.timedelta(days=1)).replace(day=1)
    on = sorted(k for k, v in d["days"].items() if v.get("flow") and P._d(k) and lo <= P._d(k) <= today)
    months, y, m = [], lo.year, lo.month
    while (y, m) <= (today.year, today.month):
        cells = []
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(y, m):
            for dt in week:
                if dt.month != m:
                    cells.append("<i></i>")
                else:
                    iso = dt.isoformat()
                    cells.append('<button type="button" class="ed%s" data-d="%s"%s>%d</button>' % (
                        " on" if iso in on else "", iso, " disabled" if dt > today else "", dt.day))
        months.append('<div class="mh">%s %d</div><div class="eg">%s</div>' % ((MONTHS_EN if lang == "en" else MONTHS)[m - 1].capitalize(), y, "".join(cells)))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return ('<form method="post" action="/finance/period/dates" class="box"><h3>%s</h3><p class="mut">%s</p>%s'
            '<input type="hidden" name="sel" id="edsel" value="%s"><input type="hidden" name="scope" value="%s,%s">'
            '<div class="row"><a class="lnk" href="/finance/period">%s</a><button>✓ %s</button></div></form>'
            '<script>(function(){var s=document.getElementById("edsel");function up(){var a=[];document.querySelectorAll(".eg .ed.on").forEach(function(b){a.push(b.dataset.d)});s.value=a.join(",")}'
            'document.querySelectorAll(".eg .ed").forEach(function(b){b.onclick=function(){b.classList.toggle("on");up()}});up()})()</script>'
            % (T(lang, "Editar datas do período", "Edit period dates"), T(lang, "Toca nos dias com menstruação.", "Tap the days with bleeding."),
               "".join(months), ",".join(on), lo.isoformat(), today.isoformat(), T(lang, "Cancelar", "Cancel"), T(lang, "Guardar", "Save")))


def _cyc_changed(d, info, lang):
    st = d["settings"]
    starts = [r[0] for r in info["runs"][::-1]]
    if len(starts) < 2:
        return ""
    last = (starts[-1] - starts[-2]).days
    ack = starts[-1].isoformat()
    if not 18 <= last <= 60 or abs(last - info["cycle"]) < 4 or st.get("cyc_ack") == ack:
        return ""
    return ('<div class="card big" style="grid-column:auto"><b>%s</b><div class="mut">%s</div><p>%s <b>%d</b> %s &rarr; %s <b>%d</b> %s</p>'
            '<form method="post" action="/finance/period/cyc" class="row"><input type="hidden" name="ack" value="%s"><input type="hidden" name="n" value="%d">'
            '<button name="act" value="save">%s</button><button name="act" value="keep" style="background:#444">%s</button></form></div>' % (
                T(lang, "A duração do ciclo mudou", "Cycle length has changed"),
                T(lang, "Reparámos uma mudança no teu ciclo. Atualiza a duração média para previsões mais certas.", "We noticed a change in your cycle. Update the average length to make predictions more accurate."),
                T(lang, "Era", "Was"), info["cycle"], T(lang, "dias (média)", "days (avg.)"), T(lang, "Passa a", "Will be"), last, T(lang, "dias (último ciclo)", "days (last cycle)"),
                ack, last, T(lang, "Guardar nova duração", "Save new cycle length"), T(lang, "Não alterar", "Do not change")))


FAQ = [("E se tiver SOP (síndrome do ovário poliquístico)?", "What if I have PCOS?",
        "A SOP costuma dar ciclos longos ou irregulares, por isso as previsões ficam menos certas. Regista os ciclos e leva o histórico ao médico para diagnóstico e tratamento.",
        "PCOS often causes long or irregular cycles, so predictions are less certain. Keep logging and take the history to your doctor for diagnosis and treatment."),
       ("É normal ter corrimento?", "Is it okay to have discharge?",
        "Sim, o corrimento varia ao longo do ciclo: mais claro e elástico perto da ovulação, mais espesso depois. Cheiro forte, cor estranha ou comichão justificam consulta.",
        "Yes, it changes through the cycle: clearer and stretchy near ovulation, thicker afterwards. Strong odor, odd colour or itching are worth a check-up."),
       ("O que é a ovulação?", "What is ovulation?",
        "É quando o ovário liberta um óvulo, cerca de 14 dias antes da menstruação seguinte. A janela fértil dura uns 6 dias, até ao dia depois da ovulação.",
        "It is when an ovary releases an egg, about 14 days before the next period. The fertile window lasts about 6 days, up to the day after ovulation."),
       ("Quando devo fazer um teste de gravidez?", "When should I take a pregnancy test?",
        "A partir do primeiro dia de atraso, de preferência de manhã. Se der negativo e a menstruação não vier, repete passados 2 a 3 dias.",
        "From the first day of a late period, preferably in the morning. If negative and the period does not arrive, repeat after 2 to 3 days."),
       ("Qual é a duração normal do ciclo?", "What is a normal cycle length?",
        "Entre 21 e 35 dias conta-se como normal. Varia de mês para mês; o que importa é o teu padrão.",
        "Between 21 and 35 days counts as normal. It varies month to month; your own pattern is what matters."),
       ("Para que serve a temperatura basal?", "What is basal temperature for?",
        "Mede-se ao acordar, sempre à mesma hora. Sobe ligeiramente após a ovulação e ajuda a confirmar que ela aconteceu.",
        "Measured on waking, at the same time every day. It rises slightly after ovulation and helps confirm it happened.")]


def _faq(lang):
    return '<details><summary>%s</summary>%s<p class="mut">%s</p></details>' % (
        T(lang, "Perguntas frequentes", "Common questions"),
        "".join('<details><summary>%s</summary><p>%s</p></details>' % (E(T(lang, a, b)), E(T(lang, c, dd))) for a, b, c, dd in FAQ),
        T(lang, "Informação geral, não substitui o médico.", "General information, not a substitute for your doctor."))


def _hbars(items, lang="pt"):
    if not items:
        return "<p class='mut'>—</p>"
    mx = max(v for _, v in items) or 1
    return "".join('<div class="hb"><i style="width:%d%%"></i><span>%s %s</span><b>%d</b></div>' % (
        int(v * 100 / mx), SYM_EMO.get(k, ""), E(lab(k, lang)), v) for k, v in items)


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
    sym = _hbars(s["sym"], lang)
    mood = _hbars(s["mood"], lang)
    st = s["streak"]
    return ('<details><summary>%s</summary><p>%s <b>%s</b></p>'
            '<div class="mut">%s</div>%s<div class="mut">%s</div>%s'
            '<div class="mut">%s</div>%s<div class="mut" style="margin-top:8px">%s</div>%s<p>%s <b>%d %s</b> · %s %d</p></details>'
            % (T(lang, "Estatísticas", "Statistics"), T(lang, "Duração média do ciclo:", "Average cycle length:"), avg,
               T(lang, "Duração dos últimos ciclos (dias)", "Length of recent cycles (days)"), _bars(s["cycles"]),
               T(lang, "Duração dos últimos períodos (dias)", "Length of recent periods (days)"), _bars(s["lens"]),
               T(lang, "Sintomas mais frequentes:", "Most frequent symptoms:"), sym,
               T(lang, "Humor mais frequente:", "Most frequent mood:"), mood,
               T(lang, "Sequência de registo:", "Logging streak:"), st, T(lang, "dia" if st == 1 else "dias", "day" if st == 1 else "days"),
               T(lang, "dias registados:", "days logged:"), s["logged"]))

def _opts(cur, items):
    return "".join('<option value="%s"%s>%s</option>' % (v, " selected" if cur == v else "", l) for v, l in items)


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
            '<div class="row"><label>Tema <select name="theme">%s</select></label><label>Cores <select name="palette">%s</select></label></div>'
            '<label><input type="checkbox" name="r_period" value="1"%s> Lembrete da menstruação</label>'
            '<label>Avisar quantos dias antes <input type="number" name="before" min="0" max="7" value="%d"></label>'
            '<label><input type="checkbox" name="r_ov" value="1"%s> Lembrete da janela fértil / ovulação</label>'
            '<label><input type="checkbox" name="r_late" value="1"%s> Avisar se a menstruação atrasar</label>'
            '<label><input type="checkbox" name="takes_pill" value="1"%s> Tomo pílula (ativa o registo e o lembrete; se desligares, os registos da pílula são apagados)</label>'
            '%s'
            '<button>Guardar</button></form>%s'
            '<p><a class="lnk" href="/finance/period/export?fmt=csv">Exportar CSV</a> <a class="lnk" href="/finance/period/export?fmt=json">Exportar JSON</a>%s</p>'
            '<form method="post" action="/finance/period/import" class="box"><b>🐧 Importar dados (Clover, outras apps, CSV ou JSON)</b>'
            '<div class="mut">Escolhe o ficheiro exportado da outra app. Os dias novos são adicionados e os teus registos existentes não são apagados.</div>'
            '<input type="file" accept=".csv,.json,.txt" onchange="var f=this.files[0];if(f){var r=new FileReader();r.onload=function(){document.getElementById(\'impd\').value=r.result};r.readAsText(f)}">'
            '<textarea id="impd" name="data" rows="2" style="display:none"></textarea><button>Importar</button></form>'
            '<form method="post" action="/finance/period/wipe" class="box"><b>Apagar todos os registos</b>'
            '<input type="text" name="confirm" placeholder="Escreve APAGAR"><button style="background:#7a3030">Apagar tudo</button></form></details>'
            % (goal, st["cycle"], st["period"], _opts(st.get("theme", "auto"), (("auto", "Automático"), ("escuro", "Escuro"), ("claro", "Claro"))),
               _opts(st.get("palette", "gelo"), (("gelo", "Gelo 🐧"), ("natural", "Natural"), ("rosa", "Rosa"), ("oceano", "Oceano"), ("lavanda", "Lavanda"))), ck(r["period"]), r["before"], ck(r["ovulation"]), ck(r["late"]), ck(st.get("takes_pill")), ('<label><input type="checkbox" name="r_pill" value="1"%s> Lembrete diário da pílula</label><label>Hora da pílula <input type="time" name="pill_time" value="%s"></label>' % (ck(r.get("pill")), r.get("pill_time", "09:00"))) if st.get("takes_pill") else "", pin,
               ' <form method="post" action="/finance/period/lock" style="display:inline"><button>Bloquear agora</button></form>' if P.has_pin(d) else ""))
    return out.replace("<label>Objetivo <select", "<label>Goal <select").replace("Lembrete diário da pílula", "Daily pill reminder").replace("Tomo pílula (ativa o registo e o lembrete; se desligares, os registos da pílula são apagados)", "I take the pill (enables logging and reminder; turning it off deletes pill records)").replace("🐧 Importar dados (Clover, outras apps, CSV ou JSON)", "🐧 Import data (Clover, other apps, CSV or JSON)").replace("Escolhe o ficheiro exportado da outra app. Os dias novos são adicionados e os teus registos existentes não são apagados.", "Pick the file exported from the other app. New days are added; your existing records are kept.").replace(">Importar<", ">Import<").replace("Hora da pílula", "Pill time") if lang == "en" else out


def _pingo_banner(d, info, ph, today, lang):
    """Pingo reage ao estado do dia: cólicas, período, ovulação, pílula, noite, atraso."""
    import datetime as _dt
    pt = lang != "en"
    e = d["days"].get(today.isoformat()) or {}
    sym = [x for x in (e.get("sym") or [])]
    key = ph[0] if ph else None
    hour = _dt.datetime.now().hour
    pill_on = bool((d["settings"].get("remind") or {}).get("pill")) or bool(e.get("pill"))
    if any("lica" in x or "ramp" in x for x in sym):
        st, tx = "cramps", ("Hoje há cólicas. Calor na barriga, chá quente e descanso ajudam." if pt else "Cramps today. A warm compress, hot tea and rest can help.")
    elif info.get("late"):
        st, tx = "warning", ("O período está atrasado. Se for habitual, está tudo bem; se tiveres dúvidas, fala com o teu médico." if pt else "Your period is late. If that's unusual, consider a test or talk to your doctor.")
    elif key == "menstrual":
        st, tx = "period", ("Estás no período. Cuida de ti e bebe água." if pt else "You're on your period. Take care and drink water.")
    elif key == "ovulatoria":
        st, tx = "ovulation", ("Janela fértil. Se não queres engravidar, usa proteção." if pt else "Fertile window. Use protection if you're avoiding pregnancy.")
    elif pill_on and not e.get("pill") and 6 <= hour < 23:
        st, tx = "pill", ("Já tomaste a pílula hoje? Marca-a no registo." if pt else "Did you take your pill today? Log it below.")
    elif hour >= 23 or hour < 6:
        st, tx = "sleep", ("É tarde. Dormir bem ajuda o ciclo." if pt else "It's late. Good sleep helps your cycle.")
    elif e.get("flow") or sym:
        st, tx = "selfcare", ("Obrigado por registares hoje." if pt else "Thanks for logging today.")
    else:
        st, tx = "idle", ("Olá! Regista como te sentes hoje." if pt else "Hi! Log how you feel today.")
    return '<div class="pgbox">%s<p>%s</p></div>' % (PG.pg(st, 130), E(tx))



def render(user, msg="", ym="", day="", cookie="", lang="pt", edit=False, tab="", q=None):
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
    stt = d["settings"]
    if tab in ("stories", "care", "ask", "profile"):
        th0 = stt.get("theme") if stt.get("theme") in ("auto", "escuro", "claro") else "auto"
        pal0 = stt.get("palette") if stt.get("palette") in ("natural", "rosa", "oceano", "lavanda", "gelo") else "gelo"
        body = PC.stories(ph, today, lang) if tab == "stories" else (PC.ask_page(lang, bool(stt.get("profile"))) if tab == "ask" else (PG.profile_page(stt.get("profile") or {}, lang, msg, q) if tab == "profile" else PC.care(q or {}, lang)))
        return CSS + PG.PG_CSS + '<div class="cy th-%s pal-%s"><div class="cybar"><a href="/finance/">← Finanças</a><a href="/finance/logout">sair</a></div><h2>Ciclo 🐧</h2>' % (th0, pal0) + PC.nav(tab, lang) + body + '</div>'
    th = stt.get("theme") if stt.get("theme") in ("auto", "escuro", "claro") else "auto"
    pal = stt.get("palette") if stt.get("palette") in ("natural", "rosa", "oceano", "lavanda", "gelo") else "gelo"
    return (CSS + PG.PG_CSS + '<div class="cy th-%s pal-%s"><div class="cybar"><a href="/finance/">← Finanças</a><a href="/finance/logout">sair</a></div><h2>Ciclo 🐧</h2>' % (th, pal) + ('<p class="green">%s</p>' % E(msg) if msg else "")
            + PC.nav('', lang) + _pingo_banner(d, info, ph, today, lang) + _week(d, info, today, lang) + (_edit(d, today, lang) if edit else "") + _cyc_changed(d, info, lang) + _hero(info, ph, lang, T(lang, P.chance(info, today), {"alta": "high", "média": "medium", "baixa": "low"}[P.chance(info, today)])) + '<div class="cards">%s</div>' % _summary(info, d["settings"]["goal"], today, ph, lang)
            + _tips(ph, today, lang) + '<div class="box">%s</div>' % _calendar(d, info, y, m, sel, today, lang)
            + _daypanel(info, sel, today, ph, lang, "/finance/period?edit=1")
            + '<h3>%s</h3>%s' % (T(lang, "Registar · %s", "Log · %s") % _pt(sel, lang), _form(d, sel, today, lang)) + _faq(lang) + _stats(d, today, lang) + hist + _settings(d, lang)
            + '<p class="aviso">Estimativas com base nos teus registos (ou nos valores das definições). '
              'Não é um método contracetivo. Em caso de dúvida, fala com o teu médico.</p></div>')


def ask_api(user, body, cookie, lang):
    d = P.load(user)
    if not P.unlocked(user, d, cookie):
        return {"error": "Bloqueado" if lang != "en" else "Locked"}
    q = str((body or {}).get("q") or "").strip()
    if not q:
        return {"error": "Escreve uma pergunta" if lang != "en" else "Type a question"}
    today = datetime.date.today()
    info = P.predict(d["days"], today, d["settings"])
    ph = P.phase(info, today)
    recent = []
    for k in sorted(d["days"])[-3:]:
        for s in d["days"][k].get("sym", []):
            if s not in recent: recent.append(str(s)[:30])
    try:
        a = PC.ask(PC.ask_system(info, ph, today, recent[:8], lang, PG.profile_text(d["settings"].get("profile") or {})), (body or {}).get("h") or [], q)
    except Exception:
        return {"error": "O Pingo não respondeu. Tenta outra vez." if lang != "en" else "Pingo didn't answer. Please try again."}
    return {"a": a or ("Sem resposta." if lang != "en" else "No answer.")}


GYM_TIPS = {
    "menstrual": ("🩸", "Fase menstrual", "Energia mais baixa: treina por sensação, não por números.",
                  ["Treino: mantém as 3 sessões se te sentires bem, mas com cargas 10 a 20% mais leves e menos séries. Se doer muito, troca por caminhada ou alongamentos.",
                   "Dieta: ferro (carne magra, leguminosas, espinafres) com fruta rica em vitamina C, e bastante água. Mantém as calorias do plano.",
                   "Pausa: se há cólicas fortes, descansar também é treino."]),
    "folicular": ("🌱", "Fase folicular", "A energia sobe: bom momento para puxar mais.",
                  ["Treino: é a melhor fase para aumentar carga (2 a 5%) e tentar recordes nos exercícios principais (hip thrust, supino).",
                   "Dieta: segue o plano com a proteína completa (1,6 a 2 g por kg) e hidratos antes do treino.",
                   "Recuperação: costuma ser mais rápida, por isso aproveita."]),
    "ovulatoria": ("✨", "Fase ovulatória", "Pico de energia, mas as articulações ficam mais soltas.",
                   ["Treino: bom dia para treinos intensos. Aquece mais tempo e cuida da técnica nos afundos e agachamentos, por causa dos joelhos.",
                    "Dieta: refeições leves com antioxidantes (frutos vermelhos, vegetais) e hidratação a sério.",
                    "Atenção: evita saltos e mudanças bruscas de direção sem aquecer."]),
    "lutea": ("🌙", "Fase lútea", "Mais fome e cansaço, sobretudo no fim.",
              ["Treino: mantém a frequência, mas se estiveres cansada baixa o volume (menos 1 série) em vez de faltar. Yoga e pilates contam como treino leve.",
               "Dieta: é normal ter mais fome. Acrescenta 100 a 200 kcal em hidratos complexos (aveia, batata-doce) e magnésio (frutos secos, cacau puro).",
               "Sono e sal: dorme bem e bebe água; podes reter líquidos, por isso o peso sobe e desce nesta fase, sem ser gordura. Compara o peso na mesma fase do ciclo."]),
}


def gym_card(user, today=None):
    """Caixa 'Treino e dieta ao ritmo do teu ciclo' para o Gym. Vazia se a conta nao usa o Ciclo."""
    import datetime as _dt
    try:
        d = P.load(user)
    except Exception:
        return ""
    today = today or _dt.date.today()
    if not d.get("days"):
        return ('<div class="box"><h2>🐧 Ciclo e treino</h2><p style="color:#aaa">Regista o teu período na aba '
                '<a href="/finance/period">Ciclo</a> e aqui aparecem dicas de treino e dieta para a fase em que estás.</p></div>')
    info = P.predict(d["days"], today, d["settings"])
    key, day = P.phase(info, today)
    if not key:
        return ""
    ico, nome, resumo, tips = GYM_TIPS[key]
    li = "".join("<li>%s</li>" % html.escape(t) for t in tips)
    return ('<div class="box" style="border-left:4px solid #6fa8ff"><h2>%s Treino e dieta · %s (dia %d)</h2>'
            '<p>%s</p><ul>%s</ul><div style="color:#aaa;font-size:12px">Orientação geral, não substitui o médico ou nutricionista. '
            'O plano base não muda.</div></div>' % (ico, nome, day, html.escape(resumo), li))
