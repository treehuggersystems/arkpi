---
title: Radio & Mesh with a Pi
category: tech
tags: [tech, raspberry pi, radio, sdr, mesh, comms]
summary: Turn a Pi into a scanner and weather-radio receiver with an RTL-SDR dongle, track aircraft, run APRS packet radio, and build Meshtastic off-grid text messaging.
---

# Radio & Mesh with a Pi

A Pi plus a ~$30–40 USB software-defined radio (SDR) becomes a wide-band receiver. A ~$30–60 LoRa radio gives off-grid text messaging. Pair these with the [Comms](/comms) section.

## RTL-SDR: A Receiver for (Almost) Everything
An **RTL-SDR** dongle (the RTL-SDR Blog V3/V4 are good) receives roughly **500 kHz – 1.7 GHz** (HF needs direct-sampling mode or an upconverter). **Receive only**: it can't transmit.

Install while you have internet:
```
sudo apt install -y rtl-sdr sox
```
Test: `rtl_test` (Ctrl+C to stop).

### Listen to an FM channel (NOAA weather, ham simplex, MURS, marine)
```
rtl_fm -f 162.550M -M fm -s 22050 -g 40 - | play -r 22050 -t raw -e s -b 16 -c 1 -V1 -
```
Change `-f` to 162.400M–162.550M for NOAA Weather Radio, `146.52M` for the 2 m calling frequency, `156.8M` for marine Ch 16. Frequencies are in [Emergency Frequencies](/comms/emergency_frequencies).

### Scan many channels
`rtl_fm -f 162.400M -f 162.425M -f 162.450M -f 162.475M -f 162.500M -f 162.525M -f 162.550M -M fm -l 50 ...` cycles through the list, stopping on activity (`-l` sets the squelch level).

### Track aircraft (ADS-B, 1090 MHz)
```
sudo apt install -y dump1090-mutability     # package name varies; readsb is a modern alternative
dump1090-mutability --interactive --net
```
Shows planes overhead with altitude and position, and serves a live map on port 8080. In an emergency, aircraft patterns tell you a lot (search patterns, supply flights, airspace closures).

### Other things to receive
- **Scanner traffic** (where not encrypted): local fire/EMS, public works, railroads. Analog FM works with `rtl_fm`; digital (P25/DMR) needs software like OP25 or DSD+.
- **Weather satellite images** (polar-orbiting satellites with simple antennas). Check which satellites are still transmitting; it changes over time.
- **AM/shortwave** with an RTL-SDR V3/V4 in direct-sampling mode and a long wire antenna.

### Antennas
The stock telescopic antenna is fine for local VHF/UHF. For better reception, use a **quarter-wave vertical** cut for the band (see the [Antenna tool](/tools/radio)) mounted high outside, connected with good coax.

## APRS & Packet Radio (ham license to transmit)
**APRS** sends short position reports, weather, and text messages over the 2 m band (**144.390 MHz** in North America). Digipeaters and iGates relay them for hundreds of miles, with no internet needed between stations.
- **Direwolf** is a software modem (TNC) for the Pi: `sudo apt install direwolf`.
- **Receive-only iGate/monitor:** RTL-SDR + Direwolf decodes APRS traffic in your area.
- **Transmit:** connect a 2 m radio via a USB sound card interface (with PTT control). Requires an amateur radio license (Technician or higher).
- Packet radio (AX.25), Winlink over radio (email without internet), and digital modes like JS8Call (HF texting; Pi + HF radio + interface) are the next steps.

## Meshtastic: Off-Grid Text Messaging (no license)
**Meshtastic** uses cheap **LoRa** radios in the license-free **915 MHz** ISM band (US). Each phone pairs with a radio over Bluetooth; radios relay messages for each other in a **mesh**.
- **Range:** 1–5 miles typical between handhelds in mixed terrain; 10+ miles from high points. Every node extends the network.
- **Hardware:** Heltec V3, LilyGO T-Beam (has GPS), RAK WisBlock, Station G2 (more power). ~$30–80 each. Add a better 915 MHz antenna.
- **Phone app:** Meshtastic for Android/iOS (download now; works fully offline).
- **Pi as a node:** a LoRa HAT (e.g., Waveshare SX1262) with **meshtasticd**, or simply a USB-connected Meshtastic radio plugged into the Pi.
- Set all your family's radios to the same **channel name and encryption key**, and put a solar-powered **relay node** on a high point (roof, tree, hill) to cover the neighborhood.
- Text, GPS positions on a shared map, and sensor telemetry. Low data rate, so think SMS, not voice.

## Kit List
- [ ] RTL-SDR V4 + telescoping antenna + a 2 m/70 cm outdoor antenna + coax
- [ ] 2–4 Meshtastic radios (one with GPS) + 915 MHz antennas + a small solar relay node
- [ ] USB sound-card radio interface (if licensed) + cables for your HT/mobile
- [ ] **Software installed and tested now**: rtl-sdr, sox, dump1090, direwolf, Meshtastic apps, plus a copy of each installer (see [Offline Software Stockpile](/tech/offline_software_stockpile))
- [ ] Spare SDR and a Meshtastic radio in the Faraday container
