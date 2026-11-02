#!/usr/bin/env bash
# Create a local certificate authority + HTTPS certificate for ARK.
#
#   sudo scripts/make-certs.sh [ip-or-hostname ...]
#
# Browsers only install PWAs / run service workers over HTTPS. With no
# internet there's no Let's Encrypt, so ARK signs its own certificate with a
# local CA. Install the CA once on each phone/computer (ARK serves it at
# /install) and HTTPS "just works" on the LAN — even fully offline.
#
# Re-run with new addresses (e.g. after moving to the Pi); the CA is reused so
# devices that already trust it keep working.
set -euo pipefail

DIR="${ARK_TLS_DIR:-/etc/ark-tls}"
mkdir -p "$DIR" && chmod 755 "$DIR"
cd "$DIR"

NAMES=("$@")
if [[ ${#NAMES[@]} -eq 0 ]]; then
  NAMES=($(hostname -I | tr ' ' '\n' | grep -E '^[0-9.]+$') "$(hostname)" "ark.local" "localhost" "127.0.0.1")
fi

SAN=""
for n in "${NAMES[@]}"; do
  if [[ "$n" =~ ^[0-9.]+$ ]]; then SAN+="IP:$n,"; else SAN+="DNS:$n,"; fi
done
SAN="${SAN%,}"

if [[ ! -f ca.key ]]; then
  openssl req -x509 -newkey rsa:3072 -nodes -days 7300 \
    -keyout ca.key -out ca.crt -subj "/CN=ARK Local CA/O=ARK Offline Knowledge Ark" \
    -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign"
  chmod 600 ca.key
  echo "Created CA: $DIR/ca.crt"
fi

# Leaf certs: keep validity <= 825 days or iOS/macOS reject them.
openssl req -newkey rsa:2048 -nodes -keyout server.key -out server.csr -subj "/CN=${NAMES[0]}"
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 825 -sha256 -out server.crt \
  -extfile <(printf "subjectAltName=%s\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n" "$SAN")
chmod 600 server.key
rm -f server.csr
echo "Server cert for: $SAN"
openssl x509 -in server.crt -noout -enddate
