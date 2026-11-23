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
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import youtube  # noqa: E402

PEND = os.path.join(ROOT, "guiones", "pendientes")
PUB = os.path.join(ROOT, "guiones", "publicados")
VOZ = os.path.join(ROOT, "voices", "en-us-ryan-high.onnx")
OUT = os.path.join(ROOT, "out")

class TelegramError(Exception):
    pass

def telegram(method, token, **kw):
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", timeout=120, **kw)
    if not r.ok:
        raise TelegramError(f"Telegram respondió {r.status_code}: {r.text[:300]}")
    return r.json()

def diagnose_chat(token):
    """Si el chat_id no sirve, mira quién le ha escrito al bot y propone el ID correcto."""
    me = telegram("getMe", token)["result"]
    print(f"Bot conectado: @{me.get('username')} ({me.get('first_name')})")
    ups = telegram("getUpdates", token)["result"]
    chats = {}
    for u in ups:
        m = u.get("message") or u.get("edited_message") or {}
        c = m.get("chat", {})
        if c.get("type") == "private":
            chats[c["id"]] = c.get("first_name", "")
    for cid, name in chats.items():
        print(f"  Chat privado encontrado: ...{str(cid)[-3:]}")
    return list(chats)

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
            try:
                telegram("sendMessage", token, data={"chat_id": chat, "text": msg})
            except TelegramError as e:
                raise SystemExit(str(e))
        return

    guion = pendientes[0]
    cfg = json.load(open(guion, encoding="utf-8"))
    os.makedirs(OUT, exist_ok=True)
    video = os.path.join(OUT, "short.mp4")
    print("Generando:", os.path.basename(guion))
    render(guion, video, a.voz)

    quedan = len(pendientes) - 1
    yt_line = ""
    conf = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8")).get("youtube", {})
    if conf.get("subir") and youtube.creds_disponibles() and not a.prueba:
        try:
            tags = [t.lstrip("#") for t in cfg.get("hashtags", "").split()]
            desc = (cfg.get("descripcion", "") + "\n\n" + cfg.get("hashtags", "") +
                    "\n\nSources:\n" + "\n".join(cfg.get("fuentes", [])))
            vid, estado = youtube.subir(video, cfg.get("titulo", "White Hole"), desc, tags,
                                        conf.get("privacidad", "public"))
            yt_line = f"\n\n▶️ YouTube ({estado}): https://youtube.com/shorts/{vid}"
            print("Subido a YouTube:", vid, estado)
        except Exception as e:
            yt_line = f"\n\n⚠️ No se pudo subir a YouTube: {str(e)[:200]}"
            print(yt_line)
    caption = (f"🎬 {cfg.get('titulo', '')}\n\n"
               f"{cfg.get('descripcion', '')}\n\n"
               f"{cfg.get('hashtags', '')}\n\n"
               f"📚 Fuentes:\n" + "\n".join(cfg.get("fuentes", [])) +
               f"{yt_line}\n\n📦 Quedan {quedan} guiones en cola.")[:1024]
    if a.prueba:
        print("---- caption ----\n" + caption)
        print("Video de prueba en:", video)
        return

    def send(cid):
        with open(video, "rb") as f:
            telegram("sendVideo", token, data={"chat_id": cid, "caption": caption, "supports_streaming": "true"},
                     files={"video": ("short.mp4", f, "video/mp4")})
    try:
        send(chat)
    except TelegramError as e:
        if "chat not found" not in str(e):
            raise SystemExit(str(e))
        print("El TELEGRAM_CHAT_ID guardado no funciona. Buscando el chat correcto...")
        found = diagnose_chat(token)
        if len(found) != 1:
            raise SystemExit("No pude deducir el chat. Escríbele /start al bot y vuelve a intentar.")
        send(found[0])
        print("✅ Enviado usando el chat detectado. Revisa el secreto TELEGRAM_CHAT_ID.")
    os.makedirs(PUB, exist_ok=True)
    hoy = datetime.date.today().isoformat()
    shutil.move(guion, os.path.join(PUB, f"{hoy}_{os.path.basename(guion)}"))
    print("Enviado a Telegram y movido a publicados.")

if __name__ == "__main__":
    main()
