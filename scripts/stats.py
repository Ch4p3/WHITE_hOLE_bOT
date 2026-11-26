"""
Recoge estadísticas de rendimiento de Facebook, Instagram y YouTube y las guarda en out/stats.json.
Uso: python scripts/stats.py
"""
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))
from facebook import GRAPH, _ids  # noqa: E402

OUT = {"generado": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "facebook": [], "instagram": [], "youtube": [], "errores": []}


def g(url, **params):
    r = requests.get(url, params=params, timeout=60)
    try:
        return r.json()
    except Exception:
        return {"error": r.text[:300]}


def facebook():
    page_id, token = _ids()
    vistos = set()
    for edge in ("video_reels", "videos"):
        url = f"{GRAPH}/{page_id}/{edge}"
        params = {"fields": "id,description,title,created_time,length,permalink_url", "limit": 100, "access_token": token}
        d = g(url, **params)
        if "error" in d:
            OUT["errores"].append({"fb_" + edge: d["error"]})
            continue
        for v in d.get("data", []):
            if v["id"] in vistos:
                continue
            vistos.add(v["id"])
            item = {"id": v["id"], "tipo": edge, "fecha": v.get("created_time"), "duracion": v.get("length"),
                    "texto": (v.get("title") or v.get("description") or "")[:140], "link": v.get("permalink_url")}
            ins = g(f"{GRAPH}/{v['id']}/video_insights", access_token=token)
            met = {}
            for m in ins.get("data", []):
                vals = m.get("values") or []
                if vals:
                    val = vals[0].get("value")
                    if isinstance(val, (int, float)):
                        met[m["name"]] = val
            if "error" in ins:
                item["insights_error"] = ins["error"].get("message", "")[:160]
            item["metricas"] = met
            soc = g(f"{GRAPH}/{v['id']}", fields="likes.summary(true).limit(0),comments.summary(true).limit(0)", access_token=token)
            item["likes"] = (soc.get("likes") or {}).get("summary", {}).get("total_count")
            item["comentarios"] = (soc.get("comments") or {}).get("summary", {}).get("total_count")
            if item["comentarios"]:
                cm = g(f"{GRAPH}/{v['id']}/comments", fields="id,from,message,comments{from,message}", limit=50, access_token=token)
                item["lista_comentarios"] = [{"id": c["id"], "de": (c.get("from") or {}).get("name"), "texto": c.get("message"),
                                              "respuestas": [((r.get("from") or {}).get("name") or "?") + ": " + r.get("message", "") for r in (c.get("comments") or {}).get("data", [])]}
                                             for c in cm.get("data", [])]
            OUT["facebook"].append(item)
    pg = g(f"{GRAPH}/{page_id}", fields="followers_count,fan_count", access_token=token)
    OUT["facebook_pagina"] = {k: pg.get(k) for k in ("followers_count", "fan_count")}


def instagram():
    page_id, token = _ids()
    d = g(f"{GRAPH}/{page_id}", fields="instagram_business_account{id,username,followers_count,media_count}", access_token=token)
    acc = d.get("instagram_business_account")
    if not acc:
        OUT["errores"].append({"ig": d.get("error", "sin cuenta")})
        return
    OUT["instagram_cuenta"] = {k: acc.get(k) for k in ("username", "followers_count", "media_count")}
    m = g(f"{GRAPH}/{acc['id']}/media", fields="id,caption,timestamp,media_product_type,like_count,comments_count,permalink",
          limit=100, access_token=token)
    for x in m.get("data", []):
        item = {"id": x["id"], "fecha": x.get("timestamp"), "tipo": x.get("media_product_type"),
                "texto": (x.get("caption") or "")[:140], "likes": x.get("like_count"), "comentarios": x.get("comments_count"),
                "link": x.get("permalink")}
        ins = g(f"{GRAPH}/{x['id']}/insights", metric="views,reach,saved,shares,total_interactions,ig_reels_avg_watch_time",
                access_token=token)
        if "error" in ins:
            ins = g(f"{GRAPH}/{x['id']}/insights", metric="views,reach,saved,shares,total_interactions", access_token=token)
        item["metricas"] = {i["name"]: (i.get("values") or [{}])[0].get("value") for i in ins.get("data", [])}
        if "error" in ins:
            item["insights_error"] = ins["error"].get("message", "")[:160]
        if x.get("comments_count"):
            cm = g(f"{GRAPH}/{x['id']}/comments", fields="id,text,username,timestamp,replies{username,text}", limit=50, access_token=token)
            item["lista_comentarios"] = [{"id": c["id"], "usuario": c.get("username"), "texto": c.get("text"),
                                          "respuestas": [r.get("username") + ": " + r.get("text", "") for r in (c.get("replies") or {}).get("data", [])]}
                                         for c in cm.get("data", [])]
            if "error" in cm: item["comentarios_error"] = cm["error"].get("message", "")[:160]
        OUT["instagram"].append(item)


def youtube():
    from youtube import access_token
    tok = access_token()
    h = {"Authorization": f"Bearer {tok}"}
    api = "https://www.googleapis.com/youtube/v3"
    ch = requests.get(f"{api}/channels", params={"part": "contentDetails,statistics", "mine": "true"}, headers=h, timeout=60).json()
    it = ch["items"][0]
    OUT["youtube_canal"] = it.get("statistics")
    uploads = it["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        p = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
        if token:
            p["pageToken"] = token
        r = requests.get(f"{api}/playlistItems", params=p, headers=h, timeout=60).json()
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    for i in range(0, len(ids), 50):
        r = requests.get(f"{api}/videos", params={"part": "snippet,statistics,contentDetails,status", "id": ",".join(ids[i:i + 50])},
                         headers=h, timeout=60).json()
        for v in r.get("items", []):
            s = v.get("statistics", {})
            OUT["youtube"].append({"id": v["id"], "titulo": v["snippet"]["title"], "fecha": v["snippet"]["publishedAt"],
                                   "duracion": v["contentDetails"]["duration"], "estado": v["status"].get("privacyStatus"),
                                   "programado": v["status"].get("publishAt"),
                                   "vistas": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                                   "comentarios": int(s.get("commentCount", 0))})


for nombre, fn in (("facebook", facebook), ("instagram", instagram), ("youtube", youtube)):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        OUT["errores"].append({nombre: repr(e)[:300]})

os.makedirs("out", exist_ok=True)
with open("out/stats.json", "w", encoding="utf-8") as f:
    json.dump(OUT, f, ensure_ascii=False, indent=1)
print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in OUT.items()}, ensure_ascii=False))
