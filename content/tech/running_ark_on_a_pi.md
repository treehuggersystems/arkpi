---
title: Running ARK·π on a Raspberry Pi
category: tech
tags: [tech, raspberry pi, ark, power, emp]
summary: Move ARK·π from the home server to a Pi, size the battery and solar to run it for days, and pack the go-kit for the Faraday container.
---

# Running ARK·π on a Raspberry Pi

## What It Needs
| Item | Notes |
|---|---|
| Raspberry Pi 5 (8 GB) or Pi 4 (4 GB+) | Pi 5 is snappier for map and Kiwix search |
| **SSD, 1 TB** | ARK·π's data is ~40 GB (Kiwix 28 GB, maps 2 GB, media ~10 GB) with plenty of room to grow |
| Official power supply + a 12 V → 5 V USB-C converter | So it can run off a battery or vehicle |
| Case with heatsink/fan | |
| Small Wi-Fi travel router *(optional)* | The Pi can be its own hotspot, but a router covers a bigger area |

## Moving ARK·π Over
On the Pi (Raspberry Pi OS 64-bit, set up per [Raspberry Pi Setup](/tech/raspberry_pi_setup)):

```
sudo apt install -y python3-venv nginx kiwix-tools git rsync
```

From the current server, copy everything (repo, git-ignored ESV, data, Kiwix, certificates):

```
rsync -a --info=progress2 /opt/offline-server /opt/kiwix /opt/offline-data youruser@ark.local:/tmp/ark/
sudo rsync -a /etc/ark-tls youruser@ark.local:/tmp/ark/
```

Then on the Pi:

```
sudo mv /tmp/ark/offline-server /tmp/ark/kiwix /tmp/ark/offline-data /opt/
sudo mv /tmp/ark/ark-tls /etc/
cd /opt/offline-server
rm -rf venv && python3 -m venv venv && venv/bin/pip install -r requirements.txt
sudo cp deploy/offline-server.service deploy/kiwix.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now offline-server kiwix
sudo scripts/make-certs.sh        # adds the Pi's IPs/hostname; keeps the same CA so phones still trust it
sudo cp deploy/nginx-ark.conf /etc/nginx/sites-available/ark
sudo ln -s /etc/nginx/sites-available/ark /etc/nginx/sites-enabled/ark
sudo nginx -t && sudo systemctl reload nginx
```

Open `http://ark.local:8000`. The full checklist is in the repo README.

## Power Budget
| Device | Typical draw |
|---|---|
| Pi 5 idle / busy | ~3–4 W / 6–8 W |
| Pi 4 idle / busy | ~3 W / 5–6 W |
| USB SSD | ~1–2 W |
| Travel router | ~2–4 W |
| **ARK·π total** | **~6–10 W** average |

**How long will it run?** Hours ≈ battery Wh × 0.85 ÷ watts.
| Battery | Runtime at ~8 W |
|---|---|
| 20,000 mAh USB-C power bank (~74 Wh) | ~8 hours |
| 100 Wh power bank | ~10 hours |
| 12 V 50 Ah LiFePO4 (640 Wh) | ~3 days |
| 12 V 100 Ah LiFePO4 (1,280 Wh) | ~5–6 days |

**Solar:** a 50–100 W panel with a small charge controller and a 12 V LiFePO4 battery runs ARK·π indefinitely in most weather. Size it with the [Battery & Solar tool](/tools/power) (add "Raspberry Pi server" from the device list).

## Run Only When Needed
To stretch the battery, power ARK·π up for set hours (morning and evening check-ins), like a radio schedule. Shut down cleanly with `sudo shutdown -h now` or the [safe shutdown button](/tech/raspberry_pi_setup).

## The Faraday Go-Kit
Pack together in a sealed, insulated metal container (see [EMP & Faraday Protection](/power/emp_faraday_protection)):
- [ ] Pi + case + SSD (ARK·π installed and tested)
- [ ] **A second SSD** with a full backup image
- [ ] USB-C power supply **and** a 12 V → USB-C converter with car-socket and battery-clamp leads
- [ ] USB-C power bank, kept charged
- [ ] Small folding solar panel with USB-C PD output
- [ ] Travel router + its power cable
- [ ] Short Ethernet cable, USB keyboard, micro-HDMI cable (to fix it with a screen if needed)
- [ ] Printed card: Wi-Fi name and password, `http://ark.local:8000`, the Pi's IP, login, and the [hotspot commands](/tech/pi_offline_network)

Test the whole kit every few months: power up from the battery, connect a phone, open a few pages.

See also: [Pi as an Offline Network](/tech/pi_offline_network).
