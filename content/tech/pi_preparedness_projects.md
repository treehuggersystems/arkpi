---
title: Pi Preparedness Projects (with code)
category: tech
tags: [tech, raspberry pi, python, sensors, security, homestead]
summary: Working Python for a motion alarm, freezer and root-cellar temperature monitor, barometer storm alert, water-tank level, relay timer for pumps and lights, and a solar battery monitor.
---

# Pi Preparedness Projects (with code)

Wiring basics are in [Electronics & GPIO Basics](/tech/electronics_gpio_basics); running scripts automatically is in the [Python & Bash Primer](/tech/python_and_bash_primer). Most examples use **gpiozero**, preinstalled on Raspberry Pi OS. Each script appends to a CSV log you can open later.

## 1. Motion Alarm (driveway, barn, back door)
**Parts:** HC-SR501 PIR sensor (VCC → 5 V pin 2, GND → pin 6, OUT → **GPIO4**, pin 7), buzzer + 220 Ω on **GPIO17** (pin 11), optional LED on GPIO27.

```python
from gpiozero import MotionSensor, Buzzer, LED
from signal import pause
from datetime import datetime

pir, buzzer, led = MotionSensor(4), Buzzer(17), LED(27)

def alert():
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("Motion!", stamp)
    open("/home/pi/motion.csv", "a").write(stamp + "\n")
    led.on(); buzzer.beep(on_time=0.2, off_time=0.2, n=5)

pir.when_motion = alert
pir.when_no_motion = led.off
pause()
```
Tip: adjust the PIR's two trim pots (sensitivity, hold time). Point it away from heaters and sunlight.

## 2. Freezer / Root-Cellar Temperature Monitor
**Parts:** DS18B20 waterproof probe: red → 3.3 V, black → GND, yellow → **GPIO4**, with a **4.7 kΩ** resistor between yellow and 3.3 V. Add `dtoverlay=w1-gpio` to `/boot/firmware/config.txt` and reboot.

```python
import glob, time
from datetime import datetime

def read_temps():
    temps = {}
    for dev in glob.glob("/sys/bus/w1/devices/28-*/temperature"):
        sensor = dev.split("/")[-2]
        c = int(open(dev).read()) / 1000
        temps[sensor] = c * 9 / 5 + 32          # °F
    return temps

ALARM_F = 10          # freezer should stay below this
while True:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for sensor, f in read_temps().items():
        line = f"{now},{sensor},{f:.1f}"
        print(line)
        open("/home/pi/temps.csv", "a").write(line + "\n")
        if f > ALARM_F:
            print("⚠ WARNING: freezer warming!", sensor, f)
    time.sleep(300)    # every 5 minutes
```
Several probes can share the same wire. Each has its own ID (freezer, fridge, root cellar, greenhouse, outdoor).

## 3. Barometer Storm Alert
**Parts:** BME280 on I²C (VIN → 3.3 V, GND, SDA → pin 3, SCL → pin 5). Enable I²C in `raspi-config`.
`~/env/bin/pip install adafruit-circuitpython-bme280`

```python
import time, board
from collections import deque
from adafruit_bme280 import basic as adafruit_bme280

bme = adafruit_bme280.Adafruit_BME280_I2C(board.I2C())   # address 0x76 or 0x77
history = deque(maxlen=37)                                 # 3 hours at 5-min samples

while True:
    hpa = bme.pressure
    history.append(hpa)
    inhg = hpa * 0.02953
    msg = f"{bme.temperature * 9/5 + 32:.1f}°F  {bme.relative_humidity:.0f}%  {inhg:.2f} inHg"
    if len(history) == history.maxlen:
        change = history[-1] - history[0]                  # hPa over 3 hours
        if change <= -2.0:
            msg += "  ⚠ FALLING FAST, storm likely"
        elif change >= 2.0:
            msg += "  rising, clearing"
    print(msg)
    time.sleep(300)
```
A fall of ~2 hPa (0.06 inHg) in 3 hours is the classic storm warning: see [Weather Lore](/fieldcraft/weather_lore).

## 4. Water Tank / Rain Barrel Level
**Simple:** float switches at "low" and "full" heights, wired like buttons (GPIO ↔ GND).

```python
from gpiozero import Button
from signal import pause

low  = Button(23)   # closes when water drops BELOW the low float (check your float's orientation)
full = Button(24)

low.when_pressed  = lambda: print("Tank LOW: switch to backup water")
full.when_pressed = lambda: print("Tank FULL: stop the pump")
pause()
```
**Continuous level:** a waterproof ultrasonic sensor (JSN-SR04T) above the water measures distance to the surface: `gpiozero.DistanceSensor(echo=..., trigger=...)`. **Its echo pin outputs 5 V, so use a voltage divider** (1 kΩ + 2 kΩ) before the GPIO.

## 5. Relay Timer: Pump, Lights, Fan, Generator Start Signal
**Parts:** opto-isolated relay module (VCC → 5 V, GND, IN → **GPIO26**). Many modules are "active low" (on when the pin is LOW), so set `active_high=False`.

```python
from gpiozero import OutputDevice
from datetime import datetime
import time

pump = OutputDevice(26, active_high=False, initial_value=False)
SCHEDULE = [("06:00", 15), ("18:00", 15)]     # start time, minutes to run

while True:
    now = datetime.now().strftime("%H:%M")
    for start, minutes in SCHEDULE:
        if now == start:
            print("Pump ON", now)
            pump.on(); time.sleep(minutes * 60); pump.off()
            print("Pump OFF")
    time.sleep(30)
```
Check the relay's rating (amps and volts) exceeds the load, and use a flyback diode on DC motor loads.

## 6. Solar Battery Monitor
**Parts:** INA219 (or INA226 for higher voltages) on I²C, in line with the battery's positive lead.
`~/env/bin/pip install adafruit-circuitpython-ina219`

```python
import time, board
from adafruit_ina219 import INA219

ina = INA219(board.I2C())
while True:
    v = ina.bus_voltage + ina.shunt_voltage / 1000
    a = ina.current / 1000
    print(f"{v:.2f} V  {a:+.2f} A  {v*a:+.1f} W")
    if v < 12.0:
        print("⚠ Battery low: cut non-essential loads")   # see Battery Basics for SoC table
    time.sleep(60)
```
The stock INA219 module is limited to **26 V** and about **3.2 A** with its default shunt. For bigger systems, use an INA226 with an external shunt, or read your charge controller's data port.

## 7. Camera Motion Recording
A Pi Camera Module plus the **motion** or **MotionEye** packages give motion-triggered recording viewable from any phone on the hotspot. Install while online: `sudo apt install motion` (or MotionEye via its docs).

## Put It Together: One Dashboard
Write each script's readings to a CSV, then serve them with the [tiny web page example](/tech/python_and_bash_primer). Or log key readings in ARK·π's [Logbook](/tools/logbook). Run each script as a **systemd service** so it starts at boot and restarts if it crashes.
