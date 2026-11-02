# ARK·π — The Pocket Ark

> *"By faith Noah, being warned of God of things not seen as yet, moved with fear, prepared an ark to the saving of his house."* (Hebrews 11:7)

**A grid-down knowledge server that fits on a Raspberry Pi.** Medical, water, comms, power, food, repair,
navigation and shelter references, field manuals, offline Wikipedia & friends,
offline maps, and survival calculators. Everything is served from a Raspberry Pi
or home server with **zero internet**, and it installs on phones as an app that keeps
working away from home.

Built to live two lives:
- **Today:** on a Proxmox VM as an everyday kitchen/garage/homestead reference.
- **Grid-down:** on a Raspberry Pi stored in a Faraday container, powered by a
  battery and solar panel, serving every phone and laptop in the house over Wi-Fi.

## What's inside

| | |
|---|---|
| **Knowledge base** | ~100 field-reference articles in 14 categories (Markdown in `content/`) |
| **Fieldcraft** | Animal & human tracking, bird language, orienteering & estimation, star navigation, weather lore, fire without matches, survival hunting/trapping/fishing |
| **Pi & Tech** | Raspberry Pi setup, running ARK·π on a Pi, offline Wi-Fi hotspot, Linux commands, Python & Bash, electronics & GPIO, sensor projects with code, SDR/APRS/Meshtastic, offline software stockpile |
| **Faith** | Scripture for hard times, Psalms of refuge, the Gospel, church without a building, discernment, prayer, hymns, burial service, Baptist beliefs |
| **Holy Bible** | Complete BSB, KJV and WEB (public domain) plus a personal ESV if installed. Search, side-by-side compare, section headings, Bible-in-a-year plan, "save to device" |
| **Morning & Evening** | C. H. Spurgeon's daily devotional, all 366 days |
| **Food & Preserving** | Canning (vegetables, meat, fruit, pickles), freezing, dehydrating, storage life, troubleshooting, planning, and a **Canning Lookup** tool driven by USDA data |
| **Books & Media** | ~60 public-domain books (Gutenberg), 16 LibriVox audiobooks incl. KJV readings, 14 classic films & cartoons |
| **Critical page** | One-tap access to life-safety content (bleeding, CPR, burns, water…) |
| **Recipes** | Tested recipes with checkable ingredients, numbered steps, keep-screen-on and print cards |
| **Offline map** | World + US + regional street maps (OpenStreetMap/Protomaps), MGRS/UTM readout, waypoints with distance & bearing |
| **Kiwix libraries** | Wikipedia (Medicine, Simple), iFixit, WikEM, MDWiki, StackExchange (DIY, ham, mechanics, gardening…), Gutenberg (Medicine, Agriculture), Appropedia, Energypedia, zimgit post-disaster collections, more |
| **Field manuals** | PDF library (Army FMs, Ranger Handbook…) |
| **Tools** | Canning lookup, water & food planners, bleach dosing, recipe scaler, battery/solar sizing, generator fuel, antenna & Ohm's law & wire-drop, Morse (audio + signal lamp), sun & moon, unit converter, wind chill & heat index, timers, pantry inventory, kit checklists, logbook |
| **PWA** | Installable; all articles + tools cached on the device for offline use |
| **Themes** | Dark · Paper (daylight/print) · **Red night-vision** |

## Layout

```
app/
  main.py              FastAPI app: content index, routes, APIs, PWA
  templates/           Jinja2 templates (tools/ = one file per tool)
  static/              CSS, JS, bundled fonts, icons, Leaflet + protomaps-leaflet
content/<category>/    Markdown articles with YAML front matter
deploy/                systemd units (ARK, Kiwix) and nginx HTTPS site
scripts/
  fetch-zims.sh        Download the curated Kiwix library (~21 GB)
  fetch-maps.sh        Download offline maps (~2 GB)
  make-certs.sh        Local CA + HTTPS certificate (for PWA install)
  fetch-media.py       Download Books & Media (catalog: media-catalog.json, ~8 GB)
  build-bible.py       Build KJV / BSB / WEB JSON from their public-domain sources
  import-bible-sql.py  Import a Bible you own from a MySQL dump (output is git-ignored)
  build-devotional.py  Build Spurgeon's Morning & Evening JSON
  gen-topo.py          Regenerates the topographic background artwork
docs/RECOMMENDED_DOWNLOADS.md   More manuals, ZIMs and installers worth grabbing
data/                  (runtime, git-ignored) pantry, waypoints, logbook, checklists
```

Large data (Kiwix libraries, maps, media) is **not** in the repo; fetch it with the
`scripts/fetch-*.sh` helpers. Paths it expects:

| Path | Contents |
|---|---|
| `/opt/kiwix/` | `*.zim` files + `library.xml` |
| `/opt/offline-data/maps/` | `*.pmtiles` + `layers.json` |
| `/opt/offline-data/manuals/` | PDF manuals |
| `/opt/offline-data/media/` | Books, audiobooks, films + `library.json` |
| `/opt/offline-data/imports/` | Files uploaded through `/import` |
| `/etc/ark-tls/` | Local CA and HTTPS certificate |

## Adding content

Drop a Markdown file into `content/<category>/` (new folders become new
categories automatically) or use the **Add entry** button on any category page.

```markdown
---
title: My Article
category: medical
tags: [medical, emergency]
summary: One line shown on cards and in lists.
---

# My Article

## Section
- Point
```

- Tag `emergency`, `medical` or `danger` to show it on the **Critical** page.
- Tag `danger`, `lye`, `bleeding` or `fire` to show a hazard warning.
- `## Ingredients`, `## Equipment` and `## Yield` sections in `content/recipes/`
  render in the recipe sidebar; `### 1. Step` headings become numbered steps.

## Running it

```bash
git clone https://github.com/treehuggersystems/arkpi.git /opt/offline-server && cd /opt/offline-server
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Production (systemd + nginx):

```bash
sudo cp deploy/offline-server.service deploy/kiwix.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now offline-server kiwix

sudo scripts/make-certs.sh                 # local CA + cert for this machine's IPs
sudo cp deploy/nginx-ark.conf /etc/nginx/sites-available/ark
sudo ln -s /etc/nginx/sites-available/ark /etc/nginx/sites-enabled/ark
sudo nginx -t && sudo systemctl reload nginx

scripts/fetch-zims.sh                      # ~21 GB
PMTILES=/path/to/pmtiles scripts/fetch-maps.sh   # ~2 GB
```

| URL | |
|---|---|
| `http://<host>:8000/` | ARK (plain HTTP) |
| `https://<host>/` | ARK over HTTPS. **Use this to install the app** |
| `https://<host>/install` | Certificate + install instructions for phones |
| `http://<host>:8000/kiwix/` · `https://<host>/kiwix/` | Kiwix libraries, proxied through ARK·π, so no extra port to open |
| `http://<host>:8081/` | Kiwix libraries direct via nginx (optional; needs the port open in any firewall) |
| `/import` | Upload a file from your device to the server |

### Environment variables

`OFFLINE_CONTENT_DIR`, `OFFLINE_DATA_DIR`, `OFFLINE_MANUALS_DIR`, `OFFLINE_MAPS_DIR`,
`OFFLINE_MEDIA_DIR`, `OFFLINE_IMPORT_DIR`, `KIWIX_HOST`, `KIWIX_PORT` (8082, internal),
`KIWIX_PUBLIC_PORT` (8081), `KIWIX_ROOT` (`/kiwix`), `ARK_TLS_DIR` (`/etc/ark-tls`).

## Bible translations

BSB, KJV and WEB are public domain and ship in `app/bible/`. Copyrighted translations
(ESV, NLT, NIV…) can't be redistributed, but if you own a copy you can add it for
personal use: upload the file at `/import`, then

```bash
venv/bin/python scripts/import-bible-sql.py /opt/offline-data/imports/BibleTexts.sql esv
sudo systemctl restart offline-server
```

The result (`app/bible/esv.json`) is git-ignored. When present, ESV becomes the default
translation; chapters missing from the source fall back to the BSB with a notice. Copy
it to the Pi separately (it is not in the repo).

## Moving to the Raspberry Pi

1. Raspberry Pi 4/5 (4 GB+), 128 GB+ **SSD** (better than SD for ~30 GB of data), Raspberry Pi OS 64-bit Lite.
2. `sudo apt install python3-venv nginx kiwix-tools git`
3. Copy `/opt/offline-server` (including the git-ignored `app/bible/esv.json`), `/opt/kiwix`, `/opt/offline-data` across
   (`rsync -a /opt/{offline-server,kiwix,offline-data} pi@<pi>:/opt/`).
4. Recreate the venv on the Pi (`rm -rf venv && python3 -m venv venv && venv/bin/pip install -r requirements.txt`).
5. Install the systemd units and nginx site as above.
6. **Copy `/etc/ark-tls/` from this server** so devices that already trust the
   ARK CA keep working, then re-run `sudo scripts/make-certs.sh <pi-ip> ark.local`.
7. Grid-down networking: set the Pi up as a **Wi-Fi access point** (NetworkManager
   hotspot: `nmcli dev wifi hotspot ssid ARK password <pw>`) so phones can connect
   with no router.
8. Power: the Pi draws ~3–7 W. A 100 Wh battery runs it ~15 h. Add a small
   solar panel + USB-C PD charger. Store the Pi, an SSD clone, cables, power
   bank and a travel router in a Faraday container (see *Power & EMP → EMP & Faraday Protection*).

## Customizing

- Default map view and the Sun & Moon tool start at the center of the contiguous US; set your own
  coordinates (the map remembers its last view on each device).
- Regional articles (gardening calendar, magnetic declination, plants) are written for the
  Kentucky / Ohio Valley. Edit them in `content/` for your area, and set `REGION_BBOX` / `REGION_NAME`
  when running `scripts/fetch-maps.sh`.
- Runtime data (pantry, waypoints, logbook) lives in `data/` and is git-ignored.

## Credits

Bible texts: KJV (Project Gutenberg #10), Berean Standard Bible (public domain, 2023),
World English Bible (eBible.org). Spurgeon's *Morning and Evening* via CCEL (public domain).
Books: Project Gutenberg. Audiobooks: LibriVox. Films: Internet Archive (public domain).
Map data © OpenStreetMap contributors, via Protomaps. Leaflet (BSD-2),
protomaps-leaflet (BSD-3). Fonts: Barlow & JetBrains Mono (SIL OFL). Kiwix
content © respective projects (Wikipedia, iFixit, Stack Exchange — CC BY-SA, etc.).

Medical content is for emergencies when professional care is unavailable. It's
summarized from Red Cross / AHA / WHO / CDC / US Army guidance and is not a substitute for training or a clinician.
