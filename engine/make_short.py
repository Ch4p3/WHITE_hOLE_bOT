"""
White Hole · motor de Shorts (1080x1920), 100% gratis y offline.

Uso:  python engine/make_short.py guiones/pendientes/mi_guion.json salida.mp4 [--voz voices/modelo.onnx]

Cada escena del guion tiene:
  "texto":   lo que dice la voz
  "visual":  una de las plantillas de abajo + sus parámetros
  "sync":    (en los parámetros) palabra del texto en la que aparece cada elemento

Plantillas disponibles (ver README para ejemplos):
  title, counter, bars, versus, equation, bigword, card, outro,
  mapa (mapa de Colombia con zoom y río), grafica (línea animada), emoji (emoji grande)
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
COLORS = {"blue": BLUE, "ice": ICE, "white": WHITE, "grey": GREY, "warm": WARM}

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
    if p.get("categorico"):
        idx = {q["x"]: i for i, q in enumerate(pts)}
        X = lambda v: bx0 + 70 + idx[v] / max(1, len(pts) - 1) * (bx1 - bx0 - 140)
    else:
        X = lambda v: bx0 + (v - xmin) / (xmax - xmin) * (bx1 - bx0)
    Y = lambda v: by0 - v / ymax * (by0 - by1)
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

VISUALS = {"title": v_title, "counter": v_counter, "bars": v_bars, "versus": v_versus,
           "equation": v_equation, "bigword": v_bigword, "card": v_card, "outro": v_outro,
           "mapa": v_mapa, "grafica": v_grafica, "emoji": v_emoji, "foto": v_foto}

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
    work = os.path.join(os.path.dirname(os.path.abspath(out_path)), "_work")
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
