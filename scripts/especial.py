"""
Publica un video especial (ya renderizado) en las redes, con créditos de fotos y fuentes.
Uso: python scripts/especial.py video.mp4 guion.json --destino facebook|tiktok [--publicar]
Siempre lo manda a Telegram; solo sube a la red si se pasa --publicar.
"""
import argparse, json, os, sys
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "engine"))
import facebook, tiktok, imagenes  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("guion")
ap.add_argument("--destino", choices=["facebook", "tiktok"], required=True)
ap.add_argument("--publicar", action="store_true")
a = ap.parse_args()

g = json.load(open(a.guion, encoding="utf-8"))
creds = []
cp = a.video + ".creditos.json"
if os.path.exists(cp):
    for c in json.load(open(cp, encoding="utf-8")):
        creds.append(f"{c.get('autor', '')[:60]} ({c.get('licencia', '')}), Wikimedia Commons")
es = g.get("idioma") == "es"
desc = f"{g['descripcion']}\n\n{g['hashtags']}\n\n" + ("Fuentes:\n" if es else "Sources:\n") + "\n".join(g.get("fuentes", []))
if creds:
    desc += ("\n\nFotos: " if es else "\n\nPhotos: ") + "; ".join(creds)

linea = ""
if a.publicar:
    try:
        if a.destino == "facebook":
            vid, est = facebook.publicar(a.video, f"{g['titulo']}\n\n{desc}", g["titulo"])
            linea = f"\n\n📘 Facebook ({est}): https://www.facebook.com/{vid}"
        else:
            pid, est = tiktok.subir(a.video, f"{g['titulo']} {g['hashtags']}", modo="bandeja")
            linea = f"\n\n🎵 TikTok: {est}"
        print("Publicado:", linea.strip())
    except Exception as e:
        linea = f"\n\n⚠️ No se pudo publicar en {a.destino}: {str(e)[:300]}"
        print(linea)

cap = (f"🎬 {g['titulo']}\n\n{g['descripcion']}\n\n{g['hashtags']}{linea}")[:1024]
with open(a.video, "rb") as f:
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_TOKEN']}/sendVideo",
                      data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "caption": cap, "supports_streaming": "true"},
                      files={"video": ("video.mp4", f, "video/mp4")}, timeout=300)
print("Telegram:", r.status_code)
