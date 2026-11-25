"""
Publica Reels en la cuenta de Instagram conectada a la Página de Facebook (Instagram Graph API).
Usa el mismo token de Página (FB_PAGE_TOKEN); necesita los permisos instagram_basic e
instagram_content_publish. El video debe estar en una URL pública (p. ej. raw.githubusercontent.com).

Uso:  python scripts/instagram.py --verificar
      python scripts/instagram.py --reel URL_VIDEO "texto del post"
"""
import os, sys, time, argparse
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from facebook import GRAPH, _ids, _check  # noqa: E402


def cuenta():
    page_id, token = _ids()
    d = _check(requests.get(f"{GRAPH}/{page_id}", params={"fields": "instagram_business_account{id,username}",
                                                          "access_token": token}, timeout=60))
    ig = d.get("instagram_business_account")
    if not ig:
        raise SystemExit("La Página no tiene una cuenta de Instagram profesional conectada (o el token no tiene instagram_basic).")
    return ig["id"], ig.get("username")


def permisos():
    _, token = _ids()
    try:
        d = requests.get(f"{GRAPH}/me/permissions", params={"access_token": token}, timeout=60).json()
        return [p["permission"] for p in d.get("data", []) if p.get("status") == "granted"]
    except Exception:
        return []


def reel(video_url, caption, compartir_en_feed=True):
    ig_id, _ = cuenta()
    _, token = _ids()
    c = _check(requests.post(f"{GRAPH}/{ig_id}/media", data={
        "media_type": "REELS", "video_url": video_url, "caption": caption[:2200],
        "share_to_feed": "true" if compartir_en_feed else "false", "access_token": token}, timeout=120))
    cid = c["id"]
    for _ in range(60):
        st = _check(requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code,status", "access_token": token}, timeout=60))
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise SystemExit(f"Instagram no pudo procesar el video: {st}")
        time.sleep(10)
    p = _check(requests.post(f"{GRAPH}/{ig_id}/media_publish", data={"creation_id": cid, "access_token": token}, timeout=120))
    return p.get("id")


def _url_publica(video_path):
    """Sube el archivo a la rama previews (API de GitHub) y devuelve su URL raw pública."""
    import base64
    repo, gh = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (repo and gh):
        raise RuntimeError("Sin GITHUB_TOKEN/GITHUB_REPOSITORY para publicar el video")
    ruta = "ig/" + time.strftime("%Y%m%d_%H%M%S_") + os.path.basename(video_path)
    with open(video_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    r = requests.put(f"https://api.github.com/repos/{repo}/contents/{ruta}",
                     headers={"Authorization": f"Bearer {gh}", "Accept": "application/vnd.github+json"},
                     json={"message": f"Reel IG {os.path.basename(video_path)}", "content": b64, "branch": "previews"},
                     timeout=600)
    r.raise_for_status()
    sha = r.json()["commit"]["sha"]
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{ruta}"


def reel_local(video_path, caption, compartir_en_feed=True):
    """Sube un archivo local como Reel. Intenta la subida reanudable y, si Meta la rechaza,
    publica el archivo en la rama previews y usa su URL pública."""
    try:
        return _reel_reanudable(video_path, caption, compartir_en_feed)
    except Exception as e:
        print("ℹ️ Subida reanudable rechazada, uso URL pública:", str(e)[:160])
    return reel(_url_publica(video_path), caption, compartir_en_feed)


def _reel_reanudable(video_path, caption, compartir_en_feed=True):
    ig_id, _ = cuenta()
    _, token = _ids()
    c = _check(requests.post(f"{GRAPH}/{ig_id}/media", data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption[:2200],
        "share_to_feed": "true" if compartir_en_feed else "false", "access_token": token}, timeout=120))
    cid = c["id"]
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        r = requests.post(f"https://rupload.facebook.com/ig-api-upload/v25.0/{cid}",
                          headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)},
                          data=f, timeout=900)
    _check(r)
    for _ in range(90):
        st = _check(requests.get(f"{GRAPH}/{cid}", params={"fields": "status_code,status", "access_token": token}, timeout=60))
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram no pudo procesar el video: {st}")
        time.sleep(10)
    p = _check(requests.post(f"{GRAPH}/{ig_id}/media_publish", data={"creation_id": cid, "access_token": token}, timeout=120))
    return p.get("id")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--reel", nargs=2, metavar=("URL", "TEXTO"))
    ap.add_argument("--archivo", nargs=2, metavar=("VIDEO", "TEXTO"))
    a = ap.parse_args()
    if a.verificar:
        print("Permisos del token:", ", ".join(permisos()) or "(no se pudieron leer)")
        ig_id, user = cuenta()
        print(f"✅ Instagram conectado: @{user} (id {ig_id})")
    if a.archivo:
        print("✅ Reel publicado en Instagram:", reel_local(*a.archivo))
    if a.reel:
        print("✅ Reel publicado en Instagram:", reel(*a.reel))
