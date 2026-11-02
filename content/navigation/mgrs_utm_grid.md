---
title: MGRS & UTM Grid Coordinates
category: navigation
tags: [navigation, maps, mgrs, coordinates, comms]
summary: How to read, plot and radio a grid coordinate — the system used by the military manuals in the Library and the ARK map.
---

# MGRS & UTM Grid Coordinates

Latitude/longitude uses degrees that change size across the globe. **UTM and MGRS** use a square **metric grid** — easy to measure distances on a map and simple to pass over the radio. The [ARK map](/map) shows both when you click.

## UTM (Universal Transverse Mercator)
- The world is split into **60 zones**, each 6° of longitude wide. **Kentucky/Ohio/Indiana are in zones 16 and 17** (boundary at 84° W, near Lexington and Cincinnati).
- Position = **zone + easting + northing**, in meters.
- Example: `16S 702345E 4212345N`
  - Easting: meters east within the zone (center line = 500,000).
  - Northing: meters north of the equator.

## MGRS (Military Grid Reference System)
MGRS is UTM with letters replacing the big numbers:

`17S KC 12345 67890`

| Part | Meaning |
|---|---|
| **17S** | Grid zone designator (UTM zone 17, latitude band S) |
| **KC** | 100 km square identifier |
| **12345** | Easting within the square (meters) |
| **67890** | Northing within the square (meters) |

### Precision
| Digits (total) | Example | Precision |
|---|---|---|
| 2 | KC 1 6 | 10 km |
| 4 | KC 12 67 | **1 km** |
| 6 | KC 123 678 | **100 m** (standard for most reports) |
| 8 | KC 1234 6789 | 10 m |
| 10 | KC 12345 67890 | 1 m |

Always **truncate**, never round: `12345` at 6-digit precision is `123`.

## Reading a Grid on a Paper Map
**"Read right, then up."**
1. Find the grid square containing the point. Read the **vertical line to its left** (easting) first, then the **horizontal line below it** (northing). That's your 4-digit grid.
2. For 6 digits, divide the square into tenths: **how many tenths right, then how many tenths up**. Use a **protractor/roamer** card.
3. Prefix the 100 km letters (printed in the map margin) for anything beyond your local area.

## Distance
Grid lines on US topos are usually **1 km apart**, so counting squares gives distance directly. Diagonal: Pythagoras or the [map tool](/map) "from waypoint" feature.

## Saying It on the Radio
"*Grid: Kilo Charlie, one two three, six seven eight.*" Digit by digit, letters phonetically. See [Phonetic Alphabet](/comms/phonetic_alphabet_prowords).

## Lat/Long Formats (for GPS)
| Format | Example |
|---|---|
| Decimal degrees | 39.50000, −98.35000 |
| Degrees decimal minutes | 39° 30.000′ N, 98° 21.000′ W |
| Degrees minutes seconds | 39° 30′ 00.0″ N, 98° 21′ 00.0″ W |

**Make sure your GPS, map and team all use the same format and datum (WGS84 / NAD83 are nearly identical).**
