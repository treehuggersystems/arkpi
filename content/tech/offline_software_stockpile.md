---
title: Offline Software Stockpile
category: tech
tags: [tech, linux, raspberry pi, preparedness, software]
summary: Without internet you can't apt install or pip install anything. How to cache Debian packages, Python wheels, OS images, phone apps and docs now, so you can build and repair systems later.
---

# Offline Software Stockpile

**The trap:** every "how to" for Linux and the Pi starts with `sudo apt install …` or `pip install …`, and both download from the internet. After the grid goes down, **you can only install what you saved beforehand.** Build a stockpile now, while it's easy.

## What to Keep (on the SSD / a USB drive in the Faraday kit)
| Item | Why |
|---|---|
| **Raspberry Pi OS image(s)** (64-bit Lite and Desktop) | Rebuild a Pi from scratch |
| **Raspberry Pi Imager** installers (Windows/Mac/Linux) | Write images to SD/SSD |
| **A full backup image** of your working ARK·π Pi | Restore in minutes |
| This repository (`/opt/offline-server`) | Includes all scripts and docs |
| **Debian packages** cache (below) | `apt install` with no internet |
| **Python wheels** cache (below) | `pip install` with no internet |
| Kiwix apps (Android/iOS/desktop) + Kiwix-tools `.deb` | Read ZIM libraries on any device |
| **Phone apps as APKs** (Android): Kiwix, Meshtastic, Organic Maps / OsmAnd + map packs, a PDF reader, VLC | Install on phones without the Play Store |
| Firmware for radios (Meshtastic), CHIRP (radio programming) + cable drivers | Reprogram radios |
| Arduino IDE installers | Microcontroller projects |
| Offline docs | Python, Bash, Git, SQLite, Docker docs, plus Raspberry Pi / Unix / Arduino Q&A, are in the [Library](/library#wiki) |

## Cache Debian / Raspberry Pi OS Packages
On the Pi (same OS version and architecture you'll use later):

```
mkdir -p ~/debcache && cd ~/debcache
PKGS="nginx kiwix-tools python3-venv python3-gpiozero rtl-sdr sox direwolf samba qrencode motion git htop rsync"
apt-get download $(apt-cache depends --recurse --no-recommends --no-suggests \
  --no-conflicts --no-breaks --no-replaces --no-enhances $PKGS | grep "^\w" | sort -u)
```
Later, offline, install from the cache:
```
cd ~/debcache && sudo dpkg -i *.deb    # run twice if it complains about order
```
*Simpler alternative:* after installing everything you need while online, copy `/var/cache/apt/archives/*.deb` to the USB drive (run `sudo apt-get clean` first, then install, so the folder only holds what you used).

## Cache Python Packages
```
mkdir -p ~/wheels
~/env/bin/pip download -d ~/wheels -r /opt/offline-server/requirements.txt
~/env/bin/pip download -d ~/wheels gpiozero adafruit-circuitpython-bme280 adafruit-circuitpython-ina219 requests flask
```
Offline install:
```
python3 -m venv ~/env
~/env/bin/pip install --no-index --find-links ~/wheels -r requirements.txt
```
Download wheels **on the Pi itself** (ARM64). Wheels built for a PC won't install on it.

## Keep It Current
- Refresh the caches every 6–12 months, and whenever you add a project.
- Write down versions that are known to work together.
- **Test it:** unplug the network cable and rebuild something from the cache. You'll find what's missing.

## Phone Readiness Checklist
- [ ] Kiwix app + a medical ZIM (e.g., WikiMed) downloaded on each phone
- [ ] Organic Maps or OsmAnd with your state's offline map downloaded
- [ ] Meshtastic app paired with your radio
- [ ] ARK·π installed as an app (see [Install](/install)) and opened once, so articles are cached
- [ ] The ESV / YouVersion app with an offline Bible downloaded
- [ ] Copies of key PDFs (this ARK·π's [Library](/library) manuals) in the phone's files

## Store It Right
Two copies on different drives; one in the Faraday container; one in a fireproof box or off-site. Label drives with contents and date.
