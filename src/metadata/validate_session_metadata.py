import csv
import sys
from datetime import date, time
from pathlib import Path

EXPECTED_COLUMNS = [
    "session_id", "capture_date", "capture_start_time",
    "capture_timezone", "capture_duration_seconds", "class_label",
    "operating_system", "os_version", "device_id", "python_version",
    "nfstream_version", "network_type", "capture_location_code",
    "vpn_software", "vpn_software_version", "vpn_protocol",
    "vpn_connected_status", "capture_tool", "capture_tool_version",
    "task_sequence_id", "repeat_number", "session_status", "notes",
]

REQUIRED_COLUMNS = [c for c in EXPECTED_COLUMNS if c != "notes"]

VALID_LABELS = {"Normal", "OpenVPN", "WireGuard"}
VALID_OS = {"Fedora", "Windows 11"}
VALID_NETWORKS = {"Home", "University", "Other"}
VALID_STATUSES = {"Valid", "Failed", "Needs_review"}
VALID_VPN_STATES = {
    "Connected", "Disconnected", "Not_applicable", "Unverified"
}


def validate(path: Path) -> bool:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            if reader.fieldnames != EXPECTED_COLUMNS:
                print("FAIL: CSV columns do not match the expected schema.")
                print(f"Expected: {EXPECTED_COLUMNS}")
                print(f"Found:    {reader.fieldnames}")
                return False

            rows = list(reader)
    except (OSError, csv.Error) as error:
        print(f"FAIL: Could not read metadata CSV: {error}")
        return False

    if not rows:
        print("PASS: Metadata CSV schema is valid.")
        print("INFO: No session records yet; record-level checks skipped.")
        return True

    errors = []
    seen_ids = set()

    for line_number, row in enumerate(rows, start=2):
        get = lambda key: (row.get(key) or "").strip()

        for column in REQUIRED_COLUMNS:
            if not get(column):
                errors.append(f"Row {line_number}: missing {column}")

        session_id = get("session_id")
        if session_id:
            if session_id in seen_ids:
                errors.append(
                    f"Row {line_number}: duplicate session_id {session_id!r}"
                )
            seen_ids.add(session_id)

        label = get("class_label")
        if label and label not in VALID_LABELS:
            errors.append(f"Row {line_number}: invalid class_label {label!r}")

        os_name = get("operating_system")
        if os_name and os_name not in VALID_OS:
            errors.append(f"Row {line_number}: invalid operating_system {os_name!r}")

        network = get("network_type")
        if network and network not in VALID_NETWORKS:
            errors.append(f"Row {line_number}: invalid network_type {network!r}")

        status = get("session_status")
        if status and status not in VALID_STATUSES:
            errors.append(f"Row {line_number}: invalid session_status {status!r}")

        vpn_state = get("vpn_connected_status")
        if vpn_state and vpn_state not in VALID_VPN_STATES:
            errors.append(
                f"Row {line_number}: invalid vpn_connected_status {vpn_state!r}"
            )

        try:
            date.fromisoformat(get("capture_date"))
        except ValueError:
            errors.append(f"Row {line_number}: capture_date must be YYYY-MM-DD")

        try:
            time.fromisoformat(get("capture_start_time"))
        except ValueError:
            errors.append(f"Row {line_number}: invalid capture_start_time")

        try:
            duration = float(get("capture_duration_seconds"))
            if duration <= 0:
                errors.append(
                    f"Row {line_number}: duration must be greater than zero"
                )
        except ValueError:
            errors.append(
                f"Row {line_number}: invalid capture_duration_seconds"
            )

        try:
            repeat = int(get("repeat_number"))
            if repeat < 1:
                errors.append(f"Row {line_number}: repeat_number must be at least 1")
        except ValueError:
            errors.append(f"Row {line_number}: repeat_number must be an integer")

        if status == "Valid":
            if label in {"OpenVPN", "WireGuard"} and vpn_state != "Connected":
                errors.append(
                    f"Row {line_number}: a Valid {label} session must have "
                    "vpn_connected_status=Connected"
                )
            elif label == "Normal" and vpn_state not in {
                "Disconnected", "Not_applicable"
            }:
                errors.append(
                    f"Row {line_number}: a Valid Normal session must have "
                    "vpn_connected_status=Disconnected or Not_applicable"
                )

    if errors:
        print(f"FAIL: Found {len(errors)} metadata issue(s):")
        for error in errors:
            print(f"- {error}")
        return False

    print(f"PASS: Validated {len(rows)} session record(s).")
    print("PASS: Schema, required fields, labels, OS, network and status checked.")
    print("PASS: Dates, times, durations, repeat numbers and unique IDs checked.")
    print("PASS: VPN connection status checked for Valid sessions.")
    return True


if __name__ == "__main__":
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "configs/session_metadata_template.csv"
    )

    if not csv_path.is_file():
        print(f"FAIL: File not found: {csv_path}")
        sys.exit(1)

    sys.exit(0 if validate(csv_path) else 1)
