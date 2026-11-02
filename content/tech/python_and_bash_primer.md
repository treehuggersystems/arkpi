---
title: Python & Bash Primer
category: tech
tags: [tech, programming, python, bash, raspberry pi]
summary: Enough Python and Bash to write useful scripts — variables, loops, functions, files, a tiny web page — and run them automatically with cron or systemd.
---

# Python & Bash Primer

Python comes installed on every Raspberry Pi and is the easiest way to automate things, read sensors, and build small tools. Full offline docs: Python and Bash manuals in the [Library](/library#wiki).

## Running Python
```
python3                 # interactive: try lines, exit with Ctrl+D
python3 myscript.py     # run a file
```
Edit files with `nano myscript.py` (or Thonny on the Pi desktop).

## Python in 15 Minutes
```python
# Variables and types
name = "ARK"
count = 3
temp_f = 72.5
ready = True
items = ["rice", "beans", "salt"]          # list
stock = {"rice": 35, "beans": 33}          # dictionary (key → value)

# Printing and f-strings
print(f"{name} has {len(items)} items; rice: {stock['rice']} lb")

# Decisions
if temp_f > 90:
    print("Hot! Check on livestock.")
elif temp_f < 32:
    print("Freezing: protect the pipes.")
else:
    print("OK")

# Loops
for item in items:
    print("-", item)

n = 0
while n < 3:
    n += 1

# Functions
def gallons_needed(people, days, per_day=1.0):
    return people * days * per_day

print(gallons_needed(4, 14))     # 56.0

# Files
with open("log.txt", "a") as f:          # "a" = append, "w" = overwrite, "r" = read
    f.write("checked water at noon\n")

with open("log.txt") as f:
    for line in f:
        print(line.strip())

# Errors
try:
    x = int("abc")
except ValueError:
    print("That's not a number")
```

### Useful built-in modules
```python
import time, datetime, json, os, random, subprocess

time.sleep(2)                                   # pause 2 s
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
json.dump({"temp": 72}, open("data.json", "w"))  # save structured data
data = json.load(open("data.json"))
os.path.exists("/opt/kiwix")                     # does it exist?
out = subprocess.run(["df", "-h"], capture_output=True, text=True).stdout
```

### A tiny web page (no extra installs)
```python
# save as web.py, run: python3 web.py, then open http://ark.local:8080
from http.server import BaseHTTPRequestHandler, HTTPServer
import datetime

class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"<h1>Root cellar</h1><p>Updated {datetime.datetime.now():%H:%M}</p>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

HTTPServer(("0.0.0.0", 8080), Page).serve_forever()
```

### Installing Python packages
Use a **virtual environment** (Raspberry Pi OS requires it for pip):
```
python3 -m venv ~/env
~/env/bin/pip install gpiozero requests
~/env/bin/python myscript.py
```
Many hardware libraries are also available via apt: `sudo apt install python3-gpiozero`.

## Bash Scripts
Bash runs the same commands you type, saved in a file.
```bash
#!/bin/bash
# save as backup.sh, then: chmod +x backup.sh && ./backup.sh
set -e                                   # stop on the first error
DEST="/mnt/usb/ark-backup-$(date +%F)"
mkdir -p "$DEST"
cp -r /opt/offline-server/data "$DEST/"
echo "Backed up to $DEST"

for f in /opt/kiwix/*.zim; do            # loop over files
  echo "$(du -h "$f" | cut -f1)  $f"
done

if [ "$(df --output=pcent / | tail -1 | tr -dc 0-9)" -gt 90 ]; then
  echo "WARNING: disk over 90% full"
fi
```

## Run Things Automatically
### cron: on a schedule
`crontab -e`, then add a line (minute hour day month weekday command):
```
*/10 * * * *  /home/pi/env/bin/python /home/pi/read_temp.py     # every 10 minutes
0 6 * * *     /home/pi/backup.sh                                # every day at 06:00
@reboot       /home/pi/start_hotspot.sh                         # at every boot
```

### systemd: a service that keeps running (and restarts if it crashes)
Create `/etc/systemd/system/cellar.service`:
```
[Unit]
Description=Root cellar monitor
After=network.target

[Service]
ExecStart=/home/pi/env/bin/python /home/pi/web.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```
Then:
```
sudo systemctl daemon-reload
sudo systemctl enable --now cellar
systemctl status cellar
```
ARK·π itself runs exactly this way (`offline-server.service`).

## Where to Go Next
- [Electronics & GPIO Basics](/tech/electronics_gpio_basics) → [Pi Preparedness Projects](/tech/pi_preparedness_projects) for code that reads sensors and switches things.
- Offline references: Python docs, Raspberry Pi Q&A, Unix & Linux Q&A and Arduino Q&A in the [Library](/library#wiki).
