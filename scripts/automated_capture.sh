#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAN="${1:-$ROOT/configs/capture_plan_21.csv}"
DURATION="${DURATION:-1800}"
EXPECTED_VPN_IP="${EXPECTED_VPN_IP:-51.75.145.20}"
VPN_ENDPOINT_IP="${VPN_ENDPOINT_IP:-51.75.145.20}"
OUT_BASE="${OUT_BASE:-$ROOT/data/raw/captures}"
WORKLOAD="$ROOT/scripts/browser_workload.py"
PYTHON="${PYTHON:-python3}"

[[ -f "$PLAN" ]] || { echo "ERROR: plan CSV not found: $PLAN"; exit 1; }
[[ -f "$WORKLOAD" ]] || { echo "ERROR: missing $WORKLOAD"; exit 1; }
command -v dumpcap >/dev/null || { echo "Install Wireshark/dumpcap (dumpcap missing)."; exit 1; }
command -v ip >/dev/null || { echo "Missing ip command."; exit 1; }
command -v curl >/dev/null || { echo "Missing curl."; exit 1; }
"$PYTHON" -c 'import playwright' >/dev/null 2>&1 || {
  echo "Playwright missing for $PYTHON. Run: $PYTHON -m pip install -r requirements_capture.txt"
  echo "Then: $PYTHON -m playwright install chromium"; exit 1;
}
sudo -v
RUN_ID="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$OUT_BASE/run_$RUN_ID"
mkdir -p "$OUT_DIR"
META="$OUT_DIR/session_metadata.csv"
printf 'session_id,network_label,traffic_class,started_at,ended_at,duration_seconds,physical_interface,tunnel_interface,public_ip,expected_vpn_ip,capture_file,tunnel_capture_file,workload_log,review_status\n' > "$META"
active_pids=()
cleanup() { for pid in "${active_pids[@]:-}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup INT TERM EXIT

get_ip() { curl --fail --silent --max-time 12 https://api.ipify.org 2>/dev/null || true; }
get_default_iface() { ip -o route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}'; }
get_physical_iface() {
  local cls="$1" route_target="1.1.1.1"
  # With VPN active, route to the VPN server to identify the underlying physical interface.
  [[ "$cls" == normal ]] || route_target="$VPN_ENDPOINT_IP"
  if [[ "$cls" == wireguard ]]; then
    ip -4 route get "$route_target" mark 51820 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}'
  else
    ip -o route get "$route_target" 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}'
  fi
}
get_tunnel() {
  case "$1" in
    openvpn) ip -o link show | awk -F': ' '$2 ~ /^tun[0-9]*(@.*)?$/ {sub(/@.*/, "", $2); print $2; exit}' ;;
    wireguard) if ip link show wg0 >/dev/null 2>&1; then echo wg0; else ip -o link show | awk -F': ' '$2 ~ /^wg[0-9]*(@.*)?$/ {sub(/@.*/, "", $2); print $2; exit}'; fi ;;
    *) echo "" ;;
  esac
}
verify_class() {
  local cls="$1" tun="$2" ipnow="$3"
  case "$cls" in
    normal)
      if pgrep -x openvpn >/dev/null 2>&1 || ip -o link show | grep -Eq ': (tun[0-9]*|wg[0-9]*)(@[^:]+)?:'; then
        echo "ERROR: VPN process/interface detected during Normal session."; return 1
      fi ;;
    openvpn)
      pgrep -x openvpn >/dev/null 2>&1 || { echo "ERROR: OpenVPN process not detected."; return 1; }
      [[ -n "$tun" ]] || { echo "ERROR: tun interface not detected."; return 1; } ;;
    wireguard)
      [[ -n "$tun" ]] || { echo "ERROR: WireGuard interface not detected."; return 1; }
      command -v wg >/dev/null && sudo wg show "$tun" >/dev/null 2>&1 || { echo "ERROR: wg cannot verify interface."; return 1; } ;;
    *) echo "ERROR: invalid class $cls"; return 1 ;;
  esac
  if [[ "$cls" != normal && -n "$EXPECTED_VPN_IP" && "$ipnow" != "$EXPECTED_VPN_IP" ]]; then
    echo "WARNING: current public IP '$ipnow' differs from expected '$EXPECTED_VPN_IP'."
    read -r -p "If you verified this VPN egress IP, type CONTINUE: " answer
    [[ "$answer" == CONTINUE ]] || return 1
  fi
}
run_session() {
  local sid="$1" network="$2" cls="$3" physical tun ipnow started ended cap tunnelcap log
  echo
  echo "=== $sid | $network | $cls | ${DURATION}s ==="
  read -r -p "Manually connect network '$network' and set VPN to '$cls'. Press ENTER when ready: " _ </dev/tty
  physical="$(get_physical_iface "$cls")"
  [[ -n "$physical" ]] || { echo "ERROR: cannot detect default interface"; return 1; }
  tun="$(get_tunnel "$cls" || true)"
  ipnow="$(get_ip)"
  echo "Underlying physical interface: $physical | tunnel: ${tun:-none} | public IPv4: ${ipnow:-unknown}"
  verify_class "$cls" "$tun" "$ipnow" || { echo "Session not started. Fix state, then rerun."; return 1; }
  cap="$OUT_DIR/${sid}_${network//[^a-zA-Z0-9_-]/_}_${cls}_physical_${physical}.pcapng"
  tunnelcap=""
  [[ -z "$tun" ]] || tunnelcap="$OUT_DIR/${sid}_${network//[^a-zA-Z0-9_-]/_}_${cls}_tunnel_${tun}.pcapng"
  cap_tmp="/tmp/${RUN_ID}_${sid}_physical.pcapng"
  tunnel_tmp=""
  [[ -z "$tun" ]] || tunnel_tmp="/tmp/${RUN_ID}_${sid}_tunnel.pcapng"
  log="$OUT_DIR/${sid}_${network//[^a-zA-Z0-9_-]/_}_${cls}_workload.log"
  started="$(date --iso-8601=seconds)"
  sudo dumpcap -q -i "$physical" -a duration:"$DURATION" -w "$cap_tmp" >"$OUT_DIR/${sid}_physical_dumpcap.log" 2>&1 &
  local physical_pid=$!
  active_pids+=("$physical_pid")
  if [[ -n "$tunnelcap" ]]; then
    sudo dumpcap -q -i "$tun" -a duration:"$DURATION" -w "$tunnel_tmp" >"$OUT_DIR/${sid}_tunnel_dumpcap.log" 2>&1 &
    local tunnel_pid=$!
    active_pids+=("$tunnel_pid")
  fi
  sleep 3
  "$PYTHON" "$WORKLOAD" --duration "$DURATION" >"$log" 2>&1 &
  local workload_pid=$!
  active_pids+=("$workload_pid")
  wait "$workload_pid" || echo "WARNING: workload error; inspect $log"
  wait "$physical_pid" || echo "WARNING: physical capture exited unexpectedly"
  if [[ -n "$tunnelcap" ]]; then wait "$tunnel_pid" || echo "WARNING: tunnel capture exited unexpectedly"; fi

  if [[ -s "$cap_tmp" ]]; then
    sudo install -o "$(id -un)" -g "$(id -gn)" -m 0644 "$cap_tmp" "$cap"
    sudo rm -f "$cap_tmp"
  else
    echo "ERROR: physical capture file missing or empty: $cap_tmp"
    return 1
  fi

  if [[ -n "$tunnelcap" ]]; then
    if [[ -s "$tunnel_tmp" ]]; then
      sudo install -o "$(id -un)" -g "$(id -gn)" -m 0644 "$tunnel_tmp" "$tunnelcap"
      sudo rm -f "$tunnel_tmp"
    else
      echo "ERROR: tunnel capture file missing or empty: $tunnel_tmp"
      return 1
    fi
  fi
  active_pids=()
  ended="$(date --iso-8601=seconds)"
  printf '"%s","%s","%s","%s","%s",%s,"%s","%s","%s","%s","%s","%s","%s",Needs_review\n' \
    "$sid" "$network" "$cls" "$started" "$ended" "$DURATION" "$physical" "$tun" "$ipnow" "$EXPECTED_VPN_IP" "$cap" "$tunnelcap" "$log" >> "$META"
  echo "Saved session $sid. Metadata is Needs_review until validated."
}
while IFS=, read -r sid network cls extra; do
  [[ -z "${sid//[[:space:]]/}" || "$sid" == session_id || "$sid" == \#* ]] && continue
  sid="${sid%$'\r'}"; network="${network%$'\r'}"; cls="${cls%$'\r'}"
  case "$cls" in normal|openvpn|wireguard) ;; *) echo "Invalid class '$cls' in plan"; exit 1 ;; esac
  run_session "$sid" "$network" "$cls"
done < "$PLAN"
echo "All plan sessions completed. Output: $OUT_DIR"
echo "Metadata: $META"
