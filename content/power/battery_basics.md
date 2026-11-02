---
title: Battery Basics & State of Charge
category: power
tags: [power, batteries, solar, off-grid]
summary: Lead-acid vs LiFePO4, voltage-to-charge charts, cold-weather rules, and getting power from your car.
---

# Battery Basics & State of Charge

## Chemistry Comparison

| | Flooded lead-acid | AGM / Gel | **LiFePO4 (lithium iron phosphate)** |
|---|---|---|---|
| Usable capacity | **50%** (deeper kills it) | 50–60% | **80–100%** |
| Cycle life | 300–1,000 | 400–1,200 | **3,000–6,000+** |
| Weight | Heavy | Heavy | ~⅓ the weight |
| Maintenance | Check water monthly, ventilate (hydrogen) | None | None |
| Cold charging | OK | OK | **Do not charge below 32°F** unless it has built-in heating |
| Cost per usable kWh over life | Low upfront, high long-term | Medium | **Lowest long-term** |

## 12 V Lead-Acid: State of Charge (resting, no load for 2+ hours)

| Voltage | Charge |
|---|---|
| **12.7+** | **100%** |
| 12.5 | ~90% |
| 12.4 | ~75% |
| 12.2 | ~50% (**recharge now**) |
| 12.0 | ~25% |
| 11.8 or less | Discharged. Damage occurring |

## 12.8 V LiFePO4: State of Charge (resting, approximate)

| Voltage | Charge |
|---|---|
| 13.4–13.6 | ~100% (just charged) |
| 13.3 | ~90% |
| 13.2 | ~70% |
| 13.1 | ~40% |
| 13.0 | ~30% |
| 12.9 | ~20% |
| 12.5 | ~10% |
| 12.0 | ~5%. Stop |
| 10.0 | 0%. BMS cuts off |

The LiFePO4 curve is **very flat**, so voltage is a rough guide. A **shunt-based battery monitor** (counts amp-hours in and out) is much more accurate.

*For 24 V systems multiply by 2; 48 V multiply by 4.*

## Rules for Long Battery Life
- **Lead-acid:** recharge to 100% often; never leave discharged (sulfation). Equalize flooded batteries per the maker.
- **LiFePO4:** happiest between 20–90%. Store at ~50–60%.
- Keep batteries **cool** (heat ages them) but above freezing when charging lithium.
- Clean corroded terminals with **baking soda + water**, then a light coat of grease.

## Small Batteries
| Type | Shelf life | Notes |
|---|---|---|
| Alkaline AA/AAA | 7–10 years | Can leak, so remove from stored devices |
| **Lithium AA (Energizer Ultimate)** | **20 years** | Light, works in deep cold, rarely leaks. Best for stored kits |
| **NiMH rechargeable (Eneloop)** | Holds ~70% after 5–10 years | Rechargeable ~2,000×. Pair with a solar USB charger |
| 18650 / 21700 Li-ion | Store at ~50% | Use protected cells and a quality charger |

## Your Car Is a Generator
- A car battery is ~50 Ah (~600 Wh). With the **engine running**, the alternator can supply 50–100+ A.
- A **300–400 W inverter** plugs into the 12 V outlet (fused for ~10–15 A, so ~120–150 W max). Larger inverters must clamp directly to the battery.
- Running a modern car at idle uses roughly **0.2–0.5 gal/hr**.
- **CO danger**: never in a garage, and keep exhaust clear of snow.
- **Hybrids** (e.g. Prius) with an inverter on the 12 V or high-voltage system make excellent quiet generators.

## Priority
- **Don't drain lead-acid below 50%. Don't charge lithium below freezing.**
