// Coordinate math used by the map and tools: DMS, UTM, MGRS, distance, bearing.
// WGS84 ellipsoid. No dependencies.
(function () {
  "use strict";
  const a = 6378137, f = 1 / 298.257223563, k0 = 0.9996;
  const e2 = f * (2 - f), ep2 = e2 / (1 - e2);
  const rad = d => d * Math.PI / 180, deg = r => r * 180 / Math.PI;

  function dms(v, pos, neg) {
    const h = v >= 0 ? pos : neg; v = Math.abs(v);
    const d = Math.floor(v), mF = (v - d) * 60, m = Math.floor(mF), s = (mF - m) * 60;
    return `${d}°${String(m).padStart(2, "0")}'${s.toFixed(1).padStart(4, "0")}"${h}`;
  }

  function utmZone(lat, lon) {
    let zone = Math.floor((lon + 180) / 6) + 1;
    if (lat >= 56 && lat < 64 && lon >= 3 && lon < 12) zone = 32;           // Norway
    if (lat >= 72 && lat < 84) {                                              // Svalbard
      if (lon >= 0 && lon < 9) zone = 31; else if (lon >= 9 && lon < 21) zone = 33;
      else if (lon >= 21 && lon < 33) zone = 35; else if (lon >= 33 && lon < 42) zone = 37;
    }
    return zone;
  }

  function toUTM(lat, lon) {
    const zone = utmZone(lat, lon);
    const phi = rad(lat), lam = rad(lon), lam0 = rad((zone - 1) * 6 - 180 + 3);
    const N = a / Math.sqrt(1 - e2 * Math.sin(phi) ** 2);
    const T = Math.tan(phi) ** 2, C = ep2 * Math.cos(phi) ** 2, A = Math.cos(phi) * (lam - lam0);
    const e4 = e2 * e2, e6 = e4 * e2;
    const M = a * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
      - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * Math.sin(2 * phi)
      + (15 * e4 / 256 + 45 * e6 / 1024) * Math.sin(4 * phi)
      - (35 * e6 / 3072) * Math.sin(6 * phi));
    const easting = k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120) + 500000;
    let northing = k0 * (M + N * Math.tan(phi) * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24
      + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720));
    if (lat < 0) northing += 10000000;
    const bands = "CDEFGHJKLMNPQRSTUVWXX";
    const band = bands[Math.max(0, Math.min(20, Math.floor((lat + 80) / 8)))];
    return { zone, band, easting, northing };
  }

  function toMGRS(lat, lon, digits = 5) {
    if (lat < -80 || lat > 84) return "outside MGRS UTM area";
    const u = toUTM(lat, lon);
    const set = u.zone % 6 || 6;
    const cols = ["ABCDEFGH", "JKLMNPQR", "STUVWXYZ"][(set - 1) % 3];
    const col = cols[Math.floor(u.easting / 100000) - 1] || "?";
    let rowIdx = Math.floor(u.northing / 100000) % 20;
    if (set % 2 === 0) rowIdx = (rowIdx + 5) % 20;
    const row = "ABCDEFGHJKLMNPQRSTUV"[rowIdx];
    const div = 10 ** (5 - digits);
    const e = String(Math.floor((u.easting % 100000) / div)).padStart(digits, "0");
    const n = String(Math.floor((u.northing % 100000) / div)).padStart(digits, "0");
    return `${u.zone}${u.band} ${col}${row} ${e} ${n}`;
  }

  function distance(lat1, lon1, lat2, lon2) {  // metres, haversine
    const R = 6371008.8, dφ = rad(lat2 - lat1), dλ = rad(lon2 - lon1);
    const h = Math.sin(dφ / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dλ / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function bearing(lat1, lon1, lat2, lon2) {  // initial true bearing, degrees
    const φ1 = rad(lat1), φ2 = rad(lat2), dλ = rad(lon2 - lon1);
    const y = Math.sin(dλ) * Math.cos(φ2), x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(dλ);
    return (deg(Math.atan2(y, x)) + 360) % 360;
  }

  function cardinal(b) { return ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][Math.round(b / 22.5) % 16]; }

  function fmtDist(m) {
    const mi = m / 1609.344;
    return mi < 0.1 ? `${Math.round(m * 3.28084)} ft (${Math.round(m)} m)` : `${mi.toFixed(mi < 10 ? 2 : 1)} mi (${(m / 1000).toFixed(2)} km)`;
  }

  window.Geo = {
    dms: (lat, lon) => `${dms(lat, "N", "S")} ${dms(lon, "E", "W")}`,
    toUTM, toMGRS, distance, bearing, cardinal, fmtDist,
    utmString(lat, lon) { const u = toUTM(lat, lon); return `${u.zone}${u.band} ${Math.round(u.easting)}E ${Math.round(u.northing)}N`; },
  };
})();
