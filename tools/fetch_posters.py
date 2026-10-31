#!/usr/bin/env python3
"""Download movie posters for Popcorn & Parks.

The page's content security policy blocks remote images, so posters are
downloaded into posters/ and published alongside index.html. This script:

1. Collects titles from the built-in lists in index.html (IMDB_TOP,
   DC_ANIMATED, STARTER_MOVIES) plus tools/extra-titles.json (the movie
   pile and chart titles from the shared database) and any --title args.
2. Finds each title with the TMDB API (api.themoviedb.org). Set
   TMDB_API_KEY to a free TMDB v3 API key or v4 read access token (or leave
   it unset where a proxy adds the Authorization header, as in Claude's cloud
   environment).
3. Downloads the w185 poster from image.tmdb.org into posters/<slug>.jpg.
4. Rewrites the POSTERS map in index.html (between the POSTERS markers).

Existing files are kept, so re-running only fetches new titles.

Usage: python3 tools/fetch_posters.py [--title "Name" [--year 2024]] [--force]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "index.html"
OUT = ROOT / "posters"
EXTRA = ROOT / "tools" / "extra-titles.json"
SIZE = "w185"
UA = "popcorn-and-parks-poster-fetch/1.0"


def norm(t):
    """Same key as the page's norm(): lowercase ASCII letters and digits only."""
    return re.sub(r"[^a-z0-9]", "", t.lower())


def slug(t, year):
    s = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60] or "movie"
    return f"{s}-{year}" if year else s


def js_string(s):
    return json.loads(s) if s.startswith('"') else s[1:-1].replace("\\'", "'")


def page_titles(src):
    """Titles and years from the page's built-in lists."""
    out = []
    for name in ("IMDB_TOP", "DC_ANIMATED"):
        m = re.search(rf"const {name} = \[(.*?)\n\];", src, re.S)
        for t, y in re.findall(r'\[("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'), (\d{4})', m.group(1)):
            out.append((js_string(t), int(y)))
    m = re.search(r"const STARTER_MOVIES = \[(.*?)\n\];", src, re.S)
    for t, y in re.findall(r'title: ("(?:[^"\\]|\\.)*"), year: (\d{4})', m.group(1)):
        out.append((js_string(t), int(y)))
    return out


def get(url, headers=None, tries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                raise
            time.sleep(2 ** i)
        except urllib.error.URLError:
            time.sleep(2 ** i)
    raise RuntimeError(f"failed: {url}")


def search_movie(title, year, key):
    """Best TMDB search result with a poster, or None."""
    headers, params = {}, {"query": title, "include_adult": "false"}
    if len(key) > 40:
        headers["Authorization"] = f"Bearer {key}"
    elif key:
        params["api_key"] = key
    if year:
        params["primary_release_year"] = str(year)
    data = json.loads(get("https://api.themoviedb.org/3/search/movie?" + urllib.parse.urlencode(params), headers))
    results = [r for r in data.get("results", []) if r.get("poster_path")]
    if not results and year:
        return search_movie(title, None, key)
    if not results:
        return None
    exact = [r for r in results if norm(r.get("title", "")) == norm(title) or norm(r.get("original_title", "")) == norm(title)]
    return (exact or results)[0]


def search_api(title, year, key):
    r = search_movie(title, year, key)
    return r["poster_path"] if r else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", action="append", default=[])
    ap.add_argument("--year", type=int)
    ap.add_argument("--force", action="store_true", help="re-download posters that already exist")
    args = ap.parse_args()

    src = PAGE.read_text(encoding="utf-8")
    m = re.search(r"/\* POSTERS:BEGIN \*/\nconst POSTERS = (\{.*?\});\n/\* POSTERS:END \*/", src, re.S)
    if not m:
        sys.exit("POSTERS markers not found in index.html")
    posters = json.loads(m.group(1))

    titles = page_titles(src)
    if EXTRA.exists():
        titles += [(x["title"], x.get("year")) for x in json.loads(EXTRA.read_text(encoding="utf-8"))]
    titles += [(t, args.year) for t in args.title]

    key = os.environ.get("TMDB_API_KEY", "").strip()
    # With no key the request goes out bare: fine where a proxy adds the Authorization header.
    OUT.mkdir(exist_ok=True)
    seen, missing = set(), []
    for title, year in titles:
        k = norm(title)
        if not k or k in seen:
            continue
        seen.add(k)
        if k in posters and (OUT / posters[k]).exists() and not args.force:
            continue
        try:
            path = search_api(title, year, key)
            if not path:
                missing.append(title)
                print(f"  no poster: {title}")
                continue
            name = slug(title, year) + ".jpg"
            (OUT / name).write_bytes(get(f"https://image.tmdb.org/t/p/{SIZE}{path}"))
            posters[k] = name
            print(f"  ok: {title} -> {name}")
            time.sleep(0.2)
        except Exception as e:  # keep going; the tile falls back to colour
            missing.append(title)
            print(f"  error: {title}: {e}")

    block = "const POSTERS = " + json.dumps(dict(sorted(posters.items())), ensure_ascii=False, separators=(",", ":")) + ";"
    src = src[: m.start()] + "/* POSTERS:BEGIN */\n" + block + "\n/* POSTERS:END */" + src[m.end():]
    PAGE.write_text(src, encoding="utf-8")
    print(f"{len(posters)} posters mapped; {len(missing)} missing")


if __name__ == "__main__":
    main()
