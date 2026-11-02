---
title: Pi as an Offline Wi-Fi Network
category: tech
tags: [tech, raspberry pi, wifi, network, comms]
summary: Turn the Pi into its own Wi-Fi hotspot so phones and laptops connect to ARK·π with no router or internet — plus file sharing and local chat.
---

# Pi as an Offline Wi-Fi Network

When the grid's down there may be no router, no internet, and no cell service. The Pi can broadcast its own Wi-Fi network, and every phone in range can open ARK·π.

## Make the Pi a Hotspot (Raspberry Pi OS Bookworm+)
Raspberry Pi OS uses NetworkManager, so it's one command:

```
sudo nmcli device wifi hotspot ifname wlan0 ssid ARK password "choose-a-strong-pass"
```

Make it come back automatically after every reboot:

```
sudo nmcli connection modify Hotspot connection.autoconnect yes connection.autoconnect-priority 100
```

- The Pi's address on its own hotspot is usually **10.42.0.1**. Phones get addresses automatically.
- Open **http://10.42.0.1:8000** (or `http://ark.local:8000` on most phones and computers).
- Turn it off: `sudo nmcli connection down Hotspot`. Back on: `sudo nmcli connection up Hotspot`.
- The Pi's built-in Wi-Fi reaches about one house and yard. A **USB Wi-Fi adapter with an external antenna**, or a small travel router plugged into the Pi's Ethernet port, covers far more.

> While the Pi is a hotspot, its Wi-Fi can't also connect to your home network. Use Ethernet for internet access (updates) when you need it.

## Finding It as `ark.local`
Raspberry Pi OS runs **Avahi (mDNS)** out of the box, so `hostname.local` works on Windows 10+, macOS, iPhone, Linux and most Android versions. Change the name with `sudo raspi-config` → System → Hostname.

## Print a QR Code for the Wi-Fi
Install `qrencode` (do it now, while you have internet: see [Offline Software Stockpile](/tech/offline_software_stockpile)):

```
qrencode -o wifi.png 'WIFI:T:WPA;S:ARK;P:choose-a-strong-pass;;'
qrencode -t ANSIUTF8 'http://10.42.0.1:8000'
```

Print the Wi-Fi QR and tape it inside the Faraday container lid and by the door. Phones join by scanning it.

## Share Files on the Network (Samba)
```
sudo apt install -y samba
sudo mkdir -p /srv/share && sudo chmod 777 /srv/share
printf '[share]\n path = /srv/share\n read only = no\n guest ok = yes\n' | sudo tee -a /etc/samba/smb.conf
sudo systemctl restart smbd
```
Windows: `\\ark.local\share`. Mac: Finder → Go → Connect to Server → `smb://ark.local/share`.

You can also upload files to ARK·π itself at [/import](/import).

## Neighborhood Messaging Without the Internet
- **ARK·π's [Logbook](/tools/logbook)** works as a shared message board for everyone on the hotspot.
- **Meshtastic** LoRa radios give phone-to-phone text messaging over miles with no network at all: see [Radio & Mesh with a Pi](/tech/pi_radio_and_mesh).

## Troubleshooting
| Problem | Try |
|---|---|
| Hotspot doesn't appear | `nmcli device status` (is wlan0 "unavailable"?). Check `rfkill list` and run `sudo rfkill unblock wifi`. Set the Wi-Fi country in `raspi-config` |
| Phone connects but pages won't load | Use the IP (`10.42.0.1:8000`) instead of `ark.local`. Turn off mobile data on the phone (some phones avoid Wi-Fi without internet) |
| "No internet" warning on phone | Normal. Tap "Stay connected" / "Use without internet" |
| Slow with many users | Add a travel router; keep Kiwix searches short |
