#!/usr/bin/env bash
set -euo pipefail

OUT="data/interim/connectivity_test/interface_pilot.pcapng"
EXPECTED_IP="51.75.145.20"

mkdir -p data/interim/connectivity_test

if [[ -e "$OUT" ]]; then
    echo "ERROR: Existing capture found: $OUT"
    echo "Purani file overwrite nahi ki."
    exit 1
fi

command -v dumpcap >/dev/null || { echo "dumpcap missing"; exit 1; }
command -v firefox >/dev/null || { echo "Firefox missing"; exit 1; }

if ! ip link show wg0 >/dev/null 2>&1; then
    echo "Starting WireGuard..."
    sudo wg-quick up wg0
fi

echo "Checking WireGuard handshake..."
if ! sudo wg show wg0 latest-handshakes |
    awk '{if ($2 > 0) ok=1} END {exit !ok}'; then
    echo "ERROR: No WireGuard handshake. Stopping."
    exit 1
fi

VPN_IP=$(curl -4 -sS --max-time 10 https://api.ipify.org) || {
    echo "ERROR: VPN internet test failed."
    exit 1
}

echo "Public IPv4: $VPN_IP"
if [[ "$VPN_IP" != "$EXPECTED_IP" ]]; then
    echo "ERROR: Unexpected VPN IP. Capture cancelled."
    exit 1
fi

echo "Starting 90-second pilot capture..."
dumpcap -q -i wlp2s0 -i wg0 -a duration:90 -w "$OUT" &
CAP_PID=$!

cleanup() {
    if kill -0 "$CAP_PID" 2>/dev/null; then
        kill -INT "$CAP_PID" 2>/dev/null || true
        wait "$CAP_PID" || true
    fi
}
trap cleanup EXIT INT TERM

sleep 3

URLS=(
  "https://example.com"
  "https://www.wikipedia.org"
  "https://developer.mozilla.org"
  "https://www.python.org"
  "https://www.iana.org"
  "https://www.gnu.org"
)

echo "Opening public websites in Firefox Private Window..."
firefox --private-window "${URLS[0]}" >/dev/null 2>&1 &
sleep 10

for url in "${URLS[@]:1}"; do
    echo "Opening $url"
    firefox --private-window "$url" >/dev/null 2>&1 &
    sleep 10
done

wait "$CAP_PID"
trap - EXIT INT TERM

echo
echo "Pilot finished: $OUT"
ls -lh "$OUT"
