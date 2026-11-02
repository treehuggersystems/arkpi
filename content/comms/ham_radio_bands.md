---
title: Ham Radio Bands & Propagation
category: comms
tags: [comms, radio, ham, hf, vhf]
summary: US amateur band plan, license privileges, which band works when, and how far your signal will actually go.
---

# Ham Radio Bands & Propagation

## License Classes (US)

| Class | Exam | Privileges |
|---|---|---|
| **Technician** | 35 questions | All bands above 50 MHz (6 m, 2 m, 70 cm…); 10 m voice 28.3–28.5 MHz; CW on parts of 80/40/15 m |
| **General** | 35 questions | Most HF voice — 160, 80, 60, 40, 20, 17, 15, 12, 10 m |
| **Amateur Extra** | 50 questions | Everything |

Exams are cheap (often free) through volunteer examiner teams. Study material lives in the [Library](/library) and the ham.stackexchange archive (Kiwix).

## Band Chart

| Band | Range (MHz) | Best for | When |
|---|---|---|---|
| 160 m | 1.800–2.000 | Regional | Night, winter |
| 80 m | 3.500–4.000 | **0–300 mi (NVIS)**, regional nets | Evening & night |
| 60 m | 5 channels ≈5.3–5.4 | NVIS, emergency interop | Day & night |
| **40 m** | 7.000–7.300 | **Workhorse:** 100–1,000 mi day, farther at night | All day |
| 30 m | 10.100–10.150 | CW/digital only | All day |
| **20 m** | 14.000–14.350 | **Worldwide** | Daytime |
| 17 m | 18.068–18.168 | Long distance | Daytime, solar max |
| 15 m | 21.000–21.450 | Long distance | Daytime, solar max |
| 12 m | 24.890–24.990 | Long distance | Daytime, solar max |
| 10 m | 28.000–29.700 | Worldwide when open; local otherwise | Daytime, solar max |
| 6 m | 50–54 | Local; "magic band" summer openings | Summer |
| **2 m** | 144–148 | **Local simplex + repeaters** | Always (line of sight) |
| 1.25 m | 222–225 | Local | Always |
| **70 cm** | 420–450 | Local, better in buildings | Always |

### Voice conventions
- **Below 10 MHz: LSB.** 10 MHz and above: **USB**. (60 m is the exception — USB.)
- 2 m FM simplex: 146.400–146.595 & 147.400–147.585 (calling **146.520**)
- 70 cm FM simplex: 446.000 calling

## How Far Will It Go?

### VHF/UHF — line of sight
Radio horizon (miles) ≈ **1.41 × √(antenna height in feet)** for each station. Add the two.

| Antenna height | Horizon | Two stations at this height |
|---|---|---|
| 5 ft (handheld) | 3.2 mi | 6.3 mi |
| 30 ft (roof mast) | 7.7 mi | 15.5 mi |
| 100 ft (tower / hill) | 14 mi | 28 mi |

**Height beats power.** Getting a handheld up a hill does more than doubling watts. A repeater on a tower can cover 40–60 miles.

### HF — skywave
The ionosphere reflects HF back to earth. It changes with time of day, season and the 11-year sunspot cycle.
- **NVIS** (Near Vertical Incidence Skywave): a low horizontal dipole (10–20 ft high) on 40/80/60 m bounces signals straight up and down — perfect for **0–300 mile** coverage that fills in "behind" hills where VHF fails.
- Daytime: higher bands (20 m and up) open for long distance.
- Night: lower bands (40/80 m) carry farther; higher bands close.
- WWV (2.5/5/10/15/20 MHz) is a free propagation beacon — whichever you hear best tells you what's open.

## Starter Station for Grid-Down

1. **Dual-band handheld (2 m / 70 cm)** + better antenna + battery eliminator/AA pack
2. **Mobile/base 2 m/70 cm** (25–50 W) with a roof antenna or J-pole
3. **HF radio** (100 W, or QRP 5–10 W for battery life) + **40/80 m dipole** — see the [Antenna tool](/tools/radio)
4. **12 V LiFePO4 battery + solar** — see [Battery & Solar tool](/tools/power)
5. Spares in a **Faraday container** — see [EMP protection](/power/emp_faraday_protection)

## Priority
- **Monitor 146.520** and learn your local repeaters *now*, while it's easy.
