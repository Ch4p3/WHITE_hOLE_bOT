"""
Tarea diaria: toma el próximo guion pendiente, genera el Short y te lo manda a Telegram
con el título, la descripción y los hashtags listos para copiar. Luego mueve el guion
a guiones/publicados/ para no repetirlo.

Uso local de prueba (sin Telegram y sin mover nada):  python scripts/daily.py --prueba
"""
import os, sys, json, glob, shutil, datetime, argparse
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from make_short import render  # noqa: E402

PEND = os.path.join(ROOT, "guiones", "pendientes")
PUB = os.path.join(ROOT, "guiones", "publicados")
VOZ = os.path.join(ROOT, "voices", "en-us-ryan-high.onnx")
OUT = os.path.join(ROOT, "out")

def telegram(method, token, **kw):
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", timeout=120, **kw)
    if not r.ok:
        raise SystemExit(f"Telegram respondió {r.status_code}: {r.text[:300]}")
    return r.json()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prueba", action="store_true", help="no envía a Telegram ni mueve el guion")
    ap.add_argument("--voz", default=VOZ)
    a = ap.parse_args()

    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not a.prueba and (not token or not chat):
        raise SystemExit("Faltan los secretos TELEGRAM_TOKEN y/o TELEGRAM_CHAT_ID en GitHub "
                         "(Settings → Secrets and variables → Actions).")

    pendientes = sorted(glob.glob(os.path.join(PEND, "*.json")))
    if not pendientes:
        msg = "⚠️ White Hole: no quedan guiones pendientes. Pídele a Claude un nuevo lote."
        print(msg)
        if not a.prueba:
            telegram("sendMessage", token, data={"chat_id": chat, "text": msg})
        return

    guion = pendientes[0]
    cfg = json.load(open(guion, encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    video = os.path.join(OUT, "short.mp4")
    print("Generando:", os.path.basename(guion))
    render(guion, video, a.voz)

    quedan = len(pendientes) - 1
    caption = (f"🎬 {cfg.get('titulo', '')}\n\n"
               f"{cfg.get('descripcion', '')}\n\n"
               f"{cfg.get('hashtags', '')}\n\n"
               f"📚 Fuentes:\n" + "\n".join(cfg.get("fuentes", [])) +
               f"\n\n📦 Quedan {quedan} guiones en cola.")[:1024]
    if a.prueba:
        print("---- caption ----\n" + caption)
        print("Video de prueba en:", video)
        return

    with open(video, "rb") as f:
        telegram("sendVideo", token, data={"chat_id": chat, "caption": caption, "supports_streaming": "true"},
                 files={"video": ("short.mp4", f, "video/mp4")})
    os.makedirs(PUB, exist_ok=True)
    hoy = datetime.date.today().isoformat()
    shutil.move(guion, os.path.join(PUB, f"{hoy}_{os.path.basename(guion)}"))
    print("Enviado a Telegram y movido a publicados.")

if __name__ == "__main__":
    main()
