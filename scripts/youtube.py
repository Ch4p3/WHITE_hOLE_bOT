"""
Subida a YouTube con la API oficial (YouTube Data API v3), solo con `requests`.

Credenciales (secretos de GitHub): YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
Uso directo para verificar la conexión:  python scripts/youtube.py --verificar
"""
import os, sys, json, argparse
import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"

def creds_disponibles():
    return all(os.environ.get(k, "").strip() for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))

def access_token():
    r = requests.post(TOKEN_URL, timeout=60, data={
        "client_id": os.environ["YT_CLIENT_ID"].strip(),
        "client_secret": os.environ["YT_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["YT_REFRESH_TOKEN"].strip(),
        "grant_type": "refresh_token"})
    if not r.ok:
        raise RuntimeError(f"No se pudo renovar el permiso de YouTube ({r.status_code}): {r.text[:200]}")
    return r.json()["access_token"]

def canal(token):
    r = requests.get(f"{API}/channels", params={"part": "snippet,status", "mine": "true"},
                     headers={"Authorization": f"Bearer {token}"}, timeout=60)
    r.raise_for_status()
    items = r.json().get("items", [])
    return items[0] if items else None

def subir(video_path, titulo, descripcion, tags, privacidad="public", publicar_en=None):
    """Sube el video con subida reanudable y devuelve (video_id, estado_privacidad)."""
    token = access_token()
    meta = {
        "snippet": {"title": titulo[:100], "description": descripcion[:4900],
                    "tags": tags[:15], "categoryId": "28"},       # 28 = Ciencia y tecnología
        "status": {"privacyStatus": privacidad, "selfDeclaredMadeForKids": False,
                   "embeddable": True},
    }
    if publicar_en:                      # programado: YouTube exige privado + publishAt
        meta["status"]["privacyStatus"] = "private"; meta["status"]["publishAt"] = publicar_en
    size = os.path.getsize(video_path)
    init = requests.post(UPLOAD, params={"uploadType": "resumable", "part": "snippet,status"},
                         headers={"Authorization": f"Bearer {token}",
                                  "Content-Type": "application/json; charset=UTF-8",
                                  "X-Upload-Content-Type": "video/mp4",
                                  "X-Upload-Content-Length": str(size)},
                         data=json.dumps(meta), timeout=60)
    if not init.ok:
        raise RuntimeError(f"YouTube rechazó la subida ({init.status_code}): {init.text[:300]}")
    with open(video_path, "rb") as f:
        up = requests.put(init.headers["Location"], data=f, timeout=600,
                          headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
    if not up.ok:
        raise RuntimeError(f"Falló la subida ({up.status_code}): {up.text[:300]}")
    v = up.json()
    return v["id"], v.get("status", {}).get("privacyStatus")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verificar", action="store_true")
    a = ap.parse_args()
    if not creds_disponibles():
        sys.exit("Faltan los secretos YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN.")
    c = canal(access_token())
    if not c:
        sys.exit("El permiso funciona, pero la cuenta no tiene canal de YouTube.")
    print("✅ Conexión con YouTube OK. Canal:", c["snippet"].get("title") or "(sin nombre todavía)")
