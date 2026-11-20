"""Pingo: pinguim SVG vetorial com 17 estados animados em CSS (sem JS, sem ficheiros externos)."""
STATES = ["idle","hello","think","talk","happy","sleep","sad","cramps","period","ovulation","pill","read","selfcare","quiz","warning","celebrate","loading"]
DK, DKS, WH, OR, PK, PKS = "#4b5b7c", "#2f3b57", "#f2f7ff", "#f0a04b", "#f4a3c0", "#c9708f"
EYE = {
 "open": '<circle cx="80" cy="80" r="6.5" fill="#1a1d2b"/><circle cx="120" cy="80" r="6.5" fill="#1a1d2b"/><circle cx="82" cy="77.5" r="2.2" fill="#fff"/><circle cx="122" cy="77.5" r="2.2" fill="#fff"/>',
 "closed": '<path d="M72 82 Q80 88 88 82M112 82 Q120 88 128 82" fill="none" stroke="#1a1d2b" stroke-width="3" stroke-linecap="round"/>',
 "happy": '<path d="M72 84 Q80 74 88 84M112 84 Q120 74 128 84" fill="none" stroke="#1a1d2b" stroke-width="3.5" stroke-linecap="round"/>',
 "sad": '<circle cx="80" cy="82" r="6" fill="#1a1d2b"/><circle cx="120" cy="82" r="6" fill="#1a1d2b"/><circle cx="82" cy="79.5" r="2" fill="#fff"/><circle cx="122" cy="79.5" r="2" fill="#fff"/><path d="M70 70 L88 75M130 70 L112 75" stroke="#1a1d2b" stroke-width="2.5" stroke-linecap="round"/>',
 "up": '<circle cx="82" cy="76" r="6.5" fill="#1a1d2b"/><circle cx="122" cy="76" r="6.5" fill="#1a1d2b"/><circle cx="84" cy="73.5" r="2.2" fill="#fff"/><circle cx="124" cy="73.5" r="2.2" fill="#fff"/>',
 "down": '<circle cx="80" cy="85" r="6.5" fill="#1a1d2b"/><circle cx="120" cy="85" r="6.5" fill="#1a1d2b"/><circle cx="82" cy="83" r="2.2" fill="#fff"/><circle cx="122" cy="83" r="2.2" fill="#fff"/>',
 "serious": '<circle cx="80" cy="81" r="6" fill="#1a1d2b"/><circle cx="120" cy="81" r="6" fill="#1a1d2b"/><circle cx="82" cy="79" r="2" fill="#fff"/><circle cx="122" cy="79" r="2" fill="#fff"/><path d="M70 72 L88 69M130 72 L112 69" stroke="#1a1d2b" stroke-width="2.5" stroke-linecap="round"/>',
}
CFG = {  # estado: (olhos, boca aberta, adereco)
 "idle": ("open", 0, ""), "hello": ("open", 1, ""), "think": ("up", 0, "think"), "talk": ("open", 1, ""),
 "happy": ("happy", 1, ""), "sleep": ("closed", 0, "zzz"), "sad": ("sad", 0, "tear"), "cramps": ("closed", 0, "bottle"),
 "period": ("closed", 0, "drop"), "ovulation": ("happy", 0, "spark"), "pill": ("open", 0, "pill"), "read": ("down", 0, "book"),
 "selfcare": ("closed", 0, "tea"), "quiz": ("open", 0, "clip"), "warning": ("serious", 0, "cross"), "celebrate": ("happy", 1, "confetti"),
 "loading": ("open", 0, "spin"),
}
PROPS = {
 "think": '<g class="bub"><circle cx="160" cy="40" r="4" fill="#fff"/><circle cx="170" cy="28" r="6" fill="#fff"/><ellipse cx="184" cy="12" rx="14" ry="10" fill="#fff" stroke="#9db" stroke-width="1"/><g fill="#4b5b7c"><circle class="d1" cx="178" cy="12" r="2"/><circle class="d2" cx="184" cy="12" r="2"/><circle class="d3" cx="190" cy="12" r="2"/></g></g>',
 "zzz": '<g class="zz" font-family="sans-serif" font-weight="700" fill="#7aa7d6"><text class="z1" x="150" y="40" font-size="16">z</text><text class="z2" x="162" y="26" font-size="20">z</text><text class="z3" x="176" y="10" font-size="24">Z</text></g>',
 "tear": '<path class="tear" d="M62 90 q-5 9 0 12 q5 -3 0 -12z" fill="#5ab4e8" stroke="#2f7fb0" stroke-width="1"/>',
 "bottle": '<g class="front"><path d="M80 150 Q70 170 90 184 Q112 190 120 170 Q122 152 108 146 L100 138 L92 142Z" fill="#e0505a" stroke="#9c2a34" stroke-width="3"/><rect x="92" y="132" width="14" height="10" rx="3" fill="#b8353f" stroke="#9c2a34" stroke-width="2"/></g>',
 "drop": '<path class="drop" d="M168 30 Q152 54 168 62 Q184 54 168 30Z" fill="#e0505a" stroke="#9c2a34" stroke-width="2"/><path class="heart" d="M30 40 q-10 -10 -4 -16 q4 -3 4 2 q0 -5 4 -2 q6 6 -4 16z" fill="#f4a3c0"/>',
 "spark": '<g fill="#ffd24a" stroke="#d9a020" stroke-width="1"><path class="s1" d="M30 40 l3 8 8 3 -8 3 -3 8 -3 -8 -8 -3 8 -3z"/><path class="s2" d="M170 30 l4 10 10 4 -10 4 -4 10 -4 -10 -10 -4 10 -4z"/><path class="s3" d="M160 100 l2 6 6 2 -6 2 -2 6 -2 -6 -6 -2 6 -2z"/></g><g class="flower" transform="translate(40 168)"><g fill="#f9b8d2" stroke="#c9708f" stroke-width="1.5"><circle cx="0" cy="-8" r="6"/><circle cx="8" cy="0" r="6"/><circle cx="0" cy="8" r="6"/><circle cx="-8" cy="0" r="6"/></g><circle r="5" fill="#ffd24a"/></g>',
 "pill": '<g class="water"><path d="M150 150 h22 l-3 34 h-16z" fill="#bfe6f7" fill-opacity=".8" stroke="#5aa4c8" stroke-width="2.5"/><path d="M153 160 h16 l-1 22 h-14z" fill="#7cc8ee"/></g><g class="pillg"><rect x="172" y="108" width="22" height="10" rx="5" fill="#e0505a" stroke="#9c2a34" stroke-width="2" transform="rotate(-30 183 113)"/></g>',
 "book": '<g class="front"><path d="M100 160 Q80 150 56 156 L56 186 Q80 180 100 190Z" fill="#fff" stroke="#6a7a98" stroke-width="3"/><path d="M100 160 Q120 150 144 156 L144 186 Q120 180 100 190Z" fill="#fff" stroke="#6a7a98" stroke-width="3"/><path class="page" d="M100 160 Q122 152 142 158 L142 184 Q122 180 100 188Z" fill="#eef3fb" stroke="#6a7a98" stroke-width="1.5"/></g>',
 "tea": '<g class="front"><path d="M82 160 h36 l-4 24 q-14 6 -28 0z" fill="#fff" stroke="#6a7a98" stroke-width="3"/><path d="M118 164 q14 0 10 12 q-4 6 -10 4" fill="none" stroke="#6a7a98" stroke-width="3"/></g><g class="steam" fill="none" stroke="#b9c6dc" stroke-width="3" stroke-linecap="round"><path class="st1" d="M92 152 q-6 -8 0 -14 q6 -6 0 -14"/><path class="st2" d="M108 152 q-6 -8 0 -14 q6 -6 0 -14"/></g><path class="heart" d="M162 50 q-12 -12 -5 -19 q5 -4 5 3 q0 -7 5 -3 q7 7 -5 19z" fill="#f4a3c0" stroke="#c9708f" stroke-width="1.5"/>',
 "clip": '<g class="front"><rect x="104" y="140" width="52" height="58" rx="6" fill="#fff" stroke="#6a7a98" stroke-width="3"/><rect x="120" y="134" width="20" height="10" rx="3" fill="#8ea3c8" stroke="#6a7a98" stroke-width="2"/><g stroke="#4fb3e0" stroke-width="3" fill="none" stroke-linecap="round"><path class="c1" d="M112 156 l4 4 8 -8"/><path class="c2" d="M112 172 l4 4 8 -8"/><path class="c3" d="M112 188 l4 4 8 -8"/></g><path d="M130 156h18M130 172h18M130 188h18" stroke="#c4cfe2" stroke-width="3"/></g>',
 "cross": '<g class="badge"><circle cx="164" cy="44" r="22" fill="#fff" stroke="#e0505a" stroke-width="4"/><path d="M164 32 v24 M152 44 h24" stroke="#e0505a" stroke-width="7" stroke-linecap="round"/></g>',
 "confetti": '<g class="conf"><rect class="k1" x="30" y="10" width="7" height="12" fill="#f4a3c0"/><rect class="k2" x="60" y="0" width="7" height="12" fill="#ffd24a"/><rect class="k3" x="100" y="6" width="7" height="12" fill="#5ab4e8"/><rect class="k4" x="140" y="0" width="7" height="12" fill="#a8e063"/><rect class="k5" x="170" y="10" width="7" height="12" fill="#e0505a"/><circle class="k6" cx="46" cy="14" r="4" fill="#5ab4e8"/><circle class="k7" cx="120" cy="10" r="4" fill="#f4a3c0"/><circle class="k8" cx="154" cy="14" r="4" fill="#ffd24a"/></g><path class="hat" d="M84 28 L100 -4 L116 28z" fill="#ffd24a" stroke="#d9a020" stroke-width="2.5"/>',
 "spin": '<g class="spin" transform="translate(166 40)"><g fill="#4fb3e0"><circle cx="0" cy="-14" r="4"/><circle cx="12" cy="-7" r="3.5" opacity=".8"/><circle cx="12" cy="7" r="3" opacity=".6"/><circle cx="0" cy="14" r="2.5" opacity=".45"/><circle cx="-12" cy="7" r="2" opacity=".3"/></g></g>',
}
CSS = """<style>
.pgsvg{display:inline-block;vertical-align:middle;overflow:visible}
.pgsvg *{transform-box:view-box}
.pgsvg .all{transform-origin:100px 200px}.pgsvg .head{transform-origin:100px 120px}.pgsvg .wl{transform-origin:52px 112px}.pgsvg .wr{transform-origin:148px 112px}
.pgsvg .tail{transform-origin:122px 132px;animation:pgsw 3s ease-in-out infinite}.pgsvg .eyes{transform-origin:100px 80px;animation:pgbl 4.5s infinite}
.pgsvg .mouth{transform-origin:100px 95px;display:none}.pgsvg.mo .mouth{display:block}.pgsvg.mo .beakc{display:none}
@keyframes pgsw{50%{transform:rotate(7deg)}}@keyframes pgbl{0%,93%,100%{transform:scaleY(1)}96%{transform:scaleY(.1)}}
@keyframes pgbr{50%{transform:scale(1.025,.985)}}@keyframes pgjp{0%,100%{transform:translateY(0)}40%{transform:translateY(-22px)}}
@keyframes pgwv{0%,100%{transform:rotate(-125deg)}50%{transform:rotate(-165deg)}}@keyframes pgtk{50%{transform:scaleY(.35)}}
@keyframes pgfl{0%{opacity:0;transform:translateY(8px)}30%,70%{opacity:1}100%{opacity:0;transform:translateY(-14px)}}
@keyframes pgtw{50%{opacity:.25;transform:scale(.6)}}@keyframes pgbo{50%{transform:translateY(-4px)}}@keyframes pgsp{to{transform:rotate(360deg)}}
@keyframes pgcf{0%{transform:translateY(-10px) rotate(0);opacity:0}15%{opacity:1}100%{transform:translateY(200px) rotate(360deg);opacity:0}}
@keyframes pgpl{50%{transform:scale(1.12)}}@keyframes pgrt{50%{transform:rotate(6deg)}}@keyframes pgdp{0%{transform:translateY(0);opacity:1}100%{transform:translateY(40px);opacity:0}}
@keyframes pgdt{0%,100%{opacity:.2}50%{opacity:1}}@keyframes pgpg{0%,100%{transform:rotate(0)}50%{transform:rotate(-8deg)}}
@keyframes pgpi{0%,40%{transform:translate(0,0)}70%,100%{transform:translate(-80px,-24px)}}
.pgs-idle .all{animation:pgbr 3.4s ease-in-out infinite}
.pgs-hello .wr{animation:pgwv 1s ease-in-out infinite}.pgs-hello .all{animation:pgbr 3s ease-in-out infinite}
.pgs-think .wr{transform:rotate(-60deg)}.pgs-think .head{animation:pgrt 3s ease-in-out infinite}.pgs-think .d1{animation:pgdt 1.2s infinite}.pgs-think .d2{animation:pgdt 1.2s .3s infinite}.pgs-think .d3{animation:pgdt 1.2s .6s infinite}
.pgs-talk .mouth{animation:pgtk .35s ease-in-out infinite}.pgs-talk .wr{animation:pgwv 1.4s ease-in-out infinite;transform:rotate(-40deg)}.pgs-talk .all{animation:pgbo .7s ease-in-out infinite}
.pgs-happy .all{animation:pgjp .8s ease-out 3}.pgs-happy .wl{transform:rotate(130deg)}.pgs-happy .wr{transform:rotate(-130deg)}
.pgs-sleep .all{animation:pgbr 5s ease-in-out infinite}.pgs-sleep .eyes{animation:none}.pgs-sleep .head{transform:rotate(6deg)}.pgs-sleep .z1{animation:pgfl 3s infinite}.pgs-sleep .z2{animation:pgfl 3s 1s infinite}.pgs-sleep .z3{animation:pgfl 3s 2s infinite}
.pgs-sad .head{transform:translateY(8px) rotate(-3deg)}.pgs-sad .tear{animation:pgdp 2s infinite}.pgs-sad .all{animation:pgbr 4s ease-in-out infinite}
.pgs-cramps .wl{transform:rotate(-50deg)}.pgs-cramps .wr{transform:rotate(50deg)}.pgs-cramps .all{animation:pgrt 2.2s ease-in-out infinite}.pgs-cramps .eyes{animation:none}
.pgs-period .all{animation:pgbr 4s ease-in-out infinite}.pgs-period .drop{animation:pgbo 2s ease-in-out infinite}.pgs-period .heart{animation:pgpl 2s infinite;transform-origin:30px 30px}.pgs-period .eyes{animation:none}
.pgs-ovulation .s1{animation:pgtw 1.6s infinite;transform-origin:30px 50px}.pgs-ovulation .s2{animation:pgtw 1.6s .5s infinite;transform-origin:170px 44px}.pgs-ovulation .s3{animation:pgtw 1.6s 1s infinite;transform-origin:160px 108px}.pgs-ovulation .flower{animation:pgsp 12s linear infinite;transform-origin:40px 168px}.pgs-ovulation .all{animation:pgbr 3s ease-in-out infinite}.pgs-ovulation .eyes{animation:none}
.pgs-pill .wr{animation:pgpg 3s ease-in-out infinite;transform:rotate(-30deg)}.pgs-pill .pillg{animation:pgpi 3s ease-in-out infinite}.pgs-pill .all{animation:pgbr 3s ease-in-out infinite}
.pgs-read .head{transform:translateY(4px)}.pgs-read .wl{transform:rotate(-35deg)}.pgs-read .wr{transform:rotate(35deg)}.pgs-read .page{animation:pgtk 3s ease-in-out infinite;transform-origin:100px 170px}.pgs-read .all{animation:pgbr 4s ease-in-out infinite}
.pgs-selfcare .wl{transform:rotate(-30deg)}.pgs-selfcare .wr{transform:rotate(30deg)}.pgs-selfcare .st1{animation:pgfl 2.4s infinite}.pgs-selfcare .st2{animation:pgfl 2.4s 1.2s infinite}.pgs-selfcare .heart{animation:pgpl 2s infinite;transform-origin:162px 40px}.pgs-selfcare .eyes{animation:none}.pgs-selfcare .all{animation:pgbr 4s ease-in-out infinite}
.pgs-quiz .wr{transform:rotate(50deg)}.pgs-quiz .c1{animation:pgdt 3s infinite}.pgs-quiz .c2{animation:pgdt 3s 1s infinite}.pgs-quiz .c3{animation:pgdt 3s 2s infinite}.pgs-quiz .head{animation:pgrt 3.5s ease-in-out infinite}
.pgs-warning .badge{animation:pgpl 1.1s ease-in-out infinite;transform-origin:164px 44px}.pgs-warning .wr{transform:rotate(-20deg)}.pgs-warning .eyes{animation:none}
.pgs-celebrate .all{animation:pgjp .7s ease-out infinite}.pgs-celebrate .wl{transform:rotate(130deg)}.pgs-celebrate .wr{transform:rotate(-130deg)}.pgs-celebrate .k1{animation:pgcf 2.2s infinite}.pgs-celebrate .k2{animation:pgcf 2.2s .3s infinite}.pgs-celebrate .k3{animation:pgcf 2.2s .6s infinite}.pgs-celebrate .k4{animation:pgcf 2.2s .9s infinite}.pgs-celebrate .k5{animation:pgcf 2.2s 1.2s infinite}.pgs-celebrate .k6{animation:pgcf 2.2s 1.5s infinite}.pgs-celebrate .k7{animation:pgcf 2.2s 1.8s infinite}.pgs-celebrate .k8{animation:pgcf 2.2s .15s infinite}
.pgs-loading .spin{animation:pgsp 1s linear infinite;transform-origin:166px 40px}.pgs-loading .all{animation:pgbo 1.2s ease-in-out infinite}.pgs-loading .head{animation:pgrt 1.6s ease-in-out infinite}
@media (prefers-reduced-motion:reduce){.pgsvg *{animation:none!important}}
</style>"""


def svg(state, size=64):
    if state not in CFG:
        state = "idle"
    eyes, mo, prop = CFG[state]
    p = PROPS.get(prop, "")
    front = p if prop in ("bottle", "book", "tea", "clip") else ""
    back = "" if front else p
    body = (
        '<ellipse cx="100" cy="202" rx="56" ry="7" fill="#000" opacity=".12"/>'
        '<g class="all">'
        '<ellipse cx="76" cy="196" rx="18" ry="8" fill="%s" stroke="#c97a2a" stroke-width="2.5"/><ellipse cx="124" cy="196" rx="18" ry="8" fill="%s" stroke="#c97a2a" stroke-width="2.5"/>'
        '<ellipse cx="100" cy="142" rx="58" ry="58" fill="%s" stroke="%s" stroke-width="3"/><ellipse cx="100" cy="152" rx="40" ry="46" fill="%s"/>'
        '<g class="wl"><path d="M52 108 C28 120 22 152 36 167 C50 162 56 142 58 118Z" fill="%s" stroke="%s" stroke-width="3"/></g>'
        '<g class="wr"><path d="M148 108 C172 120 178 152 164 167 C150 162 144 142 142 118Z" fill="%s" stroke="%s" stroke-width="3"/></g>'
        '<g class="tail"><path d="M114 130 Q132 136 142 132 L150 178 Q134 186 122 178Z" fill="%s" stroke="%s" stroke-width="3" stroke-linejoin="round"/><g fill="#fff" opacity=".6"><circle cx="130" cy="150" r="2.5"/><circle cx="138" cy="164" r="2.5"/><circle cx="126" cy="168" r="2.5"/></g></g>'
        '<g class="head"><ellipse cx="100" cy="72" rx="58" ry="52" fill="%s" stroke="%s" stroke-width="3"/>'
        '<ellipse cx="78" cy="84" rx="27" ry="27" fill="%s"/><ellipse cx="122" cy="84" rx="27" ry="27" fill="%s"/><ellipse cx="100" cy="92" rx="30" ry="21" fill="%s"/>'
        '<g class="eyes">%s</g><ellipse cx="62" cy="98" rx="9" ry="6" fill="#f7a6c2" opacity=".8"/><ellipse cx="138" cy="98" rx="9" ry="6" fill="#f7a6c2" opacity=".8"/>'
        '<path class="beakc" d="M88 92 Q100 85 112 92 Q108 104 100 104 Q92 104 88 92Z" fill="%s" stroke="#c97a2a" stroke-width="2.5" stroke-linejoin="round"/>'
        '<g class="mouth"><path d="M88 91 Q100 85 112 91 Q108 100 100 100 Q92 100 88 91Z" fill="%s" stroke="#c97a2a" stroke-width="2.5"/><path d="M90 96 Q100 116 110 96Q100 100 90 96Z" fill="#c9505a" stroke="#c97a2a" stroke-width="2.5" stroke-linejoin="round"/></g>'
        '</g>'
        '<path d="M50 112 Q100 138 150 112 L154 130 Q100 158 46 130Z" fill="%s" stroke="%s" stroke-width="3" stroke-linejoin="round"/>'
        '%s</g>%s'
    ) % (OR, OR, DK, DKS, WH, DK, DKS, DK, DKS, PK, PKS, DK, DKS, WH, WH, WH, EYE[eyes], OR, OR, PK, PKS, front, back)
    return '<svg class="pgsvg pgs-%s%s" data-pg="%s" viewBox="-6 -8 212 222" width="%d" height="%d" aria-hidden="true">%s</svg>' % (state, " mo" if mo else "", state, size, size, body)
