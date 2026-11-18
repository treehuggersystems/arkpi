"""Point-to-point geodesy for ARK·π: find places, elevations, azimuth and terrain profile.

Everything works offline from data on disk, with online services as a fallback when the
ARK happens to have internet:

* Places/addresses: ``GEOCODE_DB`` (SQLite built by ``scripts/build-addresses.py`` from US
  Census TIGER address ranges + gazetteer), then OpenStreetMap Nominatim online.
* Elevation: SRTM ``.hgt`` tiles in ``ELEVATION_DIR`` (``scripts/fetch-elevation.py``),
  then the Open-Meteo elevation API online.
* Azimuth: Vincenty on the WGS84 ellipsoid. Magnetic declination: NOAA World Magnetic
  Model (``app/geomag/WMM2025.COF``, valid 2025-2030).

Standard library only.
"""

import json
import math
import mmap
import os
import re
import sqlite3
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from functools import lru_cache
from pathlib import Path

ELEVATION_DIR = Path(os.environ.get("OFFLINE_ELEVATION_DIR", "/opt/offline-data/elevation"))
GEOCODE_DB = Path(os.environ.get("OFFLINE_GEOCODE_DB", "/opt/offline-data/geocode/addresses.sqlite"))
WMM_FILE = Path(__file__).resolve().parent / "geomag" / "WMM2025.COF"
USER_AGENT = "ARK-Pi offline knowledge server (point-to-point tool)"

# WGS84
A_WGS, F_WGS = 6378137.0, 1 / 298.257223563
B_WGS = A_WGS * (1 - F_WGS)
E2 = F_WGS * (2 - F_WGS)
R_EARTH = 6371008.8
K_RADIO = 4 / 3  # standard atmosphere: radio horizon ~15% farther than geometric

rad, deg = math.radians, math.degrees


# =====================================================================================
# Online fallback: remember when the internet is unreachable so lookups stay fast
# =====================================================================================
_offline_until = 0.0
_net_lock = threading.Lock()


def _fetch_json(url: str, timeout: float = 4.0):
    """GET JSON, or None. After a network failure, skips the internet for 2 minutes."""
    global _offline_until
    if time.time() < _offline_until:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError:  # the service answered (busy, rate limit): the internet is fine
        return None
    except (OSError, ValueError):
        with _net_lock:
            _offline_until = time.time() + 120
        return None


# =====================================================================================
# Coordinates: parse lat/lon, DMS, UTM and MGRS
# =====================================================================================
K0 = 0.9996
EP2 = E2 / (1 - E2)
MGRS_BANDS = "CDEFGHJKLMNPQRSTUVWX"


def utm_zone(lat: float, lon: float) -> int:
    zone = int((lon + 180) // 6) + 1
    if 56 <= lat < 64 and 3 <= lon < 12:
        zone = 32
    if 72 <= lat < 84:
        for lo, hi, z in ((0, 9, 31), (9, 21, 33), (21, 33, 35), (33, 42, 37)):
            if lo <= lon < hi:
                zone = z
    return min(zone, 60)


def _meridian_arc(phi: float) -> float:
    e4, e6 = E2 * E2, E2 ** 3
    return A_WGS * ((1 - E2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
                    - (3 * E2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
                    + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi)
                    - (35 * e6 / 3072) * math.sin(6 * phi))


def to_utm(lat: float, lon: float, zone: int | None = None) -> tuple[int, float, float]:
    zone = zone or utm_zone(lat, lon)
    phi, lam0 = rad(lat), rad((zone - 1) * 6 - 180 + 3)
    n = A_WGS / math.sqrt(1 - E2 * math.sin(phi) ** 2)
    t, c, a = math.tan(phi) ** 2, EP2 * math.cos(phi) ** 2, math.cos(phi) * (rad(lon) - lam0)
    m = _meridian_arc(phi)
    e = K0 * n * (a + (1 - t + c) * a ** 3 / 6 + (5 - 18 * t + t * t + 72 * c - 58 * EP2) * a ** 5 / 120) + 500000
    nn = K0 * (m + n * math.tan(phi) * (a * a / 2 + (5 - t + 9 * c + 4 * c * c) * a ** 4 / 24
                                       + (61 - 58 * t + t * t + 600 * c - 330 * EP2) * a ** 6 / 720))
    if lat < 0:
        nn += 10000000
    return zone, e, nn


def from_utm(zone: int, easting: float, northing: float, south: bool) -> tuple[float, float]:
    x, y = easting - 500000, northing - (10000000 if south else 0)
    m = y / K0
    mu = m / (A_WGS * (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - E2)) / (1 + math.sqrt(1 - E2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    n1 = A_WGS / math.sqrt(1 - E2 * math.sin(phi1) ** 2)
    t1, c1 = math.tan(phi1) ** 2, EP2 * math.cos(phi1) ** 2
    r1 = A_WGS * (1 - E2) / (1 - E2 * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * K0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (d * d / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * EP2) * d ** 4 / 24
                                              + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * EP2 - 3 * c1 * c1) * d ** 6 / 720)
    lon = (d - (1 + 2 * t1 + c1) * d ** 3 / 6
           + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * EP2 + 24 * t1 * t1) * d ** 5 / 120) / math.cos(phi1)
    return deg(lat), (zone - 1) * 6 - 180 + 3 + deg(lon)


def to_mgrs(lat: float, lon: float, digits: int = 5) -> str:
    if not -80 <= lat <= 84:
        return ""
    zone, e, n = to_utm(lat, lon)
    band = MGRS_BANDS[min(19, int((lat + 80) // 8))]
    s = zone % 6 or 6
    col = ["ABCDEFGH", "JKLMNPQR", "STUVWXYZ"][(s - 1) % 3][int(e // 100000) - 1]
    row = "ABCDEFGHJKLMNPQRSTUV"[(int(n // 100000) + (5 if s % 2 == 0 else 0)) % 20]
    div = 10 ** (5 - digits)
    return f"{zone}{band} {col}{row} {int(e % 100000) // div:0{digits}d} {int(n % 100000) // div:0{digits}d}"


def from_mgrs(text: str) -> tuple[float, float] | None:
    m = re.fullmatch(r"(\d{1,2})\s*([C-HJ-NP-X])\s*([A-HJ-NP-Z])([A-HJ-NP-V])\s*(\d+)\s*(\d*)", text.strip().upper())
    if not m:
        return None
    zone, band, col, row, e_s, n_s = int(m[1]), m[2], m[3], m[4], m[5], m[6]
    if not n_s:  # digits run together: split in half
        if len(e_s) % 2:
            return None
        e_s, n_s = e_s[: len(e_s) // 2], e_s[len(e_s) // 2:]
    if len(e_s) != len(n_s) or not 1 <= len(e_s) <= 5 or not 1 <= zone <= 60:
        return None
    s = zone % 6 or 6
    cols = ["ABCDEFGH", "JKLMNPQR", "STUVWXYZ"][(s - 1) % 3]
    if col not in cols:
        return None
    scale = 10 ** (5 - len(e_s))
    # Centre of the grid square the reference names (a 4-digit ref is a 100 m square).
    easting = (cols.index(col) + 1) * 100000 + int(e_s) * scale + scale / 2
    row_i = ("ABCDEFGHJKLMNPQRSTUV".index(row) - (5 if s % 2 == 0 else 0)) % 20
    northing = row_i * 100000 + int(n_s) * scale + scale / 2
    band_lat = -80 + 8 * MGRS_BANDS.index(band)
    south = band_lat < 0
    _, _, band_min_n = to_utm(band_lat, (zone - 1) * 6 - 180 + 3, zone)
    while northing < band_min_n - 100000:
        northing += 2000000
    return from_utm(zone, easting, northing, south)


def _dms_part(s: str) -> float | None:
    m = re.fullmatch(r"\s*([NSEW])?\s*(\d+(?:\.\d+)?)\s*[°d:\s]\s*(?:(\d+(?:\.\d+)?)\s*['′m:\s]?\s*)?(?:(\d+(?:\.\d+)?)\s*[\"″s]?\s*)?([NSEW])?\s*",
                     s, re.I)
    if not m:
        return None
    v = float(m[2]) + float(m[3] or 0) / 60 + float(m[4] or 0) / 3600
    h = (m[1] or m[5] or "").upper()
    return -v if h in ("S", "W") else v


def parse_point(text: str) -> tuple[float, float] | None:
    """Coordinates in any common format, or None if it isn't coordinates."""
    t = text.strip()
    # Decimal degrees: "38.25, -85.76" or "38.25 -85.76"
    m = re.fullmatch(r"(-?\d{1,2}(?:\.\d+)?)\s*°?\s*([NS])?\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*°?\s*([EW])?", t, re.I)
    if m:
        lat, lon = float(m[1]), float(m[3])
        if (m[2] or "").upper() == "S":
            lat = -abs(lat)
        if (m[4] or "").upper() == "W":
            lon = -abs(lon)
        return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None
    # MGRS: "16S FG 12345 67890"
    p = from_mgrs(t)
    if p:
        return p
    # UTM: "16S 612345E 4234567N" or "16 612345 4234567"
    m = re.fullmatch(r"(\d{1,2})\s*([C-HJ-NP-X])?\s+(\d{6}(?:\.\d+)?)\s*E?\s+(\d{1,8}(?:\.\d+)?)\s*N?", t, re.I)
    if m:
        band = (m[2] or "N").upper()
        return from_utm(int(m[1]), float(m[3]), float(m[4]), south=band < "N")
    # DMS: 38°15'30"N 85°45'12"W (hemisphere letters required, to avoid guessing)
    m = re.fullmatch(r"(.+?[NS])\s*[,;]?\s*(.+?[EW])", t, re.I) or re.fullmatch(r"([NS].+?)\s*[,;]?\s*([EW].+)", t, re.I)
    if m and ("°" in t or "'" in t or '"' in t or re.search(r"\d\s+\d", t)):
        lat, lon = _dms_part(m[1]), _dms_part(m[2])
        if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    return None


# =====================================================================================
# Geodesic inverse (Vincenty) on WGS84
# =====================================================================================
def inverse(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float, float]:
    """Distance (m), initial azimuth and final azimuth (degrees true)."""
    if abs(lat1 - lat2) < 1e-12 and abs(lon1 - lon2) < 1e-12:
        return 0.0, 0.0, 0.0
    f = F_WGS
    L = rad(lon2 - lon1)
    u1, u2 = math.atan((1 - f) * math.tan(rad(lat1))), math.atan((1 - f) * math.tan(rad(lat2)))
    su1, cu1, su2, cu2 = math.sin(u1), math.cos(u1), math.sin(u2), math.cos(u2)
    lam = L
    for _ in range(200):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.hypot(cu2 * sl, cu1 * su2 - su1 * cu2 * cl)
        if ss == 0:
            return 0.0, 0.0, 0.0
        cs = su1 * su2 + cu1 * cu2 * cl
        sigma = math.atan2(ss, cs)
        sa = cu1 * cu2 * sl / ss
        c2a = 1 - sa * sa
        c2sm = cs - 2 * su1 * su2 / c2a if c2a else 0.0
        C = f / 16 * c2a * (4 + f * (4 - 3 * c2a))
        prev = lam
        lam = L + (1 - C) * f * sa * (sigma + C * ss * (c2sm + C * cs * (-1 + 2 * c2sm * c2sm)))
        if abs(lam - prev) < 1e-12:
            break
    else:  # nearly antipodal: fall back to the sphere
        return _spherical(lat1, lon1, lat2, lon2)
    u2s = c2a * (A_WGS ** 2 - B_WGS ** 2) / B_WGS ** 2
    A = 1 + u2s / 16384 * (4096 + u2s * (-768 + u2s * (320 - 175 * u2s)))
    B = u2s / 1024 * (256 + u2s * (-128 + u2s * (74 - 47 * u2s)))
    ds = B * ss * (c2sm + B / 4 * (cs * (-1 + 2 * c2sm ** 2) - B / 6 * c2sm * (-3 + 4 * ss ** 2) * (-3 + 4 * c2sm ** 2)))
    dist = B_WGS * A * (sigma - ds)
    az1 = deg(math.atan2(cu2 * math.sin(lam), cu1 * su2 - su1 * cu2 * math.cos(lam))) % 360
    az2 = deg(math.atan2(cu1 * math.sin(lam), -su1 * cu2 + cu1 * su2 * math.cos(lam))) % 360
    return dist, az1, az2


def _spherical(lat1, lon1, lat2, lon2):
    p1, p2, dl = rad(lat1), rad(lat2), rad(lon2 - lon1)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 2 * R_EARTH * math.asin(min(1, math.sqrt(h)))
    brg = lambda a, b, c, dd: deg(math.atan2(math.sin(dd) * math.cos(b), math.cos(a) * math.sin(b) - math.sin(a) * math.cos(b) * math.cos(dd))) % 360
    return d, brg(p1, p2, lat1, dl), (brg(p2, p1, lat2, -dl) + 180) % 360


def intermediate(lat1, lon1, lat2, lon2, frac: float) -> tuple[float, float]:
    """Point a fraction of the way along the great circle (sphere; ample for terrain sampling)."""
    p1, l1, p2, l2 = rad(lat1), rad(lon1), rad(lat2), rad(lon2)
    d = 2 * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2))
    if d < 1e-12:
        return lat1, lon1
    a, b = math.sin((1 - frac) * d) / math.sin(d), math.sin(frac * d) / math.sin(d)
    x = a * math.cos(p1) * math.cos(l1) + b * math.cos(p2) * math.cos(l2)
    y = a * math.cos(p1) * math.sin(l1) + b * math.cos(p2) * math.sin(l2)
    z = a * math.sin(p1) + b * math.sin(p2)
    return deg(math.atan2(z, math.hypot(x, y))), deg(math.atan2(y, x))


# =====================================================================================
# Magnetic declination: NOAA World Magnetic Model
# =====================================================================================
@lru_cache(maxsize=1)
def _wmm():
    lines = WMM_FILE.read_text().splitlines()
    epoch = float(lines[0].split()[0])
    nmax = 12
    g = [[0.0] * (nmax + 1) for _ in range(nmax + 1)]
    h, gd, hd = ([[0.0] * (nmax + 1) for _ in range(nmax + 1)] for _ in range(3))
    for line in lines[1:]:
        p = line.split()
        if len(p) < 6 or p[0].startswith("9999"):
            break
        n, m = int(p[0]), int(p[1])
        g[n][m], h[n][m], gd[n][m], hd[n][m] = map(float, p[2:6])
    # Schmidt semi-normalisation factors (the recursion below is Gauss-normalised).
    s = [[0.0] * (nmax + 1) for _ in range(nmax + 1)]
    s[0][0] = 1.0
    for n in range(1, nmax + 1):
        s[n][0] = s[n - 1][0] * (2 * n - 1) / n
        for m in range(1, n + 1):
            s[n][m] = s[n][m - 1] * math.sqrt((n - m + 1) * (2 if m == 1 else 1) / (n + m))
    return epoch, nmax, g, h, gd, hd, s


def magnetic(lat: float, lon: float, alt_m: float = 0.0, year: float | None = None) -> dict:
    """Declination (deg, east positive), inclination, and field components (nT)."""
    epoch, nmax, g, h, gd, hd, s = _wmm()
    if year is None:
        today = date.today()
        year = today.year + (today.timetuple().tm_yday - 0.5) / (366 if today.year % 4 == 0 else 365)
    dt = year - epoch
    a_km, h_km = A_WGS / 1000, alt_m / 1000
    # Geodetic -> geocentric spherical
    phi = rad(lat)
    rc = a_km / math.sqrt(1 - E2 * math.sin(phi) ** 2)
    p = (rc + h_km) * math.cos(phi)
    z = (rc * (1 - E2) + h_km) * math.sin(phi)
    r = math.hypot(p, z)
    phic = math.asin(z / r)
    x, y = math.sin(phic), math.cos(phic)  # cos(theta), sin(theta)
    P = [[0.0] * (nmax + 1) for _ in range(nmax + 1)]
    dP = [[0.0] * (nmax + 1) for _ in range(nmax + 1)]
    P[0][0] = 1.0
    for n in range(1, nmax + 1):
        for m in range(n + 1):
            if n == m:
                P[n][m] = y * P[n - 1][m - 1]
                dP[n][m] = y * dP[n - 1][m - 1] + x * P[n - 1][m - 1]
            elif n == 1:
                P[n][m] = x * P[n - 1][m]
                dP[n][m] = x * dP[n - 1][m] - y * P[n - 1][m]
            else:
                k = ((n - 1) ** 2 - m * m) / ((2 * n - 1) * (2 * n - 3))
                P[n][m] = x * P[n - 1][m] - k * P[n - 2][m]
                dP[n][m] = x * dP[n - 1][m] - y * P[n - 1][m] - k * dP[n - 2][m]
    lam = rad(lon)
    ref = 6371.2
    bx = by = bz = 0.0
    for n in range(1, nmax + 1):
        ar = (ref / r) ** (n + 2)
        for m in range(n + 1):
            gnm = (g[n][m] + gd[n][m] * dt) * s[n][m]
            hnm = (h[n][m] + hd[n][m] * dt) * s[n][m]
            cm, sm = math.cos(m * lam), math.sin(m * lam)
            bx += ar * (gnm * cm + hnm * sm) * dP[n][m]
            by += ar * m * (gnm * sm - hnm * cm) * P[n][m]
            bz -= ar * (n + 1) * (gnm * cm + hnm * sm) * P[n][m]
    by = by / y if y > 1e-10 else by
    # Rotate from geocentric to geodetic frame
    psi = phic - phi
    X = bx * math.cos(psi) - bz * math.sin(psi)
    Z = bx * math.sin(psi) + bz * math.cos(psi)
    H = math.hypot(X, by)
    return {"declination": deg(math.atan2(by, X)), "inclination": deg(math.atan2(Z, H)),
            "x": X, "y": by, "z": Z, "h": H, "f": math.hypot(H, Z), "model": "WMM2025", "year": round(year, 2),
            "valid": epoch <= year <= epoch + 5}


# =====================================================================================
# Elevation: SRTM .hgt tiles (1 or 3 arc-second), online fallback
# =====================================================================================
class _Tile:
    __slots__ = ("mm", "n")

    def __init__(self, path: Path):
        f = open(path, "rb")
        self.mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        f.close()
        self.n = int(round(math.sqrt(len(self.mm) / 2)))

    def at(self, row: int, col: int) -> int | None:
        v = struct.unpack_from(">h", self.mm, 2 * (row * self.n + col))[0]
        return None if v == -32768 else v


def tile_name(lat: float, lon: float) -> str:
    la, lo = math.floor(lat), math.floor(lon)
    return f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"


@lru_cache(maxsize=64)
def _tile(name: str) -> _Tile | None:
    path = ELEVATION_DIR / f"{name}.hgt"
    try:
        return _Tile(path) if path.is_file() and path.stat().st_size > 0 else None
    except (OSError, ValueError):
        return None


def elevation_offline(lat: float, lon: float) -> float | None:
    """Bilinear-interpolated elevation in metres from local tiles, or None."""
    t = _tile(tile_name(lat, lon))
    if not t:
        return None
    n1 = t.n - 1
    fy = (math.floor(lat) + 1 - lat) * n1   # rows run north -> south
    fx = (lon - math.floor(lon)) * n1
    r0, c0 = min(int(fy), n1 - 1), min(int(fx), n1 - 1)
    dy, dx = fy - r0, fx - c0
    corners = [(t.at(r0, c0), (1 - dx) * (1 - dy)), (t.at(r0, c0 + 1), dx * (1 - dy)),
               (t.at(r0 + 1, c0), (1 - dx) * dy), (t.at(r0 + 1, c0 + 1), dx * dy)]
    good = [(v, w) for v, w in corners if v is not None]
    if not good:
        return None
    wsum = sum(w for _, w in good)
    return sum(v * w for v, w in good) / wsum if wsum > 1e-9 else sum(v for v, _ in good) / len(good)


def elevations(points: list[tuple[float, float]]) -> tuple[list[float | None], str]:
    """Elevations for many points; source is 'offline', 'online', 'mixed' or 'none'.

    Points missing from the local tiles are asked online in a single request (Open-Meteo
    takes 100): both ends first, so the elevation change survives, then an even spread.
    """
    out = [elevation_offline(la, lo) for la, lo in points]
    n_off = sum(v is not None for v in out)
    missing = [i for i, v in enumerate(out) if v is None]
    got_online = False
    if missing:
        ends = [i for i in dict.fromkeys((0, len(points) - 1)) if out[i] is None]
        rest = [i for i in missing if i not in ends]
        room = 100 - len(ends)
        if len(rest) > room:
            rest = [rest[int(k * len(rest) / room)] for k in range(room)]
        ask = ends + rest
        q = urllib.parse.urlencode({"latitude": ",".join(f"{points[i][0]:.5f}" for i in ask),
                                    "longitude": ",".join(f"{points[i][1]:.5f}" for i in ask)})
        data = _fetch_json("https://api.open-meteo.com/v1/elevation?" + q, timeout=6)
        if data and len(data.get("elevation") or []) == len(ask):
            for i, v in zip(ask, data["elevation"]):
                if v is not None and not (isinstance(v, float) and math.isnan(v)):
                    out[i] = float(v)
                    got_online = True
    src = "none" if all(v is None for v in out) else \
        "offline" if not got_online else "online" if n_off == 0 else "mixed"
    return out, src


def elevation_status() -> dict:
    files = sorted(ELEVATION_DIR.glob("*.hgt")) if ELEVATION_DIR.is_dir() else []
    if not files:
        return {"tiles": 0}
    lats, lons = [], []
    for f in files:
        m = re.fullmatch(r"([NS])(\d\d)([EW])(\d\d\d)", f.stem)
        if m:
            lats.append(int(m[2]) * (1 if m[1] == "N" else -1))
            lons.append(int(m[4]) * (1 if m[3] == "E" else -1))
    res = 30 if files[0].stat().st_size > 20_000_000 else 90
    return {"tiles": len(files), "resolution_m": res,
            "bbox": [min(lons), min(lats), max(lons) + 1, max(lats) + 1] if lats else None}


# =====================================================================================
# Places & addresses
# =====================================================================================
STATES = {
    "AL": "ALABAMA", "AK": "ALASKA", "AZ": "ARIZONA", "AR": "ARKANSAS", "CA": "CALIFORNIA", "CO": "COLORADO",
    "CT": "CONNECTICUT", "DE": "DELAWARE", "DC": "DISTRICT OF COLUMBIA", "FL": "FLORIDA", "GA": "GEORGIA",
    "HI": "HAWAII", "ID": "IDAHO", "IL": "ILLINOIS", "IN": "INDIANA", "IA": "IOWA", "KS": "KANSAS",
    "KY": "KENTUCKY", "LA": "LOUISIANA", "ME": "MAINE", "MD": "MARYLAND", "MA": "MASSACHUSETTS",
    "MI": "MICHIGAN", "MN": "MINNESOTA", "MS": "MISSISSIPPI", "MO": "MISSOURI", "MT": "MONTANA",
    "NE": "NEBRASKA", "NV": "NEVADA", "NH": "NEW HAMPSHIRE", "NJ": "NEW JERSEY", "NM": "NEW MEXICO",
    "NY": "NEW YORK", "NC": "NORTH CAROLINA", "ND": "NORTH DAKOTA", "OH": "OHIO", "OK": "OKLAHOMA",
    "OR": "OREGON", "PA": "PENNSYLVANIA", "RI": "RHODE ISLAND", "SC": "SOUTH CAROLINA", "SD": "SOUTH DAKOTA",
    "TN": "TENNESSEE", "TX": "TEXAS", "UT": "UTAH", "VT": "VERMONT", "VA": "VIRGINIA", "WA": "WASHINGTON",
    "WV": "WEST VIRGINIA", "WI": "WISCONSIN", "WY": "WYOMING", "PR": "PUERTO RICO",
}
STATE_BY_NAME = {v: k for k, v in STATES.items()}

# USPS-style abbreviations, matching how TIGER spells street names ("N Main St").
ABBR = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W", "NORTHEAST": "NE", "NORTHWEST": "NW",
    "SOUTHEAST": "SE", "SOUTHWEST": "SW",
    "STREET": "ST", "STR": "ST", "AVENUE": "AVE", "AV": "AVE", "ROAD": "RD", "DRIVE": "DR", "LANE": "LN",
    "COURT": "CT", "CIRCLE": "CIR", "BOULEVARD": "BLVD", "PLACE": "PL", "TERRACE": "TER", "PARKWAY": "PKWY",
    "HIGHWAY": "HWY", "HWAY": "HWY", "TRAIL": "TRL", "SQUARE": "SQ", "ROUTE": "RTE", "RT": "RTE",
    "EXPRESSWAY": "EXPY", "FREEWAY": "FWY", "TURNPIKE": "TPKE", "CROSSING": "XING", "POINT": "PT",
    "RIDGE": "RDG", "HOLLOW": "HOLW", "BRANCH": "BR", "CREEK": "CRK", "VALLEY": "VLY", "HILL": "HL",
    "HILLS": "HLS", "HEIGHTS": "HTS", "MOUNTAIN": "MTN", "LAKE": "LK", "ALLEY": "ALY", "BYPASS": "BYP",
    "CENTER": "CTR", "COVE": "CV", "ESTATES": "ESTS", "GROVE": "GRV", "KNOLL": "KNL", "LANDING": "LNDG",
    "MEADOW": "MDW", "MEADOWS": "MDWS", "ORCHARD": "ORCH", "PLAZA": "PLZ", "SPRING": "SPG", "SPRINGS": "SPGS",
    "STATION": "STA", "VIEW": "VW", "VILLAGE": "VLG", "WOODS": "WDS", "FORK": "FRK", "FORKS": "FRKS",
    "BEND": "BND", "BLUFF": "BLF", "GLEN": "GLN", "GARDENS": "GDNS", "HARBOR": "HBR", "JUNCTION": "JCT",
    "MANOR": "MNR", "MILL": "ML", "MILLS": "MLS", "COUNTY": "CO", "MOUNT": "MT", "FORT": "FT",
    "SAINT": "ST", "INTERSTATE": "I", "FIRST": "1ST", "SECOND": "2ND", "THIRD": "3RD", "FOURTH": "4TH",
    "FIFTH": "5TH", "SIXTH": "6TH", "SEVENTH": "7TH", "EIGHTH": "8TH", "NINTH": "9TH", "TENTH": "10TH",
    "ELEVENTH": "11TH", "TWELFTH": "12TH",
}
DIRS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
SUFFIXES = {
    "ST", "AVE", "RD", "DR", "LN", "CT", "CIR", "BLVD", "PL", "TER", "PKWY", "HWY", "TRL", "SQ", "RTE", "EXPY",
    "FWY", "TPKE", "XING", "PT", "RDG", "HOLW", "BR", "CRK", "VLY", "HL", "HLS", "HTS", "LOOP", "WAY", "PIKE",
    "RUN", "PATH", "PASS", "ROW", "WALK", "ALY", "BYP", "CTR", "CV", "ESTS", "GRV", "KNL", "LNDG", "MDW",
    "MDWS", "ORCH", "PLZ", "SPG", "SPGS", "STA", "VW", "VLG", "WDS", "FRK", "FRKS", "BND", "BLF", "GLN",
    "GDNS", "HBR", "JCT", "MNR", "ML", "MLS", "OVAL", "PARK", "TRCE", "TRACE", "LK", "MTN",
}
UNIT_RE = re.compile(r"\s+(?:(?:APT|APARTMENT|UNIT|STE|SUITE|LOT|BLDG|TRLR|RM)\b\s*#?|#)\s*[A-Z]?\d+[A-Z]?\b")


def norm_street(s: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", s.upper().replace("-", " "))
    return " ".join(ABBR.get(w, w) for w in s.split())


def street_core(norm: str) -> str:
    """Street name without directionals or the type suffix: 'N MAIN ST' -> 'MAIN'."""
    w = norm.split()
    if len(w) > 1 and w[0] in DIRS:
        w = w[1:]
    if len(w) > 1 and w[-1] in DIRS:
        w = w[:-1]
    if len(w) > 1 and w[-1] in SUFFIXES:
        w = w[:-1]
    return " ".join(w)


def _suffix(norm: str) -> str | None:
    w = [x for x in norm.split() if x not in DIRS]
    return w[-1] if len(w) > 1 and w[-1] in SUFFIXES else None


def street_variants(norm: str) -> list[str]:
    """Alternate spellings for numbered highways ("KY 22", "SR 22", "US 60", "CR 5")."""
    out = [norm]
    m = re.fullmatch(r"(?:([A-Z]{2}) )?(?:STATE )?(?:HWY |RTE |SR |RD )?(\d+[A-Z]?)", norm)
    if m and (m[1] in STATES or m[1] == "SR" or norm.startswith(("STATE", "HWY", "RTE", "SR"))):
        n = m[2]
        out += [f"STATE HWY {n}", f"STATE RTE {n}", f"HWY {n}", f"STATE RD {n}"]
    m = re.fullmatch(r"US (?:HWY |RTE )?(\d+[A-Z]?)", norm)
    if m:
        out += [f"US HWY {m[1]}", f"US RTE {m[1]}"]
    m = re.fullmatch(r"(?:CR|CO RD|CO HWY|CO RTE) (\d+[A-Z]?)", norm)
    if m:
        out += [f"CO RD {m[1]}", f"CO HWY {m[1]}", f"CO RTE {m[1]}"]
    m = re.fullmatch(r"I (\d+)", norm)
    if m:
        out += [f"I {m[1]}", f"INTERSTATE {m[1]}"]
    return list(dict.fromkeys(out))


def parse_address(q: str) -> dict:
    """Split '123 N Main Street, Springfield, KY 40069' into number, street, city, state, zip."""
    s = UNIT_RE.sub("", re.sub(r"\s+", " ", q.upper().replace(".", " ").replace("#", " # "))).strip(" ,")
    out = {"number": None, "street": None, "city": None, "state": None, "zip": None}
    m = re.search(r"\b(\d{5})(?:-\d{4})?\s*$", s)
    if m:
        out["zip"], s = m[1], s[: m.start()].strip(" ,")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    # State: trailing 2-letter code or full name
    if parts:
        last = parts[-1]
        for name, code in sorted(STATE_BY_NAME.items(), key=lambda kv: -len(kv[0])):
            if last == name or last.endswith(" " + name):
                out["state"], parts[-1] = code, last[: -len(name)].strip()
                break
        else:
            m = re.search(r"(?:^|\s)([A-Z]{2})$", last)
            if m and m[1] in STATES and (len(parts) > 1 or re.match(r"\d", parts[0])):
                out["state"], parts[-1] = m[1], last[: m.start()].strip()
        parts = [p for p in parts if p]
    if not parts:
        return out
    first = parts[0]
    m = re.match(r"(\d+)[A-Z]?(?:\s*-\s*\d+)?\s+(.+)", first)
    if m:
        out["number"], street = int(m[1]), m[2]
        if len(parts) > 1:
            out["city"] = parts[1]
        else:  # no commas: city is whatever follows the street-type word
            words = norm_street(street).split()
            idx = max((i for i, w in enumerate(words) if w in SUFFIXES and i > 0), default=None)
            if idx is not None and idx < len(words) - 1:
                tail = words[idx + 1:]
                if tail and tail[0] in DIRS:  # "MAIN ST N LOUISVILLE"
                    idx += 1
                    tail = tail[1:]
                street, out["city"] = " ".join(words[: idx + 1]), " ".join(tail) or None
        out["street"] = norm_street(street)
    else:
        out["city"] = parts[0] if len(parts) == 1 or not out["state"] else parts[0]
    return out


def _db() -> sqlite3.Connection | None:
    if not GEOCODE_DB.is_file():
        return None
    con = sqlite3.connect(f"file:{GEOCODE_DB}?mode=ro", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


_db_local = threading.local()


def db() -> sqlite3.Connection | None:
    con = getattr(_db_local, "con", None)
    if con is None:
        con = _db()
        _db_local.con = con
    return con


def _km(lat1, lon1, lat2, lon2):
    x = rad(lon2 - lon1) * math.cos(rad((lat1 + lat2) / 2))
    return math.hypot(x, rad(lat2 - lat1)) * 6371.0


def _interp_line(geom: bytes, frac: float) -> tuple[float, float]:
    pts = [(geom[i] / 1e6, geom[i + 1] / 1e6) for i in range(0, len(geom), 2)]
    if len(pts) == 1:
        return pts[0][1], pts[0][0]
    seg = [_km(a[1], a[0], b[1], b[0]) for a, b in zip(pts, pts[1:])]
    target, acc = sum(seg) * max(0.0, min(1.0, frac)), 0.0
    for (a, b), L in zip(zip(pts, pts[1:]), seg):
        if acc + L >= target and L > 0:
            t = (target - acc) / L
            return a[1] + (b[1] - a[1]) * t, a[0] + (b[0] - a[0]) * t
        acc += L
    return pts[-1][1], pts[-1][0]


def _unpack(blob: bytes):
    return struct.unpack(f"<{len(blob) // 4}i", blob)


def find_places(con, name: str, state: str | None, limit: int = 5) -> list[dict]:
    key = re.sub(r"[^A-Z0-9 ]", " ", name.upper())
    key = " ".join(ABBR.get(w, w) if w in ("SAINT", "MOUNT", "FORT") else w for w in key.split())
    if not key:
        return []
    sql = "SELECT name, state, kind, lat, lon, pop FROM place WHERE norm = ?" + (" AND state = ?" if state else "")
    rows = con.execute(sql + " ORDER BY pop DESC LIMIT ?", (key, state, limit) if state else (key, limit)).fetchall()
    if not rows:
        rows = con.execute("SELECT name, state, kind, lat, lon, pop FROM place WHERE norm LIKE ?"
                           + (" AND state = ?" if state else "") + " ORDER BY pop DESC LIMIT ?",
                           (key + "%", state, limit) if state else (key + "%", limit)).fetchall()
    return [dict(r) for r in rows]


def geocode_offline(q: str, limit: int = 6) -> list[dict]:
    con = db()
    if con is None:
        return []
    a = parse_address(q)
    results: list[dict] = []
    # ZIP code alone
    if a["zip"] and not a["street"] and not a["city"]:
        r = con.execute("SELECT name, lat, lon FROM place WHERE kind='zip' AND name=?", (a["zip"],)).fetchone()
        if r:
            return [{"label": f"ZIP {r['name']}", "lat": r["lat"], "lon": r["lon"], "precision": "zip"}]
    anchor = None  # (lat, lon) of the named city or ZIP, to rank streets by
    if a["city"]:
        cities = find_places(con, a["city"], a["state"], 3)
        if cities:
            anchor = (cities[0]["lat"], cities[0]["lon"])
        if not a["street"]:
            return [{"label": f"{c['name']}, {c['state']}", "lat": c["lat"], "lon": c["lon"],
                     "precision": c["kind"]} for c in cities]
    if a["zip"] and not anchor:
        r = con.execute("SELECT lat, lon FROM place WHERE kind='zip' AND name=?", (a["zip"],)).fetchone()
        if r:
            anchor = (r["lat"], r["lon"])
    if not a["street"]:
        return []
    variants = street_variants(a["street"])
    cores = list(dict.fromkeys(street_core(v) for v in variants))
    qmarks = ",".join("?" * len(cores))
    rows = con.execute(f"SELECT s.*, c.name AS county_name, c.state AS st FROM street s JOIN county c ON c.geoid = s.county "
                       f"WHERE s.core IN ({qmarks})" + (" AND c.state = ?" if a["state"] else "") + " LIMIT 20000",
                       cores + ([a["state"]] if a["state"] else [])).fetchall()
    num = a["number"]
    q_suffix = _suffix(a["street"])
    scored = []
    for r in rows:
        lo, hi = min(r["hn_from"], r["hn_to"]), max(r["hn_from"], r["hn_to"])
        exact = num is not None and lo <= num <= hi and (r["parity"] not in ("O", "E") or (num % 2 == 1) == (r["parity"] == "O"))
        score = (8 if exact else 0) + (3 if r["norm"] in variants else 0) + (4 if a["zip"] and r["zip"] == a["zip"] else 0)
        r_suffix = _suffix(r["norm"])
        if q_suffix and r_suffix and q_suffix != r_suffix:  # "Capital Ave" is not "Capital Heights"
            score -= 12
        mid = (r["lat"], r["lon"])
        if anchor:
            score -= min(10.0, _km(*anchor, *mid) / 4)
        gap = 0 if exact or num is None else min(abs(num - lo), abs(num - hi))
        scored.append((score, -gap, r, exact))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if any(x[3] for x in scored):  # a block that holds this number exists: drop "near" guesses
        scored = [x for x in scored if x[3]]
    seen = set()
    for score, _, r, exact in scored:
        key = (r["fullname"], r["zip"], r["county"])
        if key in seen:
            continue
        seen.add(key)
        geom = _unpack(r["geom"])
        if exact and r["hn_to"] != r["hn_from"]:
            frac = (num - r["hn_from"]) / (r["hn_to"] - r["hn_from"])
        else:
            frac = 0.5
        lat, lon = _interp_line(geom, frac)
        place = f"{r['zip']} " if r["zip"] else ""
        label = f"{num} {r['fullname']}" if exact else f"{r['fullname']} (near {num})" if num else r["fullname"]
        results.append({"label": f"{label}, {place}{r['county_name']}, {r['st']}", "lat": round(lat, 6), "lon": round(lon, 6),
                        "precision": "address" if exact else "street"})
        if len(results) >= limit:
            break
    return results


def region_bbox() -> list[float] | None:
    """The home region (west, south, east, north): installer setting, else map region, else elevation tiles."""
    s = os.environ.get("ARK_REGION_BBOX")
    if not s:
        try:
            maps = Path(os.environ.get("OFFLINE_MAPS_DIR", "/opt/offline-data/maps")) / "layers.json"
            s = next((",".join(map(str, l["bbox"])) for l in json.loads(maps.read_text())
                      if l.get("file") == "region.pmtiles" and l.get("bbox")), None)
        except (OSError, ValueError, KeyError):
            s = None
    try:
        return [float(x) for x in s.split(",")][:4] if s else elevation_status().get("bbox")
    except ValueError:
        return None


def geocode_online(q: str, limit: int = 5) -> list[dict]:
    params = {"q": q, "format": "jsonv2", "limit": limit}
    box = region_bbox()
    if box:  # prefer (not limit to) the home region
        params["viewbox"] = ",".join(f"{v:g}" for v in box)
    data = _fetch_json("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params), timeout=5)
    out = []
    for r in data or []:
        try:
            out.append({"label": r.get("display_name", q), "lat": round(float(r["lat"]), 6),
                        "lon": round(float(r["lon"]), 6),
                        "precision": "address" if r.get("addresstype") in ("building", "house", "place") or r.get("type") == "house"
                        else r.get("addresstype") or r.get("type") or "place"})
        except (KeyError, TypeError, ValueError):
            continue
    return out


def find(q: str) -> dict:
    """Resolve free text to candidate points: coordinates, then offline database, then online."""
    q = q.strip()[:200]
    if not q:
        return {"results": [], "offline_db": GEOCODE_DB.is_file()}
    p = parse_point(q)
    if p:
        return {"results": [{"label": f"{p[0]:.5f}, {p[1]:.5f}", "lat": round(p[0], 6), "lon": round(p[1], 6),
                             "precision": "coordinates", "source": "coordinates"}], "offline_db": GEOCODE_DB.is_file()}
    off = [dict(r, source="offline") for r in geocode_offline(q)]
    have_exact = any(r["precision"] in ("address", "city", "zip", "county") for r in off)
    on = [] if have_exact and len(off) >= 2 else [dict(r, source="online") for r in geocode_online(q)]
    results = (off + on) if have_exact else (on + off)
    return {"results": results[:8], "offline_db": GEOCODE_DB.is_file(), "online": bool(on)}


# =====================================================================================
# Point-to-point analysis
# =====================================================================================
def analyze(a: tuple[float, float], b: tuple[float, float], ha: float = 2.0, hb: float = 2.0) -> dict:
    """Distance, azimuths, declination, elevations, terrain profile and line of sight."""
    dist, az, az_final = inverse(*a, *b)
    back = (az_final + 180) % 360
    mag_a = magnetic(*a)
    n = 2 if dist < 1 else int(min(400, max(60, dist / 30))) + 1
    pts = [intermediate(*a, *b, i / (n - 1)) for i in range(n)]
    elev, src = elevations(pts)
    ea, eb = elev[0], elev[-1]
    out = {
        "a": {"lat": a[0], "lon": a[1], "mgrs": to_mgrs(*a), "elev": ea},
        "b": {"lat": b[0], "lon": b[1], "mgrs": to_mgrs(*b), "elev": eb},
        "distance": dist, "azimuth": az, "back_azimuth": back,
        "declination": mag_a["declination"], "declination_b": magnetic(*b)["declination"],
        "magnetic_model": {"model": mag_a["model"], "year": mag_a["year"], "valid": mag_a["valid"]},
        "elev_source": src, "elev_res_m": elevation_status().get("resolution_m") if src in ("offline", "mixed") else 90,
    }
    if ea is not None and eb is not None:
        d = eb - ea
        # slope: plain rise over run. aim: the angle to look/point from A to B, which also
        # drops by Earth's curvature over long distances (4/3 Earth, as radio sees it).
        out.update(change=d, grade=(d / dist * 100) if dist else 0.0,
                   slope_deg=deg(math.atan2(d, dist)) if dist else 0.0,
                   aim_deg=deg(math.atan2(d - dist ** 2 / (2 * K_RADIO * R_EARTH), dist)) if dist else 0.0)
    known = [(i, v) for i, v in enumerate(elev) if v is not None]
    if len(known) >= 2:
        hi_i, hi_v = max(known, key=lambda t: t[1])
        lo_i, lo_v = min(known, key=lambda t: t[1])
        climb = descent = 0.0
        anchor = known[0][1]
        for _, v in known[1:]:  # 3 m hysteresis so data noise doesn't count as climbing
            if v - anchor >= 3:
                climb += v - anchor
                anchor = v
            elif anchor - v >= 3:
                descent += anchor - v
                anchor = v
        out.update(high={"elev": hi_v, "at": dist * hi_i / (n - 1)}, low={"elev": lo_v, "at": dist * lo_i / (n - 1)},
                   climb=climb, descent=descent)
    profile = [{"d": dist * i / (n - 1), "e": v} for i, v in enumerate(elev)]
    out["profile"] = profile
    # Line of sight between antennas/eyes ha and hb metres above ground, with 4/3-Earth refraction.
    if ea is not None and eb is not None and dist > 0:
        ta, tb = ea + ha, eb + hb
        worst = None
        for i in range(1, n - 1):
            v = elev[i]
            if v is None:
                continue
            x = dist * i / (n - 1)
            line = ta + (tb - ta) * x / dist - x * (dist - x) / (2 * K_RADIO * R_EARTH)
            clear = line - v
            if worst is None or clear < worst[0]:
                worst = (clear, x, v)
        if worst:
            out["los"] = {"clear": worst[0] >= 0, "min_clearance": worst[0], "at": worst[1], "terrain": worst[2],
                          "ha": ha, "hb": hb}
        idxs = list(range(0, n, max(1, (n - 1) // 60)))
        if idxs[-1] != n - 1:
            idxs.append(n - 1)
        out["los_line"] = []
        for i in idxs:
            x = dist * i / (n - 1)
            out["los_line"].append({"d": x, "e": ta + (tb - ta) * x / dist - x * (dist - x) / (2 * K_RADIO * R_EARTH)})
    return out


def status() -> dict:
    con = db()
    addr = None
    if con is not None:
        try:
            meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
            addr = {"counties": int(meta.get("counties", 0)), "segments": int(meta.get("segments", 0)),
                    "built": meta.get("built"), "region": meta.get("region")}
        except sqlite3.Error:
            addr = {"error": "unreadable"}
    return {"elevation": elevation_status(), "addresses": addr}
