#!/usr/bin/env python3
"""Write the PLEX block in index.html (and plex.json) from a snapshot of the family Plex library.

The page can't reach the Plex server itself (it lives on James's PC), so the
library is copied into the page, like MOVIE_DATA. To refresh it, ask Claude in a
session linked to that PC (it has the Plex tools) to run Plex find_media for
each movie library (sort "title", limit 500) and once for media_type "show",
save each result's lines into a folder as "<Library name>.txt" (for TV, run it
per TV library too, e.g. "Food TV.txt"; "shows.txt" is for shows of no known
library), then run:

    python3 tools/plex_snapshot.py path/to/folder

Each movie line looks like:
    - Zootopia 2 (2025) [movie, 108 min, PG, ★9.5, Comedy/Animation, unwatched]
and each show line like:
    - Breaking Bad (2008) [show, TV-MA, ★9.0, Drama/Crime, 0/62 episodes watched]
"""
import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "index.html"
LINE = re.compile(r"^- (?P<t>.+?)(?: \((?P<y>\d{4})\))? \[(?P<meta>[^\]]*)\]\s*$")


def parse_meta(meta):
    parts = [p.strip() for p in meta.split(",")]
    kind = parts.pop(0) if parts else ""
    out = {"kind": kind, "min": 0, "cert": "", "score": 0, "genres": "", "w": 0, "eps": None}
    for p in parts:
        if re.fullmatch(r"\d+ min", p):
            out["min"] = int(p.split()[0])
        elif p.startswith("★"):
            out["score"] = float(p[1:])
        elif p == "unwatched":
            out["w"] = 0
        elif p == "watched":
            out["w"] = 1
        elif p.startswith("in progress"):
            out["w"] = 2
        elif m := re.fullmatch(r"(\d+)/(\d+) episodes watched", p):
            out["eps"] = [int(m[1]), int(m[2])]
        elif re.fullmatch(r"(G|PG|PG-13|R|NC-17|Not Rated|NR|Unrated|TV-[A-Z0-9]+|M|R1[3568]|R18)", p):
            out["cert"] = "" if p in ("Not Rated", "NR", "Unrated") else p
        else:
            out["genres"] = p
    return out


def clean_title(t, y):
    # Plex sometimes keeps the year in the title too: "The Flash (2014) (2014)".
    if y and t.endswith(f" ({y})"):
        t = t[: -len(f" ({y})")]
    return t.strip()


def main(folder):
    folder = pathlib.Path(folder)
    movies, shows = [], []
    for f in sorted(folder.glob("*.txt")):
        lib = f.stem
        for raw in f.read_text(encoding="utf-8").splitlines():
            m = LINE.match(raw.strip())
            if not m:
                continue
            y = int(m["y"]) if m["y"] else 0
            t = clean_title(m["t"], m["y"])
            meta = parse_meta(m["meta"])
            if meta["kind"] == "show":
                eps = meta["eps"] or [0, 0]
                shows.append([t, y, meta["cert"], meta["score"], meta["genres"], eps[0], eps[1], "" if lib == "shows" else lib])
            else:
                movies.append([t, y, meta["min"], meta["cert"], meta["score"], meta["genres"], lib, meta["w"]])
    movies.sort(key=lambda r: r[0].lower())
    shows.sort(key=lambda r: r[0].lower())
    data = {"asof": datetime.date.today().isoformat(), "m": movies, "s": shows}
    block = "const PLEX = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    html = PAGE.read_text(encoding="utf-8")
    if re.search(r"^const PLEX = .*;$", html, flags=re.M):
        html = re.sub(r"^const PLEX = .*;$", lambda _: block, html, count=1, flags=re.M)
    else:
        anchor = re.search(r"^const WATCH_ASOF = .*;$", html, flags=re.M)
        if not anchor:
            sys.exit("Couldn't find WATCH_ASOF in index.html to put the PLEX block after.")
        html = html[: anchor.end()] + "\n" + block + html[anchor.end():]
    PAGE.write_text(html, encoding="utf-8")
    # The same copy as a file, for keyissue.app's other apps (question box, Recipe Book).
    (ROOT / "plex.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"PLEX: {len(movies)} movies, {len(shows)} shows")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
