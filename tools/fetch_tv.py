#!/usr/bin/env python3
"""Download TV shows for the TV tab in Popcorn & Parks.

Popular shows streaming in NZ, kids' and family shows, plus the titles in
tools/extra-shows.json. For each: seasons and episode counts, genres, NZ
rating, NZ where-to-watch, next and last episode, TMDB score and poster.
Posters are packed into tv/sheet-*.jpg (an artifact holds at most 512 files)
and the TV block in index.html is rewritten. TMDB auth as for the other
scripts (TMDB_API_KEY, or a proxy that adds it).

Usage: python3 tools/fetch_tv.py
"""
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_posters import PAGE, get, norm  # noqa: E402
from fetch_details import where  # noqa: E402
from fetch_games import sheet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT, CACHE = ROOT / "tv", ROOT / "tv" / "cache"
EXTRA = ROOT / "tools" / "extra-shows.json"
BEGIN, END = "/* TV:BEGIN */\n", "\n/* TV:END */"
MAX = 190


def api(path, **params):
    key = os.environ.get("TMDB_API_KEY", "").strip()
    headers = {}
    if len(key) > 40:
        headers["Authorization"] = f"Bearer {key}"
    elif key:
        params["api_key"] = key
    return json.loads(get(f"https://api.themoviedb.org/3/{path}?" + urllib.parse.urlencode(params), headers))


def rating(cr):
    by = {r.get("iso_3166_1"): r.get("rating") for r in cr.get("results", [])}
    return by.get("NZ") or by.get("AU") or by.get("US") or None


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    ids = []
    for page in range(1, 5):
        ids += [r["id"] for r in api("discover/tv", watch_region="NZ", with_watch_monetization_types="flatrate", sort_by="popularity.desc", page=page).get("results", [])]
    for g in ("10762", "10751"):
        for page in (1, 2):
            ids += [r["id"] for r in api("discover/tv", watch_region="NZ", with_genres=g, sort_by="popularity.desc", page=page).get("results", [])]
    for t in json.loads(EXTRA.read_text(encoding="utf-8")):
        res = api("search/tv", query=t).get("results", [])
        hit = next((r for r in res if norm(r["name"]) == norm(t)), res[0] if res else None)
        if hit:
            ids.append(hit["id"])
        else:
            print(f"  not found: {t}")
    ids = list(dict.fromkeys(ids))
    shows, seen = [], set()
    for i in ids:
        if len(shows) >= MAX:
            break
        try:
            d = api(f"tv/{i}", append_to_response="content_ratings,watch/providers")
        except Exception as ex:
            print(f"  error {i}: {ex}")
            continue
        name = d.get("name")
        if not name or norm(name) in seen or not d.get("number_of_seasons"):
            continue
        g = [x["id"] for x in d.get("genres", [])]
        if set(g) & {10763, 10767}:  # skip news and talk shows
            continue
        seen.add(norm(name))
        ep = lambda e: [e["season_number"], e["episode_number"], e.get("air_date")] if e else None
        s = {"t": name, "id": d["id"], "y": int((d.get("first_air_date") or "0")[:4]) or None, "g": g,
             "eps": [x.get("episode_count") or 0 for x in d.get("seasons", []) if x.get("season_number", 0) > 0],
             "st": d.get("status"), "r": rating(d.get("content_ratings", {})), "w": where(d.get("watch/providers", {})),
             "nx": ep(d.get("next_episode_to_air")), "ls": ep(d.get("last_episode_to_air")),
             "v": round(d.get("vote_average") or 0, 1), "d": (d.get("overview") or "").split(". ")[0][:160] or None}
        f = CACHE / f"{d['id']}.jpg"
        if d.get("poster_path") and not f.exists():
            try:
                f.write_bytes(get(f"https://image.tmdb.org/t/p/w185{d['poster_path']}"))
            except Exception:
                pass
        shows.append({k: v for k, v in s.items() if v not in (None, [], {}, "")})
        time.sleep(0.12)
    shows.sort(key=lambda x: norm(x["t"]))
    sheet([x for x in shows if (CACHE / f"{x['id']}.jpg").exists()], CACHE, OUT / "sheet-{}.jpg", (120, 180), 10, 10, lambda x: f"{x['id']}.jpg")
    src = PAGE.read_text(encoding="utf-8")
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), src, re.S)
    block = BEGIN + "const TV = " + json.dumps(shows, ensure_ascii=False, separators=(",", ":")) + f';\nconst TV_ASOF = "{date.today().isoformat()}";' + END
    PAGE.write_text(src[: m.start()] + block + src[m.end():], encoding="utf-8")
    print(f"{len(shows)} shows, {sum(1 for x in shows if x.get('nx'))} with an upcoming episode")


if __name__ == "__main__":
    main()
