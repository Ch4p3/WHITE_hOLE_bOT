"""
Publica el siguiente carrusel de la cola en Instagram (CAROUSEL) y en la Página de Facebook (post multi-foto).

Uso:  python scripts/carrusel_pub.py            -> toma el primero de guiones/carruseles/pendientes
      python scripts/carrusel_pub.py RUTA.json  -> uno en concreto
      python scripts/carrusel_pub.py --prueba   -> solo genera las imágenes en out/carrusel
"""
import base64, glob, json, os, shutil, sys, time, datetime
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "engine"))
from facebook import GRAPH, _ids, _check  # noqa: E402
from instagram import cuenta              # noqa: E402
import carrusel                           # noqa: E402

PEND = os.path.join(ROOT, "guiones", "carruseles", "pendientes")
PUB = os.path.join(ROOT, "guiones", "carruseles", "publicados")


def subir_previews(paths, carpeta):
    repo, gh = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
    urls = []
    for p in paths:
        ruta = f"carruseles/{carpeta}/{os.path.basename(p)}"
        r = requests.put(f"https://api.github.com/repos/{repo}/contents/{ruta}",
                         headers={"Authorization": f"Bearer {gh}", "Accept": "application/vnd.github+json"},
                         json={"message": f"Carrusel {carpeta}", "content": base64.b64encode(open(p, "rb").read()).decode(),
                               "branch": "previews"}, timeout=300)
        if r.status_code == 422:      # ya existe: actualizar
            sha = requests.get(f"https://api.github.com/repos/{repo}/contents/{ruta}?ref=previews",
                               headers={"Authorization": f"Bearer {gh}"}, timeout=60).json()["sha"]
            r = requests.put(f"https://api.github.com/repos/{repo}/contents/{ruta}",
                             headers={"Authorization": f"Bearer {gh}", "Accept": "application/vnd.github+json"},
                             json={"message": f"Carrusel {carpeta}", "content": base64.b64encode(open(p, "rb").read()).decode(),
                                   "branch": "previews", "sha": sha}, timeout=300)
        r.raise_for_status()
        urls.append(f"https://raw.githubusercontent.com/{repo}/{r.json()['commit']['sha']}/{ruta}")
    return urls


def texto(g):
    t = g.get("caption") or g.get("titulo", "")
    if g.get("fuentes"):
        t += "\n\nFuentes:\n" + "\n".join(g["fuentes"])
    if g.get("hashtags"):
        t += "\n\n" + g["hashtags"]
    return t


def instagram(urls, caption):
    ig_id, _ = cuenta(); _, token = _ids()
    hijos = []
    for u in urls:
        c = _check(requests.post(f"{GRAPH}/{ig_id}/media", data={"image_url": u, "is_carousel_item": "true",
                                                                 "access_token": token}, timeout=120))
        hijos.append(c["id"])
    c = _check(requests.post(f"{GRAPH}/{ig_id}/media", data={"media_type": "CAROUSEL", "children": ",".join(hijos),
                                                             "caption": caption[:2200], "access_token": token}, timeout=120))
    for _ in range(30):
        st = _check(requests.get(f"{GRAPH}/{c['id']}", params={"fields": "status_code", "access_token": token}, timeout=60))
        if st.get("status_code") == "FINISHED": break
        if st.get("status_code") in ("ERROR", "EXPIRED"): raise SystemExit(f"Instagram rechazó el carrusel: {st}")
        time.sleep(5)
    p = _check(requests.post(f"{GRAPH}/{ig_id}/media_publish", data={"creation_id": c["id"], "access_token": token}, timeout=120))
    return p["id"]


def facebook(urls, caption):
    page_id, token = _ids()
    ids = []
    for u in urls:
        r = _check(requests.post(f"{GRAPH}/{page_id}/photos", data={"url": u, "published": "false",
                                                                    "access_token": token}, timeout=120))
        ids.append(r["id"])
    data = {"message": caption, "access_token": token}
    for i, fid in enumerate(ids):
        data[f"attached_media[{i}]"] = json.dumps({"media_fbid": fid})
    return _check(requests.post(f"{GRAPH}/{page_id}/feed", data=data, timeout=120))["id"]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    prueba = "--prueba" in sys.argv
    guion = args[0] if args else (sorted(glob.glob(os.path.join(PEND, "*.json"))) or [None])[0]
    if not guion:
        print("No hay carruseles en la cola."); return
    nombre = os.path.basename(guion)[:-5]
    out = os.path.join(ROOT, "out", "carrusel", nombre)
    g, slides = carrusel.render(guion, out)
    print("Slides:", len(slides))
    if prueba: return
    urls = subir_previews(slides, nombre)
    cap = texto(g)
    res = {}
    try:
        res["instagram"] = instagram(urls, cap); print("✅ Carrusel en Instagram:", res["instagram"])
    except Exception as e:
        print("⚠️ Instagram:", str(e)[:300])
    try:
        res["facebook"] = facebook(urls, cap); print("✅ Carrusel en Facebook:", res["facebook"])
    except Exception as e:
        print("⚠️ Facebook:", str(e)[:300])
    if res:
        g["publicado"] = res
        os.makedirs(PUB, exist_ok=True)
        dest = os.path.join(PUB, f"{datetime.date.today().isoformat()}_{os.path.basename(guion)}")
        json.dump(g, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if os.path.abspath(guion).startswith(os.path.abspath(PEND)): os.remove(guion)
    else:
        raise SystemExit("No se publicó en ninguna red.")


if __name__ == "__main__":
    main()
