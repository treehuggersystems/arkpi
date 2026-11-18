#!/usr/bin/env python3
"""Build the offline address finder used by the Point-to-Point tool.

    scripts/build-addresses.py [--bbox W,S,E,N] [--out FILE] [--counties 21111,21073]

Downloads (public domain, US Census Bureau):
  * Gazetteer: every US city/town, ZIP code and county with its center point (~5 MB)
  * TIGER/Line ADDRFEAT: street address ranges for each county in the region (~1-4 MB each)

and writes one SQLite file (default /opt/offline-data/geocode/addresses.sqlite). Address
positions are interpolated along the street block, typically within 20-50 m of the door.

The region defaults to ARK_REGION_BBOX, else the street-level map region, else
Kentucky/Ohio/Indiana. Re-running resumes: finished counties are skipped.
Standard library only.
"""

import argparse
import csv
import io
import json
import os
import re
import sqlite3
import struct
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.terrain import ABBR, norm_street, street_core  # noqa: E402

CENSUS = "https://www2.census.gov/geo"
DEFAULT_BBOX = "-89.6,36.4,-80.4,42.1"
UA = {"User-Agent": "ARK-Pi offline knowledge server (address builder)"}


def log(*a):
    print(*a, flush=True)


def get(url: str, tries: int = 4) -> bytes:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            err = e
        except OSError as e:
            err = e
        time.sleep(2 + 4 * i)
    raise err


def exists(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers=UA), timeout=20):
            return True
    except (OSError, urllib.error.HTTPError):
        return False


def region_bbox(arg: str | None) -> list[float]:
    s = arg or os.environ.get("ARK_REGION_BBOX")
    if not s:
        maps = Path(os.environ.get("OFFLINE_MAPS_DIR", "/opt/offline-data/maps")) / "layers.json"
        try:
            region = [l for l in json.loads(maps.read_text()) if l.get("file") == "region.pmtiles" and l.get("bbox")]
            if region:
                s = ",".join(map(str, region[0]["bbox"]))
        except (OSError, ValueError):
            pass
    bbox = [float(x) for x in (s or DEFAULT_BBOX).split(",")]
    if len(bbox) != 4 or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
        sys.exit(f"bad bbox {s!r}: want west,south,east,north")
    return bbox


def gazetteer(year: int, kind: str) -> list[dict]:
    url = f"{CENSUS}/docs/maps-data/data/gazetteer/{year}_Gazetteer/{year}_Gaz_{kind}_national.zip"
    z = zipfile.ZipFile(io.BytesIO(get(url)))
    text = z.read(z.namelist()[0]).decode("utf-8", "replace")
    head = text.split("\n", 1)[0]
    sep = "|" if head.count("|") > head.count("\t") else "\t"  # tab until 2025, pipe from 2026
    rows = csv.DictReader(io.StringIO(text), delimiter=sep)
    return [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in rows]


LSAD = re.compile(r"\s+(city|town|village|CDP|borough|municipality|urban county|consolidated government|"
                  r"metro government|metropolitan government|unified government|city and borough|"
                  r"\(balance\)|corporation|comunidad|zona urbana)(\s+\(balance\))?$", re.I)


def place_norm(name: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", name.upper())
    return " ".join(ABBR.get(w, w) if w in ("SAINT", "MOUNT", "FORT") else w for w in s.split())


# --- minimal shapefile + dBASE readers ---------------------------------------------
def read_dbf(data: bytes):
    n, hlen, rlen = struct.unpack("<IHH", data[4:12])
    fields, off = [], 32
    while data[off] != 0x0D:
        name = data[off:off + 11].split(b"\0")[0].decode()
        fields.append((name, data[off + 16]))
        off += 32
    pos = hlen
    for _ in range(n):
        rec = data[pos:pos + rlen]
        pos += rlen
        if rec[:1] == b"*":
            yield None
            continue
        out, o = {}, 1
        for name, size in fields:
            out[name] = rec[o:o + size].decode("utf-8", "replace").strip()
            o += size
        yield out


def read_shp_lines(data: bytes):
    pos = 100
    while pos + 8 <= len(data):
        clen = struct.unpack(">i", data[pos + 4:pos + 8])[0] * 2
        rec = data[pos + 8:pos + 8 + clen]
        pos += 8 + clen
        stype = struct.unpack("<i", rec[:4])[0]
        if stype not in (3, 13, 23):
            yield []
            continue
        nparts, npts = struct.unpack("<ii", rec[36:44])
        pts = struct.unpack(f"<{npts * 2}d", rec[44 + 4 * nparts:44 + 4 * nparts + 16 * npts])
        yield list(zip(pts[0::2], pts[1::2]))


def to_int(s: str) -> int | None:
    return int(s) if s.isdigit() else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS county (geoid TEXT PRIMARY KEY, name TEXT, state TEXT, lat REAL, lon REAL, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS place (name TEXT, norm TEXT, state TEXT, kind TEXT, lat REAL, lon REAL, pop REAL);
CREATE TABLE IF NOT EXISTS street (fullname TEXT, norm TEXT, core TEXT, zip TEXT, hn_from INTEGER, hn_to INTEGER,
                                   parity TEXT, county TEXT, lat REAL, lon REAL, geom BLOB);
CREATE INDEX IF NOT EXISTS street_core ON street(core);
CREATE INDEX IF NOT EXISTS place_norm ON place(norm);
CREATE INDEX IF NOT EXISTS place_kind ON place(kind, name);
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", help="west,south,east,north (default: map region)")
    ap.add_argument("--out", default=os.environ.get("OFFLINE_GEOCODE_DB", "/opt/offline-data/geocode/addresses.sqlite"))
    ap.add_argument("--counties", help="comma-separated county GEOIDs instead of the bbox (e.g. 21111)")
    ap.add_argument("--region-name", default=os.environ.get("ARK_REGION_NAME", ""))
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(out)
    con.executescript(SCHEMA)

    # Newest published Census year (TIGER appears each autumn).
    year = next((y for y in range(date.today().year, date.today().year - 4, -1)
                 if exists(f"{CENSUS}/tiger/TIGER{y}/ADDRFEAT/")
                 and exists(f"{CENSUS}/docs/maps-data/data/gazetteer/{y}_Gazetteer/{y}_Gaz_counties_national.zip")), None)
    if not year:
        sys.exit("Cannot reach census.gov (needs internet).")
    log(f"Census data year: {year}")

    if not con.execute("SELECT 1 FROM place LIMIT 1").fetchone():
        log("Gazetteer: cities, towns, ZIP codes, counties (all US)...")
        counties = gazetteer(year, "counties")
        con.executemany("INSERT OR IGNORE INTO county (geoid, name, state, lat, lon) VALUES (?,?,?,?,?)",
                        [(r["GEOID"], r["NAME"], r["USPS"], float(r["INTPTLAT"]), float(r["INTPTLONG"])) for r in counties])
        rows = []
        for r in counties:
            rows.append((r["NAME"], place_norm(r["NAME"]), r["USPS"], "county", float(r["INTPTLAT"]), float(r["INTPTLONG"]), 0))
        for r in gazetteer(year, "place"):
            name = LSAD.sub("", r["NAME"]).strip()
            # Land area as a stand-in for size when names repeat (no population in the gazetteer).
            rows.append((name, place_norm(name), r["USPS"], "city", float(r["INTPTLAT"]), float(r["INTPTLONG"]),
                         float(r.get("ALAND_SQMI") or 0)))
        for r in gazetteer(year, "zcta"):
            rows.append((r["GEOID"], r["GEOID"], "", "zip", float(r["INTPTLAT"]), float(r["INTPTLONG"]), 0))
        con.executemany("INSERT INTO place VALUES (?,?,?,?,?,?,?)", rows)
        con.commit()
        log(f"  {len(rows):,} places")

    if args.counties:
        todo = [g.strip() for g in args.counties.split(",") if g.strip()]
        region = args.region_name or "selected counties"
    else:
        w, s, e, n = region_bbox(args.bbox)
        pad = 0.3  # include counties whose center is just outside the box
        todo = [r[0] for r in con.execute("SELECT geoid FROM county WHERE lon BETWEEN ? AND ? AND lat BETWEEN ? AND ? ORDER BY geoid",
                                          (w - pad, e + pad, s - pad, n + pad))]
        region = args.region_name or f"{w},{s},{e},{n}"
    done = {r[0] for r in con.execute("SELECT geoid FROM county WHERE done = 1")}
    left = [g for g in todo if g not in done]
    log(f"Street address ranges: {len(todo)} counties ({len(todo) - len(left)} already done)")

    failed = []
    for k, geoid in enumerate(left, 1):
        name = (con.execute("SELECT name || ', ' || state FROM county WHERE geoid = ?", (geoid,)).fetchone() or [geoid])[0]
        url = f"{CENSUS}/tiger/TIGER{year}/ADDRFEAT/tl_{year}_{geoid}_addrfeat.zip"
        try:
            z = zipfile.ZipFile(io.BytesIO(get(url)))
        except urllib.error.HTTPError as e:
            if e.code == 404:  # county with no address ranges
                con.execute("UPDATE county SET done = 1 WHERE geoid = ?", (geoid,))
                con.commit()
                continue
            failed.append(geoid)
            log(f"  [{k}/{len(left)}] {name}: download failed ({e})")
            continue
        except (OSError, zipfile.BadZipFile) as e:
            failed.append(geoid)
            log(f"  [{k}/{len(left)}] {name}: download failed ({e})")
            continue
        base = f"tl_{year}_{geoid}_addrfeat"
        rows = []
        for attrs, line in zip(read_dbf(z.read(base + ".dbf")), read_shp_lines(z.read(base + ".shp"))):
            if not attrs or not line or not attrs.get("FULLNAME"):
                continue
            norm = norm_street(attrs["FULLNAME"])
            core = street_core(norm)
            mid = line[len(line) // 2]
            geom = struct.pack(f"<{len(line) * 2}i", *(round(v * 1e6) for p in line for v in p))
            for side in ("L", "R"):
                a, b = to_int(attrs.get(f"{side}FROMHN", "")), to_int(attrs.get(f"{side}TOHN", ""))
                if a is None or b is None:
                    continue
                rows.append((attrs["FULLNAME"], norm, core, attrs.get(f"ZIP{side}", ""), a, b,
                             attrs.get(f"PARITY{side}", ""), geoid, mid[1], mid[0], geom))
        con.execute("DELETE FROM street WHERE county = ?", (geoid,))
        con.executemany("INSERT INTO street VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        con.execute("UPDATE county SET done = 1 WHERE geoid = ?", (geoid,))
        con.commit()
        log(f"  [{k}/{len(left)}] {name}: {len(rows):,} address ranges")

    total = con.execute("SELECT COUNT(*) FROM street").fetchone()[0]
    ndone = con.execute("SELECT COUNT(*) FROM county WHERE done = 1").fetchone()[0]
    con.executemany("INSERT OR REPLACE INTO meta VALUES (?, ?)",
                    [("segments", str(total)), ("counties", str(ndone)), ("region", region),
                     ("built", datetime.now().strftime("%Y-%m-%d")), ("census_year", str(year))])
    con.commit()
    con.execute("ANALYZE")
    con.close()
    log(f"Done: {total:,} address ranges in {ndone} counties -> {out} ({out.stat().st_size / 1e6:.0f} MB)")
    if failed:
        log(f"{len(failed)} counties failed to download; re-run to retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
