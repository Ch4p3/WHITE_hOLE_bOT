"""Guarda el refresh token de TikTok cifrado en el repo (.tokens/tt_refresh.enc).
La llave sale del secreto TT_CLIENT_SECRET, así que solo los workflows pueden leerlo."""
import os, base64, hashlib
from cryptography.fernet import Fernet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA = os.path.join(ROOT, ".tokens", "tt_refresh.enc")

def _f():
    k = hashlib.sha256(("whitehole-tt:" + os.environ["TT_CLIENT_SECRET"].strip()).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(k))

def leer():
    if not os.path.exists(RUTA) or not os.environ.get("TT_CLIENT_SECRET"):
        return None
    try:
        return _f().decrypt(open(RUTA, "rb").read()).decode()
    except Exception:
        return None

def guardar(token):
    os.makedirs(os.path.dirname(RUTA), exist_ok=True)
    open(RUTA, "wb").write(_f().encrypt(token.encode()))
