"""Valida un guion: cada valor *sync que sea texto debe aparecer como (parte de) una palabra del 'texto' de su escena.
Uso: python tools/validar_guion.py guion.json"""
import json, re, sys
def syncs(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if k.endswith("sync") and isinstance(v, str): yield path + "." + k, v
            else: yield from syncs(v, path + "." + k)
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from syncs(v, f"{path}[{i}]")
c = json.load(open(sys.argv[1], encoding="utf-8")); bad = 0
for i, e in enumerate(c["escenas"]):
    words = [re.sub(r"[^\w']", "", w.lower()) for w in e["texto"].split()]
    for p, s in syncs(e["visual"]):
        if not any(s.lower() in w for w in words):
            bad += 1; print(f"escena {i}: sync '{s}' ({p}) no está en el texto: {e['texto'][:70]}")
print("OK" if not bad else f"{bad} problemas")
