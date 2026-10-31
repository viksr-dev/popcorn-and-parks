#!/usr/bin/env python3
"""Download genres, runtimes, age ratings and related films for Popcorn & Parks.

Feeds the Discover > Tonight picker. Uses the same title list as
fetch_posters.py (the page's built-in lists plus tools/extra-titles.json),
looks each film up on TMDB and rewrites the MOVIE_DATA block in index.html
(between the MOVIEDATA markers). Each entry, keyed by norm(title):

  t  title as listed     y  year          r  runtime in minutes
  g  TMDB genre ids      c  US rating     nz NZ rating
  v  TMDB score (0-10)   k  related films in the catalogue (keys, best first)

Re-running only looks up new titles; --force refreshes everything.
Set TMDB_API_KEY as for fetch_posters.py.

Usage: python3 tools/fetch_details.py [--force]
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_posters import EXTRA, PAGE, get, norm, page_titles, search_movie  # noqa: E402

BEGIN, END = "/* MOVIEDATA:BEGIN */\n", "\n/* MOVIEDATA:END */"


def cert(release_dates, country):
    for c in release_dates.get("results", []):
        if c.get("iso_3166_1") == country:
            # Prefer theatrical (3) then any other release type with a rating.
            for want in (3, 2, 4, 5, 6, 1):
                for d in c.get("release_dates", []):
                    if d.get("type") == want and d.get("certification", "").strip():
                        return d["certification"].strip()
    return None


def details(movie_id, key):
    headers, q = {}, "append_to_response=release_dates,recommendations,similar"
    if len(key) > 40:
        headers["Authorization"] = f"Bearer {key}"
    elif key:
        q += "&api_key=" + key
    return json.loads(get(f"https://api.themoviedb.org/3/movie/{movie_id}?{q}", headers))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    src = PAGE.read_text(encoding="utf-8")
    m = re.search(re.escape(BEGIN) + r"const MOVIE_DATA = (\{.*?\});" + re.escape(END), src, re.S)
    if not m:
        sys.exit("MOVIEDATA markers not found in index.html")
    data = json.loads(m.group(1))
    cache_ids = {k: v.pop("_id", None) for k, v in data.items()}

    titles = page_titles(src)
    if EXTRA.exists():
        titles += [(x["title"], x.get("year")) for x in json.loads(EXTRA.read_text(encoding="utf-8"))]

    key = os.environ.get("TMDB_API_KEY", "").strip()
    raw, seen, missing = {}, set(), []
    for title, year in titles:
        k = norm(title)
        if not k or k in seen:
            continue
        seen.add(k)
        if k in data and not args.force:
            continue
        try:
            hit = search_movie(title, year, key)
            if not hit:
                missing.append(title)
                continue
            d = details(hit["id"], key)
            raw[k] = d
            data[k] = {
                "t": title,
                "y": int((d.get("release_date") or "0")[:4]) or year,
                "r": d.get("runtime") or None,
                "g": [g["id"] for g in d.get("genres", [])],
                "c": cert(d.get("release_dates", {}), "US"),
                "nz": cert(d.get("release_dates", {}), "NZ"),
                "v": round(d.get("vote_average") or 0, 1),
            }
            cache_ids[k] = hit["id"]
            print(f"  ok: {title}")
            time.sleep(0.15)
        except Exception as e:  # keep going; the film just won't show in Tonight
            missing.append(title)
            print(f"  error: {title}: {e}")

    # Related films: TMDB recommendations then similar, limited to films we know.
    by_id = {i: k for k, i in cache_ids.items() if i}
    for k, d in raw.items():
        rel = []
        for src_list in ("recommendations", "similar"):
            for r in d.get(src_list, {}).get("results", []):
                rk = by_id.get(r.get("id"))
                if rk and rk != k and rk not in rel:
                    rel.append(rk)
        data[k]["k"] = rel[:12]

    out = {}
    for k in sorted(data):
        e = {f: v for f, v in data[k].items() if v not in (None, [], "")}
        if cache_ids.get(k):
            e["_id"] = cache_ids[k]
        out[k] = e
    block = BEGIN + "const MOVIE_DATA = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";" + END
    src = src[: m.start()] + block + src[m.end():]
    PAGE.write_text(src, encoding="utf-8")
    print(f"{len(out)} films with details; {len(missing)} missing: {', '.join(missing)}")


if __name__ == "__main__":
    main()
