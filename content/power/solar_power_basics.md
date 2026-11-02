---
title: Off-Grid Solar Basics
category: power
tags: [power, solar, batteries, off-grid]
summary: How panels, charge controllers, batteries and inverters fit together — wiring, sizing, fusing and orientation.
---

# Off-Grid Solar Basics

Size a system with the [Battery & Solar calculator](/tools/power).

## The Chain

**Solar panels → Charge controller → Battery bank → Inverter → AC loads**
*(DC loads like USB, 12 V lights, and radios can run straight off the battery through a fuse block.)*

| Part | Job | Key spec |
|---|---|---|
| **Panels** | Make DC power from sunlight | Watts, Voc (open-circuit voltage), Isc (short-circuit current) |
| **Charge controller** | Charges the battery safely | **MPPT** (20–30% more efficient, handles high-voltage arrays) vs PWM (cheap, simple) |
| **Battery** | Stores energy | Voltage (12/24/48 V), amp-hours, chemistry |
| **Inverter** | DC → 120 V AC | Continuous watts, surge watts, **pure sine wave** for electronics & motors |

## Watts, Amps, Volts
- **Watts = Volts × Amps**
- **Watt-hours = Watts × Hours** (energy)
- 100 Ah battery at 12 V = **1,200 Wh** (but usable depends on chemistry)

## Wiring Panels
- **Series** (+ to −): voltages **add**, current stays the same. Thinner wire over long runs. Needs MPPT. **Shading one panel hurts the whole string.**
- **Parallel** (+ to +, − to −): currents **add**, voltage stays the same. More shade tolerant, needs heavier wire.
- **Check:** array Voc (adjusted for cold, +10–25% in winter) must stay **below** the controller's max input voltage.

## Battery Banks
- **Series** raises voltage (two 12 V = 24 V); **parallel** raises capacity.
- Use **identical batteries** (same age, type, capacity) in a bank.
- Bigger systems → higher voltage (24/48 V) = less current = thinner wire.

## Fusing (do not skip)
- Fuse or breaker on **every positive conductor** close to the battery.
- Between battery and inverter: a **Class T fuse** or ANL rated for the inverter's max current.
- Between controller and battery; between panels and controller (breaker/disconnect).
- **Wire size must handle the current**. Check the [voltage drop calculator](/tools/radio).

## Panel Placement
- Face **true south** (in the Northern Hemisphere).
- Tilt ≈ **your latitude** for year-round (~38° in Kentucky). Latitude **+15°** favors winter, **−15°** summer.
- **Avoid shade** 9 AM–3 PM. Even a small shadow cuts output a lot.
- Keep panels clean; snow slides off steep tilts.

## Peak Sun Hours (Ohio Valley, approx.)
| Season | Peak sun hours / day |
|---|---|
| Summer | 5–5.5 |
| Spring / fall | 4–4.5 |
| **Winter** | **2–3** |

**Design for winter** if you need year-round power, or plan generator backup.

## Starter Systems
| Size | Parts | Runs |
|---|---|---|
| **Grab-and-go** | 100 W folding panel + 500–1,000 Wh portable power station | Phones, radios, lights, laptop, **this Pi** |
| **Essentials** | 400–800 W panels, 40 A MPPT, 24 V 200 Ah LiFePO4 (~5 kWh), 2,000 W inverter | Fridge, lights, internet/radio, fans, CPAP |
| **Whole home** | 5–10 kW array, 48 V 15–30 kWh bank, hybrid inverter | Most loads (not electric heat) |

## Grid-Tie Warning
Standard grid-tied solar **shuts off when the grid goes down** (anti-islanding). You need a **hybrid inverter with batteries** to use your panels in an outage.

See also: [Battery Basics](/power/battery_basics), [EMP Protection](/power/emp_faraday_protection).
