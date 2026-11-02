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
#   5. creates the Wi-Fi hotspot so phones can join with no router
#
# Options (environment variables):
#   ARK_SSID       Wi-Fi name                    (default: ARK)
#   ARK_PASS       Wi-Fi password, 8+ chars      (default: asks; random if non-interactive)
#   ARK_HOTSPOT    yes | no | auto               (default: auto, see below)
#   ARK_HOSTNAME   set the Pi's hostname         (default: leave unchanged)
#   ARK_REPO       git URL to install from       (default: the official repo)
#   ARK_BRANCH     branch                        (default: main)
#   ARK_DIR        install location              (default: /opt/offline-server)
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
apt-get install -y -qq python3 python3-venv python3-pip git nginx openssl curl ca-certificates avahi-daemon >/dev/null
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
mkdir -p "$DIR/data" /opt/kiwix /opt/offline-data/{maps,manuals,media,imports}

say "Installing services"
sed "s#/opt/offline-server#$DIR#g" "$DIR/deploy/offline-server.service" > /etc/systemd/system/offline-server.service
systemctl daemon-reload
systemctl enable -q offline-server
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
  nmcli connection modify Hotspot connection.autoconnect yes connection.autoconnect-priority 100
  HOTSPOT_MSG="Wi-Fi network: $SSID    password: $pass"
}

if [[ "$HOTSPOT" != "no" ]]; then
  if ! command -v nmcli >/dev/null || ! nmcli -t -f DEVICE device 2>/dev/null | grep -qx wlan0; then
    warn "no NetworkManager Wi-Fi (wlan0) found; skipping hotspot"
  else
    ACTIVE="$(nmcli -t -f DEVICE,TYPE,STATE device 2>/dev/null | grep -E '^wlan0:wifi:connected' || true)"
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

# --- done -------------------------------------------------------------------
sleep 2
systemctl is-active -q offline-server || warn "offline-server is not running; check: journalctl -u offline-server -e"
HOST="$(hostname)"
cat <<EOF

$(printf '\033[1;32m')ARK·π is installed.$(printf '\033[0m')

  Hotspot : $HOTSPOT_MSG
  Open    : http://$HOST.local:8000        (or http://10.42.0.1:8000 on the hotspot)
  Install : https://$HOST.local/install    (trust the certificate once, then "Add to Home Screen")

Next (optional, needs internet, big downloads):
  sudo $DIR/scripts/fetch-zims.sh     offline Wikipedia & friends (~21 GB)
  sudo $DIR/scripts/fetch-maps.sh     offline maps (~2 GB)

Update later:  sudo $DIR/install.sh
EOF
