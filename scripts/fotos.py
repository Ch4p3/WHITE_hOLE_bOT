"""
Busca fotos candidatas con licencia libre en Wikimedia Commons y arma hojas de contacto
para elegirlas a ojo antes de ponerlas en un guion.

Uso: python scripts/fotos.py "hipopótamo Colombia" "Hacienda Nápoles" ...   -> out/fotos/
"""
import io, json, os, sys
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
import imagenes  # noqa: E402

OUT = os.path.join(ROOT, "out", "fotos")
os.makedirs(OUT, exist_ok=True)
F = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", "Inter-Bold.otf"), 22)
todo = {}
for qi, q in enumerate(sys.argv[1:]):
    cands = imagenes.buscar(q, n=8)
    todo[q] = cands
    sheet = Image.new("RGB", (4 * 420, 2 * 330), (12, 14, 24))
    d = ImageDraw.Draw(sheet)
    for i, c in enumerate(cands):
        try:
            im = Image.open(io.BytesIO(requests.get(c["url"], headers=imagenes.UA, timeout=60).content)).convert("RGB")
        except Exception as e:
            print("fallo", c["titulo"], e); continue
        im.thumbnail((410, 270))
        x, y = (i % 4) * 420 + 5, (i // 4) * 330 + 5
        sheet.paste(im, (x, y))
        d.text((x, y + 275), f"{i}  {c['licencia'][:18]}", font=F, fill=(255, 200, 120))
        d.text((x, y + 300), c["titulo"][5:45], font=F, fill=(200, 210, 230))
    sheet.save(os.path.join(OUT, f"q{qi:02d}.jpg"), quality=85)
    print(f"[{qi}] {q}: {len(cands)} candidatas")
json.dump(todo, open(os.path.join(OUT, "candidatas.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
