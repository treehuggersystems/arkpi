---
title: Home Electrical Basics
category: repair
tags: [repair, electrical, danger, power]
summary: Safety first, wire colors, matching wire gauge to breakers, replacing outlets and switches, and finding faults.
---

# Home Electrical Basics

## ⚠ Safety
- **Turn off the breaker AND verify it's dead** with a **non-contact voltage tester** (test it on a known live outlet first).
- Never work on live circuits. Lock or tape the breaker and leave a note.
- Water + electricity: never stand in water; flooded panels/outlets must be inspected before re-energizing.
- When the grid comes back after an outage, **surges are common**. Unplug electronics until power is stable.

## Wire Colors (US residential)
| Color | Purpose |
|---|---|
| **Black** (or red) | **Hot**, live |
| **White** | Neutral (can still carry current!) |
| **Green or bare copper** | Ground |
| White with black/red tape | Re-purposed as hot (e.g. switch loops) |

## Wire Gauge vs Breaker (copper)
| Breaker | Minimum wire | Typical use |
|---|---|---|
| 15 A | **14 AWG** | Lighting, general outlets |
| 20 A | **12 AWG** | Kitchen, bath, garage outlets |
| 30 A | **10 AWG** | Dryer, water heater, generator inlet |
| 40 A | 8 AWG | Range |
| 50 A | 6 AWG | Range, sub-panel, EV |

**Never put a larger breaker on a smaller wire.** The breaker protects the wire.

## Replacing an Outlet
1. Breaker off, verify dead.
2. Note which wires go where (photo). **Brass screw = hot (black). Silver screw = neutral (white). Green screw = ground.**
3. Loop wires clockwise around screws (or use back-wire clamps, not push-in "stab" holes).
4. Tuck wires, mount, cover plate, power on, test.
- Kitchens, bathrooms, garages, outdoors and near water need **GFCI** protection. Outlets marked **LINE** (feed in) and **LOAD** (downstream).

## Replacing a Switch
- Single-pole: two hot terminals (either wire on either brass screw) + ground.
- 3-way switches (two switches, one light) have a **common** (darker screw) plus two travelers. Label before removing.

## Finding Problems
| Symptom | Check |
|---|---|
| Outlet dead | GFCI tripped somewhere upstream (press RESET on GFCIs in kitchen/bath/garage/outdoor) → breaker tripped → loose wire |
| Breaker trips immediately | Short circuit: unplug everything on the circuit, reset; if it still trips, fault is in the wiring |
| Breaker trips after a while | Overload: too much on one circuit |
| Lights flicker house-wide | Loose service neutral: **call the utility/electrician, dangerous** |
| Warm outlet / burning smell | Loose connection: turn off and fix immediately |

## Tools
Non-contact voltage tester · multimeter · wire strippers · screwdrivers (insulated) · lineman's pliers · wire nuts (assorted) · electrical tape · flashlight/headlamp

## Multimeter Basics
- **AC volts (V~):** outlet should read 110–125 V; 240 V circuits 220–250 V.
- **DC volts (V⎓):** batteries (see [Battery Basics](/power/battery_basics)).
- **Continuity (beep):** test fuses, wires, switches. Circuit must be **unpowered**.
- **Resistance (Ω):** heating elements, motor windings.

## Generator Connection
Only through a **transfer switch or interlock**. See [Generator Safety](/power/generator_safety).
