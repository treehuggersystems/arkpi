---
title: EMP & Faraday Protection
category: power
tags: [power, emp, faraday, electronics, emergency]
summary: What an EMP actually does, what survives, and how to build Faraday containers for radios, this Raspberry Pi, and spare electronics.
---

# EMP & Faraday Protection

## What Is an EMP?
An electromagnetic pulse is a burst of energy that induces damaging voltages in conductors. Sources:
- **High-altitude nuclear detonation (HEMP)**: could affect a whole continent
- **Severe solar storm (geomagnetic disturbance)**: the 1859 Carrington Event is the classic example
- Localized non-nuclear EMP weapons

A HEMP arrives in three parts:

| Component | Timing | Threatens |
|---|---|---|
| **E1** | Nanoseconds | **Electronics**: microchips, computers, radios, control systems. Too fast for surge protectors |
| **E2** | Microseconds–1 s | Similar to lightning, so normal surge protection helps |
| **E3** | Seconds–minutes | **Long power lines and large transformers**: the grid. Similar to a solar storm |

**Solar storms mainly produce E3-type effects**, which threaten the **power grid**, not handheld electronics. That means a grid-down event where your *unplugged* gadgets may survive.

## What's Most Vulnerable
- Anything **connected to long wires**: plugged-in electronics, devices on antennas, grid-tied solar inverters, hard-wired networks
- Modern control electronics: inverters, charge controllers, appliance boards
- Large grid transformers (E3), which take **months to years** to replace

## Less Vulnerable (but not guaranteed)
- Small, **unplugged**, battery-powered devices with short leads
- **Solar panels** themselves are fairly robust. Their **charge controllers and inverters** are not.
- **Vehicles**: EMP Commission testing (2004) found most running cars and trucks had minor or no effects (some stalled and restarted). Not guaranteed for newer vehicles.

## Faraday Containers
A closed conductive shell blocks external fields. Requirements:
1. **Fully enclosed conductive metal** with tight seams and no gaps
2. **Insulation inside**, so contents don't touch the metal (cardboard, foam, bubble wrap)
3. **Nothing poking through**: no wires, no antennas leaving the box

### Options
| Container | Notes |
|---|---|
| **Galvanized steel trash can** with tight lid | Classic, cheap. Line with cardboard. Tape the lid seam with **conductive** aluminum foil tape |
| Metal ammo can | Remove or bridge the rubber gasket with foil tape for metal-to-metal contact |
| **Nested** containers (e.g. Faraday bag in a metal can) | Layers add protection. Each layer insulated from the next |
| Commercial Faraday bags (multi-layer, rated) | Good for laptops, phones, **this Pi** |
| Old microwave oven (unplugged, cord cut off) | Works okay, but seal is designed for 2.4 GHz only |
| Heavy-duty aluminum foil, **3+ layers**, each wrapped in plastic | Cheap, fragile. Tears = leaks |

### Test (rough)
Put an AM/FM radio inside on a strong station, or call a phone inside. If you still hear it, there's a leak. **Passing this test doesn't guarantee EMP protection, but failing it means definite trouble.**

## What to Store in a Faraday Container
- [ ] **Spare handheld radio(s)** + programming cable + charger
- [ ] AM/FM/shortwave receiver
- [ ] **Spare Raspberry Pi** (or this one) + SD card/SSD backup of this server + power supply
- [ ] Small solar panel *charge controller* & USB solar charger
- [ ] LED flashlights / headlamps
- [ ] USB drives with documents, manuals, and maps (copy this server's `/opt` data)
- [ ] Small inverter, cables, USB cords
- [ ] Old laptop or tablet with offline maps
- [ ] Hearing aids / medical devices (spares) if applicable
- [ ] Batteries (they're fine either way, but it keeps the kit together)

## For This ARK Server
- Keep a **full, tested backup** (SD card or SSD image) of the Pi in a Faraday bag inside a metal can.
- Include a **5 V USB power source** that runs from solar/12 V. The Pi draws ~3–7 W. A 100 Wh battery runs it ~15+ hours.
- Store a small Wi-Fi travel router too, so phones can connect to the Pi when the house network is dead.

## When Warning Comes (solar storm alerts)
- **Unplug** electronics from walls; disconnect antenna cables from radios.
- Switch off main breaker / disconnect solar arrays from inverters if instructed.
- Keep spares in their containers until the event is over.

## Priority
- **Unplugged + inside a sealed, insulated metal box = best odds.** Have spares for the radio and this server.
