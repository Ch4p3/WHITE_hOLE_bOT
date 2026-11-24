"""
Fotos reales con licencia libre para los videos (Wikimedia Commons).

Solo se aceptan licencias que permiten uso comercial sin obligar a licenciar el video entero:
dominio público, CC0 y CC BY (cualquier versión). Las CC BY-SA, NC o ND se descartan.
Cada foto guarda su crédito (autor + licencia) para ponerlo en el video y en la descripción.

Uso en un guion:   "visual": {"tipo": "foto", "src": "commons:File:Nombre.jpg", ...}
Buscar candidatas: python scripts/fotos.py guion.json   (genera una hoja de contacto)
"""
import hashlib, html, json, os, re
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "assets_cache", "img")
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "WhiteHoleBot/1.0 (https://ch4p3.github.io/WHITE_hOLE_bOT/; educational shorts)"}


def licencia_ok(lic):
    l = (lic or "").strip().lower()
    if not l:
        return False
    if any(x in l for x in ("-sa", " sa ", "sharealike", "share alike", "nc", "nd", "fair use", "non-free")):
        return False
    return (l.startswith("cc0") or l.startswith("public domain") or l.startswith("pd")
            or re.match(r"^cc[ -]by[ -]?\d", l) is not None or l in ("cc by", "cc-by", "attribution"))


def _limpio(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()


def _info(titulos, ancho=1600):
    r = requests.get(API, headers=UA, timeout=60, params={
        "action": "query", "format": "json", "prop": "imageinfo", "titles": "|".join(titulos),
        "iiprop": "url|extmetadata|size|mime", "iiurlwidth": ancho})
    r.raise_for_status()
    out = []
    for pg in r.json().get("query", {}).get("pages", {}).values():
        ii = (pg.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        out.append({
            "titulo": pg.get("title"),
            "url": ii.get("thumburl") or ii.get("url"),
            "pagina": ii.get("descriptionurl"),
            "ancho": ii.get("width", 0), "alto": ii.get("height", 0), "mime": ii.get("mime", ""),
            "licencia": _limpio(md.get("LicenseShortName", {}).get("value")),
            "autor": _limpio(md.get("Artist", {}).get("value")) or "Wikimedia Commons",
            "descripcion": _limpio(md.get("ImageDescription", {}).get("value"))[:200],
        })
    return out


def buscar(consulta, n=8):
    r = requests.get(API, headers=UA, timeout=60, params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f"{consulta} filetype:bitmap", "gsrlimit": 30})
    r.raise_for_status()
    titulos = [p["title"] for p in r.json().get("query", {}).get("pages", {}).values()]
    if not titulos:
        return []
    cands = []
    for i in range(0, len(titulos), 20):
        cands += _info(titulos[i:i + 20], ancho=800)
    ok = [c for c in cands if licencia_ok(c["licencia"]) and c["ancho"] >= 1000 and "jpeg" in c["mime"] + "jpg"]
    return ok[:n]


def obtener(src):
    """Descarga (con caché) la foto de `src` = 'commons:File:...'. Devuelve (ruta, credito_dict)."""
    if not src.startswith("commons:"):
        raise ValueError(f"Fuente de foto no soportada: {src}")
    titulo = src.split(":", 1)[1]
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.md5(titulo.encode()).hexdigest()[:16]
    ruta, meta_p = os.path.join(CACHE, key + ".jpg"), os.path.join(CACHE, key + ".json")
    if os.path.exists(ruta) and os.path.exists(meta_p):
        return ruta, json.load(open(meta_p, encoding="utf-8"))
    info = _info([titulo])[0]
    if not info.get("url"):
        raise RuntimeError(f"No encontré la foto {titulo} en Wikimedia Commons")
    if not licencia_ok(info["licencia"]):
        raise RuntimeError(f"La foto {titulo} tiene licencia '{info['licencia']}', no apta para uso comercial")
    img = requests.get(info["url"], headers=UA, timeout=120)
    img.raise_for_status()
    open(ruta, "wb").write(img.content)
    json.dump(info, open(meta_p, "w", encoding="utf-8"), ensure_ascii=False)
    return ruta, info


def credito_corto(info):
    autor = re.sub(r"\s+", " ", info.get("autor", ""))[:40]
    return f"Foto: {autor} · {info.get('licencia', '')} · Wikimedia Commons"
