"""
Publica un video en TikTok con la Content Posting API (Direct Post, subida de archivo).

Ojo: mientras la app de TikTok no pase la auditoría, TikTok obliga a que todo lo publicado
quede en privado (SELF_ONLY) y la cuenta tiene que estar en privado. Por eso la subida se
enciende en config.json ("tiktok": {"subir": true}) solo después de la aprobación.

Secretos necesarios:
  TT_CLIENT_KEY, TT_CLIENT_SECRET   de la app en developers.tiktok.com
  TT_REFRESH_TOKEN                  del usuario (scopes user.info.basic, video.publish)

Uso:  python scripts/tiktok.py --verificar
      python scripts/tiktok.py --subir out/short.mp4 "título #tags"
"""
import os, sys, time, argparse
import requests

API = "https://open.tiktokapis.com/v2"


class TikTokError(Exception):
    pass


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tt_token  # noqa: E402


def _refresh():
    return tt_token.leer() or os.environ.get("TT_REFRESH_TOKEN", "").strip()


def creds_disponibles():
    return all(os.environ.get(k, "").strip() for k in ("TT_CLIENT_KEY", "TT_CLIENT_SECRET")) and bool(_refresh())


def access_token():
    r = requests.post(f"{API}/oauth/token/", timeout=60,
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      data={"client_key": os.environ["TT_CLIENT_KEY"].strip(),
                            "client_secret": os.environ["TT_CLIENT_SECRET"].strip(),
                            "grant_type": "refresh_token",
                            "refresh_token": _refresh()})
    d = r.json()
    if "access_token" not in d:
        raise TikTokError(f"No se pudo renovar el token de TikTok: {str(d)[:300]}")
    if d.get("refresh_token") and d["refresh_token"] != _refresh():
        tt_token.guardar(d["refresh_token"])      # TikTok rota el token: se guarda cifrado en .tokens/
        print("🔁 Refresh token de TikTok renovado y guardado (cifrado).")
    return d["access_token"]


def _post(token, path, body):
    r = requests.post(f"{API}{path}", json=body, timeout=60,
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"})
    d = r.json()
    err = d.get("error", {})
    if err.get("code") not in (None, "ok"):
        raise TikTokError(f"TikTok {path}: {err.get('code')} — {err.get('message', '')[:200]}")
    return d.get("data", {})


def _put(url, video_path, size):
    with open(video_path, "rb") as f:
        up = requests.put(url, data=f, timeout=600, headers={
            "Content-Type": "video/mp4", "Content-Length": str(size),
            "Content-Range": f"bytes 0-{size - 1}/{size}"})
    if up.status_code not in (200, 201):
        raise TikTokError(f"Falló la subida a TikTok: {up.status_code} {up.text[:200]}")


def creador(token):
    return _post(token, "/post/publish/creator_info/query/", {})


def subir(video_path, titulo, privacidad="PUBLIC_TO_EVERYONE", modo="bandeja"):
    """Sube el video. modo="bandeja": llega a la bandeja de TikTok y uno le da Publicar en la app
    (no necesita auditoría). modo="directo": publica de una (solo público tras la auditoría).
    Devuelve (publish_id, estado)."""
    token = access_token()
    size = os.path.getsize(video_path)
    if modo == "bandeja":
        data = _post(token, "/post/publish/inbox/video/init/", {
            "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                            "chunk_size": size, "total_chunk_count": 1}})
        _put(data["upload_url"], video_path, size)
        pid = data["publish_id"]
        estado = "enviado"
        for _ in range(18):
            time.sleep(10)
            st = _post(token, "/post/publish/status/fetch/", {"publish_id": pid})
            estado = st.get("status", estado)
            if estado in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
                break
            if estado == "FAILED":
                raise TikTokError(f"TikTok rechazó el video: {st.get('fail_reason')}")
        return pid, ("en tu bandeja de TikTok, listo para publicar" if estado == "SEND_TO_USER_INBOX" else estado)
    info = creador(token)
    opciones = info.get("privacy_level_options", [])
    if privacidad not in opciones:
        privacidad = "SELF_ONLY" if "SELF_ONLY" in opciones else (opciones[0] if opciones else "SELF_ONLY")
    if size > 64 * 1024 * 1024:
        raise TikTokError("El video pesa más de 64 MB; habría que subirlo por partes.")
    data = _post(token, "/post/publish/video/init/", {
        "post_info": {"title": titulo[:2200], "privacy_level": privacidad,
                      "disable_comment": False, "disable_duet": False, "disable_stitch": False,
                      "is_aigc": True},
        "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                        "chunk_size": size, "total_chunk_count": 1}})
    pid = data["publish_id"]
    _put(data["upload_url"], video_path, size)
    estado = "enviado"
    for _ in range(30):
        time.sleep(10)
        st = _post(token, "/post/publish/status/fetch/", {"publish_id": pid})
        estado = st.get("status", estado)
        if estado == "PUBLISH_COMPLETE":
            break
        if estado == "FAILED":
            raise TikTokError(f"TikTok rechazó el video: {st.get('fail_reason')}")
    return pid, f"{estado} ({privacidad})"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--subir", nargs=2, metavar=("VIDEO", "TITULO"))
    a = ap.parse_args()
    if not creds_disponibles():
        sys.exit("Faltan TT_CLIENT_KEY, TT_CLIENT_SECRET y/o TT_REFRESH_TOKEN.")
    if a.verificar:
        tok = access_token()
        try:
            info = creador(tok)
            print(f"✅ Conexión con TikTok OK. Cuenta: @{info.get('creator_username')} · "
                  f"privacidades permitidas: {info.get('privacy_level_options')}")
        except TikTokError as e:
            print(f"✅ Token de TikTok OK (la consulta de perfil respondió: {e})")
    if a.subir:
        print(subir(*a.subir))
