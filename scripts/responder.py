"""
Responde automáticamente a los comentarios con la palabra clave ("Comenta RUTINA y te la envío").

Lee los carruseles/reels publicados que tengan "palabra" y "enlace" en su guion (con los ids de publicación en
"publicado": {"instagram": id, "facebook": id}) y contesta cada comentario que contenga la palabra y que
la cuenta todavía no haya respondido. Uso: python scripts/responder.py
"""
import glob, json, os, random, sys
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from facebook import GRAPH, _ids  # noqa: E402

PLANTILLAS = [
    "¡Aquí la tienes! 👉 {enlace} Guárdala y cuéntame cómo te va 💪",
    "¡Listo! Te la dejo aquí: {enlace} 🔖 Si la haces, vuelve y escribe HECHO 🙌",
    "Con gusto 😊 Aquí está completa: {enlace} ¡A darle!",
    "¡Hecho! 👉 {enlace} Si te sirve, compártela con alguien que la necesite 💛",
]
IG_USER = "whi.tehole1"


def guiones():
    out = []
    for f in glob.glob(os.path.join(ROOT, "guiones", "**", "publicados", "*.json"), recursive=True):
        try:
            g = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if g.get("palabra") and g.get("enlace") and g.get("publicado"):
            out.append(g)
    return out


def responder_ig(media_id, palabra, enlace, token):
    n = 0
    r = requests.get(f"{GRAPH}/{media_id}/comments", params={"fields": "id,text,username,replies{username}", "limit": 100,
                                                             "access_token": token}, timeout=60).json()
    for c in r.get("data", []):
        if c.get("username") == IG_USER or palabra.lower() not in (c.get("text") or "").lower():
            continue
        if any(x.get("username") == IG_USER for x in (c.get("replies") or {}).get("data", [])):
            continue
        msg = random.choice(PLANTILLAS).format(enlace=enlace)
        res = requests.post(f"{GRAPH}/{c['id']}/replies", data={"message": msg, "access_token": token}, timeout=60).json()
        print("IG", c["id"], "->", "ok" if "id" in res else res.get("error", {}).get("message", res))
        n += "id" in res
    if "error" in r: print("IG error:", r["error"].get("message"))
    return n


def responder_fb(post_id, palabra, enlace, page_id, token):
    n = 0
    r = requests.get(f"{GRAPH}/{post_id}/comments", params={"fields": "id,message,from,comments{from}", "limit": 100,
                                                            "access_token": token}, timeout=60).json()
    for c in r.get("data", []):
        if (c.get("from") or {}).get("id") == page_id or palabra.lower() not in (c.get("message") or "").lower():
            continue
        if any((x.get("from") or {}).get("id") == page_id for x in (c.get("comments") or {}).get("data", [])):
            continue
        msg = random.choice(PLANTILLAS).format(enlace=enlace)
        res = requests.post(f"{GRAPH}/{c['id']}/comments", data={"message": msg, "access_token": token}, timeout=60).json()
        print("FB", c["id"], "->", "ok" if "id" in res else res.get("error", {}).get("message", res))
        n += "id" in res
    if "error" in r: print("FB error:", r["error"].get("message"))
    return n


def main():
    page_id, token = _ids()
    total = 0
    for g in guiones():
        pub = g["publicado"]
        if pub.get("instagram"): total += responder_ig(pub["instagram"], g["palabra"], g["enlace"], token)
        if pub.get("facebook"): total += responder_fb(pub["facebook"], g["palabra"], g["enlace"], page_id, token)
    print("Respuestas enviadas:", total)


if __name__ == "__main__":
    main()
