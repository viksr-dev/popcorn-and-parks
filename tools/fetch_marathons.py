#!/usr/bin/env python3
"""Download film series for the Marathon planner in Popcorn & Parks.

Reads collection names from tools/marathons.json, finds each on TMDB,
and for every released film gets its runtime, ratings and NZ where-to-watch
data. Downloads missing posters into posters/ (adding them to the POSTERS
map) and rewrites the MARATHONS block in index.html.

Usage: python3 tools/fetch_marathons.py
"""
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_posters import OUT, PAGE, SIZE, get, norm, slug  # noqa: E402
from fetch_details import cert, where  # noqa: E402

LIST = Path(__file__).resolve().parent / "marathons.json"
BEGIN, END = "/* MARATHONS:BEGIN */\n", "\n/* MARATHONS:END */"


def api(path, **params):
    key = os.environ.get("TMDB_API_KEY", "").strip()
    headers = {}
    if len(key) > 40:
        headers["Authorization"] = f"Bearer {key}"
    elif key:
        params["api_key"] = key
    return json.loads(get(f"https://api.themoviedb.org/3/{path}?" + urllib.parse.urlencode(params), headers))


def main():
    src = PAGE.read_text(encoding="utf-8")
    pm = re.search(r"/\* POSTERS:BEGIN \*/\nconst POSTERS = (\{.*?\});\n/\* POSTERS:END \*/", src, re.S)
    posters = json.loads(pm.group(1))
    today = date.today().isoformat()
    out = []
    for name in json.loads(LIST.read_text(encoding="utf-8")):
        res = api("search/collection", query=name).get("results", [])
        hit = next((r for r in res if norm(r["name"]) == norm(name)), res[0] if res else None)
        if not hit:
            print(f"  not found: {name}")
            continue
        col = api(f"collection/{hit['id']}")
        parts = sorted((p for p in col.get("parts", []) if p.get("release_date") and p["release_date"] <= today),
                       key=lambda p: p["release_date"])
        films = []
        for p in parts:
            d = api(f"movie/{p['id']}", append_to_response="release_dates,watch/providers")
            if not d.get("runtime"):
                continue
            t, y = d["title"], int(d["release_date"][:4])
            k = norm(t)
            if p.get("poster_path") and not (k in posters and (OUT / posters[k]).exists()):
                fn = slug(t, y) + ".jpg"
                (OUT / fn).write_bytes(get(f"https://image.tmdb.org/t/p/{SIZE}{p['poster_path']}"))
                posters[k] = fn
            f = {"t": t, "y": y, "r": d["runtime"], "c": cert(d.get("release_dates", {}), "US"),
                 "nz": cert(d.get("release_dates", {}), "NZ"), "w": where(d.get("watch/providers", {})), "_id": d["id"]}
            films.append({a: b for a, b in f.items() if b not in (None, {}, "")})
            time.sleep(0.1)
        if len(films) < 2:
            print(f"  skipped (fewer than 2 films): {name}")
            continue
        label = re.sub(r"\s*(\(.*?\)\s*)?Collection$", "", col["name"]).strip()
        out.append({"n": label, "f": films})
        print(f"  ok: {label}: {len(films)} films, {sum(f['r'] for f in films) // 60}h")

    src = src[: pm.start()] + "/* POSTERS:BEGIN */\nconst POSTERS = " + json.dumps(dict(sorted(posters.items())), ensure_ascii=False, separators=(",", ":")) + ";\n/* POSTERS:END */" + src[pm.end():]
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), src, re.S)
    block = BEGIN + "const MARATHONS = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";" + END
    src = src[: m.start()] + block + src[m.end():]
    PAGE.write_text(src, encoding="utf-8")
    print(f"{len(out)} marathons")


if __name__ == "__main__":
    main()
