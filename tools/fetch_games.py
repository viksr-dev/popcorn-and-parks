#!/usr/bin/env python3
"""Download the games catalogue for the Games tab in Popcorn & Parks.

Takes every Xbox Game Pass console game in NZ (Microsoft's public Game Pass
catalogue) plus the titles in tools/extra-games.json (found with Microsoft
Store search), then reads each game's Microsoft Store details: genres,
couch co-op / split-screen / online co-op player counts, age ratings and box
art. Covers go in games/<id>.jpg; the GAMES block in index.html is rewritten.

No API key needed. Game Pass changes monthly; re-run to refresh.

Each entry: t title, id store id, g genres, lc couch co-op [min,max],
lm local multiplayer [min,max], ss split-screen, oc online co-op max,
om online multiplayer max, sp single player, r AU/NZ-style rating
(G, PG, M, MA, R), e ESRB, y year, d short description, gp on Game Pass.

Also saves Steam NZ specials, new releases, coming soon and top sellers
(with review ratings and small capsule images in steam/) into the STEAM
block. Prices and specials change daily; re-run to refresh.

Usage: python3 tools/fetch_games.py
"""
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_posters import PAGE, get, norm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "games"
EXTRA = ROOT / "tools" / "extra-games.json"
GP_CONSOLE = "f6f1f99f-9b49-4ccd-b3bf-4d9767a77f5e"
BEGIN, END = "/* GAMES:BEGIN */\n", "\n/* GAMES:END */"
SKIP = re.compile(r"(\bpreview\b|\bbeta\b|technical test|playtest|friend'?s pass|bundle|soundtrack|season pass|dlc|upgrade|pack\b(?!.*party)|add-on|demo|trial|vip|currency|coins|points)", re.I)


def gamepass_ids():
    d = json.loads(get(f"https://catalog.gamepass.com/sigls/v2?id={GP_CONSOLE}&language=en-nz&market=NZ"))
    return [x["id"] for x in d[1:] if "id" in x]


def search_id(title):
    q = urllib.parse.urlencode({"market": "NZ", "languages": "en-NZ", "query": title, "productFamilyNames": "Games"})
    d = json.loads(get(f"https://displaycatalog.mp.microsoft.com/v7.0/productFamilies/autosuggest?{q}"))
    prods = [p for r in d.get("Results", []) for p in r.get("Products", []) if p.get("Type") == "Game" and not SKIP.search(p.get("Title", ""))]
    exact = [p for p in prods if norm(p["Title"]) == norm(title)]
    starts = [p for p in prods if norm(p["Title"]).startswith(norm(title))]
    pick = (exact or starts or prods or [None])[0]
    return pick["ProductId"] if pick else None


def details(ids):
    q = urllib.parse.urlencode({"bigIds": ",".join(ids), "market": "NZ", "languages": "en-nz"})
    return json.loads(get(f"https://displaycatalog.mp.microsoft.com/v7.0/products?{q}")).get("Products", [])


def entry(p, gp):
    L, P = p["LocalizedProperties"][0], p["Properties"]
    M = (p.get("MarketProperties") or [{}])[0]
    attrs = {a["Name"]: a for a in (P.get("Attributes") or [])}
    rng = lambda n: [attrs[n].get("Minimum") or 2, attrs[n].get("Maximum") or 2] if n in attrs else None
    ratings = {r["RatingSystem"]: r["RatingId"].split(":")[-1] for r in (M.get("ContentRatings") or [])}
    au = ratings.get("COB-AU")
    au = {"MA": "MA", "R": "R", "RC": "R", "M": "M", "PG": "PG", "G": "G"}.get((au or "").replace("15", "").replace("18", "").replace("+", ""), None)
    title = re.sub(r"\s*[™®]", "", L["ProductTitle"]).strip()
    # One entry per game: drop console/edition suffixes so Xbox One and Series X|S versions merge.
    title = re.sub(r"\s*[-–:]?\s*\(?(for )?(Xbox One( and| &) Xbox Series X\|S|Xbox Series X\|S|Xbox One|Windows( 10| 11)?|PC)\)?$", "", title, flags=re.I).strip()
    e = {
        "t": title, "id": p["ProductId"], "g": P.get("Categories") or ([P["Category"]] if P.get("Category") else []),
        "lc": rng("XblLocalCoop"), "lm": rng("XblLocalMultiPlayer"), "ss": 1 if "SharedSplitScreen" in attrs else None,
        "oc": (attrs["XblOnlineCoop"].get("Maximum") or 2) if "XblOnlineCoop" in attrs else None,
        "om": (attrs["XblOnlineMultiPlayer"].get("Maximum") or 2) if "XblOnlineMultiPlayer" in attrs else None,
        "sp": 1 if "SinglePlayer" in attrs else None, "r": au, "e": ratings.get("ESRB"),
        "y": int((M.get("OriginalReleaseDate") or "0")[:4]) or None,
        "d": (L.get("ShortDescription") or L.get("ProductDescription") or "").strip().split("\n")[0][:160] or None,
        "gp": 1 if gp else None,
    }
    # Xbox Store price in NZD; "pr" is [sale, normal] only when it's on special.
    for sku in p.get("DisplaySkuAvailabilities", []):
        for av in sku.get("Availabilities", []):
            pr = (av.get("OrderManagementData") or {}).get("Price") or {}
            if pr.get("MSRP") and pr.get("ListPrice") is not None and pr["ListPrice"] < pr["MSRP"] and "Purchase" in (av.get("Actions") or []):
                e["pr"] = [pr["ListPrice"], pr["MSRP"]]
                break
        if "pr" in e:
            break
    imgs = {i["ImagePurpose"]: i for i in L.get("Images", [])}
    img = imgs.get("Poster") or imgs.get("BoxArt")
    return {k: v for k, v in e.items() if v not in (None, [], "")}, img


STEAM_OUT = ROOT / "steam"
SBEGIN, SEND = "/* STEAM:BEGIN */\n", "\n/* STEAM:END */"


def steam():
    """Steam NZ specials, new releases, coming soon and top sellers, with review ratings."""
    STEAM_OUT.mkdir(exist_ok=True)
    d = json.loads(get("https://store.steampowered.com/api/featuredcategories?cc=nz&l=english"))
    out = {}
    for key, short in (("specials", "deals"), ("new_releases", "new"), ("coming_soon", "soon"), ("top_sellers", "top")):
        items = []
        for x in d.get(key, {}).get("items", [])[:24]:
            i = x.get("id")
            if not i or any(it["id"] == i for it in items):
                continue
            e = {"id": i, "t": x.get("name"), "pct": x.get("discount_percent") or None,
                 "now": (x.get("final_price") or 0) / 100 or None, "was": (x.get("original_price") or 0) / 100 or None}
            try:
                ad = json.loads(get(f"https://store.steampowered.com/api/appdetails?appids={i}&cc=nz&filters=metacritic,recommendations,genres,categories"))[str(i)].get("data") or {}
                e["mc"] = (ad.get("metacritic") or {}).get("score")
                e["n"] = (ad.get("recommendations") or {}).get("total")
                e["g"] = [g["description"] for g in ad.get("genres", [])][:3] or None
                cats = {c["description"] for c in ad.get("categories", [])}
                e["coop"] = [lab for lab, keys in (("Split-screen", ("Shared/Split Screen Co-op", "Shared/Split Screen PvP", "Shared/Split Screen")), ("Online co-op", ("Online Co-op",)), ("Couch co-op", ("Shared/Split Screen Co-op",))) if cats & set(keys)] or None
            except Exception:
                pass
            f = STEAM_OUT / f"{i}.jpg"
            if not f.exists():
                try:
                    f.write_bytes(get(x.get("small_capsule_image") or x.get("header_image")))
                except Exception:
                    pass
            if f.exists():
                e["img"] = 1
            items.append({k: v for k, v in e.items() if v not in (None, "")})
            time.sleep(0.1)
        out[short] = items
    return out


def main():
    OUT.mkdir(exist_ok=True)
    gp = gamepass_ids()
    extra = []
    for t in json.loads(EXTRA.read_text(encoding="utf-8")):
        try:
            i = search_id(t)
            if i:
                extra.append(i)
            else:
                print(f"  not found: {t}")
        except Exception as ex:
            print(f"  search error: {t}: {ex}")
        time.sleep(0.1)
    ids = list(dict.fromkeys(gp + extra))
    games, seen = [], set()
    for i in range(0, len(ids), 20):
        for p in details(ids[i:i + 20]):
            if p.get("ProductType") not in (None, "Game") or SKIP.search(p["LocalizedProperties"][0]["ProductTitle"]):
                continue
            e, img = entry(p, p["ProductId"] in gp)
            k = norm(e["t"])
            if k in seen:
                continue
            seen.add(k)
            f = OUT / f"{e['id']}.jpg"
            if img and not f.exists():
                try:
                    poster = img["ImagePurpose"] == "Poster"
                    url = "https:" + img["Uri"] if img["Uri"].startswith("//") else img["Uri"]
                    f.write_bytes(get(url + ("?w=180&h=270&q=70&format=jpg" if poster else "?w=220&h=220&q=70&format=jpg")))
                except Exception as ex:
                    print(f"  image error: {e['t']}: {ex}")
            if f.exists():
                e["img"] = 1
            games.append(e)
        time.sleep(0.2)
    games.sort(key=lambda g: norm(g["t"]))
    src = PAGE.read_text(encoding="utf-8")
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), src, re.S)
    block = BEGIN + "const GAMES = " + json.dumps(games, ensure_ascii=False, separators=(",", ":")) + ";" + END
    src = src[: m.start()] + block + src[m.end():]
    st = steam()
    from datetime import date
    m = re.search(re.escape(SBEGIN) + r".*?" + re.escape(SEND), src, re.S)
    sblock = SBEGIN + "const STEAM = " + json.dumps(st, ensure_ascii=False, separators=(",", ":")) + f';\nconst DEALS_ASOF = "{date.today().isoformat()}";' + SEND
    src = src[: m.start()] + sblock + src[m.end():]
    PAGE.write_text(src, encoding="utf-8")
    print("steam:", {k: len(v) for k, v in st.items()})
    print(f"{len(games)} games ({sum(1 for g in games if g.get('gp'))} on Game Pass), {sum(1 for g in games if g.get('lc') or g.get('ss'))} with couch co-op or split-screen")


if __name__ == "__main__":
    main()
