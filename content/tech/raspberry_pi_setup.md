---
title: Raspberry Pi Setup
category: tech
tags: [tech, raspberry pi, linux, setup]
summary: Choose a Pi, flash the OS, connect headless over SSH, boot from an SSD, protect against power loss, and keep a backup image.
---

# Raspberry Pi Setup

## Which Pi?
| Model | RAM | Power supply | Good for |
|---|---|---|---|
| **Raspberry Pi 5** | 4 / 8 / 16 GB | **5 V 5 A USB-C** (27 W official) | Best for ARK·π: fast, PCIe for NVMe SSD |
| Raspberry Pi 4 | 2 / 4 / 8 GB | 5 V 3 A USB-C | Runs ARK·π well; boots from USB SSD |
| Raspberry Pi Zero 2 W | 512 MB | 5 V 2.5 A micro-USB | Tiny, low power: sensors, mesh nodes, small jobs |

**For ARK·π:** Pi 5 (8 GB) or Pi 4 (4 GB+), a **1 TB SSD** (USB, or NVMe on a Pi 5 M.2 HAT), the official power supply, and a case with a fan or heatsink.

## Flash the OS
1. On another computer, install **Raspberry Pi Imager**.
2. Choose your Pi model → **Raspberry Pi OS (64-bit)**. Choose "Lite" for a headless server (no desktop).
3. Choose the storage (SD card or SSD in a USB adapter).
4. Click **Edit settings** (customization):
   - Hostname: `ark` (you'll reach it as `ark.local`)
   - Username and password
   - Wi-Fi network and country (optional)
   - Services → **Enable SSH**
5. Write, insert, power on. First boot takes a couple of minutes.

## Connect Headless (SSH)
```
ssh youruser@ark.local
```
If `ark.local` doesn't resolve, find its IP in your router's client list, then `ssh youruser@192.168.x.x`.
Windows 10/11, macOS and Linux all have `ssh` built in.

## First Things to Run
```
sudo apt update && sudo apt full-upgrade -y   # while you still have internet
sudo raspi-config                              # locale, timezone, interfaces
sudo reboot
```

## Boot From an SSD (faster, far more reliable than SD)
- **Pi 4 / 5 with a USB SSD:** flash the SSD with Imager exactly like an SD card and plug it into a **blue USB 3 port**. Recent Pis boot from USB automatically. If not: `sudo raspi-config` → Advanced Options → Boot Order → USB Boot.
- **Pi 5 with NVMe:** fit an M.2 HAT, flash the NVMe drive, then set boot order to NVMe in `raspi-config`.
- Already running on SD? Clone it to the SSD with the desktop **SD Card Copier** or the `rpi-clone` script, then change the boot order.

## Protect Against Power Loss
Sudden power cuts are the #1 way SD cards get corrupted.
- **Use an SSD**, not an SD card, for anything important.
- **Shut down properly:** `sudo shutdown -h now`. Wait for the green LED to stop flashing before unplugging.
- **Safe shutdown button:** add to `/boot/firmware/config.txt`:
  ```
  dtoverlay=gpio-shutdown
  ```
  Then a momentary button between **GPIO3 (pin 5)** and **GND (pin 6)** shuts the Pi down cleanly, and pressing it again boots it.
- **Overlay file system** (read-only root): `sudo raspi-config` → Performance → Overlay File System. The SD card can't be corrupted, but changes are lost on reboot. Good for a sensor box, not for ARK·π (which saves waypoints and logs).
- **UPS HAT / power bank with pass-through:** keeps the Pi up through brief outages.

## Backups
- Make a full image of the boot drive **after** everything works: Raspberry Pi Imager can't read back, so use `dd` from another Linux machine:
  ```
  sudo dd if=/dev/sdX of=ark-backup.img bs=4M status=progress
  ```
  (Check the device with `lsblk` first. `dd` to the wrong disk destroys it.) On Windows, use Win32 Disk Imager → Read.
- Keep the image, and a spare SD/SSD with it already written, in your Faraday container (see [EMP protection](/power/emp_faraday_protection)).

## Handy Facts
- Find the IP: `hostname -I`
- Temperature: `vcgencmd measure_temp` (throttles around 80–85 °C, so use a heatsink or fan)
- Under-voltage check: `vcgencmd get_throttled` (`0x0` = all good; anything else = weak power supply or cable)
- Config file: `/boot/firmware/config.txt` (Bookworm and later)

See also: [Running ARK·π on a Pi](/tech/running_ark_on_a_pi), [Linux Command Line](/tech/linux_command_line).
