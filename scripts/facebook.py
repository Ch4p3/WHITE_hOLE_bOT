"""
Publica un video vertical como Reel en la Página de Facebook (Reels Publishing API).

Secretos necesarios (GitHub → Settings → Secrets → Actions):
  FB_PAGE_ID     ID numérico de la Página White Hole
  FB_PAGE_TOKEN  token de Página de larga duración (no expira) con pages_manage_posts

Uso:  python scripts/facebook.py --verificar
      python scripts/facebook.py --subir out/short.mp4 "descripción #tags"
"""
import os, sys, time, argparse
import requests

GRAPH = "https://graph.facebook.com/v25.0"


class FacebookError(Exception):
    pass


def creds_disponibles():
    return bool(os.environ.get("FB_PAGE_ID", "").strip() and os.environ.get("FB_PAGE_TOKEN", "").strip())


def _ids():
    return os.environ["FB_PAGE_ID"].strip(), os.environ["FB_PAGE_TOKEN"].strip()


def _check(r):
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text[:300]}
    if not r.ok or (isinstance(data, dict) and "error" in data):
        err = data.get("error", data) if isinstance(data, dict) else data
        raise FacebookError(f"Facebook {r.status_code}: {str(err)[:400]}")
    return data


def pagina():
    page_id, token = _ids()
    return _check(requests.get(f"{GRAPH}/{page_id}", params={"fields": "id,name,link", "access_token": token}, timeout=60))


def subir_reel(video_path, descripcion, titulo=None, esperar=True):
    """Sube y publica el Reel. Devuelve (video_id, estado)."""
    page_id, token = _ids()
    # 1) abrir sesión de subida
    ini = _check(requests.post(f"{GRAPH}/{page_id}/video_reels",
                               data={"upload_phase": "start", "access_token": token}, timeout=60))
    video_id, upload_url = ini["video_id"], ini["upload_url"]
    # 2) subir los bytes a rupload.facebook.com
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        up = requests.post(upload_url, data=f, timeout=600, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size),
            "Content-Type": "application/octet-stream"})
    res = _check(up)
    if not res.get("success", True):
        raise FacebookError(f"La subida no se completó: {res}")
    # 3) cerrar la sesión y publicar
    params = {"upload_phase": "finish", "video_id": video_id, "video_state": "PUBLISHED",
              "description": descripcion[:2200], "access_token": token}
    if titulo:
        params["title"] = titulo[:255]
    fin = _check(requests.post(f"{GRAPH}/{page_id}/video_reels", data=params, timeout=120))
    if not fin.get("success", True):
        raise FacebookError(f"Facebook no aceptó la publicación: {fin}")
    estado = "enviado"
    if esperar:
        for _ in range(30):  # hasta ~5 min
            time.sleep(10)
            st = _check(requests.get(f"{GRAPH}/{video_id}", params={"fields": "status", "access_token": token},
                                     timeout=60)).get("status", {})
            vs = st.get("video_status")
            pub = (st.get("publishing_phase") or {}).get("status")
            if vs == "error" or pub == "error":
                raise FacebookError(f"Facebook rechazó el video: {st}")
            if pub == "complete" or vs == "ready" and pub in (None, "complete"):
                estado = "publicado"
                break
            estado = f"procesando ({vs}/{pub})"
    return video_id, estado


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--subir", nargs=2, metavar=("VIDEO", "DESCRIPCION"))
    a = ap.parse_args()
    if not creds_disponibles():
        sys.exit("Faltan FB_PAGE_ID y/o FB_PAGE_TOKEN.")
    if a.verificar:
        p = pagina()
        print(f"✅ Conexión con Facebook OK. Página: {p.get('name')}")
    if a.subir:
        vid, est = subir_reel(*a.subir)
        print(f"Reel {vid}: {est}")
