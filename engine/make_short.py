"""
White Hole · motor de Shorts (1080x1920), 100% gratis y offline.

Uso:  python engine/make_short.py guiones/pendientes/mi_guion.json salida.mp4 [--voz voices/modelo.onnx]

Cada escena del guion tiene:
  "texto":   lo que dice la voz
  "visual":  una de las plantillas de abajo + sus parámetros
  "sync":    (en los parámetros) palabra del texto en la que aparece cada elemento

Plantillas disponibles (ver README para ejemplos):
  title, counter, bars, versus, equation, bigword, card, outro,
  mapa (mapa de Colombia con zoom y río), grafica (línea animada), emoji (emoji grande),
  monito (personaje animado: flexiones, abdominales, músculo… ver engine/monitos.py)
"""
import json, math, os, re, subprocess, sys, wave, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
W, H, FPS = 1080, 1920, 30

# --- paleta de marca White Hole (negro, blanco, azul eléctrico) ---
BG     = (8, 10, 20)
BLUE   = (88, 166, 255)
ICE    = (181, 212, 244)
WHITE  = (244, 246, 251)
GREY   = (128, 138, 160)
WARM   = (255, 138, 76)       # acento de contraste (alertas, "falta", etc.)
PANEL  = (20, 26, 46)
GREEN_ = (64, 214, 150)
COLORS = {"blue": BLUE, "ice": ICE, "white": WHITE, "grey": GREY, "warm": WARM, "green": (64, 214, 150)}

FONT_DIR = os.path.join(ROOT, "assets", "fonts")
FONTS = {"black": "Inter-Black.otf", "xbold": "Inter-ExtraBold.otf",
         "bold": "Inter-Bold.otf", "semi": "Inter-SemiBold.otf"}
_fc = {}

def font(size, weight="black"):
    size = max(8, int(round(size / 2) * 2))
    if (size, weight) not in _fc:
        _fc[(size, weight)] = ImageFont.truetype(os.path.join(FONT_DIR, FONTS[weight]), size)
    return _fc[(size, weight)]

def col(c, default=WHITE):
    if c is None: return default
    if isinstance(c, (list, tuple)): return tuple(c)
    return COLORS.get(c, default)

# ---------------------------------------------------------------- animación
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def back(x, s=1.9):
    x = clamp(x) - 1
    return x * x * ((s + 1) * x + s) + 1
def prog(t, start, dur): return clamp((t - start) / dur)
def ease_inout(x): x = clamp(x); return 3 * x * x - 2 * x * x * x
def mix(c1, c2, k): return tuple(int(a + (b - a) * k) for a, b in zip(c1, c2))

LANG = {"code": "en"}
def fmt_num(v, dec=0):
    s = f"{v:,.{dec}f}"
    if LANG["code"] == "es":
        s = s.replace(",", "\u0001").replace(".", ",").replace("\u0001", ".")
    return s

def text(d, xy, s, size, fill, weight="black", anchor="mm"):
    d.text(xy, s, font=font(size, weight), fill=fill, anchor=anchor)

def fit(d, s, size, weight, maxw):
    while size > 20 and d.textlength(s, font=font(size, weight)) > maxw:
        size -= 4
    return size

def pop(d, xy, s, size, fill, t, start, weight="black", dur=0.4, maxw=900):
    k = prog(t, start, dur)
    if k <= 0: return
    size = fit(d, s, size, weight, maxw)
    text(d, xy, s, size * (0.4 + 0.6 * back(k)), fill, weight)

def slide(d, xy, s, size, fill, t, start, dx=0, dy=60, weight="black", dur=0.45, maxw=900):
    k = prog(t, start, dur)
    if k <= 0: return
    size = fit(d, s, size, weight, maxw)
    e = ease_out(k)
    text(d, (xy[0] + dx * (1 - e), xy[1] + dy * (1 - e)), s, size, mix(BG, fill, e), weight)

# ---------------------------------------------------------------- fondo
def make_background():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.40) / H) ** 2)
    glow = np.clip(1 - r * 1.7, 0, 1)[..., None]
    base = np.array(BG, np.float32) + glow * np.array([10, 18, 40], np.float32)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(7)
    for _ in range(120):
        x, y = rng.integers(0, W), rng.integers(0, H)
        b = int(rng.uniform(30, 90))
        d.ellipse([x, y, x + 2, y + 2], fill=(b, b + 8, b + 25))
    # anillo de disco de acreción muy tenue al fondo (identidad de marca)
    ring = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(ring)
    for i, a in enumerate([26, 18, 10]):
        rd.ellipse([W / 2 - 520 - i * 40, 1640 - 90 - i * 10, W / 2 + 520 + i * 40, 1640 + 90 + i * 10],
                   outline=a, width=6)
    img.paste((60, 120, 220), mask=ring)
    return img

# ---------------------------------------------------------------- tiempos
def word_times(textstr, dur, lead=0.08):
    words = textstr.split()
    wts = []
    for w in words:
        wt = len(re.sub(r"[^\w]", "", w)) + 2.0
        if w.endswith((".", "?", "!")): wt += 5
        elif w.endswith((",", ":", ";")): wt += 3
        wts.append(wt)
    span = max(0.1, dur - lead - 0.25)
    times, acc = [], lead
    for wt in wts:
        times.append(acc); acc += span * wt / sum(wts)
    return words, times

def at(sc, needle, default=0.0):
    """Momento en que se dice la palabra `needle` (o un número de segundos)."""
    if needle is None: return default
    if isinstance(needle, (int, float)): return float(needle)
    n = needle.lower()
    for w, t in zip(sc["words"], sc["times"]):
        if n in re.sub(r"[^\w']", "", w.lower()): return t
    return default

# ---------------------------------------------------------------- plantillas
def v_title(img, d, t, sc, p):
    y0 = p.get("y", 640)
    if p.get("pre"):
        slide(d, (W // 2, y0 - 170), p["pre"], 74, GREY, t, at(sc, p.get("pre_sync"), 0), weight="xbold")
    lines = p.get("lines", [])
    colors = p.get("colors", ["white", "blue", "blue", "white"])
    st = at(sc, p.get("sync"), 0.1)
    for i, ln in enumerate(lines):
        slide(d, (W // 2, y0 + i * 180), ln, p.get("size", 170), col(colors[i % len(colors)]), t,
              st + i * 0.18, dx=(-120 if i % 2 == 0 else 120), dy=0, maxw=960)
    ku = ease_out(prog(t, st + 0.3 + 0.18 * len(lines), 0.5))
    if ku > 0 and p.get("underline", True):
        yy = y0 + len(lines) * 180 - 70
        d.rounded_rectangle([W / 2 - 300 * ku, yy, W / 2 + 300 * ku, yy + 20], 10, fill=BLUE)

def v_counter(img, d, t, sc, p):
    if p.get("pre"):
        slide(d, (W // 2, 470), p["pre"], 56, GREY, t, 0.0, weight="xbold")
    st = at(sc, p.get("sync"), 0.2)
    k = ease_out(prog(t, st, p.get("dur", 1.2)))
    if k > 0:
        a, b = float(p.get("from", 0)), float(p["to"])
        v = a + (b - a) * k
        dec = int(p.get("decimals", 0))
        s = f"{p.get('prefix', '')}{fmt_num(v, dec)}{p.get('suffix', '')}"
        size = fit(d, s, p.get("size", 220), "black", 980)
        text(d, (W // 2, 760), s, size, col(p.get("color"), BLUE))
    if p.get("label"):
        slide(d, (W // 2, 930), p["label"], 64, WHITE, t, st + 0.3, weight="xbold")
    if p.get("note"):
        pop(d, (W // 2, 1110), p["note"], 56, col(p.get("note_color"), GREY), t, at(sc, p.get("note_sync"), st + 0.8), "bold")

def v_bars(img, d, t, sc, p):
    items = p["items"]
    vmax = max(float(it["value"]) for it in items)
    x0, maxw = 120, 840
    y = p.get("y", 520)
    for i, it in enumerate(items):
        st = at(sc, it.get("sync"), 0.15 * i)
        k = ease_out(prog(t, st, 0.9))
        if prog(t, st - 0.2, 0.3) <= 0: y += 270; continue
        text(d, (x0, y), it["label"], 48, WHITE, "bold", "lm")
        wbar = maxw * float(it["value"]) / vmax * k
        d.rounded_rectangle([x0, y + 40, x0 + max(30, wbar), y + 150], 20, fill=col(it.get("color"), BLUE))
        if it.get("show_value", True) and k > 0.6:
            text(d, (x0 + max(30, wbar) - 24, y + 95), it.get("value_text", f"{it['value']}"), 52, BG, "black", "rm")
        y += 270
    if p.get("note"):
        pop(d, (W // 2, y + 20), p["note"], 80, col(p.get("note_color"), WARM), t, at(sc, p.get("note_sync"), 1.0))

def v_versus(img, d, t, sc, p):
    L, R = p["left"], p["right"]
    for x, c, dflt in [(70, L, 0.0), (W // 2 + 20, R, 0.6)]:
        k = back(prog(t, at(sc, c.get("sync"), dflt), 0.5))
        if k <= 0: continue
        cw, ch = W // 2 - 90, 440
        cy = 780 + 60 * (1 - k)
        cc = col(c.get("color"), BLUE)
        d.rounded_rectangle([x, cy - ch / 2, x + cw, cy + ch / 2], 34, fill=PANEL, outline=cc, width=6)
        text(d, (x + cw / 2, cy - 120), c["label"], fit(d, c["label"], 52, "xbold", cw - 40), GREY, "xbold")
        size = fit(d, c["value"], 120, "black", cw - 50)
        text(d, (x + cw / 2, cy + 30), c["value"], size * (0.6 + 0.4 * k), cc)
        if c.get("sub"):
            text(d, (x + cw / 2, cy + 150), c["sub"], fit(d, c["sub"], 40, "semi", cw - 40), GREY, "semi")
    if p.get("badge"):
        b = p["badge"]
        k = back(prog(t, at(sc, b.get("sync"), 1.5), 0.5))
        if k > 0:
            r = 120 * k
            d.ellipse([W / 2 - r, 1150 - r, W / 2 + r, 1150 + r], fill=WHITE)
            text(d, (W / 2, 1120), b.get("top", ""), 36 * k, BG, "bold")
            text(d, (W / 2, 1172), b.get("bottom", ""), 64 * k, BG)

def v_equation(img, d, t, sc, p):
    y = 470
    for i, ln in enumerate(p.get("lines", [])):
        slide(d, (W // 2, y), ln["text"], ln.get("size", 96), col(ln.get("color"), WHITE), t,
              at(sc, ln.get("sync"), 0.4 * i), dy=40, weight="xbold", maxw=980)
        if ln.get("sub") and t > at(sc, ln.get("sync"), 0.4 * i) + 0.3:
            text(d, (W // 2, y + 78), ln["sub"], 40, GREY, "semi")
        y += 200
    r = p.get("result")
    if r:
        st = at(sc, r.get("sync"), 1.5)
        kl = ease_out(prog(t, st - 0.4, 0.5))
        if kl > 0:
            d.rounded_rectangle([W / 2 - 420 * kl, y - 70, W / 2 + 420 * kl, y - 58], 6, fill=WHITE)
        kc = ease_out(prog(t, st, 1.1))
        if kc > 0:
            v = float(r.get("from", 0)) + (float(r["value"]) - float(r.get("from", 0))) * kc
            s = f"{r.get('prefix', '')}{fmt_num(v, int(r.get('decimals', 0)))}{r.get('suffix', '')}"
            text(d, (W // 2, y + 90), s, fit(d, s, 200, "black", 980), col(r.get("color"), BLUE))
            if r.get("label"):
                text(d, (W // 2, y + 230), r["label"], 60, WHITE, "xbold")

def v_bigword(img, d, t, sc, p):
    st = at(sc, p.get("sync"), 0.2)
    if p.get("pre"):
        slide(d, (W // 2, 470), p["pre"], 50, GREY, t, 0.0, weight="semi")
    pop(d, (W // 2, 720), p["word"], p.get("size", 280), col(p.get("color"), BLUE), t, st - 0.15, maxw=980)
    if p.get("sub"):
        slide(d, (W // 2, 950), p["sub"], 86, WHITE, t, st + 0.25, weight="xbold")
    if p.get("sub2"):
        slide(d, (W // 2, 1070), p["sub2"], 50, GREY, t, st + 0.5, weight="semi")

def v_card(img, d, t, sc, p):
    k = back(prog(t, 0.0, 0.5))
    cx, cy = W // 2, 640
    w, h = 580 * (0.5 + 0.5 * k), 340 * (0.5 + 0.5 * k)
    if k > 0:
        d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 38, fill=WHITE)
        d.rounded_rectangle([cx - w / 2 + 34, cy + h / 2 - 54, cx - w / 2 + 120, cy + h / 2 - 32], 9, fill=BLUE)
        text(d, (cx, cy - 10), p["title"], fit(d, p["title"], 150, "black", 520) * k, BG)
        if p.get("tag"):
            text(d, (cx + w / 2 - 40, cy + h / 2 - 43), p["tag"], 34 * k, GREY, "bold", "rm")
    pnl = p.get("panel")
    if pnl:
        st = at(sc, pnl.get("sync"), 1.0)
        k2 = ease_out(prog(t, st - 0.1, 0.5))
        if k2 > 0:
            py = 1080 + 80 * (1 - k2)
            d.rounded_rectangle([130, py - 130, W - 130, py + 160], 30, fill=PANEL)
            text(d, (180, py - 80), pnl.get("label", ""), 40, GREY, "semi", "lm")
            d.rounded_rectangle([180, py - 25, W - 180, py + 15], 12, fill=(40, 50, 80))
            fw = (W - 360) * float(pnl.get("progress", 1.0)) * ease_out(prog(t, st + 0.2, 0.9))
            d.rounded_rectangle([180, py - 25, 180 + max(24, fw), py + 15], 12, fill=col(pnl.get("color"), WARM))
            pop(d, (W // 2, py + 95), pnl["value"], 92, col(pnl.get("color"), WARM), t, at(sc, pnl.get("value_sync"), st + 0.4))

def v_outro(img, d, t, sc, p):
    lines = p.get("lines", ["SAME BYTES.", "DIFFERENT", "RULER."])
    colors = p.get("colors", ["white", "blue", "blue"])
    syncs = p.get("syncs", [None] * len(lines))
    for i, ln in enumerate(lines):
        slide(d, (W // 2, 600 + i * 165), ln, 130, col(colors[i % len(colors)]), t,
              at(sc, syncs[i] if i < len(syncs) else None, 0.35 * i), dx=(-100 if i % 2 == 0 else 100), dy=0, maxw=980)
    k = back(prog(t, at(sc, p.get("button_sync", "follow"), 1.2) - 0.1, 0.5))
    if k > 0:
        w2, h2 = 300 * k, 62 * k
        yb = 600 + len(lines) * 165 + 40
        d.rounded_rectangle([W / 2 - w2, yb - h2, W / 2 + w2, yb + h2], int(h2), fill=BLUE)
        text(d, (W / 2, yb), p.get("button", "FOLLOW  +"), 58 * k, BG)


# ---------------------------------------------------------------- plantillas "documental"
_GEO = None
def geo():
    global _GEO
    if _GEO is None:
        _GEO = json.load(open(os.path.join(ROOT, "assets", "geo", "sudamerica.json"), encoding="utf-8"))
    return _GEO

def _lerp(a, b, k): return a + (b - a) * k

def _path_point(pts, f):
    """Punto a una fracción f (0-1) del largo de una polilínea en píxeles."""
    segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(segs) or 1
    goal, acc = clamp(f) * total, 0.0
    for i, L in enumerate(segs):
        if acc + L >= goal:
            k = (goal - acc) / (L or 1)
            return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * k, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * k), i
        acc += L
    return pts[-1], len(pts) - 2

_FADE = None
def _map_fade():
    global _FADE
    if _FADE is None:
        g = np.ones((H, 1), np.float32)
        yy = np.arange(H, dtype=np.float32)[:, None]
        g = np.clip((1340 - yy) / 220, 0, 1) * np.clip((yy - 150) / 120, 0, 1)
        _FADE = Image.fromarray((np.repeat(g, W, axis=1) * 255).astype(np.uint8))
    return _FADE

def v_mapa(img, d, t, sc, p):
    """Mapa de Colombia con zoom de cámara, río Magdalena, marcadores y puntos que se expanden."""
    g = geo()
    c0 = p.get("desde", [-73.6, 4.3, 1.0]); c1 = p.get("hasta", c0)
    kc = ease_inout(prog(t, at(sc, p.get("zoom_sync"), 0.0), p.get("zoom_dur", 2.6)))
    lon_c, lat_c, z = _lerp(c0[0], c1[0], kc), _lerp(c0[1], c1[1], kc), _lerp(c0[2], c1[2], kc)
    cy = p.get("y", 780); s = 50 * z; cosl = math.cos(math.radians(lat_c))
    P = lambda lon, lat: (W / 2 + (lon - lon_c) * s * cosl, cy - (lat - lat_c) * s)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
    fade = ease_out(prog(t, 0.0, 0.6))
    for name, polys in g.items():
        if name.startswith("_"): continue
        main = name == p.get("pais", "Colombia")
        fill = (30, 48, 92, int(255 * fade)) if main else (20, 28, 50, int(200 * fade))
        line = (*BLUE, int(255 * fade)) if main else (50, 64, 100, int(200 * fade))
        for poly in polys:
            pts = [P(x, y) for x, y in poly]
            ld.polygon(pts, fill=fill)
            ld.line(pts + [pts[0]], fill=line, width=5 if main else 2, joint="curve")
    rio = [P(x, y) for x, y in g["_rios"]["Magdalena"]]
    if p.get("rio", True):
        kr = ease_inout(prog(t, at(sc, p.get("rio_sync"), 0.3), p.get("rio_dur", 1.8)))
        if kr > 0:
            end, idx = _path_point(rio, kr)
            ld.line(rio[:idx + 1] + [end], fill=(110, 190, 255, 255), width=max(5, int(4 * z ** 0.5)), joint="curve")
            if p.get("rio_label") and kr > 0.6:
                lp, _ = _path_point(rio, p.get("rio_label_pos", 0.82))
                ld.text((lp[0] + 26, lp[1]), p["rio_label"], font=font(34, "xbold"), fill=(150, 205, 255, 255), anchor="lm")
    sp = p.get("expansion")
    if sp:
        st = at(sc, sp.get("sync"), 1.0)
        n = int(sp.get("n", 16)); f0, f1 = sp.get("desde", 0.4), sp.get("hasta", 0.6)
        rng = np.random.default_rng(3)
        for i in range(n):
            k = back(prog(t, st + i * sp.get("paso", 0.12), 0.35))
            if k <= 0: continue
            q, _ = _path_point(rio, f0 + (f1 - f0) * (i / max(1, n - 1)))
            jx, jy = rng.normal(0, 10 * z ** 0.5, 2)
            r = 9 * k * z ** 0.3
            ld.ellipse([q[0] + jx - r, q[1] + jy - r, q[0] + jx + r, q[1] + jy + r], fill=(*WARM, 235))
    for m in p.get("marcadores", []):
        st = at(sc, m.get("sync"), 0.6)
        k = back(prog(t, st, 0.45))
        if k <= 0: continue
        x, y = P(m["lon"], m["lat"]); cc = col(m.get("color"), WARM)
        pulse = (t - st) % 1.4 / 1.4
        rr = 18 + 46 * pulse
        ld.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(*cc, int(220 * (1 - pulse))), width=5)
        r0 = 16 * k
        ld.ellipse([x - r0, y - r0, x + r0, y + r0], fill=(*cc, 255), outline=(255, 255, 255, 255), width=4)
        if m.get("label"):
            f = font(40, "black"); tw = ld.textlength(m["label"], font=f)
            side = m.get("lado", "der")
            bx = x + 40 if side == "der" else x - 40 - tw - 44
            by = y - 34
            ld.rounded_rectangle([bx, by, bx + tw + 44, by + 68], 34, fill=(255, 255, 255, int(255 * k)))
            ld.text((bx + 22, by + 34), m["label"], font=f, fill=(*BG, 255), anchor="lm")
            if m.get("sub"):
                ld.text((bx + 22, by + 96), m["sub"], font=font(32, "semi"), fill=(*ICE, int(255 * k)), anchor="lm")
    a = layer.getchannel("A")
    a = Image.composite(a, Image.new("L", (W, H), 0), _map_fade())
    layer.putalpha(a)
    img.paste(layer, (0, 0), layer)
    if p.get("titulo"):
        slide(d, (W // 2, 330), p["titulo"], 64, WHITE, t, at(sc, p.get("titulo_sync"), 0.0), weight="black", dy=30)

def v_grafica(img, d, t, sc, p):
    """Gráfica de línea animada (ej. población por año). Puntos con "proyeccion": true van punteados."""
    pts = p["puntos"]
    bx0, bx1, by0, by1 = 150, W - 130, 1180, 560
    xmin, xmax = p.get("xmin", pts[0]["x"]), p.get("xmax", pts[-1]["x"])
    ymax = p.get("ymax", max(q["y"] for q in pts) * 1.18)
    ymin = p.get("ymin", 0)
    if p.get("categorico"):
        idx = {q["x"]: i for i, q in enumerate(pts)}
        X = lambda v: bx0 + 70 + idx[v] / max(1, len(pts) - 1) * (bx1 - bx0 - 140)
    else:
        X = lambda v: bx0 + (v - xmin) / (xmax - xmin) * (bx1 - bx0)
    Y = lambda v: by0 - (v - ymin) / (ymax - ymin) * (by0 - by1)
    ka = ease_out(prog(t, 0.0, 0.5))
    if p.get("titulo"):
        slide(d, (W // 2, 400), p["titulo"], 58, WHITE, t, 0.0, weight="black", dy=30)
    d.line([bx0, by0, bx0 + (bx1 - bx0) * ka, by0], fill=(60, 74, 110), width=4)
    for gy in (0.33, 0.66, 1.0):
        yy = by0 - (by0 - by1) * gy
        d.line([bx0, yy, bx0 + (bx1 - bx0) * ka, yy], fill=(28, 36, 62), width=2)
    times = [at(sc, q.get("sync"), 0.4 + i * 0.9) for i, q in enumerate(pts)]
    for i, q in enumerate(pts):
        x, y = X(q["x"]), Y(q["y"])
        if i > 0:
            k = ease_inout(prog(t, times[i] - 0.55, 0.55))
            if k > 0:
                xa, ya = X(pts[i - 1]["x"]), Y(pts[i - 1]["y"])
                xe, ye = xa + (x - xa) * k, ya + (y - ya) * k
                cc = WARM if q.get("proyeccion") else BLUE
                if q.get("proyeccion"):
                    nseg = 14
                    for j in range(nseg):
                        if j % 2: continue
                        f0, f1 = j / nseg, (j + 1) / nseg
                        if f0 > k: break
                        f1 = min(f1, k)
                        d.line([xa + (x - xa) * f0, ya + (y - ya) * f0, xa + (x - xa) * f1, ya + (y - ya) * f1], fill=cc, width=10)
                else:
                    d.line([xa, ya, xe, ye], fill=cc, width=10)
        kp = back(prog(t, times[i], 0.4))
        if kp > 0:
            cc = WARM if q.get("proyeccion") else BLUE
            r = 16 * kp
            d.ellipse([x - r, y - r, x + r, y + r], fill=cc, outline=WHITE, width=4)
            lab = q.get("label", str(q["y"]))
            text(d, (x, y - 64), lab, fit(d, lab, 70, "black", 300) * (0.5 + 0.5 * kp), cc)
            text(d, (x, by0 + 50), str(q.get("xlabel", q["x"])), 40, GREY, "bold")
            if q.get("nota"):
                text(d, (x, by0 + 100), q["nota"], 30, GREY, "semi")

_EMO = {}
def emoji_img(ch, px):
    key = (ch, px)
    if key not in _EMO:
        im = None
        for pth in ["/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
                    "/usr/share/fonts/noto/NotoColorEmoji.ttf",
                    os.path.join(ROOT, "assets", "fonts", "NotoColorEmoji.ttf")]:
            if os.path.exists(pth):
                f = ImageFont.truetype(pth, 109)
                im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
                ImageDraw.Draw(im).text((100, 100), ch, font=f, embedded_color=True, anchor="mm")
                bb = im.getbbox()
                if bb:
                    im = im.crop(bb); r = px / max(im.size)
                    im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
                break
        _EMO[key] = im
    return _EMO[key]

def v_emoji(img, d, t, sc, p):
    """Emoji grande flotando + texto opcional (ej. "4 → 200")."""
    st = at(sc, p.get("sync"), 0.0)
    y = p.get("y", 640)
    if p.get("pre"):
        slide(d, (W // 2, 330), p["pre"], 58, GREY, t, 0.0, weight="xbold", dy=30)
    k = back(prog(t, st, 0.6))
    em = emoji_img(p["emoji"], int(p.get("size", 420))) if k > 0 else None
    if em is not None:
        sc_k = 0.5 + 0.5 * k
        e2 = em.resize((max(1, int(em.width * sc_k)), max(1, int(em.height * sc_k))))
        bob = math.sin(t * 2.4) * 12
        # sombra/halo
        r = 260 * sc_k
        d.ellipse([W / 2 - r, y - r * 0.92, W / 2 + r, y + r * 0.92], fill=(16, 24, 48))
        img.paste(e2, (int(W / 2 - e2.width / 2), int(y - e2.height / 2 + bob)), e2)
    if p.get("texto"):
        pop(d, (W // 2, y + 360), p["texto"], p.get("tsize", 170), col(p.get("color"), BLUE), t,
            at(sc, p.get("texto_sync"), st + 0.5), maxw=980)
    if p.get("sub"):
        slide(d, (W // 2, y + 500), p["sub"], 54, WHITE, t, at(sc, p.get("sub_sync"), st + 0.9), weight="xbold")


# ---------------------------------------------------------------- fotos reales (Wikimedia Commons)
_IMG, CREDITOS = {}, []
_SHADE = None
def _shade():
    global _SHADE
    if _SHADE is None:
        yy = np.arange(H, dtype=np.float32)[:, None]
        a = 0.18 + 0.55 * np.clip((yy - 1050) / 600, 0, 1) + 0.45 * np.clip((380 - yy) / 380, 0, 1)
        _SHADE = Image.fromarray((np.repeat(np.clip(a, 0, 0.92), W, axis=1) * 255).astype(np.uint8))
    return _SHADE

def foto_base(src):
    if src not in _IMG:
        sys.path.insert(0, HERE)
        import imagenes
        ruta, info = imagenes.obtener(src)
        im0 = Image.open(ruta).convert("RGB")
        r = max(W * 1.3 / im0.width, H * 1.3 / im0.height)
        im = im0.resize((int(im0.width * r) + 2, int(im0.height * r) + 2), Image.LANCZOS)
        from PIL import ImageFilter, ImageEnhance
        blur = im0.resize((int(im0.width * max(W / im0.width, H / im0.height)) + 2,
                           int(im0.height * max(W / im0.width, H / im0.height)) + 2), Image.BILINEAR)
        blur = blur.crop(((blur.width - W) // 2, (blur.height - H) // 2, (blur.width - W) // 2 + W, (blur.height - H) // 2 + H))
        blur = ImageEnhance.Brightness(blur.filter(ImageFilter.GaussianBlur(40))).enhance(0.45)
        fw = int(W * 1.18); fh = int(im0.height * fw / im0.width)
        fg = im0.resize((fw, fh), Image.LANCZOS)
        _IMG[src] = (im, info, blur, fg, im0.width / im0.height)
        if info not in CREDITOS: CREDITOS.append(info)
    return _IMG[src]

def v_foto(img, d, t, sc, p):
    """Foto a pantalla completa con movimiento lento (Ken Burns), chip de texto y crédito."""
    im, info, blur, fg, aspect = foto_base(p["src"])
    k = ease_inout(clamp(t / max(1.0, sc["dur"])))
    modo = p.get("modo", "marco" if aspect > 1.05 else "cover")
    if modo == "marco":
        zr = p.get("zoom", [1.0, 1.15])
        zz = clamp(zr[0] + (zr[1] - zr[0]) * k, 1.0, 1.18)
        f0 = p.get("foco", [0.5, 0.5]); f1 = p.get("foco_fin", f0)
        fx, fy = f0[0] + (f1[0] - f0[0]) * k, f0[1] + (f1[1] - f0[1]) * k
        cw, chh = fg.width / zz, fg.height / zz
        boxh = int(W / aspect)
        cx = clamp(fx * fg.width, cw / 2, fg.width - cw / 2); cy = clamp(fy * fg.height, chh / 2, fg.height - chh / 2)
        crop = fg.crop((int(cx - cw / 2), int(cy - chh / 2), int(cx + cw / 2), int(cy + chh / 2))).resize((W, boxh), Image.BILINEAR)
        if p.get("brillo"):
            from PIL import ImageEnhance
            crop = ImageEnhance.Brightness(crop).enhance(float(p["brillo"]))
        frame = blur.copy()
        y0 = int(p.get("y", 760) - boxh / 2)
        frame.paste(crop, (0, y0))
        frame.paste((4, 6, 14), mask=_shade())
    else:
        frame = None
    z0, z1 = p.get("zoom", [1.0, 1.15])
    z = clamp(z0 + (z1 - z0) * k, 1.0, 1.3)
    f0 = p.get("foco", [0.5, 0.5]); f1 = p.get("foco_fin", f0)
    fx, fy = f0[0] + (f1[0] - f0[0]) * k, f0[1] + (f1[1] - f0[1]) * k
    if frame is None:
        cw, ch = W * 1.3 / z, H * 1.3 / z
        cx = clamp(fx * im.width, cw / 2, im.width - cw / 2); cy = clamp(fy * im.height, ch / 2, im.height - ch / 2)
        frame = im.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((W, H), Image.BILINEAR)
        if p.get("brillo"):
            from PIL import ImageEnhance
            frame = ImageEnhance.Brightness(frame).enhance(float(p["brillo"]))
        frame.paste((4, 6, 14), mask=_shade())
    kin = ease_out(prog(t, 0.0, 0.35))
    if kin < 1: frame = Image.blend(img, frame, kin)
    img.paste(frame)
    if p.get("chip"):
        kk = ease_out(prog(t, at(sc, p.get("chip_sync"), 0.3), 0.4))
        if kk > 0:
            f = font(42, "black"); tw = d.textlength(p["chip"], font=f)
            x0, y0 = 70 - 40 * (1 - kk), p.get("chip_y", 1210)
            d.rounded_rectangle([x0, y0, x0 + tw + 48, y0 + 72], 36, fill=col(p.get("chip_color"), WARM))
            d.text((x0 + 24, y0 + 36), p["chip"], font=f, fill=BG, anchor="lm")
    if p.get("titulo"):
        st = at(sc, p.get("titulo_sync"), 0.2)
        kk = ease_out(prog(t, st, 0.45))
        if kk > 0:
            size = fit(d, p["titulo"], p.get("tsize", 110), "black", 960)
            d.text((W // 2, p.get("ty", 1060) + 30 * (1 - kk)), p["titulo"], font=font(size, "black"),
                   fill=col(p.get("color"), WHITE), anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))
    sys.path.insert(0, HERE)
    import imagenes
    d.text((W // 2, 1868), imagenes.credito_corto(info), font=font(24, "semi"), fill=(170, 178, 196), anchor="mm")

# ---------------------------------------------------------------- plantillas de matemáticas
def _isprime(n):
    if n < 2: return False
    i = 2
    while i * i <= n:
        if n % i == 0: return False
        i += 1
    return True

def v_primos(img, d, t, sc, p):
    """Cuadrícula de números donde los primos se encienden uno a uno."""
    n, cols = int(p.get("n", 100)), int(p.get("cols", 10))
    rows = (n + cols - 1) // cols
    cell = min(96, 940 // cols, 860 // rows)
    x0 = (W - cell * cols) / 2; y0 = p.get("y", 800) - cell * rows / 2
    st = at(sc, p.get("sync"), 0.3); dur = p.get("dur", 3.0)
    primes = [k for k in range(1, n + 1) if _isprime(k)]
    order = {pr: i for i, pr in enumerate(primes)}
    fsize = int(cell * 0.42)
    for k in range(1, n + 1):
        r, c = (k - 1) // cols, (k - 1) % cols
        cx, cy = x0 + c * cell + cell / 2, y0 + r * cell + cell / 2
        ka = ease_out(prog(t, 0.02 * (k % 37) * 0.3, 0.4))
        if ka <= 0: continue
        if k in order:
            kp = back(prog(t, st + dur * order[k] / max(1, len(primes)), 0.35))
            if kp > 0:
                rr = cell * 0.46 * (0.6 + 0.4 * kp)
                d.rounded_rectangle([cx - rr, cy - rr, cx + rr, cy + rr], int(cell * 0.18), fill=col(p.get("color"), BLUE))
                text(d, (cx, cy), str(k), fsize, BG, "black")
                continue
        dim = 0.35 if t > st + 0.2 and k not in order else 1.0
        text(d, (cx, cy), str(k), fsize, mix(BG, GREY if k not in order else WHITE, ka * dim), "bold")
    if p.get("titulo"):
        slide(d, (W // 2, y0 - 70), p["titulo"], 58, WHITE, t, 0.0, weight="black", dy=30)

_TEX = {}
def tex_img(tex, size, color=(244, 246, 251)):
    key = (tex, size, color)
    if key not in _TEX:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig = plt.figure(figsize=(0.01, 0.01), dpi=100)
        fig.text(0, 0, f"${tex}$", fontsize=size, color=tuple(c / 255 for c in color))
        import io
        buf = io.BytesIO()
        fig.savefig(buf, dpi=100, transparent=True, bbox_inches="tight", pad_inches=0.05)
        plt.close(fig)
        buf.seek(0)
        _TEX[key] = Image.open(buf).convert("RGBA")
    return _TEX[key]

def v_formula(img, d, t, sc, p):
    """Fórmula matemática (sintaxis tipo LaTeX de matplotlib) que aparece con un pop."""
    y = p.get("y", 720)
    if p.get("pre"):
        slide(d, (W // 2, y - 260), p["pre"], 56, GREY, t, 0.0, weight="xbold", dy=30)
    st = at(sc, p.get("sync"), 0.3)
    k = back(prog(t, st, 0.5))
    if k > 0:
        im = tex_img(p["tex"], p.get("size", 64), col(p.get("color"), WHITE))
        sc_k = min(1.0, 980 / im.width) * (0.6 + 0.4 * k)
        im2 = im.resize((max(1, int(im.width * sc_k)), max(1, int(im.height * sc_k))), Image.LANCZOS)
        img.paste(im2, (int(W / 2 - im2.width / 2), int(y - im2.height / 2)), im2)
    if p.get("sub"):
        slide(d, (W // 2, y + 230), p["sub"], 60, col(p.get("sub_color"), BLUE), t, at(sc, p.get("sub_sync"), st + 0.6), weight="black")
    if p.get("sub2"):
        slide(d, (W // 2, y + 320), p["sub2"], 44, GREY, t, at(sc, p.get("sub2_sync"), st + 0.9), weight="semi")

_ZETA = {}
def _zeta_curve(t0, t1, step=0.02):
    key = (t0, t1, step)
    if key not in _ZETA:
        import mpmath
        ts = np.arange(t0, t1 + 1e-9, step)
        zs = np.array([complex(mpmath.zeta(mpmath.mpc(0.5, float(x)))) for x in ts])
        zeros = []
        n = 1
        while True:
            z = float(mpmath.zetazero(n).imag)
            if z > t1: break
            if z >= t0: zeros.append(z)
            n += 1
        _ZETA[key] = (ts, zs, zeros)
    return _ZETA[key]

def v_espiral(img, d, t, sc, p):
    """Dibuja ζ(1/2 + it) en el plano complejo; marca cada paso por el origen (un cero)."""
    t0, t1 = p.get("desde", 0.0), p.get("hasta", 35.0)
    ts, zs, zeros = _zeta_curve(t0, t1)
    cx, cy, S = W / 2 + p.get("dx", 60), p.get("y", 780), p.get("escala", 150)
    P = lambda z: (cx + z.real * S, cy - z.imag * S)
    ka = ease_out(prog(t, 0.0, 0.5))
    axc = mix(BG, (55, 68, 104), ka)
    d.line([60, cy, W - 60, cy], fill=axc, width=3); d.line([cx, 330, cx, 1290], fill=axc, width=3)
    text(d, (W - 90, cy - 30), "Re", 34, mix(BG, GREY, ka), "bold"); text(d, (cx + 40, 350), "Im", 34, mix(BG, GREY, ka), "bold")
    st = at(sc, p.get("sync"), 0.4); dur = p.get("dur", max(2.0, sc["dur"] - st - 0.6))
    k = ease_inout(prog(t, st, dur)) if p.get("suave", True) else prog(t, st, dur)
    m = max(2, int(len(ts) * k))
    pts = [P(z) for z in zs[:m]]
    pts = [(clamp(x, 20, W - 20), clamp(y, 300, 1330)) for x, y in pts]
    if len(pts) > 1:
        seg = 40
        for i in range(0, len(pts) - 1, seg):
            f = i / max(1, len(ts))
            d.line(pts[i:i + seg + 1], fill=mix((60, 110, 210), ICE, f), width=6, joint="curve")
        hx, hy = pts[-1]
        d.ellipse([hx - 13, hy - 13, hx + 13, hy + 13], fill=WARM, outline=WHITE, width=3)
    tcur = ts[m - 1]
    hit = [zz for zz in zeros if zz <= tcur]
    for i, zz in enumerate(hit):
        age = tcur - zz
        if age < 2.5:
            rr = 20 + 60 * clamp(age / 2.5)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=mix(WARM, BG, clamp(age / 2.5)), width=6)
    d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=WHITE)
    if p.get("contador", True) and k > 0:
        text(d, (90, 1240), f"t = {tcur:5.2f}", 46, ICE, "black", "lm")
        text(d, (W - 90, 1240), f"{'zeros' if LANG['code'] != 'es' else 'ceros'}: {len(hit)}", 46, WARM, "black", "rm")
    if p.get("titulo"):
        slide(d, (W // 2, 330), p["titulo"], 60, WHITE, t, 0.0, weight="black", dy=30)

def v_franja(img, d, t, sc, p):
    """Franja crítica: eje Re de -0.25 a 1.25, línea Re=1/2 y ceros como puntos sobre ella."""
    import mpmath
    nz = int(p.get("n", 16))
    if "_zz" not in _ZETA:
        _ZETA["_zz"] = [float(mpmath.zetazero(i).imag) for i in range(1, 41)]
    zz = _ZETA["_zz"][:nz]
    xL, xR = 110, W - 110
    X = lambda re: xL + (re + 0.25) / 1.5 * (xR - xL)
    yb, yt = 1280, 430
    tmax = zz[-1] * 1.06
    Y = lambda im: yb - im / tmax * (yb - yt)
    ka = ease_out(prog(t, 0.0, 0.6))
    b0, b1 = 0.0, 1.0
    band = p.get("banda")
    if band:
        kb = ease_inout(prog(t, at(sc, band.get("sync"), 1.0), band.get("dur", 1.6)))
        b0, b1 = band["desde"][0] + (band["hasta"][0] - band["desde"][0]) * kb, band["desde"][1] + (band["hasta"][1] - band["desde"][1]) * kb
    d.rectangle([X(0), yt, X(1), yb], fill=mix(BG, (26, 34, 64), ka))
    if band:
        d.rectangle([X(b0), yt, X(b1), yb], fill=mix(BG, (60, 40, 30), ka), outline=mix(BG, WARM, ka), width=4)
    d.line([X(0), yb, X(0), yt], fill=mix(BG, GREY, ka), width=3)
    d.line([X(1), yb, X(1), yt], fill=mix(BG, GREY, ka), width=3)
    kl = ease_out(prog(t, at(sc, p.get("linea_sync"), 0.5), 0.8))
    if kl > 0:
        d.line([X(0.5), yb, X(0.5), yb - (yb - yt) * kl], fill=BLUE, width=8)
        text(d, (X(0.5), yt - 40), "Re = ½", 46, BLUE, "black")
    d.line([X(-0.25), yb, X(1.25), yb], fill=mix(BG, (70, 84, 120), ka), width=3)
    for v, lab in [(0, "0"), (0.5, "½"), (1, "1")]:
        text(d, (X(v), yb + 44), lab, 40, mix(BG, GREY, ka), "bold")
    if band and kb > 0.05:
        text(d, (X(b0) - 6, yb + 96), band.get("label0", ""), 36, WARM, "black", "rm")
        text(d, (X(b1) + 6, yb + 96), band.get("label1", ""), 36, WARM, "black", "lm")
    st = at(sc, p.get("sync"), 0.8)
    for i, z in enumerate(zz):
        kz = back(prog(t, st + i * p.get("paso", 0.12), 0.35))
        if kz <= 0: continue
        r = 13 * kz
        x, y = X(0.5), Y(z)
        d.ellipse([x - r, y - r, x + r, y + r], fill=WARM, outline=WHITE, width=3)
        if i < p.get("etiquetas", 5):
            text(d, (x + 30, y), f"{z:.2f}i", 32, ICE, "bold", "lm")
    if p.get("titulo"):
        slide(d, (W // 2, 300), p["titulo"], 56, WHITE, t, 0.0, weight="black", dy=30)

def v_lista(img, d, t, sc, p):
    """Lista para guardar: título + ítems que aparecen en orden (con número o emoji) + chip "GUÁRDALO"."""
    y = p.get("y", 330)
    if p.get("pastilla"):
        f = font(46, "black"); tw = d.textlength(p["pastilla"], font=f)
        k = back(prog(t, 0.0, 0.4))
        if k > 0:
            d.rounded_rectangle([W / 2 - tw / 2 - 30, y - 34, W / 2 + tw / 2 + 30, y + 34], 34, fill=WARM)
            text(d, (W // 2, y), p["pastilla"], 46 * k, BG)
        y += 100
    if p.get("titulo"):
        pop(d, (W // 2, y + 20), p["titulo"], p.get("titulo_size", 96), col(p.get("titulo_color"), WHITE), t, 0.05, maxw=980)
        y += 150
    items = p.get("items", [])
    for i, it in enumerate(items):
        it = it if isinstance(it, dict) else {"texto": it}
        st = at(sc, it.get("sync"), 0.5 + 0.6 * i)
        k = ease_out(prog(t, st - 0.1, 0.4))
        if k <= 0: y += 150; continue
        x0 = 80 - 60 * (1 - k)
        d.rounded_rectangle([x0, y, W - 80, y + 128], 28, fill=PANEL)
        icon = it.get("emoji")
        if icon:
            em = emoji_img(icon, 70)
            if em: img.paste(em, (int(x0 + 28), int(y + 29)), em)
        else:
            d.rounded_rectangle([x0 + 24, y + 24, x0 + 104, y + 104], 22, fill=col(it.get("color"), BLUE))
            text(d, (x0 + 64, y + 66), str(i + 1), 52, BG)
        size = fit(d, it["texto"], 52, "xbold", W - 80 - (x0 + 130) - 20)
        d.text((x0 + 130, y + 64), it["texto"], font=font(size, "xbold"), fill=WHITE, anchor="lm")
        y += 150
    if p.get("boton"):
        k = back(prog(t, at(sc, p.get("boton_sync"), 1.6) - 0.1, 0.5))
        if k > 0:
            f = font(56, "black"); tw = d.textlength(p["boton"], font=f)
            yb = y + 72
            d.rounded_rectangle([W / 2 - tw / 2 - 44, yb - 46, W / 2 + tw / 2 + 44, yb + 46], 46, fill=BLUE)
            text(d, (W / 2, yb), p["boton"], 56 * k, BG)


def v_mercado(img, d, t, sc, p):
    """Gráfico de precio REAL (serie de cierres) que se dibuja de izquierda a derecha.
    p: serie=[[fecha_txt, precio], ...], desde/hasta (índices visibles al inicio/fin de la escena),
       marcas=[{i, texto, pos:'arriba'|'abajo', color, sync}], niveles=[{precio, texto, color, sync}],
       pre, titulo, color, ymin, ymax, fechas=[i,...] (etiquetas en el eje), precio_final (mostrar)"""
    serie = p["serie"]; n = len(serie)
    ind = p.get("indicador")
    bx0, bx1, by0, by1 = 110, W - 110, p.get("y_base", 1010 if ind else 1240), p.get("y_tope", 560)
    precios = [q[1] for q in serie]
    ymin = p.get("ymin", min(precios) * 0.94); ymax = p.get("ymax", max(precios) * 1.04)
    fut = p.get("futuro", 0)
    X = lambda i: bx0 + i / max(1, n - 1 + fut) * (bx1 - bx0)
    Y = lambda v: by0 - (v - ymin) / (ymax - ymin) * (by0 - by1)
    if fut:
        xa = X(n - 1)
        for yy in range(int(by1), int(by0), 30):
            d.line([xa, yy, xa, yy + 12], fill=(60, 74, 110), width=2)
        text(d, ((xa + bx1) / 2, by1 - 10), p.get("futuro_txt", "proyección"), 30, GREY, "bold")
    if p.get("pre"):
        slide(d, (W // 2, 330), p["pre"], 44, GREY, t, 0.0, weight="xbold")
    if p.get("titulo"):
        slide(d, (W // 2, 410), p["titulo"], fit(d, p["titulo"], 80, "black", 960), WHITE, t, 0.1, weight="black")
    ka = ease_out(prog(t, 0.0, 0.4))
    for gy in (0.0, 0.33, 0.66, 1.0):
        yy = by0 - (by0 - by1) * gy
        d.line([bx0, yy, bx0 + (bx1 - bx0) * ka, yy], fill=(28, 36, 62) if gy else (60, 74, 110), width=2 if gy else 4)
    i0 = p.get("desde", n - 1 if p.get("estatico") else 0); i1 = p.get("hasta", n - 1)
    kd = ease_inout(prog(t, at(sc, p.get("sync"), 0.2), max(0.6, sc["dur"] * p.get("vel", 0.7))))
    vis = i0 + (i1 - i0) * kd
    cc = col(p.get("color"), BLUE)
    last = int(vis)
    pts = [(X(i), Y(precios[i])) for i in range(0, min(n, last + 1))]
    if last < n - 1 and vis > last:
        f = vis - last
        pts.append((X(last) + (X(last + 1) - X(last)) * f, Y(precios[last] + (precios[last + 1] - precios[last]) * f)))
    def _serie_parcial(vals, yf):
        out = []
        for i in range(0, min(n, last + 1)):
            if vals[i] is not None: out.append((X(i), yf(vals[i])))
        if last < n - 1 and vis > last and vals[last] is not None and vals[last + 1] is not None:
            f = vis - last
            out.append((X(last) + (X(last + 1) - X(last)) * f, yf(vals[last] + (vals[last + 1] - vals[last]) * f)))
        return out
    for ln in p.get("lineas", []):  # medias móviles u otras líneas sobre el precio
        if ease_out(prog(t, at(sc, ln.get("sync"), 0.0), 0.3)) <= 0: continue
        lp = _serie_parcial(ln["valores"], Y)
        if len(lp) > 1:
            d.line(lp, fill=col(ln.get("color"), GREY), width=5, joint="curve")
            if ln.get("texto"):
                f = font(30, "xbold"); tw = d.textlength(ln["texto"], font=f)
                lx = min(lp[-1][0] + 14, bx1 - tw); ly = lp[-1][1] + ln.get("dy", 0)
                d.text((lx, ly), ln["texto"], font=f, fill=col(ln.get("color"), GREY), anchor="lm", stroke_width=5, stroke_fill=BG)
    if len(pts) > 1:
        d.line(pts, fill=cc, width=9, joint="curve")
    if ind:  # panel de indicador (RSI o MACD) debajo del precio
        py0, py1 = ind.get("y0", 1070), ind.get("y1", 1290)
        ka2 = ease_out(prog(t, at(sc, ind.get("sync"), 0.0), 0.4))
        d.rounded_rectangle([bx0 - 20, py0 - 16, bx1 + 20, py1 + 16], 18, fill=(16, 22, 42))
        tit = ind.get("texto") or ind["tipo"].upper()
        f = font(30, "black"); d.text((bx0, py0 + 4), tit, font=f, fill=GREY, anchor="lm")
        if ind["tipo"] == "rsi":
            YR = lambda v: py1 - v / 100 * (py1 - py0)
            for z, c2 in ((70, WARM), (30, GREEN_)):
                xx = bx0
                while xx < bx0 + (bx1 - bx0) * ka2:
                    d.line([xx, YR(z), min(xx + 18, bx1), YR(z)], fill=c2, width=3); xx += 32
                d.text((bx0 + 4, YR(z) + (-18 if z == 70 else 18)), "sobrecompra 70" if z == 70 else "sobreventa 30", font=font(24, "bold"), fill=c2, anchor="lm")
            rp = _serie_parcial(ind["valores"], YR)
            if len(rp) > 1: d.line(rp, fill=(190, 140, 255), width=6, joint="curve")
            if rp:
                v = ind["valores"][min(n - 1, last)]
                if v is not None:
                    d.ellipse([rp[-1][0] - 9, rp[-1][1] - 9, rp[-1][0] + 9, rp[-1][1] + 9], fill=(190, 140, 255))
                    text(d, (min(rp[-1][0], bx1 - 60), rp[-1][1] - 34 if rp[-1][1] > py0 + 50 else rp[-1][1] + 34), f"{v:.0f}", 34, WHITE, "black")
        elif ind["tipo"] == "macd":
            vals = [v for v in ind["macd"] + ind["senal"] if v is not None]
            m = max(abs(v) for v in vals) or 1
            hm = max([abs(v) for v in ind["hist"] if v is not None] or [1]) or 1
            hk = 0.55 * m / hm  # el histograma va a su propia escala para que se vea
            YM = lambda v: (py0 + py1) / 2 - v / m * (py1 - py0) / 2 * 0.9
            d.line([bx0, YM(0), bx0 + (bx1 - bx0) * ka2, YM(0)], fill=(60, 74, 110), width=2)
            bw = max(2, (bx1 - bx0) / max(1, n + p.get("futuro", 0)) * 0.6)
            for i in range(0, min(n, last + 1)):
                h = ind["hist"][i]
                if h is None: continue
                d.rectangle([X(i) - bw / 2, min(YM(0), YM(h * hk)), X(i) + bw / 2, max(YM(0), YM(h * hk))], fill=GREEN_ if h >= 0 else WARM)
            for key, c2 in (("macd", BLUE), ("senal", (255, 170, 60))):
                lp = _serie_parcial(ind[key], YM)
                if len(lp) > 1: d.line(lp, fill=c2, width=5, joint="curve")
            f2 = font(26, "bold")
            d.text((bx1, py0 + 4), "MACD", font=f2, fill=BLUE, anchor="rm")
            d.text((bx1 - 100, py0 + 4), "señal", font=f2, fill=(255, 170, 60), anchor="rm")
    hx, hy = pts[-1]
    d.ellipse([hx - 14, hy - 14, hx + 14, hy + 14], fill=cc, outline=WHITE, width=4)
    if p.get("precio_cabeza", True):
        pv = precios[min(n - 1, last)]
        lab = "$" + fmt_num(pv, 0)
        tx = min(max(hx, bx0 + 90), bx1 - 90)
        text(d, (tx, hy - 50 if hy > by1 + 80 else hy + 50), lab, 46, WHITE, "black")
    for nv in p.get("niveles", []):
        k = ease_out(prog(t, at(sc, nv.get("sync"), 0.5), 0.5))
        if k <= 0: continue
        yy = Y(nv["precio"]); c2 = col(nv.get("color"), GREY)
        xx = bx0
        while xx < bx0 + (bx1 - bx0) * k:
            d.line([xx, yy, min(xx + 26, bx1), yy], fill=c2, width=4); xx += 44
        if nv.get("texto"):
            f = font(34, "xbold"); tw = d.textlength(nv["texto"], font=f)
            d.rounded_rectangle([bx0, yy - 50, bx0 + tw + 30, yy - 8], 12, fill=PANEL)
            d.text((bx0 + 15, yy - 29), nv["texto"], font=f, fill=c2, anchor="lm")
    for m in p.get("marcas", []):
        if m["i"] > vis + 0.01: continue
        k = back(prog(t, at(sc, m.get("sync"), 0.3), 0.4))
        if k <= 0: continue
        x, y = X(m["i"]), Y(precios[m["i"]])
        c2 = col(m.get("color"), WARM)
        yy = y - 70 if m.get("pos", "arriba") == "arriba" else y + 70
        r = 38 * k
        d.ellipse([x - r, yy - r, x + r, yy + r], fill=c2)
        text(d, (x, yy), m["texto"], 46 * k, BG, "black")
        if m.get("nota") and k > 0.6:
            ny = yy - 64 if m.get("pos", "arriba") == "arriba" else yy + 64
            nx = min(max(x, bx0 + 70), bx1 - 70)
            text(d, (nx, ny), m["nota"], 36, c2, "black")
    for pr in p.get("proyecciones", []):
        k = ease_inout(prog(t, at(sc, pr.get("sync"), 0.4), pr.get("dur", 1.6)))
        if k <= 0: continue
        c2 = col(pr.get("color"), GREEN_)
        pts = [(X(n - 1), Y(precios[-1]))] + [(X(n - 1 + q[0]), Y(q[1])) for q in pr["puntos"]]
        segs = [(pts[j], pts[j + 1]) for j in range(len(pts) - 1)]
        tot = sum(((b2[0] - a2[0]) ** 2 + (b2[1] - a2[1]) ** 2) ** 0.5 for a2, b2 in segs)
        lim, acc, head = tot * k, 0.0, pts[0]
        for a2, b2 in segs:
            L = ((b2[0] - a2[0]) ** 2 + (b2[1] - a2[1]) ** 2) ** 0.5
            if acc >= lim: break
            f = min(1.0, (lim - acc) / L) if L else 1.0
            e = (a2[0] + (b2[0] - a2[0]) * f, a2[1] + (b2[1] - a2[1]) * f)
            nd = max(1, int(L * f / 22))
            for j in range(nd):
                if j % 2: continue
                f0, f1 = j / nd, min(1.0, (j + 1) / nd)
                d.line([a2[0] + (e[0] - a2[0]) * f0, a2[1] + (e[1] - a2[1]) * f0,
                        a2[0] + (e[0] - a2[0]) * f1, a2[1] + (e[1] - a2[1]) * f1], fill=c2, width=8)
            head = e; acc += L
        d.ellipse([head[0] - 12, head[1] - 12, head[0] + 12, head[1] + 12], fill=c2)
        for lb in pr.get("etiquetas", []):
            if k < lb.get("k", 1.0): continue
            q = pr["puntos"][lb["p"]]
            x, y = X(n - 1 + q[0]), Y(q[1])
            yy = y - 46 if lb.get("pos", "arriba") == "arriba" else y + 46
            text(d, (min(max(x, bx0 + 80), bx1 - 80), yy), lb["texto"], lb.get("size", 36), c2, "black")
    fy = (ind.get("y1", 1290) + 10) if ind else by0
    for i in p.get("fechas", []):
        text(d, (X(i), fy + 40), serie[i][0], 34, GREY, "bold")
    if p.get("fuente"):
        text(d, (W // 2, (by1 - 50) if ind else (fy + 92)), p["fuente"], 28, (110, 120, 145), "semi")


VISUALS = {"mercado": v_mercado, "lista": v_lista, "title": v_title, "counter": v_counter, "bars": v_bars, "versus": v_versus,
           "equation": v_equation, "bigword": v_bigword, "card": v_card, "outro": v_outro,
           "mapa": v_mapa, "grafica": v_grafica, "emoji": v_emoji, "foto": v_foto,
           "primos": v_primos, "formula": v_formula, "espiral": v_espiral, "franja": v_franja}

import monitos  # noqa: E402  (personaje animado de la serie "¿Qué pasa si…?")
VISUALS["monito"] = lambda img, d, t, sc, p: monitos.v_monito(img, d, t, sc, p, sys.modules[__name__])

# ---------------------------------------------------------------- subtítulos
def captions(d, t, sc):
    words, times = sc["words"], sc["times"]
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        if len(cur) == 3 or w.endswith((".", ",", "?", "!")):
            groups.append(cur); cur = []
    if cur: groups.append(cur)
    active = None
    for g in groups:
        if t >= times[g[0]] - 0.05: active = g
    if active is None: return
    cw = max([i for i in range(len(words)) if times[i] <= t + 0.02] or [active[0]])
    parts = [words[i].upper() for i in active]
    size = 66
    while size > 40 and sum(d.textlength(p_ + " ", font=font(size, "black")) for p_ in parts) > 960:
        size -= 4
    f = font(size, "black")
    widths = [d.textlength(p_ + " ", font=f) for p_ in parts]
    x = W / 2 - sum(widths) / 2
    for i, p_, wd in zip(active, parts, widths):
        d.text((x, 1430), p_, font=f, fill=BLUE if i == cw else WHITE, anchor="lm",
               stroke_width=8, stroke_fill=(0, 0, 0))
        x += wd

# ---------------------------------------------------------------- audio
def synth_kokoro(scenes, kcfg, outdir):
    from kokoro_onnx import Kokoro
    kd = os.environ.get("KOKORO_DIR", os.path.join(ROOT, "voices", "kokoro"))
    k = Kokoro(os.path.join(kd, "kokoro-v1.0.int8.onnx"), os.path.join(kd, "voices-v1.0.bin"))
    sr = 24000
    for i, sc in enumerate(scenes):
        samples, sr = k.create(sc["texto"], voice=kcfg.get("voz", "am_michael"),
                               speed=float(kcfg.get("velocidad", 1.0)), lang=kcfg.get("lang", "en-us"))
        pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
        pth = os.path.join(outdir, f"v{i:02d}.wav")
        with wave.open(pth, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(pcm.tobytes())
        sc["audio_dur"] = len(pcm) / sr; sc["wav"] = pth
    return sr

def synth_voice(scenes, voice_path, speed, outdir):
    from piper import PiperVoice, SynthesisConfig
    voice = PiperVoice.load(voice_path)
    cfg = SynthesisConfig(length_scale=speed)
    for i, sc in enumerate(scenes):
        pth = os.path.join(outdir, f"v{i:02d}.wav")
        with wave.open(pth, "wb") as wf:
            voice.synthesize_wav(sc["texto"], wf, syn_config=cfg)
        with wave.open(pth) as wf:
            sc["audio_dur"] = wf.getnframes() / wf.getframerate(); sr = wf.getframerate()
        sc["wav"] = pth
    return sr

def build_voice(scenes, sr, gap, out):
    ch = []
    for sc in scenes:
        with wave.open(sc["wav"]) as wf:
            ch.append(np.frombuffer(wf.readframes(wf.getnframes()), np.int16))
        ch.append(np.zeros(int(gap * sr), np.int16))
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(np.concatenate(ch).tobytes())

def build_music(dur, out, sr=44100):
    tt = np.arange(int(dur * sr)) / sr
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66], [164.81, 196.0, 246.94]]
    sig = np.zeros_like(tt)
    for ci in range(int(dur // 4) + 1):
        s0, s1 = ci * 4.0, (ci + 1) * 4.0 + 1.0
        env = np.clip((tt - s0) / 0.8, 0, 1) * np.clip((s1 - tt) / 1.0, 0, 1)
        for f in chords[ci % 4]:
            sig += env * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt))
    ph = tt % 0.6
    sig += 1.8 * np.sin(2 * np.pi * 55 * ph) * np.exp(-ph * 18)
    sig *= np.clip(tt, 0, 1) * np.clip((dur - tt) / 1.5, 0, 1)
    sig = sig / np.max(np.abs(sig)) * 0.9
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes((sig * 32767).astype(np.int16).tobytes())

# ---------------------------------------------------------------- render
def render(script_path, out_path, voice_path, channel="@whitehole"):
    cfg = json.load(open(script_path, encoding="utf-8"))
    LANG["code"] = cfg.get("idioma", "en")
    scenes = cfg["escenas"]
    work = os.path.join(os.path.dirname(os.path.abspath(out_path)), "_work_" + os.path.splitext(os.path.basename(out_path))[0])  # una carpeta por video: así dos renders a la vez no se pisan el audio
    os.makedirs(work, exist_ok=True)
    gap = 0.22
    print("1/3 Voz...")
    if cfg.get("kokoro") and os.environ.get("NO_KOKORO") != "1":
        sr = synth_kokoro(scenes, cfg["kokoro"], work)
    else:
        sr = synth_voice(scenes, voice_path, cfg.get("velocidad", 0.9), work)
    t0 = 0.0
    for sc in scenes:
        sc["start"] = t0; sc["dur"] = sc["audio_dur"] + gap
        sc["words"], sc["times"] = word_times(sc["texto"], sc["audio_dur"])
        t0 += sc["dur"]
    total = t0 + 0.6
    vw, mw = os.path.join(work, "voice.wav"), os.path.join(work, "music.wav")
    build_voice(scenes, sr, gap, vw); build_music(total, mw)
    print(f"   duración: {total:.1f}s")
    bg = make_background()
    print("2/3 Frames...")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", vw, "-i", mw,
           "-filter_complex", "[2:a]volume=0.10[m];[1:a]aresample=44100[v];[v][m]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.89[a]",
           "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_path]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(int(total * FPS)):
        T = fi / FPS
        sc = scenes[max(i for i, s in enumerate(scenes) if s["start"] <= T)]
        t = T - sc["start"]
        img = bg.copy(); d = ImageDraw.Draw(img)
        vis = sc["visual"]
        VISUALS[vis["tipo"]](img, d, t, sc, vis)
        captions(d, t, sc)
        text(d, (70, 250), channel, 34, GREY, "bold", "lm")
        ff.stdin.write(img.tobytes())
    ff.stdin.close(); ff.wait()
    if CREDITOS:
        json.dump(CREDITOS, open(out_path + ".creditos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("3/3 Listo ->", out_path)
    return total

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("guion"); ap.add_argument("salida")
    ap.add_argument("--voz", default=os.path.join(ROOT, "voices", "en-us-ryan-high.onnx"))
    ap.add_argument("--canal", default="@whitehole")
    a = ap.parse_args()
    render(a.guion, a.salida, a.voz, a.canal)
