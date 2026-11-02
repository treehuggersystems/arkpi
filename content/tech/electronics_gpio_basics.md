---
title: Electronics & GPIO Basics
category: tech
tags: [tech, electronics, raspberry pi, gpio]
summary: The Pi's 40-pin header, the 3.3-volt rule, LED resistors, resistor color codes, switching big loads with transistors and relays, and soldering basics.
---

# Electronics & GPIO Basics

## ⚠ The Rules That Save Your Pi
1. **GPIO pins are 3.3 V.** Putting 5 V on a GPIO pin can destroy the Pi. Use a level shifter or voltage divider for 5 V sensors.
2. **Small currents only:** about **16 mA per pin**, and keep the total across all pins low (~50 mA). Never drive motors, relay coils, or more than an LED directly. Use a transistor or a relay module.
3. **Never short 5 V or 3.3 V to GND.**
4. **Power off before rewiring.**
5. **Mains (120 V) is lethal.** Use pre-built, enclosed relay modules or smart plugs rated for the load; never expose mains wiring.

## The 40-Pin Header (Pi 2/3/4/5, Zero)
Pin 1 is the corner pin nearest the SD card slot (square solder pad). Odd pins are on the inside row.

| Function | Physical pin(s) |
|---|---|
| **3.3 V** power | 1, 17 |
| **5 V** power | 2, 4 |
| **GND** | 6, 9, 14, 20, 25, 30, 34, 39 |
| I²C SDA / SCL (GPIO2 / GPIO3) | 3 / 5 |
| 1-Wire default (GPIO4) | 7 |
| UART TX / RX (GPIO14 / 15) | 8 / 10 |
| GPIO17 · 18 · 27 · 22 | 11 · 12 · 13 · 15 |
| GPIO23 · 24 · 25 | 16 · 18 · 22 |
| SPI MOSI · MISO · SCLK · CE0 | 19 · 21 · 23 · 24 |
| GPIO5 · 6 · 12 · 13 · 19 · 16 · 26 · 20 · 21 | 29 · 31 · 32 · 33 · 35 · 36 · 37 · 38 · 40 |

Code uses **GPIO numbers** (BCM), not pin numbers: "GPIO17" is physical pin 11. Run `pinout` on the Pi for a diagram.

## Ohm's Law & the LED Resistor
**V = I × R**, **P = V × I** (use the [Ohm's law calculator](/tools/radio)).

LEDs need a series resistor or they burn out:
**R = (supply V − LED forward V) ÷ current**

| LED color | Forward voltage (typ.) | Resistor at 3.3 V, ~10 mA | At 5 V, ~15 mA |
|---|---|---|---|
| Red | 2.0 V | 130 Ω → use **150 Ω** | 200 Ω → use **220 Ω** |
| Green / yellow | 2.1 V | 120 Ω → use **150 Ω** | 200 Ω → use **220 Ω** |
| Blue / white | 3.0 V | 30 Ω → use **47–100 Ω** | 133 Ω → use **150 Ω** |

The long leg (anode, +) goes to the GPIO pin via the resistor; the short leg (cathode, flat side) goes to GND. **220–330 Ω is a safe default** for any LED on a Pi.

## Resistor Color Code
Black 0 · Brown 1 · Red 2 · Orange 3 · Yellow 4 · Green 5 · Blue 6 · Violet 7 · Gray 8 · White 9
Bands: **digit, digit, multiplier (number of zeros), tolerance** (gold ±5%, silver ±10%).
Examples: red-red-brown = **220 Ω** · orange-orange-brown = **330 Ω** · brown-black-red = **1 kΩ** · brown-black-orange = **10 kΩ**.

## Buttons & Pull-Ups
A button between a GPIO pin and **GND**, with the Pi's internal **pull-up** enabled (gpiozero does this by default), reads "pressed" when the button connects the pin to ground. No extra resistor needed.

## Switching Bigger Loads
| Load | Use |
|---|---|
| LED, buzzer (< 15 mA) | Direct from GPIO with resistor |
| 12 V LED strip, small DC motor, fan, solenoid | **Logic-level N-channel MOSFET** (e.g. IRLZ44N, AO3400): gate to GPIO via ~100 Ω, 10 kΩ gate-to-GND pull-down, load between +12 V and drain, source to GND. **Flyback diode** (1N4007) across motors/solenoids/coils |
| Pump, light, heater (12 V or 120 V) | **Relay module** with opto-isolation, powered from 5 V, triggered from GPIO. Check its contact rating exceeds the load |
| 120 V appliances | Enclosed relay box or a smart plug: no exposed mains |

**Always connect grounds together** (Pi GND to the external supply's negative) when a GPIO controls a separately powered circuit (except fully isolated relay modules).

## Common Sensors (all 3.3 V-friendly)
| Sensor | Measures | Connection |
|---|---|---|
| DS18B20 | Temperature (waterproof probe versions) | 1-Wire on GPIO4, 4.7 kΩ pull-up to 3.3 V |
| BME280 / BME680 | Temp, humidity, **barometric pressure** | I²C (pins 3/5) |
| DHT22 | Temp & humidity | One GPIO + 10 kΩ pull-up |
| HC-SR501 PIR | Motion | Powered by 5 V, **output is 3.3 V**, so it's safe on GPIO |
| Float switch / reed switch | Water level, door open | Like a button |
| INA219 / INA226 | Battery voltage & current | I²C |
| ADS1115 | Analog sensors (soil moisture, light) | I²C. The Pi has no analog inputs |

Enable I²C, SPI and 1-Wire in `sudo raspi-config` → Interface Options.

## Soldering in Brief
1. Iron ~330–370 °C for leaded solder (60/40 or 63/37), hotter for lead-free.
2. Heat the **joint** (pad and wire together) for 1–2 s, feed solder into the joint, not the iron.
3. A good joint is shiny and cone-shaped. Dull and balled = reheat.
4. Heat-shrink tubing over every wire joint. Work ventilated; wash hands (lead).

## Tools Worth Having
Multimeter · breadboard and jumper wires · assorted resistors, LEDs, buttons · soldering iron · wire strippers · heat-shrink · a few relay modules, MOSFETs, DS18B20 probes, a BME280 and a PIR sensor. Keep spares in the Faraday kit.
