#!/usr/bin/env python3
"""Download terrain elevation tiles (SRTM, 1 arc-second ~30 m) for offline use.

    scripts/fetch-elevation.py [--bbox W,S,E,N] [--dest DIR] [--res 30|90]

Tiles come from the public AWS Terrain Tiles bucket (Mapzen "skadi" SRTM .hgt files) and are
stored uncompressed (25 MB per 1°x1° tile at 30 m, 2.9 MB at 90 m) so the ARK can read any
point instantly. The default region (Kentucky/Ohio/Indiana) is 70 tiles, ~1.8 GB at 30 m.

Region: --bbox, else ARK_REGION_BBOX, else the street-level map region, else KY/OH/IN.
Re-running skips tiles already downloaded. Standard library only.
"""

import argparse
import gzip
import json
import math
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SOURCE = "https://elevation-tiles-prod.s3.amazonaws.com/skadi/{d}/{n}.hgt.gz"
DEFAULT_BBOX = "-89.6,36.4,-80.4,42.1"
FULL = 3601 * 3601 * 2


def region_bbox(arg):
    s = arg or os.environ.get("ARK_REGION_BBOX")
    if not s:
        maps = Path(os.environ.get("OFFLINE_MAPS_DIR", "/opt/offline-data/maps")) / "layers.json"
        try:
            s = next((",".join(map(str, l["bbox"])) for l in json.loads(maps.read_text())
                      if l.get("file") == "region.pmtiles" and l.get("bbox")), None)
        except (OSError, ValueError, KeyError):
            pass
    b = [float(x) for x in (s or DEFAULT_BBOX).split(",")]
    if len(b) != 4 or b[0] >= b[2] or b[1] >= b[3]:
        sys.exit(f"bad bbox {s!r}: want west,south,east,north")
    return b


def name(lat, lon):
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def downsample(src: Path, dst: Path):
    """3601x3601 (1") -> 1201x1201 (3") by keeping every third sample."""
    with open(src, "rb") as f, open(dst, "wb") as out:
        for r in range(3601):
            row = f.read(3601 * 2)
            if r % 3 == 0:
                out.write(b"".join(row[c * 2:c * 2 + 2] for c in range(0, 3601, 3)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox")
    ap.add_argument("--dest", default=os.environ.get("OFFLINE_ELEVATION_DIR", "/opt/offline-data/elevation"))
    ap.add_argument("--res", type=int, choices=(30, 90), default=int(os.environ.get("ARK_ELEVATION_RES", "30")))
    args = ap.parse_args()
    w, s, e, n = region_bbox(args.bbox)
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    want = (FULL if args.res == 30 else 1201 * 1201 * 2)
    tiles = [(la, lo) for la in range(math.floor(s), math.ceil(n)) for lo in range(math.floor(w), math.ceil(e))]
    print(f"Elevation: {len(tiles)} tiles at {args.res} m for {w},{s},{e},{n} -> {dest}", flush=True)
    failed = 0
    for k, (la, lo) in enumerate(tiles, 1):
        t = name(la, lo)
        out = dest / f"{t}.hgt"
        if out.is_file() and out.stat().st_size == want:
            continue
        url = SOURCE.format(d=t[:3], n=t)
        part = dest / f"{t}.part"
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ARK-Pi offline knowledge server"})
                with urllib.request.urlopen(req, timeout=60) as r, gzip.open(r) as gz, open(part, "wb") as f:
                    shutil.copyfileobj(gz, f, 1 << 20)
                if part.stat().st_size != FULL:
                    raise OSError(f"unexpected size {part.stat().st_size}")
                if args.res == 90:
                    small = dest / f"{t}.small"
                    downsample(part, small)
                    part.unlink()
                    small.rename(out)
                else:
                    part.rename(out)
                print(f"  [{k}/{len(tiles)}] {t}", flush=True)
                break
            except urllib.error.HTTPError as err:
                if err.code in (403, 404):  # open ocean: no tile
                    print(f"  [{k}/{len(tiles)}] {t}: none (ocean)", flush=True)
                    break
                time.sleep(3 + 5 * attempt)
            except (OSError, EOFError) as err:
                print(f"  [{k}/{len(tiles)}] {t}: retry ({err})", flush=True)
                time.sleep(3 + 5 * attempt)
        else:
            failed += 1
        part.unlink(missing_ok=True)
    have = list(dest.glob("*.hgt"))
    print(f"Done: {len(have)} tiles, {sum(f.stat().st_size for f in have) / 1e9:.2f} GB in {dest}")
    if failed:
        print(f"{failed} tiles failed; re-run to retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
