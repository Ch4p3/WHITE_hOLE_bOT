"""
White Hole · motor de videos LARGOS horizontales (1920x1080), 100% gratis y offline.

Uso:
  python engine/make_long.py guiones/largos/001_que_es_ia.json salida.mp4
  python engine/make_long.py guion.json carpeta_frames --frames     # solo fotos de control (sin voz)

Reutiliza la voz (Kokoro/Piper), la música y los helpers de make_short.py,
pero con plantillas pensadas para pantalla ancha, capítulos, barra de progreso
y miniatura automática (salida + ".jpg") + metadatos con capítulos (salida + ".meta.json").
"""
import json, math, os, re, subprocess, sys, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_short as ms
from make_short import (font, col, clamp, ease_out, back, prog, ease_inout, mix, fmt_num, text, fit,
                        word_times, at, BG, BLUE, ICE, WHITE, GREY, WARM, PANEL, LANG)

W, H, FPS = 1920, 1080, 30
GREEN = (90, 210, 150)
VIOLET = (160, 130, 255)
TINTS = [BLUE, ICE, WARM, VIOLET, GREEN]
DIM = (38, 48, 78)

MONO_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"]
_mono = {}
def mono(size, bold=False):
    key = (size, bold)
    if key not in _mono:
        pth = MONO_PATHS[1 if bold else 0]
        _mono[key] = ImageFont.truetype(pth, size) if os.path.exists(pth) else font(size, "semi")
    return _mono[key]

def pop(d, xy, s, size, fill, t, start, weight="black", dur=0.4, maxw=1600, anchor="mm"):
    k = prog(t, start, dur)
    if k <= 0: return
    size = fit(d, s, size, weight, maxw)
    d.text(xy, s, font=font(size * (0.4 + 0.6 * back(k)), weight), fill=fill, anchor=anchor)

def slide(d, xy, s, size, fill, t, start, dx=0, dy=50, weight="black", dur=0.45, maxw=1600, anchor="mm"):
    k = prog(t, start, dur)
    if k <= 0: return
    size = fit(d, s, size, weight, maxw)
    e = ease_out(k)
    d.text((xy[0] + dx * (1 - e), xy[1] + dy * (1 - e)), s, font=font(size, weight),
           fill=mix(BG, fill, e), anchor=anchor)

# ---------------------------------------------------------------- fondo
def make_background():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.45) / H * 0.8) ** 2)
    glow = np.clip(1 - r * 1.6, 0, 1)[..., None]
    vig = np.clip(1 - np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 0.55, 0.6, 1)[..., None]
    base = (np.array(BG, np.float32) + glow * np.array([10, 18, 40], np.float32)) * vig
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(11)
    for _ in range(180):
        x, y = rng.integers(0, W), rng.integers(0, H)
        b = int(rng.uniform(30, 85))
        d.ellipse([x, y, x + 2, y + 2], fill=(b, b + 8, b + 25))
    ring = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(ring)
    for i, a in enumerate([20, 13, 7]):
        rd.ellipse([W / 2 - 900 - i * 50, 1030 - 60 - i * 8, W / 2 + 900 + i * 50, 1030 + 60 + i * 8],
                   outline=a, width=5)
    img.paste((60, 120, 220), mask=ring)
    return img

def chip(d, cx, cy, s, size=40, fill=PANEL, fg=WHITE, outline=None, weight="xbold", pad=26, anchor="mm"):
    f = font(size, weight)
    w = d.textlength(s, font=f) + pad * 2; h = size * 1.6
    x0 = cx - w / 2 if anchor == "mm" else cx
    d.rounded_rectangle([x0, cy - h / 2, x0 + w, cy + h / 2], int(h / 2), fill=fill,
                        outline=outline, width=3 if outline else 0)
    d.text((x0 + w / 2, cy), s, font=f, fill=fg, anchor="mm")
    return w

def arrow(d, x0, y0, x1, y1, fill, width=6, head=18):
    d.line([x0, y0, x1, y1], fill=fill, width=width)
    a = math.atan2(y1 - y0, x1 - x0)
    p1 = (x1 - head * math.cos(a - 0.45), y1 - head * math.sin(a - 0.45))
    p2 = (x1 - head * math.cos(a + 0.45), y1 - head * math.sin(a + 0.45))
    d.polygon([(x1, y1), p1, p2], fill=fill)

# ---------------------------------------------------------------- plantillas
def v_capitulo(img, d, t, sc, p):
    k = back(prog(t, 0.0, 0.55))
    if k > 0:
        text(d, (W / 2, 360), f"{int(p['num']):02d}", 210 * (0.5 + 0.5 * k), BLUE)
    slide(d, (W / 2, 560), p["titulo"].upper(), 110, WHITE, t, 0.25, dy=40, maxw=1650)
    if p.get("sub"):
        slide(d, (W / 2, 670), p["sub"], 52, GREY, t, 0.5, dy=30, weight="semi")
    ku = ease_out(prog(t, 0.45, 0.6))
    if ku > 0:
        for sgn in (-1, 1):
            xa, xb = W / 2 + sgn * 170, W / 2 + sgn * (170 + 260 * ku)
            d.rounded_rectangle([min(xa, xb), 356, max(xa, xb), 364], 4, fill=DIM)

def v_titulo(img, d, t, sc, p):
    lines = p.get("lines", [])
    n = len(lines); gap = p.get("gap", 160)
    y0 = p.get("y", 520 - (n - 1) * gap / 2)
    if p.get("pre"):
        slide(d, (W / 2, y0 - 150), p["pre"], 60, GREY, t, at(sc, p.get("pre_sync"), 0), weight="xbold")
    colors = p.get("colors", ["white", "blue", "blue", "white"])
    st = at(sc, p.get("sync"), 0.1)
    for i, ln in enumerate(lines):
        slide(d, (W / 2, y0 + i * gap), ln, p.get("size", 150), col(colors[i % len(colors)]), t,
              st + i * 0.2, dx=(-140 if i % 2 == 0 else 140), dy=0, maxw=1700)
    ku = ease_out(prog(t, st + 0.3 + 0.2 * n, 0.5))
    if ku > 0 and p.get("underline", True):
        yy = y0 + (n - 1) * gap + 95
        d.rounded_rectangle([W / 2 - 280 * ku, yy, W / 2 + 280 * ku, yy + 16], 8, fill=BLUE)

def v_bigword(img, d, t, sc, p):
    st = at(sc, p.get("sync"), 0.2)
    if p.get("pre"):
        slide(d, (W / 2, 320), p["pre"], 54, GREY, t, at(sc, p.get("pre_sync"), 0.0), weight="semi")
    pop(d, (W / 2, 500), p["word"], p.get("size", 220), col(p.get("color"), BLUE), t, st - 0.15, maxw=1700)
    if p.get("sub"):
        slide(d, (W / 2, 690), p["sub"], 76, WHITE, t, at(sc, p.get("sub_sync"), st + 0.3), weight="xbold")
    if p.get("sub2"):
        slide(d, (W / 2, 790), p["sub2"], 48, GREY, t, at(sc, p.get("sub2_sync"), st + 0.6), weight="semi")

def v_counter(img, d, t, sc, p):
    if p.get("pre"):
        slide(d, (W / 2, 300), p["pre"], 54, GREY, t, 0.0, weight="xbold")
    st = at(sc, p.get("sync"), 0.2)
    k = ease_out(prog(t, st, p.get("dur", 1.3)))
    if k > 0:
        a, b = float(p.get("from", 0)), float(p["to"])
        s = f"{p.get('prefix', '')}{fmt_num(a + (b - a) * k, int(p.get('decimals', 0)))}{p.get('suffix', '')}"
        text(d, (W / 2, 490), s, fit(d, s, p.get("size", 230), "black", 1700), col(p.get("color"), BLUE))
    if p.get("label"):
        slide(d, (W / 2, 660), p["label"], 60, WHITE, t, st + 0.3, weight="xbold")
    if p.get("note"):
        pop(d, (W / 2, 770), p["note"], 48, col(p.get("note_color"), GREY), t,
            at(sc, p.get("note_sync"), st + 0.8), "bold")

def v_ecuacion(img, d, t, sc, p):
    lines = p.get("lines", [])
    y = p.get("y", 300)
    for i, ln in enumerate(lines):
        slide(d, (W / 2, y), ln["text"], ln.get("size", 96), col(ln.get("color"), WHITE), t,
              at(sc, ln.get("sync"), 0.4 * i), dy=40, weight="xbold")
        y += 140
    r = p.get("result")
    if r:
        st = at(sc, r.get("sync"), 1.5)
        kl = ease_out(prog(t, st - 0.4, 0.5))
        if kl > 0:
            d.rounded_rectangle([W / 2 - 520 * kl, y - 50, W / 2 + 520 * kl, y - 40], 5, fill=WHITE)
        kc = ease_out(prog(t, st, 1.1))
        if kc > 0:
            v = float(r.get("from", 0)) + (float(r["value"]) - float(r.get("from", 0))) * kc
            s = f"{r.get('prefix', '')}{fmt_num(v, int(r.get('decimals', 0)))}{r.get('suffix', '')}"
            text(d, (W / 2, y + 75), s, fit(d, s, 190, "black", 1600), col(r.get("color"), BLUE))
            if r.get("label"):
                text(d, (W / 2, y + 200), r["label"], 54, GREY, "xbold")

def v_versus(img, d, t, sc, p):
    L, R = p["left"], p["right"]
    cw, ch = 700, 420
    for x, c, dflt in [(W / 2 - 60 - cw, L, 0.0), (W / 2 + 60, R, 0.6)]:
        k = back(prog(t, at(sc, c.get("sync"), dflt), 0.5))
        if k <= 0: continue
        cy = 500 + 50 * (1 - k)
        cc = col(c.get("color"), BLUE)
        d.rounded_rectangle([x, cy - ch / 2, x + cw, cy + ch / 2], 34, fill=PANEL, outline=cc, width=5)
        text(d, (x + cw / 2, cy - 130), c["label"], fit(d, c["label"], 50, "xbold", cw - 60), GREY, "xbold")
        size = fit(d, c["value"], c.get("size", 130), "black", cw - 70)
        text(d, (x + cw / 2, cy + 10), c["value"], size * (0.6 + 0.4 * k), cc)
        if c.get("sub"):
            text(d, (x + cw / 2, cy + 135), c["sub"], fit(d, c["sub"], 42, "semi", cw - 60), WHITE, "semi")
    kb = back(prog(t, at(sc, p.get("vs_sync"), 0.4), 0.4))
    if kb > 0 and p.get("vs", True):
        r = 52 * kb
        d.ellipse([W / 2 - r, 500 - r, W / 2 + r, 500 + r], fill=WHITE)
        vt = p.get("vs_text", "VS")
        text(d, (W / 2, 500 - (4 if len(vt) == 1 else 0)), vt, (40 if len(vt) > 1 else 64) * kb, BG)
    if p.get("note"):
        pop(d, (W / 2, 820), p["note"], 56, col(p.get("note_color"), WARM), t, at(sc, p.get("note_sync"), 1.4))

def v_bars(img, d, t, sc, p):
    items = p["items"]
    vmax = max(float(it["value"]) for it in items)
    x0, maxw = 260, 1400
    y = p.get("y", 520 - (len(items) - 1) * 110)
    for i, it in enumerate(items):
        st = at(sc, it.get("sync"), 0.3 * i)
        if prog(t, st - 0.2, 0.3) <= 0: y += 220; continue
        k = ease_out(prog(t, st, 1.0))
        text(d, (x0, y - 50), it["label"], 46, WHITE, "bold", "lm")
        wbar = max(30, maxw * float(it["value"]) / vmax * k)
        c = col(it.get("color"), BLUE)
        d.rounded_rectangle([x0, y, x0 + wbar, y + 90], 18, fill=c)
        if k > 0.5:
            vt = it.get("value_text", f"{it['value']}")
            tw = d.textlength(vt, font=font(48, "black"))
            if wbar > tw + 50: text(d, (x0 + wbar - 24, y + 45), vt, 48, BG, "black", "rm")
            else: text(d, (x0 + wbar + 20, y + 45), vt, 48, c, "black", "lm")
        y += 220
    if p.get("note"):
        pop(d, (W / 2, min(870, y - 20)), p["note"], 60, col(p.get("note_color"), WARM), t, at(sc, p.get("note_sync"), 1.5))

def v_lista(img, d, t, sc, p):
    if p.get("titulo"):
        slide(d, (W / 2, 250), p["titulo"], 64, col(p.get("color"), BLUE), t, at(sc, p.get("sync"), 0.0), weight="black")
    items = p["items"]
    n = len(items); gap = 125
    y = 560 - (n - 1) * gap / 2 + 20
    x0 = p.get("x", 560)
    for i, it in enumerate(items):
        it = it if isinstance(it, dict) else {"texto": it}
        st = at(sc, it.get("sync"), 0.5 + 0.6 * i)
        k = ease_out(prog(t, st, 0.45))
        if k <= 0: continue
        xx = x0 - 80 * (1 - k)
        c = mix(BG, col(it.get("color"), BLUE), k)
        d.ellipse([xx - 34, y - 34, xx + 34, y + 34], fill=c)
        text(d, (xx, y), it.get("icono", str(i + 1)), 36, BG, "black")
        d.text((xx + 70, y), it["texto"], font=font(fit(d, it["texto"], 58, "xbold", 1180), "xbold"),
               fill=mix(BG, WHITE, k), anchor="lm")
        y += gap

def v_archivo(img, d, t, sc, p):
    k = back(prog(t, 0.0, 0.55))
    cx, cy = 640, 500
    fw, fh = 300 * (0.6 + 0.4 * k), 380 * (0.6 + 0.4 * k)
    if k > 0:
        x0, y0 = cx - fw / 2, cy - fh / 2
        fold = fw * 0.26
        poly = [(x0, y0), (x0 + fw - fold, y0), (x0 + fw, y0 + fold), (x0 + fw, y0 + fh), (x0, y0 + fh)]
        d.polygon(poly, fill=PANEL, outline=BLUE, width=5)
        d.polygon([(x0 + fw - fold, y0), (x0 + fw - fold, y0 + fold), (x0 + fw, y0 + fold)], fill=(40, 70, 130))
        f = mono(int(22 * (0.6 + 0.4 * k)))
        rows = int((fh - fold - 40) / 30)
        for r in range(rows):
            tf = min(t, at(sc, p.get("candado_sync"), 1.0)) if p.get("candado") else t
            rng = np.random.default_rng(r * 977 + int(tf * 6))
            s = " ".join(f"{v:+.2f}" for v in rng.normal(0, 0.4, 3))
            d.text((x0 + 22, y0 + fold + 10 + r * 30), s, font=f, fill=(70, 110, 170) if r % 3 else (110, 160, 230))
        if p.get("candado") and t > at(sc, p.get("candado_sync"), 1.0):
            kk = back(prog(t, at(sc, p.get("candado_sync"), 1.0), 0.45))
            lx, ly, s = x0 + fw - 10, y0 + fh - 10, 90 * kk
            d.rounded_rectangle([lx - s * 0.6, ly - s * 0.35, lx + s * 0.6, ly + s * 0.55], int(14 * kk), fill=WARM)
            d.arc([lx - s * 0.38, ly - s * 0.9, lx + s * 0.38, ly - s * 0.1], 180, 360, fill=WARM, width=max(1, int(12 * kk)))
        name = p.get("nombre", "model.safetensors")
        slide(d, (cx, cy + 250), name, 40, GREY, t, 0.3, weight="semi", maxw=560)
    st = at(sc, p.get("sync"), 0.5)
    kc = ease_out(prog(t, st, p.get("dur", 1.4)))
    if kc > 0 and p.get("tamano") is not None:
        v = float(p["tamano"]) * kc
        s = f"{fmt_num(v, int(p.get('decimals', 0)))} {p.get('unidad', 'GB')}"
        text(d, (1290, 470), s, fit(d, s, 200, "black", 820), col(p.get("color"), BLUE))
    if p.get("etiqueta"):
        slide(d, (1290, 610), p["etiqueta"], 52, WHITE, t, st + 0.4, weight="xbold", maxw=820)
    if p.get("sub"):
        slide(d, (1290, 690), p["sub"], 40, GREY, t, at(sc, p.get("sub_sync"), st + 0.8), weight="semi", maxw=820)

def v_numeros(img, d, t, sc, p):
    modo = p.get("modo", "flicker")
    cols, rows = 9, 7
    x0, y0, dx, dy = 260, 300, 175, 72
    st = at(sc, p.get("sync"), 0.0)
    f = mono(34)
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            kk = ease_out(prog(t, st + idx * 0.008, 0.4))
            if kk <= 0: continue
            if modo == "ruido":
                step = int(t * 8); sd = 2.5
            elif modo == "ajuste":
                step = int(t * 2.5); sd = 0.35
            else:
                step = int(t * 1.5); sd = 0.35
            v = np.random.default_rng(idx * 131 + step * 7919).normal(0, sd)
            base = (90, 130, 190) if modo != "ruido" else (110, 115, 135)
            color = base
            if modo == "ajuste":
                prev = np.random.default_rng(idx * 131 + (step - 1) * 7919).normal(0, sd)
                ph = (t * 2.5) % 1.0
                if ph < 0.45 and (idx * 7 + step) % 3 == 0:
                    color = GREEN if v > prev else WARM
            elif modo == "flicker" and (idx + step) % 11 == 0:
                color = ICE
            d.text((x0 + c * dx, y0 + r * dy), f"{v:+.4f}", font=f, fill=mix(BG, color, kk), anchor="lm")
    if p.get("etiqueta"):
        k = back(prog(t, at(sc, p.get("etiqueta_sync"), st + 0.6), 0.45))
        if k > 0:
            chip(d, W / 2, 210, p["etiqueta"], 44 * (0.6 + 0.4 * k), fill=col(p.get("color"), BLUE), fg=BG, weight="black")

def v_codigo(img, d, t, sc, p):
    lines = p["lineas"]
    px0, py0, pw, ph = 360, 230, 1200, 560
    k = ease_out(prog(t, 0, 0.4))
    d.rounded_rectangle([px0, py0 + 30 * (1 - k), px0 + pw, py0 + ph + 30 * (1 - k)], 26, fill=(14, 18, 34), outline=DIM, width=3)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([px0 + 30 + i * 34, py0 + 26, px0 + 50 + i * 34, py0 + 46], fill=c)
    f = mono(38)
    st = at(sc, p.get("sync"), 0.3)
    cps = p.get("cps", 38)
    shown = max(0, int((t - st) * cps))
    kw = {"if", "else", "then", "return", "for", "while", "def", "and", "or", "not"}
    y = py0 + 90
    for ln in lines:
        if shown <= 0: break
        s = ln[:shown]; shown -= len(ln) + 4
        x = px0 + 50
        for tok in re.split(r"(\W)", s):
            if not tok: continue
            c = BLUE if tok in kw else (WARM if tok.startswith("#") or tok.isdigit() else ICE)
            if s.lstrip().startswith("#"): c = GREY
            d.text((x, y), tok, font=f, fill=c, anchor="lm")
            x += d.textlength(tok, font=f)
        last_x, last_y = x, y
        y += 62
    if t >= st and int(t * 2) % 2 == 0:
        try: d.rectangle([last_x + 4, last_y - 22, last_x + 24, last_y + 22], fill=BLUE)
        except NameError: pass
    if p.get("etiqueta"):
        pop(d, (W / 2, 860), p["etiqueta"], 52, col(p.get("color"), WHITE), t, at(sc, p.get("etiqueta_sync"), st + 1.5), "xbold")

def _layout_chips(d, pieces, size, maxw=1640, gap=18):
    f = font(size, "xbold")
    ws = [d.textlength(s.replace(" ", "·") if s.startswith(" ") else s, font=f) + 44 for s in pieces]
    rows, cur, cw = [], [], 0
    for i, w in enumerate(ws):
        if cur and cw + w > maxw: rows.append(cur); cur, cw = [], 0
        cur.append(i); cw += w + gap
    if cur: rows.append(cur)
    return ws, rows

def v_tokens(img, d, t, sc, p):
    pieces = p["piezas"]; ids = p.get("ids")
    size = p.get("size", 64)
    if p.get("frase"):
        kf = ease_out(prog(t, 0.0, 0.4))
        cut = at(sc, p.get("sync"), 0.8)
        ky = ease_out(prog(t, cut, 0.4))
        text(d, (W / 2, 330 - 40 * ky), p["frase"], 70, mix(BG, GREY if ky > 0 else WHITE, kf), "xbold")
    st = at(sc, p.get("sync"), 0.3)
    ws, rows = _layout_chips(d, pieces, size)
    rh = size * 2.6 if ids else size * 1.9
    ytop = 520 - (len(rows) - 1) * rh / 2
    for ri, row in enumerate(rows):
        tw = sum(ws[i] for i in row) + 18 * (len(row) - 1)
        x = W / 2 - tw / 2
        y = ytop + ri * rh
        for i in row:
            k = back(prog(t, st + i * p.get("stagger", 0.18), 0.4))
            if k > 0:
                c = TINTS[i % len(TINTS)]
                hidden = p.get("oculto") and i == len(pieces) - 1 and t < at(sc, p.get("revela_sync"), 1e9)
                label = "???" if hidden else (pieces[i].replace(" ", "·") if pieces[i].startswith(" ") else pieces[i])
                h = size * 1.5 * (0.5 + 0.5 * k)
                if hidden:
                    d.rounded_rectangle([x, y - h / 2, x + ws[i], y + h / 2], 18, outline=GREY, width=4)
                    text(d, (x + ws[i] / 2, y), label, size * k, GREY, "xbold")
                else:
                    d.rounded_rectangle([x, y - h / 2, x + ws[i], y + h / 2], 18, fill=mix(PANEL, c, 0.22), outline=c, width=4)
                    text(d, (x + ws[i] / 2, y), label, size * k, WHITE, "xbold")
                if ids and i < len(ids):
                    ki = ease_out(prog(t, at(sc, p.get("ids_sync"), st + 1.2) + i * 0.1, 0.35))
                    if ki > 0:
                        d.text((x + ws[i] / 2, y + size * 1.25), str(ids[i]), font=mono(int(size * 0.62), True),
                               fill=mix(BG, c, ki), anchor="mm")
            x += ws[i] + 18
    if p.get("nota"):
        pop(d, (W / 2, 850), p["nota"], 44, GREY, t, at(sc, p.get("nota_sync"), st + 1.6), "semi")

def v_prediccion(img, d, t, sc, p):
    ctx = p["contexto"]; ops = p["opciones"]
    k0 = ease_out(prog(t, 0, 0.4))
    f = font(72, "xbold")
    tw = d.textlength(ctx + " ", font=f)
    bw = 260
    x0 = W / 2 - (tw + bw) / 2
    d.text((x0, 250), ctx, font=f, fill=mix(BG, WHITE, k0), anchor="lm")
    ch_i = p.get("elegido", 0)
    ksel = ease_out(prog(t, at(sc, p.get("elegido_sync"), 1e9), 0.5))
    bx = x0 + tw
    if ksel > 0:
        d.rounded_rectangle([bx, 250 - 52, bx + bw, 250 + 52], 16, fill=mix(PANEL, BLUE, 0.3), outline=BLUE, width=4)
        text(d, (bx + bw / 2, 250), ops[ch_i][0], 64 * (0.5 + 0.5 * back(ksel)), WHITE, "xbold")
    else:
        if int(t * 2) % 2 == 0 or t < 0.4:
            d.rounded_rectangle([bx, 250 - 52, bx + bw, 250 + 52], 16, outline=GREY, width=4)
        text(d, (bx + bw / 2, 250), "?", 64, GREY, "xbold")
    st = at(sc, p.get("sync"), 0.6)
    pmax = max(o[1] for o in ops)
    y = 390
    for i, op in enumerate(ops):
        tok, pr = op[0], op[1]
        k = ease_out(prog(t, st + i * 0.15, 0.8))
        if k <= 0: y += 92; continue
        hl = at(sc, ops[i][2], 1e9) if len(ops[i]) > 2 else 1e9
        is_sel = ksel > 0 and i == ch_i
        c = BLUE if (is_sel or (ksel <= 0 and t >= hl)) else (GREY if ksel > 0 else ICE)
        d.text((640, y), tok, font=font(52, "xbold"), fill=mix(BG, WHITE, k), anchor="rm")
        wb = max(12, 760 * pr / pmax * k)
        d.rounded_rectangle([670, y - 28, 670 + wb, y + 28], 14, fill=mix(BG, c, k))
        d.text((670 + wb + 20, y), ("<1%" if pr < 0.01 else f"{pr * 100:.0f}%"), font=font(44, "bold"), fill=mix(BG, c, k), anchor="lm")
        y += 92
    if p.get("nota", "illustrative scores"):
        d.text((W - 90, 900), p.get("nota", "illustrative scores"), font=font(30, "semi"), fill=(80, 90, 115), anchor="rm")

def v_bucle(img, d, t, sc, p):
    base = p["base"]; new = p["nuevos"]
    st = at(sc, p.get("sync"), 0.6)
    iv = p.get("intervalo", 0.55)
    n = clamp((t - st) / iv, 0, len(new))
    ni = int(n)
    words = [(base, WHITE, 1.0)]
    for i in range(ni):
        kk = back(prog(t, st + i * iv, 0.35))
        words.append((new[i], BLUE if i == ni - 1 else ICE, kk))
    f = font(80, "xbold")
    full = base + "".join(new[:ni])
    tw = d.textlength(full, font=f)
    x = W / 2 - min(tw, 1700) / 2
    y = 400
    for s, c, kk in words:
        wd = d.textlength(s, font=f)
        d.text((x, y + 30 * (1 - min(1, kk))), s, font=f, fill=mix(BG, c, clamp(kk)), anchor="lm")
        x += wd
    if ni < len(new) and t >= st - 0.3 and int(t * 3) % 2 == 0:
        d.rectangle([x + 8, y - 40, x + 22, y + 40], fill=BLUE)
    steps = p.get("pasos", ["predict", "append", "repeat"])
    ks = ease_out(prog(t, 0.2, 0.5))
    if ks > 0:
        active = int(((t - st) / iv) * 3) % 3 if t >= st and ni < len(new) else -1
        cxs = [W / 2 - 420, W / 2, W / 2 + 420]
        for i, (cx, s) in enumerate(zip(cxs, steps)):
            on = i == active
            chip(d, cx, 680, s.upper(), 44, fill=BLUE if on else PANEL, fg=BG if on else mix(BG, WHITE, ks),
                 outline=None if on else DIM)
            if i < 2:
                arrow(d, cx + 130, 680, cxs[i + 1] - 130, 680, mix(BG, GREY, ks), 5, 16)

def _net_pos(capas):
    L = len(capas)
    xs = [360 + i * (1200 / (L - 1)) for i in range(L)]
    pos = []
    for i, n in enumerate(capas):
        gap = min(78, 470 / max(1, n - 1)) if n > 1 else 0
        pos.append([(xs[i], 500 - (n - 1) * gap / 2 + j * gap) for j in range(n)])
    return pos

def draw_net(d, capas, phase, k=1.0, glow=True):
    pos = _net_pos(capas); L = len(capas)
    for i in range(L - 1):
        e = clamp(1 - abs(phase - (i + 0.5)) * 1.3) if glow else 0
        for a in pos[i]:
            for b in pos[i + 1]:
                d.line([a, b], fill=mix(BG, mix(DIM, BLUE, e), k), width=2 if e < 0.5 else 3)
    for i in range(L):
        e = clamp(1 - abs(phase - i) * 1.2) if glow else 0
        for (x, y) in pos[i]:
            r = 20 + 6 * e
            d.ellipse([x - r, y - r, x + r, y + r], fill=mix(BG, mix(PANEL, ICE, e), k), outline=mix(BG, BLUE, k), width=4)

def v_red(img, d, t, sc, p):
    capas = p.get("capas", [5, 7, 7, 7, 4])
    k = ease_out(prog(t, 0, 0.6))
    L = len(capas)
    phase = ((t * p.get("velocidad", 0.7)) % 1.0) * (L + 0.6) - 0.3
    draw_net(d, capas, phase, k)
    pos = _net_pos(capas)
    if p.get("entrada"):
        slide(d, (pos[0][0][0], pos[0][-1][1] + 90), p["entrada"], 40, GREY, t, 0.4, weight="xbold", dy=20)
    if p.get("salida"):
        slide(d, (pos[-1][0][0], pos[-1][-1][1] + 90), p["salida"], 40, GREY, t, 0.4, weight="xbold", dy=20)
    if p.get("medio"):
        mx = (pos[L // 2 - 1][0][0] + pos[L // 2][0][0]) / 2
        kk = back(prog(t, at(sc, p.get("medio_sync"), 0.8), 0.45))
        if kk > 0: chip(d, mx, 175, p["medio"], 46 * (0.6 + 0.4 * kk), fill=BLUE, fg=BG, weight="black")
    if p.get("etiqueta"):
        pop(d, (W / 2, 900), p["etiqueta"], 50, WHITE, t, at(sc, p.get("etiqueta_sync"), 1.2), "xbold")

def v_gpu(img, d, t, sc, p):
    fase = p.get("fase", "cpu")
    gpu_on = fase == "gpu"
    # CPU
    cx0 = 210 if gpu_on else W / 2 - 330
    k = ease_out(prog(t, 0, 0.5))
    d.rounded_rectangle([cx0, 250, cx0 + 660, 750], 30, fill=PANEL, outline=DIM, width=4)
    text(d, (cx0 + 330, 205), "CPU", 54, mix(BG, WHITE, k), "black")
    seq = int(t * 3) % 8
    for i in range(8):
        r, c = divmod(i, 4)
        x, y = cx0 + 45 + c * 150, 300 + r * 210
        on = i == seq and t > 0.5
        d.rounded_rectangle([x, y, x + 120, y + 170], 18, fill=BLUE if on else mix(BG, DIM, k))
    text(d, (cx0 + 330, 800), p.get("cpu_label", "a handful of big cores"), 40, GREY, "semi")
    if gpu_on:
        gx0 = 1050
        kg = ease_out(prog(t, at(sc, p.get("sync"), 0.3), 0.6))
        d.rounded_rectangle([gx0, 250, gx0 + 660, 750], 30, fill=PANEL, outline=mix(BG, BLUE, kg), width=4)
        text(d, (gx0 + 330, 205), "GPU", 54, mix(BG, WHITE, kg), "black")
        cols, rows = 40, 28
        cs = 620 / cols
        wave_t = t - at(sc, p.get("fuego_sync"), 1.2)
        for r in range(rows):
            for c in range(cols):
                x, y = gx0 + 20 + c * cs, 275 + r * (450 / rows)
                lit = wave_t > 0 and (math.sin(wave_t * 6 - (c + r) * 0.08) > 0.2)
                fc = mix(BG, (BLUE if lit else DIM), kg)
                d.rectangle([x, y, x + cs - 4, y + 450 / rows - 4], fill=fc)
        text(d, (gx0 + 330, 800), p.get("gpu_label", "~17,000 small cores (H100)"), 40, mix(BG, BLUE, kg), "xbold")

def v_chat(img, d, t, sc, p):
    msgs = p["mensajes"]
    y = 230
    rects = []
    for i, m in enumerate(msgs):
        k = ease_out(prog(t, at(sc, m.get("sync"), 0.3 + 0.7 * i), 0.4))
        f = font(38, "semi")
        tw = d.textlength(m["texto"], font=f) + 60
        user = m.get("quien", "user") == "user"
        x1 = 1150 if user else 200 + tw
        x0 = x1 - tw
        if k > 0:
            fill = mix(BG, BLUE if user else PANEL, k)
            d.rounded_rectangle([x0, y + 20 * (1 - k), x1, y + 76 + 20 * (1 - k)], 28, fill=fill)
            d.text((x0 + 30, y + 38 + 20 * (1 - k)), m["texto"], font=f, fill=mix(BG, BG if user else WHITE, k), anchor="lm")
            rects.append((x1, y + 38))
        y += 104
    bx, by = 1560, 500
    kb = ease_out(prog(t, 0.2, 0.5))
    feed = at(sc, p.get("feed_sync"), 1e9)
    kf = prog(t, feed, 1.0)
    glow = clamp(1 - abs(kf - 0.9) * 3) if kf > 0 else 0
    d.rounded_rectangle([bx - 170, by - 120, bx + 170, by + 120], 30, fill=mix(BG, mix(PANEL, BLUE, glow * 0.5), kb),
                        outline=mix(BG, BLUE, kb), width=5)
    text(d, (bx, by - 20), "MODEL", 54, mix(BG, WHITE, kb), "black")
    text(d, (bx, by + 40), "reads it all", 32, mix(BG, GREY, kb), "semi")
    if kf > 0:
        for j, (x1, yy) in enumerate(rects):
            e = ease_inout(clamp(kf * 1.4 - j * 0.08))
            if e <= 0: continue
            xe, ye = x1 + 20 + (bx - 190 - x1 - 20) * e, yy + (by - yy) * e
            d.line([x1 + 20, yy, xe, ye], fill=ICE, width=3)
            d.ellipse([xe - 7, ye - 7, xe + 7, ye + 7], fill=ICE)
    if p.get("etiqueta"):
        pop(d, (W / 2, 900), p["etiqueta"], 48, WARM, t, at(sc, p.get("etiqueta_sync"), feed + 0.8), "xbold")

def v_ventana(img, d, t, sc, p):
    words = (p.get("texto") or "you asked about black holes and then about coffee and then about your cat and then about").split()
    st_move = at(sc, p.get("mover_sync"), 1e9)
    off = max(0.0, t - st_move) * p.get("velocidad", 180)
    wx0, wx1 = 330, 1590
    y = 520
    f = font(40, "xbold")
    x = wx1 - 40 - off * 0 + 0
    # cinta: tokens se agregan por la derecha y la cinta corre a la izquierda
    xs = []
    cur = 120 - off
    i = 0
    while cur < W + 200 and i < 400:
        s = words[i % len(words)]
        w = d.textlength(s, font=f) + 40
        xs.append((cur, w, s, i)); cur += w + 14; i += 1
    k = ease_out(prog(t, 0, 0.5))
    for (x0, w, s, i) in xs:
        if x0 + w < -10 or x0 > W + 10: continue
        inside = x0 >= wx0 and x0 + w <= wx1
        c = TINTS[i % len(TINTS)] if inside else (60, 66, 88)
        fg = WHITE if inside else (90, 96, 120)
        d.rounded_rectangle([x0, y - 34, x0 + w, y + 34], 14, fill=mix(BG, mix(PANEL, c, 0.2 if inside else 0), k),
                            outline=mix(BG, c, k), width=3)
        d.text((x0 + w / 2, y), s, font=f, fill=mix(BG, fg, k), anchor="mm")
    kw = ease_out(prog(t, at(sc, p.get("sync"), 0.4), 0.5))
    if kw > 0:
        d.rounded_rectangle([wx0 - 14, y - 80, wx1 + 14, y + 80], 26, outline=mix(BG, BLUE, kw), width=6)
        chip(d, W / 2, y - 140, p.get("etiqueta", "CONTEXT WINDOW · ~128K TOKENS"), 40, fill=mix(BG, BLUE, kw), fg=BG, weight="black")
    if t > st_move:
        kk = ease_out(prog(t, st_move, 0.5))
        text(d, ((wx0 - 14) / 2, y + 120), "falls out", 36, mix(BG, WARM, kk), "xbold")
        arrow(d, wx0 - 30, y + 120, 60, y + 120, mix(BG, WARM, kk), 4, 14) if False else None
    if p.get("nota"):
        pop(d, (W / 2, 820), p["nota"], 50, WHITE, t, at(sc, p.get("nota_sync"), 2.0), "xbold")

def v_formula(img, d, t, sc, p):
    y = p.get("y", 470)
    if p.get("pre"):
        slide(d, (W / 2, y - 220), p["pre"], 54, GREY, t, 0.0, weight="xbold", dy=30)
    st = at(sc, p.get("sync"), 0.3)
    k = back(prog(t, st, 0.5))
    if k > 0:
        im = ms.tex_img(p["tex"], p.get("size", 64), col(p.get("color"), WHITE))
        sk = min(1.4, 1600 / im.width) * (0.6 + 0.4 * k)
        im2 = im.resize((max(1, int(im.width * sk)), max(1, int(im.height * sk))), Image.LANCZOS)
        img.paste(im2, (int(W / 2 - im2.width / 2), int(y - im2.height / 2)), im2)
    if p.get("sub"):
        slide(d, (W / 2, y + 210), p["sub"], 64, col(p.get("sub_color"), BLUE), t, at(sc, p.get("sub_sync"), st + 0.6))
    if p.get("sub2"):
        slide(d, (W / 2, y + 300), p["sub2"], 44, GREY, t, at(sc, p.get("sub2_sync"), st + 0.9), weight="semi")

def v_flujo(img, d, t, sc, p):
    steps = p["pasos"]; n = len(steps)
    bw, bh = 250, 130
    span = 1660
    gap = (span - n * bw) / (n - 1)
    x0 = (W - span) / 2
    y = 470
    for i, s in enumerate(steps):
        s = s if isinstance(s, dict) else {"texto": s}
        k = back(prog(t, at(sc, s.get("sync"), 0.3 + 0.45 * i), 0.45))
        x = x0 + i * (bw + gap)
        if k > 0:
            c = col(s.get("color"), BLUE)
            hh = bh * (0.5 + 0.5 * k)
            d.rounded_rectangle([x, y - hh / 2, x + bw, y + hh / 2], 24, fill=mix(PANEL, c, 0.18), outline=c, width=4)
            lines = s["texto"].split("\n")
            for j, ln in enumerate(lines):
                text(d, (x + bw / 2, y + (j - (len(lines) - 1) / 2) * 46), ln,
                     fit(d, ln, 42, "black", bw - 30) * k, WHITE, "black")
            if i > 0:
                ka = ease_out(prog(t, at(sc, s.get("sync"), 0.3 + 0.45 * i) - 0.1, 0.3))
                arrow(d, x - gap + 14, y, x - 14, y, mix(BG, GREY, ka), 5, 16)
    kl = ease_out(prog(t, at(sc, p.get("bucle_sync"), 1e9), 0.8))
    if kl > 0:
        xl, xr = x0 + bw / 2, x0 + (n - 1) * (bw + gap) + bw / 2
        pts = []
        for j in range(int(60 * kl) + 1):
            a = j / 60
            xx = xr + (xl - xr) * a
            yy = y + bh / 2 + 20 + math.sin(a * math.pi) * 150
            pts.append((xx, yy))
        if len(pts) > 1:
            d.line(pts, fill=BLUE, width=6)
            if kl > 0.95: arrow(d, pts[-2][0], pts[-2][1], xl, y + bh / 2 + 16, BLUE, 6, 20)
        text(d, (W / 2, y + bh / 2 + 210), p.get("bucle", "repeat"), 44 * kl, BLUE, "xbold")

def v_outro(img, d, t, sc, p):
    lines = p.get("lines", ["NEXT WEEK"])
    colors = p.get("colors", ["grey", "blue", "white"])
    syncs = p.get("syncs", [None] * len(lines))
    n = len(lines); gap = 150
    y0 = 430 - (n - 1) * gap / 2
    for i, ln in enumerate(lines):
        slide(d, (W / 2, y0 + i * gap), ln, p.get("size", 130), col(colors[i % len(colors)]), t,
              at(sc, syncs[i] if i < len(syncs) else None, 0.35 * i), dx=(-120 if i % 2 == 0 else 120), dy=0, maxw=1700)
    k = back(prog(t, at(sc, p.get("button_sync", "subscribe"), 1.5) - 0.1, 0.5))
    if k > 0:
        w2, h2 = 300 * k, 64 * k
        yb = y0 + n * gap + 60
        d.rounded_rectangle([W / 2 - w2, yb - h2, W / 2 + w2, yb + h2], int(h2), fill=BLUE)
        text(d, (W / 2, yb), p.get("button", "SUBSCRIBE"), 56 * k, BG)

def v_emoji(img, d, t, sc, p):
    st = at(sc, p.get("sync"), 0.1)
    k = back(prog(t, st, 0.5))
    if k > 0:
        em = ms.emoji_img(p["emoji"], int(p.get("px", 300)))
        if em is not None:
            s = 0.5 + 0.5 * k
            em2 = em.resize((max(1, int(em.width * s)), max(1, int(em.height * s))), Image.LANCZOS)
            fy = math.sin(t * 2) * 10
            img.paste(em2, (int(W / 2 - em2.width / 2), int(430 + fy - em2.height / 2)), em2)
    if p.get("texto"):
        slide(d, (W / 2, 720), p["texto"], 80, col(p.get("color"), WHITE), t, at(sc, p.get("texto_sync"), st + 0.3))

VISUALS = {
    "capitulo": v_capitulo, "titulo": v_titulo, "bigword": v_bigword, "counter": v_counter,
    "ecuacion": v_ecuacion, "versus": v_versus, "bars": v_bars, "lista": v_lista,
    "archivo": v_archivo, "numeros": v_numeros, "codigo": v_codigo, "tokens": v_tokens,
    "prediccion": v_prediccion, "bucle": v_bucle, "red": v_red, "gpu": v_gpu, "chat": v_chat,
    "ventana": v_ventana, "formula": v_formula, "flujo": v_flujo, "outro": v_outro, "emoji": v_emoji,
}

# ---------------------------------------------------------------- HUD y subtítulos
def captions(d, t, sc):
    words, times = sc["words"], sc["times"]
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        if len(cur) == 6 or w.endswith((".", ",", "?", "!", ":")):
            groups.append(cur); cur = []
    if cur: groups.append(cur)
    active = None
    for g in groups:
        if t >= times[g[0]] - 0.05: active = g
    if active is None: return
    cw = max([i for i in range(len(words)) if times[i] <= t + 0.02] or [active[0]])
    parts = [words[i] for i in active]
    size = 46
    while size > 30 and sum(d.textlength(p_ + " ", font=font(size, "xbold")) for p_ in parts) > 1600:
        size -= 2
    f = font(size, "xbold")
    widths = [d.textlength(p_ + " ", font=f) for p_ in parts]
    x = W / 2 - sum(widths) / 2
    for i, p_, wd in zip(active, parts, widths):
        d.text((x, 990), p_, font=f, fill=BLUE if i == cw else WHITE, anchor="lm", stroke_width=6, stroke_fill=(0, 0, 0))
        x += wd

def hud(d, T, total, chapter, channel):
    d.text((70, 62), channel, font=font(30, "black"), fill=(110, 120, 145), anchor="lm")
    if chapter:
        d.text((W - 70, 62), chapter, font=font(28, "bold"), fill=(110, 120, 145), anchor="rm")
    d.rectangle([0, H - 6, W, H], fill=(20, 26, 46))
    d.rectangle([0, H - 6, W * T / total, H], fill=BLUE)

# ---------------------------------------------------------------- miniatura
def thumbnail(cfg, path):
    m = cfg.get("miniatura", {})
    bg = make_background()
    img = bg.copy(); d = ImageDraw.Draw(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
    draw_net(ld, [4, 6, 6, 6, 3], 2.0, 1.0)
    layer = layer.crop((250, 120, 1670, 880)).resize((1100, 590), Image.LANCZOS)
    fade = np.clip(np.linspace(0, 2.6, layer.width), 0, 1)[None, :] * np.ones((layer.height, 1))
    a = (np.array(layer.split()[3], np.float32) * fade).astype(np.uint8)
    layer.putalpha(Image.fromarray(a))
    img.paste(layer, (W - layer.width - 40, 230), layer)
    lines = m.get("lineas", ["WHAT IS AI", "REALLY?"])
    colors = m.get("colores", ["white", "blue"])
    y = 330
    for i, ln in enumerate(lines):
        size = fit(d, ln, 210, "black", 1050)
        d.text((100, y), ln, font=font(size, "black"), fill=col(colors[i % len(colors)]), anchor="lm",
               stroke_width=10, stroke_fill=(0, 0, 0))
        y += size + 30
    if m.get("chip"):
        chip(d, 100, y + 40, m["chip"], 60, fill=WARM, fg=BG, weight="black", anchor="lm")
    d.text((100, 120), "WHITE HOLE", font=font(44, "black"), fill=GREY, anchor="lm")
    img.resize((1280, 720), Image.LANCZOS).save(path, quality=92)

# ---------------------------------------------------------------- render
def plan(cfg, durs):
    gap = cfg.get("pausa", 0.35)
    t0 = 0.0; chapter = None; chapters = [(0.0, cfg.get("intro_capitulo", "Intro"))]
    for sc, dur in zip(cfg["escenas"], durs):
        sc["start"] = t0; sc["dur"] = dur + gap
        sc["words"], sc["times"] = word_times(sc["texto"], dur)
        v = sc["visual"]
        if v["tipo"] == "capitulo":
            chapter = f"{int(v['num']):02d} · {v['titulo'].upper()}"
            chapters.append((t0, v["titulo"]))
        sc["chapter"] = chapter
        t0 += sc["dur"]
    return t0 + 1.0, chapters

def ts(s):
    s = int(s); h, r = divmod(s, 3600); m, s2 = divmod(r, 60)
    return f"{h}:{m:02d}:{s2:02d}" if h else f"{m}:{s2:02d}"

def draw_frame(bg, sc, t, T, total, channel):
    img = bg.copy(); d = ImageDraw.Draw(img)
    vis = sc["visual"]
    VISUALS[vis["tipo"]](img, d, t, sc, vis)
    fade = sc["dur"] - t
    if fade < 0.2:
        img = Image.blend(bg, img, clamp(fade / 0.2)); d = ImageDraw.Draw(img)
    captions(d, t, sc)
    hud(d, T, total, sc.get("chapter"), channel)
    return img

def render(script_path, out_path, channel="WHITE HOLE", frames_only=False):
    cfg = json.load(open(script_path, encoding="utf-8"))
    LANG["code"] = cfg.get("idioma", "en")
    scenes = cfg["escenas"]
    bg = make_background()
    if frames_only:
        os.makedirs(out_path, exist_ok=True)
        durs = [max(2.5, len(sc["texto"].split()) / 2.7) for sc in scenes]
        total, chapters = plan(cfg, durs)
        for i, sc in enumerate(scenes):
            for frac in p_fracs(sc):
                t = sc["dur"] * frac
                draw_frame(bg, sc, t, sc["start"] + t, total, channel).save(
                    os.path.join(out_path, f"s{i:02d}_{int(frac * 100):02d}_{sc['visual']['tipo']}.jpg"), quality=80)
        thumbnail(cfg, os.path.join(out_path, "miniatura.jpg"))
        print("frames ->", out_path, f"(~{total / 60:.1f} min estimado)")
        return
    work = os.path.join(os.path.dirname(os.path.abspath(out_path)), "_work_long")
    os.makedirs(work, exist_ok=True)
    print("1/4 Voz...", flush=True)
    if cfg.get("kokoro") and os.environ.get("NO_KOKORO") != "1":
        sr = ms.synth_kokoro(scenes, cfg["kokoro"], work)
    else:
        sr = ms.synth_voice(scenes, os.path.join(ms.ROOT, "voices", "en-us-ryan-high.onnx"), cfg.get("velocidad", 0.9), work)
    total, chapters = plan(cfg, [sc["audio_dur"] for sc in scenes])
    vw, mw = os.path.join(work, "voice.wav"), os.path.join(work, "music.wav")
    ms.build_voice(scenes, sr, cfg.get("pausa", 0.35), vw); ms.build_music(total, mw)
    print(f"   duración: {total:.1f}s ({total / 60:.1f} min)", flush=True)
    print("2/4 Frames...", flush=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", vw, "-i", mw,
           "-filter_complex", "[2:a]volume=0.07[m];[1:a]aresample=44100[v];[v][m]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.89[a]",
           "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_path]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nf = int(total * FPS); si = 0
    for fi in range(nf):
        T = fi / FPS
        while si + 1 < len(scenes) and scenes[si + 1]["start"] <= T: si += 1
        sc = scenes[si]
        ff.stdin.write(draw_frame(bg, sc, T - sc["start"], T, total, channel).tobytes())
        if fi % (FPS * 30) == 0: print(f"   {T / 60:.1f}/{total / 60:.1f} min", flush=True)
    ff.stdin.close(); ff.wait()
    print("3/4 Miniatura...", flush=True)
    thumbnail(cfg, out_path + ".jpg")
    meta = {"titulo": cfg.get("titulo", ""), "duracion": round(total, 1),
            "capitulos": [{"t": ts(c[0]), "titulo": c[1]} for c in chapters]}
    desc = cfg.get("descripcion", "").strip()
    meta["descripcion"] = (desc + "\n\nChapters:\n" if desc else "Chapters:\n") + \
        "\n".join(f"{c['t']} {c['titulo']}" for c in meta["capitulos"])
    if cfg.get("fuentes"):
        meta["descripcion"] += "\n\nSources:\n" + "\n".join(f"- {f}" for f in cfg["fuentes"])
    if cfg.get("hashtags"): meta["descripcion"] += "\n\n" + " ".join(cfg["hashtags"])
    json.dump(meta, open(out_path + ".meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("4/4 Listo ->", out_path, flush=True)
    return total

def p_fracs(sc):
    return sc.get("_fracs", [0.85])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("guion"); ap.add_argument("salida")
    ap.add_argument("--frames", action="store_true")
    ap.add_argument("--canal", default="WHITE HOLE")
    a = ap.parse_args()
    render(a.guion, a.salida, a.canal, a.frames)
