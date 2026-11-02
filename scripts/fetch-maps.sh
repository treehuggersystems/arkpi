#!/usr/bin/env bash
# Download offline vector maps (Protomaps / OpenStreetMap) as .pmtiles files.
#
#   scripts/fetch-maps.sh [dest_dir]          (default: /opt/offline-data/maps)
#
# Layers (the map viewer stacks them, using the most detailed one available):
#   world.pmtiles   whole planet, zoom 0-7        (~190 MB)
#   us.pmtiles      continental US, zoom 0-10     (~385 MB)  roads & towns
#   region.pmtiles  REGION_BBOX, zoom 0-15        (~1.5 GB)  street level
#
# Change REGION_BBOX (west,south,east,north) for your area, e.g. at
# https://boundingbox.klokantech.com (CSV format). Needs the `pmtiles` CLI:
# https://github.com/protomaps/go-pmtiles/releases
set -euo pipefail

DEST="${1:-/opt/offline-data/maps}"
REGION_BBOX="${REGION_BBOX:--89.6,36.4,-80.4,42.1}"   # Kentucky / Ohio / Indiana
REGION_NAME="${REGION_NAME:-Kentucky · Ohio · Indiana}"
PMTILES="${PMTILES:-$(command -v pmtiles || echo ./pmtiles)}"

# Newest daily planet build (they're kept for a short while).
BUILD=""
for i in $(seq 1 10); do
  d=$(date -u -d "-$i day" +%Y%m%d)
  if curl -sfI "https://build.protomaps.com/$d.pmtiles" >/dev/null; then BUILD="https://build.protomaps.com/$d.pmtiles"; break; fi
done
[[ -n "$BUILD" ]] || { echo "No recent Protomaps build found" >&2; exit 1; }
echo "Source: $BUILD"

mkdir -p "$DEST"
"$PMTILES" extract "$BUILD" "$DEST/world.pmtiles"  --maxzoom=7
"$PMTILES" extract "$BUILD" "$DEST/us.pmtiles"     --maxzoom=10 --bbox=-125,24,-66.5,49.5
"$PMTILES" extract "$BUILD" "$DEST/region.pmtiles" --maxzoom=15 --bbox="$REGION_BBOX"

cat > "$DEST/layers.json" <<EOF
[
  {"file": "world.pmtiles",  "name": "World",            "minzoom": 0,  "maxzoom": 7},
  {"file": "us.pmtiles",     "name": "United States",    "minzoom": 6,  "maxzoom": 10, "bbox": [-125, 24, -66.5, 49.5]},
  {"file": "region.pmtiles", "name": "$REGION_NAME",     "minzoom": 9,  "maxzoom": 15, "bbox": [${REGION_BBOX}]}
]
EOF
echo "Done: $(du -sh "$DEST" | cut -f1) in $DEST"
