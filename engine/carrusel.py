"""
White Hole · generador de carruseles (Instagram / Facebook), 1080x1350 (4:5).

Uso:  python engine/carrusel.py guiones/carruseles/pendientes/x.json carpeta_salida
Guion:
{
  "titulo": "...", "caption": "...", "hashtags": "...", "fuentes": [...],
  "palabra": "RUTINA", "enlace": "https://...",            (opcional: comenta PALABRA y te lo envío)
  "personaje": "monita",                                     (por defecto para las poses)
  "slides": [
    {"tipo": "portada", "pre": "RUTINA EN CASA", "titulo": "GLÚTEOS SIN PESAS", "sub": "4 ejercicios · 15 min", "pose": "puente"},
    {"tipo": "item", "titulo": "PUENTE DE GLÚTEO", "dosis": "3 × 15", "puntos": ["...", "..."], "pose": "puente"},
    {"tipo": "texto", "titulo": "...", "puntos": ["...", "..."], "emoji": "💡"},
    {"tipo": "foto", "src": "commons:File:....jpg", "titulo": "...", "texto": "..."},
    {"tipo": "cierre"}
  ]
}
"""
import json, os, sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_short as M   # noqa: E402
import monitos           # noqa: E402

W, H = 1080, 1350
BG, BLUE, ICE, WHITE, GREY, WARM, PANEL = M.BG, M.BLUE, M.ICE, M.WHITE, M.GREY, M.WARM, M.PANEL
HANDLE = "@whi.tehole1"
LOGO = os.path.join(M.ROOT, "assets", "marca", "icon_1024.png")


def F(size, weight="black"):
    return M.font(size, weight)


def wrap(d, text, size, weight, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=F(size, weight)) <= maxw: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


def block(d, xy, text, size, fill, weight="black", maxw=940, gap=1.12, anchor="la", max_lines=None):
    x, y = xy
    lines = wrap(d, text, size, weight, maxw)
    while max_lines and len(lines) > max_lines and size > 30:
        size -= 4; lines = wrap(d, text, size, weight, maxw)
    for ln in lines:
        d.text((x, y), ln, font=F(size, weight), fill=fill, anchor=anchor)
        y += int(size * gap)
    return y


def fondo():
    img = M.make_background().resize((W, int(1920 * W / 1080))).crop((0, 280, W, 280 + H))
    return img


def marca(img, d, idx, total):
    try:
        lg = Image.open(LOGO).convert("RGBA").resize((56, 56), Image.LANCZOS)
        m = Image.new("L", (56, 56), 0); ImageDraw.Draw(m).ellipse([0, 0, 55, 55], fill=255)
        img.paste(lg, (60, 52), m)
    except Exception:
        pass
    d.text((130, 80), "White Hole", font=F(32, "black"), fill=WHITE, anchor="lm")
    d.text((W - 60, 80), f"{idx}/{total}", font=F(30, "bold"), fill=GREY, anchor="rm")


def monito_png(pose, personaje, t=0.55, escala=None):
    """Dibuja el monito (pose de un instante) y devuelve el recorte RGBA sobre el fondo del canal."""
    canvas = Image.new("RGB", (1080, 1920), BG)
    d = ImageDraw.Draw(canvas)
    sc = {"start": 0, "dur": 3, "words": ["x"], "times": [0], "texto": "x"}
    p = {"tipo": "monito", "pose": pose, "personaje": personaje, "colchoneta": pose in monitos.LADO and pose not in ("escalon", "caminar")}
    if escala: p["escala"] = escala
    monitos.v_monito(canvas, d, t, sc, p, M)
    return canvas.crop((0, 440, 1080, 1340))


def prep_monito(pose, personaje, alto=560, t=0.55, maxw=960):
    import numpy as np
    fig = monito_png(pose, personaje, t)
    a = np.asarray(fig).astype(np.int16)
    diff = np.abs(a - np.array(BG, np.int16)).sum(axis=2)
    alpha = np.clip((diff - 6) * 12, 0, 255).astype(np.uint8)      # fondo -> transparente
    rgba = fig.convert("RGBA"); rgba.putalpha(Image.fromarray(alpha))
    bb = rgba.getchannel("A").point(lambda v: 255 if v > 60 else 0).getbbox() or (0, 0, fig.width, fig.height)
    rgba = rgba.crop((max(0, bb[0] - 20), max(0, bb[1] - 20), min(fig.width, bb[2] + 20), min(fig.height, bb[3] + 10)))
    r = min(alto / rgba.height, maxw / rgba.width)
    return rgba.resize((int(rgba.width * r), int(rgba.height * r)), Image.LANCZOS)


def pega_monito(img, pose, personaje, y, alto=560, t=0.55, maxw=960):
    rgba = prep_monito(pose, personaje, alto, t, maxw)
    img.paste(rgba, ((W - rgba.width) // 2, y), rgba)
    return y + rgba.height


def chip(d, x, y, text, fill=WARM, fg=BG, size=34, anchor="l"):
    f = F(size, "black"); tw = d.textlength(text, font=f); h = int(size * 1.7)
    x0 = x if anchor == "l" else x - tw / 2 - 26
    d.rounded_rectangle([x0, y, x0 + tw + 52, y + h], h // 2, fill=fill)
    d.text((x0 + 26 + tw / 2, y + h / 2), text, font=f, fill=fg, anchor="mm")
    return x0 + tw + 52


def s_portada(g, s, idx, total):
    img = fondo(); d = ImageDraw.Draw(img); marca(img, d, idx, total)
    y = 190
    if s.get("pre"): chip(d, W / 2, y, s["pre"], anchor="c"); y += 100
    y = block(d, (W / 2, y), s["titulo"], 104, WHITE, maxw=960, anchor="ma", max_lines=3) + 6
    if s.get("sub"): y = block(d, (W / 2, y + 4), s["sub"], 46, ICE, "xbold", maxw=900, anchor="ma") + 10
    if s.get("pose"):
        fig = prep_monito(s["pose"], s.get("personaje", g.get("personaje", "monita")), min(640, H - y - 240))
        y0 = y + max(30, ((H - 150) - y - fig.height) // 2)
        img.paste(fig, ((W - fig.width) // 2, y0), fig)
    elif s.get("emoji"):
        em = M.emoji_img(s["emoji"], 360)
        if em: img.paste(em, ((W - em.width) // 2, max(y + 40, 700)), em)
    d = ImageDraw.Draw(img)
    chip(d, W / 2, H - 120, "Desliza  →", fill=BLUE, anchor="c")
    return img


def s_item(g, s, idx, total, n):
    img = fondo(); d = ImageDraw.Draw(img); marca(img, d, idx, total)
    x = 70
    d.rounded_rectangle([x, 160, x + 96, 256], 26, fill=BLUE)
    d.text((x + 48, 208), str(s.get("num", n)), font=F(60, "black"), fill=BG, anchor="mm")
    block(d, (x + 124, 162), s["titulo"], 62, WHITE, maxw=W - x - 124 - 60, max_lines=2)
    y = 300
    if s.get("dosis"):
        chip(d, x, y, s["dosis"], fill=WARM, size=40); y += 100
    pts_h = sum(len(wrap(d, pt, 46, "xbold", W - x - 50 - 60)) * 52 + 18 for pt in s.get("puntos", []))
    if s.get("pose"):
        alto = max(380, min(640, H - y - 80 - pts_h - 50))
        fig = prep_monito(s["pose"], s.get("personaje", g.get("personaje", "monita")), alto, s.get("t", 0.55))
        libre = (H - 70) - y - fig.height - 40 - pts_h
        y += max(0, libre // 2)
        img.paste(fig, ((W - fig.width) // 2, y), fig); y += fig.height + 40
    d = ImageDraw.Draw(img)
    for pt in s.get("puntos", []):
        d.ellipse([x + 4, y + 18, x + 26, y + 40], fill=BLUE)
        y = block(d, (x + 50, y), pt, 46, WHITE, "xbold", maxw=W - x - 50 - 60) + 18
    return img


def s_texto(g, s, idx, total):
    img = fondo(); d = ImageDraw.Draw(img); marca(img, d, idx, total)
    x, y = 70, 170
    if s.get("emoji"):
        em = M.emoji_img(s["emoji"], 150)
        if em: img.paste(em, (x, y), em); y += 180
    d = ImageDraw.Draw(img)
    y = block(d, (x, y), s["titulo"], 80, s.get("color") and M.col(s["color"]) or WHITE, maxw=W - 140, max_lines=3) + 30
    for i, pt in enumerate(s.get("puntos", [])):
        d.rounded_rectangle([x, y, W - x, y + 4], 2, fill=(34, 44, 74)); y += 34
        y = block(d, (x, y), pt, 52, ICE if i % 2 == 0 else WHITE, "xbold", maxw=W - 140) + 30
    if s.get("nota"):
        block(d, (x, H - 130), s["nota"], 28, GREY, "semi", maxw=W - 140)
    return img


def s_foto(g, s, idx, total):
    import imagenes
    img = fondo()
    ruta, info = imagenes.obtener(s["src"])
    ph = Image.open(ruta).convert("RGB")
    r = max(W / ph.width, 760 / ph.height)
    ph = ph.resize((int(ph.width * r) + 1, int(ph.height * r) + 1), Image.LANCZOS)
    fx = s.get("foco", [0.5, 0.5])
    cx = min(max(int(ph.width * fx[0]) - W // 2, 0), ph.width - W); cy = min(max(int(ph.height * fx[1]) - 380, 0), ph.height - 760)
    img.paste(ph.crop((cx, cy, cx + W, cy + 760)), (0, 140))
    d = ImageDraw.Draw(img); marca(img, d, idx, total)
    d.rectangle([0, 0, W, 130], fill=BG); marca(img, d, idx, total)
    d.text((W - 30, 890), imagenes.credito_corto(info)[:80], font=F(20, "semi"), fill=GREY, anchor="rs")
    y = block(d, (70, 930), s["titulo"], 62, s.get("color") and M.col(s["color"]) or WHITE, maxw=W - 140, max_lines=2) + 14
    if s.get("texto"): block(d, (70, y), s["texto"], 40, ICE, "xbold", maxw=W - 140, max_lines=4)
    return img


def s_cierre(g, s, idx, total):
    img = fondo(); d = ImageDraw.Draw(img); marca(img, d, idx, total)
    y = 230
    pal = s.get("palabra") or g.get("palabra")
    if pal:
        y = block(d, (W / 2, y), "¿La quieres completa?", 70, WHITE, maxw=960, anchor="ma") + 30
        d.text((W / 2, y + 20), "Comenta", font=F(54, "xbold"), fill=ICE, anchor="ma"); y += 100
        tw = d.textlength(pal, font=F(130, "black"))
        d.rounded_rectangle([W / 2 - tw / 2 - 50, y, W / 2 + tw / 2 + 50, y + 190], 40, fill=WARM)
        d.text((W / 2, y + 95), pal, font=F(130, "black"), fill=BG, anchor="mm"); y += 240
        y = block(d, (W / 2, y), s.get("promesa", "y te respondo con el enlace"), 46, ICE, "xbold", maxw=900, anchor="ma") + 40
    else:
        y = block(d, (W / 2, y), s.get("titulo", "¿Te sirvió?"), 76, WHITE, maxw=960, anchor="ma") + 40
    for icon, txt in [("🔖", "Guárdalo para después"), ("📤", "Compártelo con quien lo necesite"), ("➕", "Sígueme: " + HANDLE)]:
        em = M.emoji_img(icon, 64)
        if em: img.paste(em, (180, y), em)
        d.text((270, y + 32), txt, font=F(40, "xbold"), fill=WHITE, anchor="lm"); y += 100
    if g.get("fuentes"):
        d.text((W / 2, H - 70), "Fuentes en la descripción", font=F(26, "semi"), fill=GREY, anchor="mm")
    return img


def render(guion_path, outdir):
    g = json.load(open(guion_path, encoding="utf-8"))
    M.LANG["code"] = g.get("idioma", "es")
    os.makedirs(outdir, exist_ok=True)
    slides, total, n = [], len(g["slides"]), 0
    for i, s in enumerate(g["slides"], 1):
        tp = s.get("tipo", "texto")
        if tp == "portada": im = s_portada(g, s, i, total)
        elif tp == "item": n += 1; im = s_item(g, s, i, total, n)
        elif tp == "foto": im = s_foto(g, s, i, total)
        elif tp == "cierre": im = s_cierre(g, s, i, total)
        else: im = s_texto(g, s, i, total)
        p = os.path.join(outdir, f"slide_{i:02d}.jpg")
        im.convert("RGB").save(p, quality=92)
        slides.append(p)
    return g, slides


if __name__ == "__main__":
    g, s = render(sys.argv[1], sys.argv[2])
    print("\n".join(s))
