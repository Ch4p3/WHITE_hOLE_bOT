"""
White Hole · monitos animados (personaje original) para la serie "¿Qué pasa si…?".

Plantilla "monito" (se registra en make_short.VISUALS):
  "pose":      parado | saludo | musculo | cansado | pensando | flexion | abdominal
  "cara":      feliz | esfuerzo | dolor | sorprendido | pensando   (opcional, si no se elige según la pose)
  "ritmo":     segundos por repetición (flexion / abdominal)
  "escala":    tamaño del monito (1.0 por defecto)
  "pastilla":  texto en una etiqueta naranja arriba (ej. "SEMANA 1")
  "titulo", "sub", "titulo_sync", "sub_sync", "titulo_color"
  "brillo":    partes que se iluminan: pecho, abdomen, hombros, brazos, piernas  (+ "brillo_sync")
  "etiquetas": [{"texto": "PECHO", "parte": "pecho", "lado": "izq"|"der", "dy": 0, "sync": "pecho"}]
  "contador":  {"hasta": 20, "sync": "...", "x": 540, "y": 820}
  "accesorio": {"emoji": "🧠", "sync": "...", "dx": 150, "dy": -120}
  "sudor":     true
  "boton":     texto de botón final (ej. "SEGUIR  +"), "boton_sync"
"""
import math
from PIL import Image, ImageDraw, ImageFilter

SS = 2                       # supermuestreo para bordes suaves
LADO = ("flexion", "abdominal", "sentadilla", "puente", "caminar", "plancha")
HAIR = (78, 50, 44)
SKINS = {"monito": ((88, 166, 255), (58, 120, 205), (34, 48, 92)),
         "monita": ((255, 122, 164), (220, 86, 132), (70, 40, 92))}
CW, CH = 1080, 900           # lienzo local del monito (ancho completo)

BODY = (238, 242, 250)       # el monito es blanco (White Hole)
LINE = (10, 12, 24)          # contorno
SHIRT = (88, 166, 255)
SHIRT_D = (58, 120, 205)
SHORTS = (34, 48, 92)
SHOE = (255, 138, 76)
BAND = (255, 138, 76)
EYE = (16, 18, 30)
BLUSH = (255, 150, 160)
GLOW = (255, 92, 60)
FAR = (196, 204, 222)        # extremidades del fondo (un poco más oscuras)


def _v(a, b): return (b[0] - a[0], b[1] - a[1])
def _len(v): return math.hypot(v[0], v[1]) or 1e-6
def _norm(v): L = _len(v); return (v[0] / L, v[1] / L)
def _add(a, v, k=1.0): return (a[0] + v[0] * k, a[1] + v[1] * k)
def _lerp(a, b, k): return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
def _osc(t, per): return 0.5 - 0.5 * math.cos(2 * math.pi * t / per)   # 0 -> 1 -> 0


def _ik(root, target, l1, l2, bend=1):
    """Codo/rodilla de una cadena de dos huesos (bend = ±1 elige hacia qué lado se dobla)."""
    v = _v(root, target); d = min(_len(v), l1 + l2 - 0.5)
    base = math.atan2(v[1], v[0])
    c = max(-1.0, min(1.0, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)))
    a = base + bend * math.acos(c)
    return (root[0] + l1 * math.cos(a), root[1] + l1 * math.sin(a))


# ------------------------------------------------------------------ poses
def pose(kind, t, p):
    """Devuelve puntos del esqueleto (coordenadas relativas: x a la derecha, y hacia arriba negativo; suelo y=0)."""
    P = {"vista": "frente"}
    if kind in LADO:
        P["vista"] = "lado"
    per = float(p.get("ritmo", 1.15))

    if kind == "sentadilla":
        k = _osc(t, per)
        A = (30, -34)
        hip = (-15 - 125 * k, -300 + 150 * k)
        c1, c2 = _ik(hip, A, 150, 150, 1), _ik(hip, A, 150, 150, -1)
        knee = c1 if c1[0] > c2[0] else c2
        th = math.radians(8 + 32 * k)
        d = (math.sin(th), -math.cos(th))
        S = _add(hip, d, 205)
        hand = _add(S, (math.cos(math.radians(8 - 20 * k)), math.sin(math.radians(8 - 20 * k))), 180)
        P.update(S=S, hip=hip, knee=knee, foot=A, hand=hand, E=_add(_lerp(S, hand, 0.5), (0, 8)),
                 head=_add(_add(S, d, 80), (14, 0)), cara_dx=(30, 0), baja=k, reps=t / per)
        return P
    if kind == "caminar":
        w = 2 * math.pi * t / per
        bob = -abs(math.sin(w)) * 8
        hip = (0, -292 + bob)
        def pierna(ph):
            a = math.radians(26 * math.sin(ph))
            b = math.radians(max(0.0, 38 * math.sin(ph + math.pi / 2)))
            k = (hip[0] + 150 * math.sin(a), hip[1] + 150 * math.cos(a))
            f = (k[0] + 145 * math.sin(a - b), k[1] + 145 * math.cos(a - b))
            return k, f
        k1, f1 = pierna(w); k2, f2 = pierna(w + math.pi)
        S = (hip[0] + 10, hip[1] - 205)
        def brazo(ph):
            a = math.radians(-24 * math.sin(ph))
            e = (S[0] + 118 * math.sin(a), S[1] + 118 * math.cos(a))
            h = (e[0] + 108 * math.sin(a + math.radians(28)), e[1] + 108 * math.cos(a + math.radians(28)))
            return e, h
        e1, h1 = brazo(w); e2, h2 = brazo(w + math.pi)
        P.update(S=S, hip=hip, knee=k1, foot=f1, knee2=k2, foot2=f2, E=e1, hand=h1, E2=e2, hand2=h2,
                 head=(S[0] + 14, S[1] - 86), cara_dx=(28, 0), baja=0, reps=t / per)
        return P
    if kind == "plancha":
        tr = float(p.get("temblor", 0)) * math.sin(t * 47) * 2.2
        S, toes = (150, -132 + tr), (-300, -8)
        d = _norm(_v(toes, S)); up = (d[1], -d[0])
        P.update(S=S, toes=toes, E=(150, -14), hand=(255, -14), hip=_lerp(toes, S, 0.50),
                 thigh=_lerp(toes, S, 0.40), knee=_lerp(toes, S, 0.22),
                 head=_add(_add(S, d, 78), up, 44), cara_dx=(30, 14), baja=float(p.get("esfuerzo", 0)))
        return P
    if kind == "puente":
        k = _osc(t, per)
        S, A = (-175, -42), (185, -16)
        hip = (20, -58 - 140 * k)
        c1, c2 = _ik(hip, A, 165, 160, 1), _ik(hip, A, 165, 160, -1)
        knee = c1 if c1[1] < c2[1] else c2
        P.update(S=S, hip=hip, knee=knee, foot=A, E=(-105, -24), hand=(-30, -16),
                 head=(-262, -78), cara_dx=(6, -14), baja=k, reps=t / per)
        return P

    if kind == "flexion":
        k = _osc(t, per)                                  # 0 arriba, 1 abajo
        h = 232 - 140 * k
        toes, hand = (-300, -8), (175, 0)
        S = (160, -h)
        d = _norm(_v(toes, S))
        up = (d[1], -d[0])                                # perpendicular hacia arriba
        P.update(S=S, hand=hand, toes=toes, hip=_lerp(toes, S, 0.50), thigh=_lerp(toes, S, 0.40),
                 knee=_lerp(toes, S, 0.22), E=_ik(S, hand, 122, 122, bend=-1),
                 head=_add(_add(S, d, 78), up, 46), cara_dx=(30, 14), baja=k,
                 reps=t / per)
    elif kind == "abdominal":
        k = _osc(t, per)
        a = math.radians(10 + 34 * k)
        hip, knee, foot = (40, -64), (175, -210), (300, -26)
        d = (-math.cos(a), -math.sin(a))
        S = _add(hip, d, 215)
        up = (math.sin(a), -math.cos(a))
        reach = _norm(_v(S, knee))
        hand = _add(S, reach, 190 + 25 * k)
        P.update(S=S, hip=hip, knee=knee, foot=foot, hand=hand,
                 E=_lerp(S, hand, 0.5), head=_add(_add(S, d, 76), up, 30),
                 cara_dx=(18, -16), baja=k, reps=t / per)
    else:
        bob = math.sin(t * 3.0) * 4
        sh_y = -480 + bob
        P.update(head=(0, -592 + bob), neck=(0, -505 + bob), Sl=(-74, sh_y), Sr=(74, sh_y),
                 hipc=(0, -290), Hl=(-40, -290), Hr=(40, -290), Kl=(-48, -150), Kr=(48, -150),
                 Fl=(-56, -10), Fr=(56, -10), El=(-98, -365 + bob), Er=(98, -365 + bob),
                 Al=(-104, -255 + bob), Ar=(104, -255 + bob), cara_dx=(0, 0))
        if kind == "saludo":
            w = math.sin(t * 9) * 26
            P.update(Er=(165, -560 + bob), Ar=(170 + w, -690 + bob))
        elif kind == "musculo":
            pump = 0.5 + 0.5 * math.sin(t * 5.5)
            P.update(El=(-205, -492 + bob), Er=(205, -492 + bob),
                     Al=(-196, -628 + bob - 10 * pump), Ar=(196, -628 + bob - 10 * pump), pump=pump)
        elif kind == "cansado":
            br = math.sin(t * 6.5) * 6
            P.update(head=(0, -560 + br), neck=(0, -478 + br), Sl=(-70, -452 + br), Sr=(70, -452 + br),
                     El=(-92, -340 + br), Er=(92, -340 + br), Al=(-88, -235 + br), Ar=(88, -235 + br),
                     Kl=(-58, -145), Kr=(58, -145), hipc=(0, -280), Hl=(-40, -280), Hr=(40, -280))
        elif kind == "pensando":
            P.update(Er=(118, -372 + bob), Ar=(36, -508 + bob), El=(-72, -372 + bob), Al=(70, -385 + bob))
    return P


def anchors(P):
    """Puntos de cada parte del cuerpo (para brillos y etiquetas)."""
    if P["vista"] == "lado":
        S, hip, E = P["S"], P["hip"], P["E"]
        d = _norm(_v(hip, S)); down = (-d[1], d[0])
        if down[1] < 0: down = (d[1], -d[0])
        knee = P.get("knee", hip)
        glu = _add(hip, (-40, -2)) if "foot" in P and P["hip"][1] < -100 else _add(hip, (-6, 22))
        return {"pecho": _add(_lerp(S, hip, 0.22), down, 34), "abdomen": _add(_lerp(S, hip, 0.62), down, 30),
                "hombros": S, "brazos": _lerp(S, E, 0.55), "triceps": _lerp(S, E, 0.55),
                "piernas": _lerp(hip, knee, 0.55), "gluteos": glu, "cabeza": P["head"]}
    return {"pecho": (0, -440), "abdomen": (0, -345), "hombros": P["Sr"], "brazos": _lerp(P["Sr"], P["Er"], 0.55),
            "triceps": _lerp(P["Sr"], P["Er"], 0.55), "piernas": P["Kr"], "cabeza": P["head"]}


# ------------------------------------------------------------------ dibujo
class _Pen:
    def __init__(self, cx, gy, s):
        self.cx, self.gy, self.s = cx, gy, s
        self.im = Image.new("RGBA", (CW * SS, CH * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
        self.chica = False

    def P(self, pt): return ((self.cx + pt[0] * self.s) * SS, (self.gy + pt[1] * self.s) * SS)
    def W(self, w): return max(1, int(w * self.s * SS))

    def seg(self, a, b, w, col):
        A, B, r = self.P(a), self.P(b), self.W(w) / 2
        self.d.line([A, B], fill=col, width=self.W(w))
        for X in (A, B): self.d.ellipse([X[0] - r, X[1] - r, X[0] + r, X[1] + r], fill=col)

    def dot(self, c, r, col):
        X, R = self.P(c), r * self.s * SS
        self.d.ellipse([X[0] - R, X[1] - R, X[0] + R, X[1] + R], fill=col)

    def ell(self, c, rx, ry, col, outline=None, w=0):
        X = self.P(c); a, b = rx * self.s * SS, ry * self.s * SS
        self.d.ellipse([X[0] - a, X[1] - b, X[0] + a, X[1] + b], fill=col, outline=outline,
                       width=self.W(w) if outline else 0)


def _limb(pen, pts, w, col, out=11):
    for a, b in zip(pts, pts[1:]): pen.seg(a, b, w + out, LINE)
    for a, b in zip(pts, pts[1:]): pen.seg(a, b, w, col)


def _shoe(pen, foot, toward=1):
    pen.seg(foot, (foot[0] + 26 * toward, foot[1] + 2), 44, LINE)
    pen.seg(foot, (foot[0] + 26 * toward, foot[1] + 2), 33, SHOE)


def _face(pen, head, cara, t, dx=(0, 0)):
    c = (head[0] + dx[0], head[1] + dx[1])
    ex = 25
    L, R = (c[0] - ex, c[1] - 6), (c[0] + ex, c[1] - 6)
    if cara == "esfuerzo":
        for e, sg in ((L, 1), (R, -1)):
            pen.seg((e[0] - 10 * sg, e[1] - 8), (e[0] + 6 * sg, e[1]), 7, EYE)
            pen.seg((e[0] + 6 * sg, e[1]), (e[0] - 10 * sg, e[1] + 8), 7, EYE)
        pen.ell((c[0], c[1] + 30), 22, 11, (255, 255, 255), outline=EYE, w=5)
        pen.seg((c[0] - 18, c[1] + 30), (c[0] + 18, c[1] + 30), 3, EYE)
    elif cara == "dolor":
        for e in (L, R):
            pen.seg((e[0] - 11, e[1] + 2), (e[0], e[1] - 4), 7, EYE); pen.seg((e[0], e[1] - 4), (e[0] + 11, e[1] + 2), 7, EYE)
        pts = [(c[0] - 22 + i * 8.8, c[1] + 30 + (5 if i % 2 else -3)) for i in range(6)]
        for a, b in zip(pts, pts[1:]): pen.seg(a, b, 6, EYE)
    elif cara == "sorprendido":
        for e in (L, R):
            pen.dot(e, 13, EYE); pen.dot((e[0] + 4, e[1] - 5), 4.5, (255, 255, 255))
        pen.ell((c[0], c[1] + 32), 10, 13, EYE)
    else:
        look = (0, -6) if cara == "pensando" else (0, 0)
        blink = (t % 3.4) < 0.12
        for e in (L, R):
            if blink:
                pen.seg((e[0] - 9, e[1]), (e[0] + 9, e[1]), 6, EYE)
            else:
                pen.ell((e[0] + look[0], e[1] + look[1]), 9, 13, EYE)
                pen.dot((e[0] + 3 + look[0], e[1] - 5 + look[1]), 3.6, (255, 255, 255))
        if cara == "pensando":
            pen.seg((c[0] - 6, c[1] + 30), (c[0] + 16, c[1] + 26), 6, EYE)
        else:
            X = pen.P((c[0], c[1] + 18)); r = 20 * pen.s * SS
            pen.d.arc([X[0] - r, X[1] - r, X[0] + r, X[1] + r], 20, 160, fill=EYE, width=pen.W(6))
    for e in (L, R):
        pen.ell((e[0] + (-8 if e is L else 8), e[1] + 26), 11, 6, BLUSH + (150,))


def _head(pen, head, cara, t, dx, side=False):
    if pen.chica:
        _hair(pen, head, t, side)
    pen.dot(head, 84 + 6, LINE)
    pen.dot(head, 84, BODY)
    if pen.chica:
        _hair_cap(pen, head)
    # cinta deportiva
    a = (head[0] - 82, head[1] - 34); b = (head[0] + 82, head[1] - 34)
    X0, X1 = pen.P((head[0] - 84, head[1] - 84)), pen.P((head[0] + 84, head[1] + 84))
    band = Image.new("L", pen.im.size, 0); bd = ImageDraw.Draw(band)
    bd.ellipse([X0[0], X0[1], X1[0], X1[1]], fill=255)
    stripe = Image.new("L", pen.im.size, 0); sd = ImageDraw.Draw(stripe)
    Y = max(0, pen.P((0, head[1] - 46))[1]); Y2 = max(Y, pen.P((0, head[1] - 22))[1])
    sd.rectangle([0, Y, pen.im.size[0], Y2], fill=255)
    from PIL import ImageChops
    m = ImageChops.multiply(band, stripe)
    pen.im.paste(BAND + (255,), mask=m)
    if side:
        tail = pen.P((head[0] - 84, head[1] - 34))
        pen.seg((head[0] - 80, head[1] - 34), (head[0] - 118, head[1] - 18 + math.sin(t * 8) * 6), 14, BAND)
    _face(pen, head, cara, t, dx)


def _draw_front(pen, P, kind, cara, t):
    # piernas
    for H_, K_, F_ in (("Hl", "Kl", "Fl"), ("Hr", "Kr", "Fr")):
        _limb(pen, [P[H_], P[K_], P[F_]], 46, BODY)
    _shoe(pen, P["Fl"], -1); _shoe(pen, P["Fr"], 1)
    # short
    pen.seg((-36, -300), (36, -300), 96 + 11, LINE); pen.seg((-36, -300), (36, -300), 96, SHORTS)
    # torso (cápsula = camiseta)
    top = (P["neck"][0], P["neck"][1] + 46)
    pen.seg(top, (0, -330), 150 + 11, LINE); pen.seg(top, (0, -330), 150, SHIRT)
    pen.seg((-44, top[1] + 8), (44, top[1] + 8), 10, SHIRT_D)            # cuello de la camiseta
    # brazos
    for S_, E_, A_ in (("Sl", "El", "Al"), ("Sr", "Er", "Ar")):
        _limb(pen, [P[S_], P[E_], P[A_]], 40, BODY)
        pen.dot(P[S_], 30, SHIRT)                       # manga
        pen.dot(P[A_], 23 + 5, LINE); pen.dot(P[A_], 23, BODY)
    if kind == "musculo":
        pump = P.get("pump", 0.5)
        for S_, E_ in (("Sl", "El"), ("Sr", "Er")):
            m = _lerp(P[S_], P[E_], 0.55)
            pen.ell((m[0], m[1] - 18), 34 + 8 * pump + 5, 28 + 8 * pump + 5, LINE)
            pen.ell((m[0], m[1] - 18), 34 + 8 * pump, 28 + 8 * pump, BODY)
    _head(pen, P["head"], cara, t, P["cara_dx"])


def _draw_side(pen, P, kind, cara, t):
    if kind == "flexion":
        # brazo del fondo
        off = (16, -6)
        S2, E2, H2 = _add(P["S"], off), _add(P["E"], off), _add(P["hand"], off)
        _limb(pen, [S2, E2, H2], 38, FAR)
        # piernas (rectas en plancha)
        _limb(pen, [P["thigh"], P["knee"], P["toes"]], 54, BODY)
        _shoe(pen, P["toes"], -1)
        pen.seg(P["hip"], P["thigh"], 92 + 11, LINE); pen.seg(P["hip"], P["thigh"], 92, SHORTS)
        pen.seg(P["S"], P["hip"], 104 + 11, LINE); pen.seg(P["S"], P["hip"], 104, SHIRT)
        _head(pen, P["head"], cara, t, P["cara_dx"], side=True)
        _limb(pen, [P["S"], P["E"], P["hand"]], 40, BODY)
        pen.dot(P["S"], 30, SHIRT)
        pen.ell((P["hand"][0] + 8, P["hand"][1] - 6), 26, 14, LINE); pen.ell((P["hand"][0] + 8, P["hand"][1] - 6), 21, 10, BODY)
    elif kind == "caminar":
        _limb(pen, [P["S"], P["E2"], P["hand2"]], 38, FAR)
        _limb(pen, [P["hip"], P["knee2"], P["foot2"]], 46, FAR)
        _shoe(pen, P["foot2"], 1)
        _limb(pen, [P["hip"], P["knee"], P["foot"]], 50, BODY)
        _shoe(pen, P["foot"], 1)
        pen.seg(P["hip"], (P["hip"][0], P["hip"][1] + 20), 96 + 11, LINE); pen.seg(P["hip"], (P["hip"][0], P["hip"][1] + 20), 96, SHORTS)
        pen.seg(P["S"], P["hip"], 108 + 11, LINE); pen.seg(P["S"], P["hip"], 108, SHIRT)
        _head(pen, P["head"], cara, t, P["cara_dx"], side=True)
        _limb(pen, [P["S"], P["E"], P["hand"]], 40, BODY)
        pen.dot(P["S"], 30, SHIRT)
        pen.dot(P["hand"], 22 + 5, LINE); pen.dot(P["hand"], 22, BODY)
    elif kind == "plancha":
        off = (16, -6)
        _limb(pen, [_add(P["S"], off), _add(P["E"], off), _add(P["hand"], off)], 38, FAR)
        _limb(pen, [P["thigh"], P["knee"], P["toes"]], 54, BODY)
        _shoe(pen, P["toes"], -1)
        pen.seg(P["hip"], P["thigh"], 92 + 11, LINE); pen.seg(P["hip"], P["thigh"], 92, SHORTS)
        pen.seg(P["S"], P["hip"], 104 + 11, LINE); pen.seg(P["S"], P["hip"], 104, SHIRT)
        _head(pen, P["head"], cara, t, P["cara_dx"], side=True)
        _limb(pen, [P["S"], P["E"], P["hand"]], 40, BODY)
        pen.dot(P["S"], 30, SHIRT)
        pen.dot(P["hand"], 22 + 5, LINE); pen.dot(P["hand"], 22, BODY)
    elif kind == "sentadilla":
        off = (-16, -4)
        _limb(pen, [_add(P["hip"], off), _add(P["knee"], off), _add(P["foot"], off)], 46, FAR)
        _shoe(pen, _add(P["foot"], off), 1)
        _limb(pen, [_add(P["S"], (14, -4)), _add(P["E"], (14, -4)), _add(P["hand"], (14, -4))], 38, FAR)
        _limb(pen, [P["hip"], P["knee"], P["foot"]], 50, BODY)
        _shoe(pen, P["foot"], 1)
        g = _add(P["hip"], (-24, 4))
        pen.ell(g, 66 + 6, 58 + 6, LINE); pen.ell(g, 66, 58, SHORTS)
        pen.seg(P["hip"], _lerp(P["hip"], P["knee"], 0.3), 96 + 11, LINE)
        pen.seg(P["hip"], _lerp(P["hip"], P["knee"], 0.3), 96, SHORTS)
        pen.ell(g, 62, 54, SHORTS)
        pen.seg(P["S"], P["hip"], 108 + 11, LINE); pen.seg(P["S"], P["hip"], 108, SHIRT)
        _head(pen, P["head"], cara, t, P["cara_dx"], side=True)
        _limb(pen, [P["S"], P["E"], P["hand"]], 40, BODY)
        pen.dot(P["S"], 30, SHIRT)
        pen.dot(P["hand"], 22 + 5, LINE); pen.dot(P["hand"], 22, BODY)
    elif kind == "puente":
        off = (14, -6)
        _limb(pen, [_add(P["hip"], off), _add(P["knee"], off), _add(P["foot"], off)], 46, FAR)
        _limb(pen, [P["hip"], P["knee"], P["foot"]], 50, BODY)
        _shoe(pen, P["foot"], 1)
        pen.seg(P["hip"], _lerp(P["hip"], P["knee"], 0.28), 98 + 11, LINE)
        pen.seg(P["hip"], _lerp(P["hip"], P["knee"], 0.28), 98, SHORTS)
        g = _add(P["hip"], (-4, 14))
        pen.ell(g, 60 + 6, 52 + 6, LINE); pen.ell(g, 60, 52, SHORTS)
        pen.seg(P["S"], P["hip"], 108 + 11, LINE); pen.seg(P["S"], P["hip"], 108, SHIRT)
        _head(pen, P["head"], cara, t, P["cara_dx"], side=True)
        _limb(pen, [P["S"], P["E"], P["hand"]], 40, BODY)
        pen.dot(P["S"], 30, SHIRT)
        pen.dot(P["hand"], 22 + 5, LINE); pen.dot(P["hand"], 22, BODY)
    else:
        _limb(pen, [P["hip"], P["knee"], P["foot"]], 46, BODY)
        _shoe(pen, P["foot"], 1)
        pen.seg(P["hip"], _lerp(P["hip"], P["knee"], 0.25), 100 + 11, LINE)
        pen.seg(P["hip"], _lerp(P["hip"], P["knee"], 0.25), 100, SHORTS)
        pen.seg(P["S"], P["hip"], 128 + 11, LINE); pen.seg(P["S"], P["hip"], 128, SHIRT)
        _head(pen, P["head"], cara, t, P["cara_dx"], side=True)
        _limb(pen, [P["S"], P["E"], P["hand"]], 40, BODY)
        pen.dot(P["S"], 30, SHIRT)
        pen.dot(P["hand"], 22 + 5, LINE); pen.dot(P["hand"], 22, BODY)


def _set_personaje(nombre):
    global SHIRT, SHIRT_D, SHORTS
    SHIRT, SHIRT_D, SHORTS = SKINS.get(nombre, SKINS["monito"])


def _hair(pen, head, t, side=False, front_behind=True):
    """Coleta de la monita (se dibuja detrás de la cabeza)."""
    sw = math.sin(t * 3.2) * 10
    if side:
        base = (head[0] - 70, head[1] - 40)
        tip = (head[0] - 150, head[1] + 20 + sw)
        _limb(pen, [base, _lerp(base, tip, 0.5), tip], 46, HAIR, out=10)
        pen.dot(tip, 28 + 5, LINE); pen.dot(tip, 28, HAIR)
    else:
        base = (head[0] + 60, head[1] - 60)
        tip = (head[0] + 118 + sw * 0.4, head[1] + 30)
        _limb(pen, [base, _lerp(base, tip, 0.5), tip], 48, HAIR, out=10)
        pen.dot(tip, 30 + 5, LINE); pen.dot(tip, 30, HAIR)


def _hair_cap(pen, head):
    from PIL import ImageChops
    X0, X1 = pen.P((head[0] - 84, head[1] - 84)), pen.P((head[0] + 84, head[1] + 84))
    circ = Image.new("L", pen.im.size, 0); ImageDraw.Draw(circ).ellipse([X0[0], X0[1], X1[0], X1[1]], fill=255)
    cap = Image.new("L", pen.im.size, 0)
    Y = max(0, pen.P((0, head[1] - 44))[1])
    ImageDraw.Draw(cap).rectangle([0, 0, pen.im.size[0], Y], fill=255)
    pen.im.paste(HAIR + (255,), mask=ImageChops.multiply(circ, cap))


def _mat(pen, P):
    xs = [-360, 360] if P["vista"] == "lado" else [-210, 210]
    a, b = pen.P((xs[0], -6)), pen.P((xs[1], 12))
    pen.d.rounded_rectangle([a[0], a[1], b[0], b[1]], radius=pen.W(9), fill=(46, 78, 150))
    a2, b2 = pen.P((xs[0] + 6, -6)), pen.P((xs[1] - 6, 0))
    pen.d.rounded_rectangle([a2[0], a2[1], b2[0], b2[1]], radius=pen.W(4), fill=(78, 116, 196))


def _auto_face(kind, P):
    if kind in LADO:
        return "esfuerzo" if P.get("baja", 0) > (0.7 if kind == "puente" else 0.55) else "feliz"
    return {"cansado": "dolor", "pensando": "pensando", "musculo": "feliz"}.get(kind, "feliz")


# ------------------------------------------------------------------ plantilla
def v_monito(img, d, t, sc, p, M):
    kind = p.get("pose", "parado")
    lado = kind in LADO
    _set_personaje(p.get("personaje", "monito"))
    s = float(p.get("escala", {"sentadilla": 1.0, "puente": 1.15, "caminar": 1.0}.get(kind, 1.25 if lado else 1.0)))
    top = int(p.get("y_lienzo", 440))                     # dónde empieza el lienzo en la pantalla
    gy = int(p.get("suelo", 1290 if lado and kind != "caminar" else 1350)) - top                 # suelo dentro del lienzo
    cx = CW // 2 + int(p.get("dx", 0)) - int({"flexion": 70, "abdominal": 60, "sentadilla": -20, "puente": 0,
                                               "caminar": 0, "plancha": 70}.get(kind, 0) * s)
    t_anim = t + float(p.get("desfase", 0))
    st_anim = M.at(sc, p.get("anim_sync"), 0.0)
    ta = max(0.0, t_anim - st_anim) if kind in LADO else t_anim
    P = pose(kind, ta, p)
    cara = p.get("cara") or _auto_face(kind, P)

    # suelo + sombra
    sh_w = 330 * s if P["vista"] == "lado" else 170 * s
    d.ellipse([cx - sh_w, top + gy - 16, cx + sh_w, top + gy + 16], fill=(16, 22, 42))
    d.line([90, top + gy + 2, M.W - 90, top + gy + 2], fill=(34, 44, 74), width=4)

    if kind == "caminar":
        off = (t * 260 * s) % 120
        for i in range(-1, 11):
            x = 90 + i * 120 - off
            if 90 <= x <= M.W - 150:
                d.line([x, top + gy + 2, x + 60, top + gy + 2], fill=(70, 90, 140), width=6)
    pen = _Pen(cx, gy, s)
    pen.chica = p.get("personaje") == "monita"
    if p.get("colchoneta"):
        _mat(pen, P)
    (_draw_side if P["vista"] == "lado" else _draw_front)(pen, P, kind, cara, t)
    fig = pen.im.reduce(SS)

    # brillos (partes que trabajan / duelen)
    br = p.get("brillo") or []
    if br:
        kb = M.ease_out(M.prog(t, M.at(sc, p.get("brillo_sync"), 0.2), 0.5))
        if kb > 0:
            A = anchors(P)
            g = Image.new("L", (CW, CH), 0); gd = ImageDraw.Draw(g)
            for part in br:
                pts = [A[part]] if part != "hombros" or P["vista"] == "lado" else [P["Sl"], P["Sr"]]
                if part == "brazos" and P["vista"] == "frente":
                    pts = [_lerp(P["Sl"], P["El"], 0.55), _lerp(P["Sr"], P["Er"], 0.55)]
                for q in pts:
                    X = (cx + q[0] * s, gy + q[1] * s); r = 46 * s
                    gd.ellipse([X[0] - r, X[1] - r, X[0] + r, X[1] + r], fill=255)
            g = g.filter(ImageFilter.GaussianBlur(16))
            pulse = 0.55 + 0.25 * math.sin(t * 6)
            g = g.point(lambda v: int(v * pulse * kb))
            alpha = fig.getchannel("A")
            from PIL import ImageChops
            g = ImageChops.multiply(g, alpha)
            fig.paste(GLOW + (255,), mask=g)
    img.paste(fig, (0, top), fig)

    # sudor
    if p.get("sudor"):
        hx, hy = cx + P["head"][0] * s, top + gy + P["head"][1] * s
        for i, (ox, oy) in enumerate(((95, -40), (-100, -10), (80, 30))):
            ph = (t * 0.9 + i * 0.37) % 1.0
            x, y = hx + ox * s, hy + oy * s + ph * 70
            a = 1 - ph
            if a > 0.05:
                r = 11 * s
                col = M.mix((30, 50, 90), (150, 210, 255), a)
                d.polygon([(x, y - r * 2.1), (x - r, y), (x + r, y)], fill=col)
                d.ellipse([x - r, y - r, x + r, y + r], fill=col)

    # accesorio (emoji junto a la cabeza)
    acc = p.get("accesorio")
    if acc:
        k = M.back(M.prog(t, M.at(sc, acc.get("sync"), 0.3), 0.5))
        em = M.emoji_img(acc["emoji"], int(acc.get("size", 150))) if k > 0 else None
        if em is not None:
            e2 = em.resize((max(1, int(em.width * k)), max(1, int(em.height * k))))
            hx = cx + (P["head"][0] + acc.get("dx", 160)) * s
            hy = top + gy + (P["head"][1] + acc.get("dy", -110)) * s + math.sin(t * 2.6) * 10
            img.paste(e2, (int(hx - e2.width / 2), int(hy - e2.height / 2)), e2)

    # etiquetas con flecha a la parte del cuerpo
    A = anchors(P)
    A0 = anchors(pose(kind, 0.0, p))                      # la etiqueta queda quieta; la flecha sigue al cuerpo
    for e in p.get("etiquetas", []):
        st = M.at(sc, e.get("sync"), 0.3)
        k = M.back(M.prog(t, st - 0.1, 0.45))
        if k <= 0: continue
        q = A[e["parte"]]
        X = (cx + q[0] * s, top + gy + q[1] * s)
        izq = e.get("lado", "izq") == "izq"
        lx = 205 if izq else M.W - 205
        ly = top + gy + A0[e["parte"]][1] * s + e.get("dy", -150)
        f = M.font(int(46 * min(1, k)) or 1, "black")
        tw = d.textlength(e["texto"], font=f)
        tw_full = d.textlength(e["texto"], font=M.font(46, "black"))
        lx = max(lx, tw_full / 2 + 40) if izq else min(lx, M.W - tw_full / 2 - 40)
        ex = lx + (tw / 2 + 26) * (1 if izq else -1)
        kl = M.ease_out(M.prog(t, st + 0.1, 0.35))
        d.line([ex, ly, ex + (X[0] - ex) * kl, ly + (X[1] - ly) * kl], fill=M.WARM, width=6)
        if kl > 0.95: d.ellipse([X[0] - 11, X[1] - 11, X[0] + 11, X[1] + 11], fill=M.WARM)
        d.rounded_rectangle([lx - tw / 2 - 26, ly - 38 * k, lx + tw / 2 + 26, ly + 38 * k], int(30 * k), fill=M.WARM)
        M.text(d, (lx, ly), e["texto"], 46 * k, M.BG)

    # contador de repeticiones
    cnt = p.get("contador")
    if cnt and "reps" in P:
        n = min(int(cnt.get("hasta", 20)), int(P["reps"] + float(cnt.get("inicio", 0))))
        x, y = cnt.get("x", M.W // 2), cnt.get("y", 820)
        k = M.back(M.prog(t, 0.0, 0.45))
        bump = 1 + 0.12 * max(0.0, 1 - ((P["reps"] % 1.0) / 0.18)) if P["reps"] >= 1 else 1
        M.text(d, (x, y), str(n), 210 * k * bump, M.BLUE)
        M.text(d, (x, y + 125), f"de {cnt.get('hasta', 20)}" if M.LANG.get("code") == "es" else f"of {cnt.get('hasta', 20)}",
               50 * k, M.GREY, "bold")

    # cronómetro (anillo que se llena)
    cr = p.get("cronometro")
    if cr:
        st = M.at(sc, cr.get("sync"), 0.0)
        k = M.back(M.prog(t, st, 0.45))
        if k > 0:
            x, y, r = cr.get("x", 800), cr.get("y", 780), 120 * k
            dur = float(cr.get("dur", 3.0))
            frac = M.clamp((t - st) / dur)
            secs = int(round(float(cr.get("desde", 0)) + (float(cr.get("hasta", 30)) - float(cr.get("desde", 0))) * frac))
            d.ellipse([x - r, y - r, x + r, y + r], outline=(40, 52, 88), width=int(18 * k))
            if frac > 0:
                d.arc([x - r, y - r, x + r, y + r], -90, -90 + 360 * frac, fill=M.col(cr.get("color"), M.BLUE), width=int(18 * k))
            etiqueta = cr.get("texto") or (f"{secs // 3600}h {secs % 3600 // 60:02d}m" if secs >= 3600 else f"{secs // 60}:{secs % 60:02d}")
            M.text(d, (x, y - 6), etiqueta, (64 if len(etiqueta) > 5 else 76) * k, M.WHITE)
            if cr.get("sub"):
                M.text(d, (x, y + r + 40), cr["sub"], 40 * k, M.GREY, "bold")

    # sello tipo "MITO" / "VERDAD"
    se = p.get("sello")
    if se:
        k = M.back(M.prog(t, M.at(sc, se.get("sync"), 0.4), 0.45), 2.6)
        if k > 0:
            colr = M.col(se.get("color"), M.WARM)
            f = M.font(150, "black")
            tw = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(se["texto"], font=f))
            st_im = Image.new("RGBA", (tw + 120, 250), (0, 0, 0, 0)); sd = ImageDraw.Draw(st_im)
            sd.rounded_rectangle([8, 8, tw + 112, 242], 34, outline=colr, width=16)
            sd.text(((tw + 120) / 2, 128), se["texto"], font=f, fill=colr, anchor="mm")
            st_im = st_im.rotate(se.get("angulo", -12), expand=True, resample=Image.BICUBIC)
            sz = max(1.0, 1.6 - 0.6 * k) * min(1.0, k * 1.2)
            st_im = st_im.resize((max(1, int(st_im.width * sz)), max(1, int(st_im.height * sz))), Image.BICUBIC)
            img.paste(st_im, (int(se.get("x", M.W // 2) - st_im.width / 2), int(se.get("y", 860) - st_im.height / 2)), st_im)

    # textos de arriba
    if p.get("pastilla"):
        k = M.back(M.prog(t, M.at(sc, p.get("pastilla_sync"), 0.0), 0.45))
        if k > 0:
            f = M.font(52, "black"); tw = d.textlength(p["pastilla"], font=f)
            d.rounded_rectangle([M.W / 2 - (tw / 2 + 34) * k, 360 - 44 * k, M.W / 2 + (tw / 2 + 34) * k, 360 + 44 * k],
                                int(44 * k), fill=M.WARM)
            M.text(d, (M.W // 2, 362), p["pastilla"], 52 * k, M.BG)
    ty = 360 + (130 if p.get("pastilla") else 90)
    if p.get("titulo"):
        M.pop(d, (M.W // 2, ty), p["titulo"], p.get("titulo_size", 112), M.col(p.get("titulo_color"), M.WHITE), t,
              M.at(sc, p.get("titulo_sync"), 0.05), maxw=980)
    if p.get("sub"):
        M.slide(d, (M.W // 2, ty + 105), p["sub"], 56, M.ICE, t, M.at(sc, p.get("sub_sync"), 0.4), weight="xbold")
    if p.get("boton"):
        k = M.back(M.prog(t, M.at(sc, p.get("boton_sync"), 1.0) - 0.1, 0.5))
        if k > 0:
            w2, h2, yb = 300 * k, 62 * k, ty + 120
            d.rounded_rectangle([M.W / 2 - w2, yb - h2, M.W / 2 + w2, yb + h2], int(h2), fill=M.BLUE)
            M.text(d, (M.W / 2, yb), p["boton"], 58 * k, M.BG)
