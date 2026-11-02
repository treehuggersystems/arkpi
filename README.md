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

## Quick start (Raspberry Pi) — about 15 minutes

**You need:** a Raspberry Pi 4 or 5 (4 GB+), a **32 GB+** microSD card (enough for the app and core content; use a bigger SD or an SSD if you add the full Wikipedia and map libraries, ~23 GB more), a computer to flash it, and Ethernet or internet for the install.

**1. Flash the Pi.** In [Raspberry Pi Imager](https://www.raspberrypi.com/software/) pick your Pi, **Raspberry Pi OS Lite (64-bit)**, and
your SD card. Click the ⚙ settings: set hostname `ark`, a username and password, and enable SSH. Write it, put it in the Pi, plug in Ethernet, power on.

**2. Connect.** From your computer: `ssh youruser@ark.local`

**3. Install** (paste these three lines):

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/treehuggersystems/arkpi.git
sudo ./arkpi/install.sh
```

It asks for a Wi-Fi password (or makes one), then installs everything, starts ARK·π on every boot, and creates the **ARK Wi-Fi hotspot**.

**4. Use it.** Join the **ARK** Wi-Fi on a phone and open **http://ark.local:8000**. To install it as an app, open **https://ark.local/install** once.

That's it. The Pi now works with no internet. Open the sections below only if you want more.

<details>
<summary><b>Options</b> — Wi-Fi name/password, hostname, and so on</summary>

Set environment variables in front of the install command:

```bash
sudo ARK_SSID=MyArk ARK_PASS='a long passphrase' ./arkpi/install.sh
```

| Variable | Default | Meaning |
|---|---|---|
| `ARK_SSID` | `ARK` | Wi-Fi network name |
| `ARK_PASS` | asks (random if non-interactive) | Wi-Fi password, 8+ characters |
| `ARK_HOTSPOT` | `auto` | `yes`, `no`, or `auto` (skips the hotspot if the Pi is using its Wi-Fi for its connection, so you can't lock yourself out of SSH) |
| `ARK_HOSTNAME` | unchanged | Set the Pi's hostname |
| `ARK_DIR` | `/opt/offline-server` | Install location |
| `ARK_REPO` / `ARK_BRANCH` | official repo / `main` | Install from a fork or branch |

</details>

<details>
<summary><b>Update</b> to the latest version</summary>

```bash
sudo /opt/offline-server/install.sh
```

Re-running the installer pulls the newest code, refreshes dependencies and restarts the services. Your data in `data/` is kept.

</details>

<details>
<summary><b>Add the big offline libraries</b> (Wikipedia, maps) — needs internet once</summary>

```bash
sudo /opt/offline-server/scripts/fetch-zims.sh     # Wikipedia, iFixit, medical, how-to: ~21 GB
sudo /opt/offline-server/scripts/fetch-maps.sh     # offline maps: ~2 GB (needs the `pmtiles` CLI)
sudo systemctl restart kiwix
```

Both are resumable. See `docs/RECOMMENDED_DOWNLOADS.md` for manuals and more.

</details>

<details>
<summary><b>Troubleshooting</b></summary>

- `ark.local` doesn't resolve: use the Pi's IP (`hostname -I`) or `10.42.0.1` on the hotspot.
- Hotspot didn't start: the Pi was on Wi-Fi. Connect Ethernet (or use a monitor) and run `sudo ARK_HOTSPOT=yes /opt/offline-server/install.sh`.
- Site down: `systemctl status offline-server` and `journalctl -u offline-server -e`.
- Offline Wikipedia empty: run `fetch-zims.sh`, then `sudo systemctl restart kiwix`.

</details>

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

<details>
<summary><b>Running it manually (development, other Linux)</b></summary>

On a Pi, `install.sh` (above) does all of this for you.

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

</details>

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

<details>
<summary><b>Moving an existing server to a Pi (with your data)</b></summary>

1. Raspberry Pi 4/5 (4 GB+), 32 GB+ SD card (an **SSD** of 128 GB+ is better if you hold the full ~30 GB of libraries), Raspberry Pi OS 64-bit Lite.
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

</details>

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
