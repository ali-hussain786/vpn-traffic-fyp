#!/usr/bin/env bash
set -Eeuo pipefail

# Three-session controlled pilot: Normal, OpenVPN, WireGuard
# Duration: 30 minutes per session
# Captures are saved separately by interface.
# This script does NOT assign labels to individual network flows.

ROOT="$HOME/vpn-traffic-fyp"
WIFI_IF="wlp2s0"
EXPECTED_VPN_IP="51.75.145.20"
DURATION=1800
TASKSEQ="TASKSEQ_01"

cd "$ROOT"

for cmd in dumpcap curl ip python date; do
    command -v "$cmd" >/dev/null || {
        echo "ERROR: Required command missing: $cmd"
        exit 1
    }
done

FIREFOX="$(command -v firefox || true)"
CHROME="$(command -v google-chrome-stable || command -v google-chrome || command -v chromium || true)"

if [[ -z "$FIREFOX" || -z "$CHROME" ]]; then
    echo "ERROR: Both Firefox and Chrome/Chromium are required."
    echo "Firefox: ${FIREFOX:-not found}"
    echo "Chrome:  ${CHROME:-not found}"
    exit 1
fi

ip link show "$WIFI_IF" >/dev/null 2>&1 || {
    echo "ERROR: Wi-Fi interface $WIFI_IF not found."
    exit 1
}

echo "Three-session capture automation"
echo "Sessions: Normal -> OpenVPN -> WireGuard"
echo "Duration: 30 minutes each"
echo "Raw captures will remain local and separate."
echo
read -rp "Network type (Home/University/Other): " NETWORK_TYPE
case "$NETWORK_TYPE" in
    Home|University|Other) ;;
    *) echo "ERROR: Enter Home, University or Other."; exit 1 ;;
esac

read -rp "Capture location code (e.g. HOME_01): " LOCATION_CODE
[[ -n "$LOCATION_CODE" ]] || {
    echo "ERROR: Location code cannot be empty."
    exit 1
}

sudo -v

RUN_ID="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT/data/raw/captures/three_session_pilot_$RUN_ID"
mkdir -p "$OUT"
META="$OUT/session_metadata.csv"

printf '%s\n' \
'session_id,capture_date,capture_start_time,capture_timezone,capture_duration_seconds,class_label,operating_system,os_version,device_id,python_version,nfstream_version,network_type,capture_location_code,vpn_software,vpn_software_version,vpn_protocol,vpn_connected_status,capture_tool,capture_tool_version,task_sequence_id,repeat_number,session_status,notes' \
> "$META"

OS_NAME="Fedora"
OS_VERSION="$(. /etc/os-release; printf '%s' "$PRETTY_NAME")"
PY_VERSION="$(python --version 2>&1 | awk '{print $2}')"
NF_VERSION="$(python -c 'from importlib.metadata import version; print(version("nfstream"))' 2>/dev/null || echo unknown)"
DUMPCAP_VERSION="$(dumpcap --version | head -n1 | sed 's/,.*//')"

public_ip() {
    curl -4 -fsS --max-time 12 https://api.ipify.org
}

verify_class() {
    local class="$1"
    local ip_now tunnel handshake now

    ip_now="$(public_ip)" || {
        echo "ERROR: Cannot verify public IPv4."
        return 1
    }

    case "$class" in
        normal)
            if pgrep -x openvpn >/dev/null 2>&1 ||
               sudo wg show interfaces 2>/dev/null | grep -qw wg0 ||
               ip -o link show | grep -Eq ': (tun[0-9]+|wg0):'; then
                echo "ERROR: VPN interface/process still active. Normal session refused."
                return 1
            fi
            if [[ "$ip_now" == "$EXPECTED_VPN_IP" ]]; then
                echo "ERROR: Public IP matches the expected VPN endpoint."
                return 1
            fi
            echo "Normal session verified; public IPv4: $ip_now"
            ;;

        openvpn)
            pgrep -x openvpn >/dev/null 2>&1 || {
                echo "ERROR: OpenVPN process is not running."
                return 1
            }
            tunnel="$(ip -o link show | awk -F': ' '$2 ~ /^tun[0-9]+$/ {print $2; exit}')"
            [[ -n "$tunnel" ]] || {
                echo "ERROR: No OpenVPN tunnel interface found."
                return 1
            }
            [[ "$ip_now" == "$EXPECTED_VPN_IP" ]] || {
                echo "ERROR: Public IP $ip_now does not match expected $EXPECTED_VPN_IP."
                return 1
            }
            echo "OpenVPN verified; interface: $tunnel; public IPv4: $ip_now"
            ;;

        wireguard)
            ip link show wg0 >/dev/null 2>&1 || {
                echo "ERROR: wg0 interface not found."
                return 1
            }
            handshake="$(sudo wg show wg0 latest-handshakes | awk 'NR==1 {print $2}')"
            [[ "$handshake" =~ ^[0-9]+$ ]] && (( handshake > 0 )) || {
                echo "ERROR: No WireGuard handshake found."
                return 1
            }
            now="$(date +%s)"
            (( now - handshake <= 180 )) || {
                echo "ERROR: WireGuard handshake is older than 180 seconds."
                return 1
            }
            [[ "$ip_now" == "$EXPECTED_VPN_IP" ]] || {
                echo "ERROR: Public IP $ip_now does not match expected $EXPECTED_VPN_IP."
                return 1
            }
            echo "WireGuard verified; interface: wg0; public IPv4: $ip_now"
            ;;
    esac
}

open_pages() {
    local browser="$1"
    shift
    if [[ "$browser" == "firefox" ]]; then
        "$FIREFOX" --private-window "$@" >/dev/null 2>&1 &
    else
        "$CHROME" --incognito --new-window "$@" >/dev/null 2>&1 &
    fi
}

run_phase() {
    local phase="$1" browser="$2"
    shift 2
    echo
    echo "[$(date +%H:%M:%S)] $phase"
    echo "Browse these pages during this 5-minute phase; no personal accounts."
    open_pages "$browser" "$@"
    sleep 300
}

run_browsing_schedule() {
    run_phase "Phase 1/6: Firefox public text pages" firefox \
        https://example.com https://www.wikipedia.org https://www.python.org

    run_phase "Phase 2/6: Chrome public documentation" chrome \
        https://developer.mozilla.org https://docs.python.org/3/ https://www.iana.org

    run_phase "Phase 3/6: Firefox image-rich public pages" firefox \
        https://commons.wikimedia.org/wiki/Main_Page https://unsplash.com https://www.nasa.gov

    run_phase "Phase 4/6: Chrome technical documentation" chrome \
        https://developer.mozilla.org/en-US/docs/Web/HTTP https://www.wireshark.org/docs/ https://fedoraproject.org

    run_phase "Phase 5/6: Firefox public documents" firefox \
        https://www.rfc-editor.org/rfc/rfc9293.pdf https://www.rfc-editor.org/

    run_phase "Phase 6/6: Chrome navigation and public pages" chrome \
        https://www.gnu.org https://www.wikipedia.org https://www.iana.org/domains/reserved
}

run_session() {
    local number="$1" class="$2" tunnel="${3:-}"
    local session_id start_date start_time timezone vpn_software vpn_version protocol connected
    local wifi_file tunnel_file wifi_log tunnel_log
    local -a pids=()

    echo
    echo "======================================================"
    echo "SESSION $number: $class — 30 minutes"
    echo "======================================================"

    case "$class" in
        normal)
            echo "Ensure OpenVPN and WireGuard are both disconnected."
            vpn_software="None"; vpn_version="N/A"
            protocol="None"; connected="Disconnected"
            ;;
        openvpn)
            echo "In another terminal, connect with:"
            echo "sudo openvpn --config ~/Downloads/vpnbook-de20-secure.ovpn"
            echo "Wait for Initialization Sequence Completed."
            read -rp "Once connected, press Enter here to verify: "
            vpn_software="OpenVPN"; vpn_version="$(openvpn --version | head -n1)"
            protocol="OpenVPN-TCP"; connected="Connected"
            ;;
        wireguard)
            echo "Stop OpenVPN first. Then connect WireGuard:"
            echo "sudo wg-quick up wg0"
            echo "If it is already connected, do not run that command again."
            read -rp "Once WireGuard is connected, press Enter here to verify: "
            vpn_software="WireGuard"; vpn_version="$(wg --version | head -n1)"
            protocol="WireGuard"; connected="Connected"
            ;;
        *) echo "ERROR: Unknown session class."; return 1 ;;
    esac

    verify_class "$class" || {
        echo "Session refused. Fix the connection state before continuing."
        return 1
    }

    if [[ "$class" == "openvpn" ]]; then
        tunnel="$(ip -o link show | awk -F': ' '$2 ~ /^tun[0-9]+$/ {print $2; exit}')"
    elif [[ "$class" == "wireguard" ]]; then
        tunnel="wg0"
    else
        tunnel=""
    fi

    session_id="PILOT_${RUN_ID}_${number}_${class}"
    start_date="$(date +%F)"
    start_time="$(date +%T)"
    timezone="$(date +%Z)"

    wifi_file="$OUT/session_${number}_${class}_wifi.pcapng"
    wifi_log="$OUT/session_${number}_${class}_wifi_dumpcap.log"

    echo "Output directory: $OUT"
    echo "Wi-Fi capture: $wifi_file"
    [[ -n "$tunnel" ]] && echo "Tunnel capture: $OUT/session_${number}_${class}_${tunnel}.pcapng"
    echo
    read -rp "Ready to start the 30-minute capture? Press Enter to continue, Ctrl+C to cancel: "

    sudo dumpcap -q -i "$WIFI_IF" -a duration:"$DURATION" -w "$wifi_file" >"$wifi_log" 2>&1 &
    pids+=("$!")

    if [[ -n "$tunnel" ]]; then
        tunnel_file="$OUT/session_${number}_${class}_${tunnel}.pcapng"
        tunnel_log="$OUT/session_${number}_${class}_${tunnel}_dumpcap.log"
        sudo dumpcap -q -i "$tunnel" -a duration:"$DURATION" -w "$tunnel_file" >"$tunnel_log" 2>&1 &
        pids+=("$!")
    fi

    printf '"%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","%s","1","Needs_review","Pilot only; interface captures separate; per-flow labels not assigned"\n' \
        "$session_id" "$start_date" "$start_time" "$timezone" "$DURATION" "$class" \
        "$OS_NAME" "$OS_VERSION" "fedora-main" "$PY_VERSION" "$NF_VERSION" \
        "$NETWORK_TYPE" "$LOCATION_CODE" "$vpn_software" "$vpn_version" "$protocol" \
        "$connected" "dumpcap" "$DUMPCAP_VERSION" "$TASKSEQ" >> "$META"

    echo
    echo "Capture started. Follow the same 6-phase browsing schedule."
    echo "Actively browse the opened pages during each five-minute phase."
    run_browsing_schedule

    echo
    echo "Waiting for capture processes to finish..."
    local failed=0 pid
    for pid in "${pids[@]}"; do
        wait "$pid" || failed=1
    done

    echo
    echo "Capture logs for session $number:"
    cat "$wifi_log"
    if [[ -n "$tunnel" ]]; then
        cat "$tunnel_log"
    fi

    if (( failed )); then
        echo "WARNING: At least one capture process reported failure."
    else
        echo "Capture processes finished. Review packet/drop counts before accepting data."
    fi

    echo "Metadata status remains Needs_review until manual quality checks."
    echo "Session $number complete."
}

echo
echo "IMPORTANT: These are pilot captures, not a validated training dataset."
echo "The Wi-Fi interface sees outer tunnel traffic plus unrelated background traffic."
echo "Tunnel-interface flows are decapsulated traffic; do not label them as encrypted VPN flows."
echo "The script will ask you to prepare and verify each VPN state."
echo

run_session 01 normal
echo
read -rp "Prepare OpenVPN for session 02, then press Enter to continue: " _
run_session 02 openvpn
echo
echo "Stop OpenVPN with Ctrl+C in its terminal before proceeding."
read -rp "After OpenVPN is stopped, press Enter to prepare WireGuard: " _
run_session 03 wireguard

echo
echo "ALL THREE SESSIONS FINISHED."
echo "Output: $OUT"
echo "Metadata: $META"
echo "Do not use these pilot captures for model training until reviewed."
echo "When finished, disconnect WireGuard with: sudo wg-quick down wg0"
