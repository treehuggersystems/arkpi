#!/usr/bin/env bash
# ARK·π installer for Raspberry Pi OS / Debian / Ubuntu.
#
#   git clone https://github.com/treehuggersystems/arkpi.git
#   sudo ./arkpi/install.sh
#
# Safe to re-run: it pulls the latest code, refreshes dependencies and restarts
# the services, so it doubles as the updater.
#
# What it does
#   1. installs packages (python3-venv, git, nginx, openssl, kiwix-tools, network-manager)
#   2. puts the app in /opt/offline-server (cloning or updating from GitHub)
#   3. builds the Python venv and installs systemd services
#   4. makes a local HTTPS certificate and the nginx site (needed to install the PWA)
#   5. creates the Wi-Fi hotspot with a captive portal, so phones can join with no router
#      and are taken straight to ARK (http://ark.local, no port number)
#
# Options (environment variables):
#   ARK_SSID       Wi-Fi name                    (default: ARK)
#   ARK_PASS       Wi-Fi password, 8+ chars      (default: asks; random if non-interactive)
#   ARK_HOTSPOT    yes | no | auto               (default: auto, see below)
#   ARK_HOSTNAME   set the Pi's hostname         (default: leave unchanged)
#   ARK_REPO       git URL to install from       (default: the official repo)
#   ARK_BRANCH     branch                        (default: main)
#   ARK_DIR        install location              (default: /opt/offline-server)
#   ARK_FETCH      big offline downloads, comma-separated: wiki, maps, elevation, addresses, or "all"
#                  (default: none; wiki ~21 GB, maps ~2 GB, elevation ~1.8 GB, addresses ~0.5 GB;
#                  resumable, safe to re-run)
#   ARK_ELEVATION_RES  30 or 90 (metres) terrain detail     (default: 30; 90 is ~9x smaller)
#   ARK_AUTO_DATA  yes | no: fetch the Point to Point terrain + address data on every
#                  install/update until it's complete (default: yes; ~2.3 GB once)
#   ARK_REGION_BBOX / ARK_REGION_NAME   map region "west,south,east,north" and its label
#                  (default: Kentucky / Ohio / Indiana; get a box at boundingbox.klokantech.com)
#
# ARK_HOTSPOT=auto starts the hotspot only if the Pi is NOT currently using its
# Wi-Fi for its connection (e.g. you're on Ethernet), so you can't lock yourself
# out of an SSH session. Use ARK_HOTSPOT=yes to force it.
set -euo pipefail

REPO="${ARK_REPO:-https://github.com/treehuggersystems/arkpi.git}"
BRANCH="${ARK_BRANCH:-main}"
DIR="${ARK_DIR:-/opt/offline-server}"
SSID="${ARK_SSID:-ARK}"
HOTSPOT="${ARK_HOTSPOT:-auto}"

say()  { printf '\n\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run as root:  sudo $0"
command -v apt-get >/dev/null || die "this installer needs a Debian-based OS (Raspberry Pi OS, Debian, Ubuntu)"

# --- 1. packages ------------------------------------------------------------
say "Installing packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git nginx openssl curl wget ca-certificates avahi-daemon >/dev/null
# These two are optional: skip quietly if the distro doesn't package them.
apt-get install -y -qq kiwix-tools >/dev/null 2>&1 || warn "kiwix-tools not available; offline Wikipedia (Kiwix) will be skipped"
apt-get install -y -qq network-manager >/dev/null 2>&1 || true

# --- 2. code ----------------------------------------------------------------
say "Getting the latest ARK·π into $DIR"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$DIR/.git" ]]; then
  git -C "$DIR" fetch -q origin "$BRANCH"
  git -C "$DIR" merge -q --ff-only "origin/$BRANCH" || warn "local changes in $DIR; kept them and did not update code"
elif [[ "$SRC" == "$DIR" ]]; then
  :  # already running from the install dir
else
  git clone -q --branch "$BRANCH" "$REPO" "$DIR"
fi

# --- 3. python + services ---------------------------------------------------
say "Installing Python dependencies"
[[ -d "$DIR/venv" ]] || python3 -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install -q --upgrade pip
"$DIR/venv/bin/pip" install -q -r "$DIR/requirements.txt"
mkdir -p "$DIR/data" /opt/kiwix /opt/offline-data/{maps,manuals,media,imports,elevation,geocode}

say "Installing services"
sed "s#/opt/offline-server#$DIR#g" "$DIR/deploy/offline-server.service" > /etc/systemd/system/offline-server.service
systemctl daemon-reload
systemctl enable -q offline-server
# Fail loudly (with the real Python error) instead of leaving a silently crash-looping service.
(cd "$DIR" && "$DIR/venv/bin/python" -c "import app.main") || die "ARK failed to load; see the error above"
systemctl restart offline-server

if command -v kiwix-serve >/dev/null; then
  sed "s#/usr/bin/kiwix-serve#$(command -v kiwix-serve)#" "$DIR/deploy/kiwix.service" > /etc/systemd/system/kiwix.service
  systemctl daemon-reload
  systemctl enable -q kiwix
  if [[ -s /opt/kiwix/library.xml ]]; then
    systemctl restart kiwix
  else
    warn "no Kiwix library yet; run $DIR/scripts/fetch-zims.sh, then: sudo systemctl restart kiwix"
  fi
fi

# --- 4. HTTPS + nginx -------------------------------------------------------
[[ -z "${ARK_HOSTNAME:-}" ]] || { say "Setting hostname to ${ARK_HOSTNAME}"; hostnamectl set-hostname "$ARK_HOSTNAME"; }

say "Creating the local HTTPS certificate"
# Include the hotspot address and ark.local so the cert is valid on the hotspot.
mapfile -t IPS < <(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9.]+$' || true)
"$DIR/scripts/make-certs.sh" "${IPS[@]}" 10.42.0.1 "$(hostname)" "$(hostname).local" ark.local localhost 127.0.0.1 >/dev/null

rm -f /etc/nginx/sites-enabled/default      # ARK takes over port 80
cp "$DIR/deploy/nginx-ark.conf" /etc/nginx/sites-available/ark
ln -sf /etc/nginx/sites-available/ark /etc/nginx/sites-enabled/ark
nginx -t 2>/dev/null || die "nginx config test failed (run: sudo nginx -t)"
systemctl enable -q nginx
systemctl reload nginx 2>/dev/null || systemctl restart nginx

# --- 5. Wi-Fi hotspot -------------------------------------------------------
HOTSPOT_MSG="not configured"
setup_hotspot() {
  local pass="${ARK_PASS:-}"
  if [[ -z "$pass" && -t 0 ]]; then
    read -r -s -p "Choose a Wi-Fi password for '$SSID' (8+ characters, blank = random): " pass; echo
  fi
  if [[ -z "$pass" ]]; then
    pass="$(tr -dc 'a-km-zA-HJ-NP-Z2-9' </dev/urandom | head -c 12 || true)"
  fi
  [[ ${#pass} -ge 8 ]] || die "Wi-Fi password must be at least 8 characters"
  nmcli connection delete Hotspot >/dev/null 2>&1 || true
  nmcli device wifi hotspot ifname wlan0 con-name Hotspot ssid "$SSID" password "$pass" >/dev/null
  nmcli connection modify Hotspot connection.autoconnect yes connection.autoconnect-priority 100 \
    ipv4.addresses 10.42.0.1/24 ipv4.method shared
  # Captive portal: answer every DNS lookup on the hotspot with the Pi, so phones that probe
  # for internet land on ARK's welcome page. (Applies to the hotspot only, not Ethernet.)
  mkdir -p /etc/NetworkManager/dnsmasq-shared.d
  echo "address=/#/10.42.0.1" > /etc/NetworkManager/dnsmasq-shared.d/ark-captive.conf
  nmcli connection up Hotspot >/dev/null 2>&1 || true
  HOTSPOT_MSG="Wi-Fi network: $SSID    password: $pass"
}

if [[ "$HOTSPOT" != "no" ]]; then
  if ! command -v nmcli >/dev/null || ! nmcli -t -f DEVICE device 2>/dev/null | grep -qx wlan0; then
    warn "no NetworkManager Wi-Fi (wlan0) found; skipping hotspot"
  else
    # Only treat Wi-Fi as "in use" if it carries the default route (an existing ARK hotspot on wlan0 doesn't count)
    ACTIVE="$(ip route show default 2>/dev/null | grep -E ' dev wlan0( |$)' || true)"
    if [[ "$HOTSPOT" == "yes" || -z "$ACTIVE" ]]; then
      say "Creating the Wi-Fi hotspot"
      setup_hotspot
    else
      warn "this Pi is using Wi-Fi for its connection, so I did not start the hotspot (it would drop your session)"
      warn "to start it later, on Ethernet or at the console:  sudo ARK_HOTSPOT=yes $DIR/install.sh"
      HOTSPOT_MSG="skipped (Pi is on Wi-Fi); re-run with ARK_HOTSPOT=yes when ready"
    fi
  fi
fi

# --- 6. offline libraries (optional) ---------------------------------------
FETCH="${ARK_FETCH:-}"
[[ "$FETCH" == "all" ]] && FETCH="wiki,maps,elevation,addresses"
# Point to Point data (terrain + addresses, ~2.3 GB) comes with every install/update until
# it's complete, so a plain update gets it too. Finished data is skipped quickly.
# ARK_AUTO_DATA=no (or ARK_FETCH=none) turns this off.
if [[ "${ARK_AUTO_DATA:-yes}" != "no" && "$FETCH" != "none" ]]; then
  [[ ",$FETCH," == *",elevation,"* ]] || FETCH+="${FETCH:+,}elevation"
  ADDR_DB=/opt/offline-data/geocode/addresses.sqlite
  if ! "$DIR/venv/bin/python" - "$ADDR_DB" 2>/dev/null <<'PY'
import sqlite3, sys
con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
sys.exit(0 if con.execute("SELECT value FROM meta WHERE key='built'").fetchone() else 1)
PY
  then
    [[ ",$FETCH," == *",addresses,"* ]] || FETCH+="${FETCH:+,}addresses"
  fi
fi
want() { [[ ",$FETCH," == *",$1,"* ]]; }

free_gb() { df -BG --output=avail "$1" | tail -1 | tr -dc '0-9'; }
FETCH_MSG=""

if want wiki; then
  say "Downloading offline Wikipedia & friends (~21 GB, resumable)"
  if [[ "$(free_gb /opt/kiwix)" -lt 26 ]]; then
    warn "less than 26 GB free; skipping wiki. Use a bigger card or an SSD."
    FETCH_MSG+=$'\n  wiki : skipped (not enough disk space)'
  elif "$DIR/scripts/fetch-zims.sh"; then
    systemctl restart kiwix 2>/dev/null || true
    FETCH_MSG+=$'\n  wiki : done'
  else
    warn "wiki download did not finish; re-run: sudo ARK_FETCH=wiki $DIR/install.sh"
    FETCH_MSG+=$'\n  wiki : incomplete, re-run to resume'
  fi
fi

if want maps; then
  say "Downloading offline maps (~2 GB)"
  if [[ "$(free_gb /opt/offline-data)" -lt 4 ]]; then
    warn "less than 4 GB free; skipping maps."
    FETCH_MSG+=$'\n  maps : skipped (not enough disk space)'
  else
    if ! command -v pmtiles >/dev/null; then
      case "$(uname -m)" in aarch64|arm64) ARCH=Linux_arm64;; x86_64) ARCH=Linux_x86_64;; *) ARCH="";; esac
      if [[ -n "$ARCH" ]]; then
        TMP="$(mktemp -d)"
        URL="$(curl -fsSL https://api.github.com/repos/protomaps/go-pmtiles/releases/latest \
               | grep -oE "https://[^\"]+${ARCH}\.tar\.gz" | head -1 || true)"
        if [[ -n "$URL" ]] && curl -fsSL "$URL" | tar -xz -C "$TMP" pmtiles; then
          install -m 0755 "$TMP/pmtiles" /usr/local/bin/pmtiles
        fi
        rm -rf "$TMP"
      fi
    fi
    if ! command -v pmtiles >/dev/null; then
      warn "could not install the pmtiles tool (needs internet); skipping maps"
      FETCH_MSG+=$'\n  maps : skipped (pmtiles tool unavailable)'
    elif REGION_BBOX="${ARK_REGION_BBOX:--89.6,36.4,-80.4,42.1}" \
         REGION_NAME="${ARK_REGION_NAME:-Kentucky · Ohio · Indiana}" \
         "$DIR/scripts/fetch-maps.sh"; then
      FETCH_MSG+=$'\n  maps : done'
    else
      warn "map download did not finish; re-run: sudo ARK_FETCH=maps $DIR/install.sh"
      FETCH_MSG+=$'\n  maps : incomplete, re-run to retry'
    fi
  fi
fi

# Region: what you set, else the scripts follow the installed map region, else KY/OH/IN.
REGION_ENV=(ARK_FETCH_REGION=1)
[[ -n "${ARK_REGION_BBOX:-}" ]] && REGION_ENV+=(ARK_REGION_BBOX="$ARK_REGION_BBOX")
[[ -n "${ARK_REGION_NAME:-}" ]] && REGION_ENV+=(ARK_REGION_NAME="$ARK_REGION_NAME")

if want elevation; then
  RES="${ARK_ELEVATION_RES:-30}"
  say "Downloading terrain elevation for the Point to Point tool (${RES} m; ~1.8 GB at 30 m for the default region)"
  NEED=$([[ "$RES" == 90 ]] && echo 1 || echo 3)
  if [[ "$(free_gb /opt/offline-data)" -lt "$NEED" ]]; then
    warn "less than $NEED GB free; skipping elevation (try ARK_ELEVATION_RES=90, about 200 MB)."
    FETCH_MSG+=$'\n  elevation : skipped (not enough disk space)'
  elif env "${REGION_ENV[@]}" "$DIR/venv/bin/python" "$DIR/scripts/fetch-elevation.py" --res "$RES"; then
    FETCH_MSG+=$'\n  elevation : done'
  else
    warn "elevation download did not finish; re-run: sudo ARK_FETCH=elevation $DIR/install.sh"
    FETCH_MSG+=$'\n  elevation : incomplete, re-run to resume'
  fi
fi

if want addresses; then
  say "Building the offline address finder (US Census street ranges for the region; ~0.5 GB)"
  if [[ "$(free_gb /opt/offline-data)" -lt 2 ]]; then
    warn "less than 2 GB free; skipping addresses."
    FETCH_MSG+=$'\n  addresses : skipped (not enough disk space)'
  elif env "${REGION_ENV[@]}" "$DIR/venv/bin/python" "$DIR/scripts/build-addresses.py"; then
    FETCH_MSG+=$'\n  addresses : done'
  else
    warn "address download did not finish; re-run: sudo ARK_FETCH=addresses $DIR/install.sh"
    FETCH_MSG+=$'\n  addresses : incomplete, re-run to resume'
  fi
fi

# --- done -------------------------------------------------------------------
sleep 2
systemctl is-active -q offline-server || warn "offline-server is not running; check: journalctl -u offline-server -e"
HOST="$(hostname)"
cat <<EOF

$(printf '\033[1;32m')ARK·π is installed.$(printf '\033[0m')

  Hotspot : $HOTSPOT_MSG
  Open    : http://$HOST.local             (or http://10.42.0.1 on the hotspot; phones get a pop-up automatically)
  Install : https://$HOST.local/install    (trust the certificate once, then "Add to Home Screen")

Offline libraries:${FETCH_MSG:-
  not downloaded. Add them any time (needs internet, ~26 GB):
  sudo ARK_FETCH=all $DIR/install.sh}

Update later:  sudo $DIR/install.sh
EOF
