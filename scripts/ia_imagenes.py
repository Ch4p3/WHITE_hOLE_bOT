"""Genera imágenes con IA (Pollinations, gratis) para carruseles y Reels.
Uso: python scripts/ia_imagenes.py "prompt 1" "prompt 2" ...  -> out/ia/NN.jpg + out/ia/hoja.jpg
Nivel anónimo: 1 pedido cada ~15 s; por eso espera entre imágenes."""
import os, sys, time, requests
from urllib.parse import quote
from PIL import Image, ImageDraw

OUT = os.path.join("out", "ia"); os.makedirs(OUT, exist_ok=True)
W, H = int(os.environ.get("ANCHO", 1080)), int(os.environ.get("ALTO", 1350))
SEED = int(os.environ.get("SEMILLA", 7))

def generar(prompt, n):
    url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"
    params = {"width": W, "height": H, "model": "flux", "seed": SEED + n, "nologo": "true", "safe": "true"}
    for intento in range(4):
        r = requests.get(url, params=params, timeout=180)
        if r.ok and r.headers.get("content-type", "").startswith("image"):
            p = os.path.join(OUT, f"{n:02d}.jpg"); open(p, "wb").write(r.content); return p
        print("reintento", n, r.status_code, r.text[:120]); time.sleep(20)
    raise RuntimeError(f"No se pudo generar la imagen {n}")

paths = []
for i, pr in enumerate(sys.argv[1:]):
    if i: time.sleep(16)
    paths.append(generar(pr, i)); print("ok", i, pr[:70])
tiles = [Image.open(p).convert("RGB").resize((360, int(360 * H / W))) for p in paths]
th = tiles[0].height + 40
hoja = Image.new("RGB", (360 * min(4, len(tiles)), th * ((len(tiles) + 3) // 4)), (10, 12, 22))
d = ImageDraw.Draw(hoja)
for i, t in enumerate(tiles):
    x, y = (i % 4) * 360, (i // 4) * th
    hoja.paste(t, (x, y)); d.text((x + 8, y + t.height + 10), str(i), fill=(255, 200, 120))
hoja.save(os.path.join(OUT, "hoja.jpg"), quality=88)
