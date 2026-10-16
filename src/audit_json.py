import csv
import json
import time
from pathlib import Path
from collections import Counter
from datetime import datetime

ROOT = Path("data/raw/extracted/2022_json/encrypted_vpn_dataset")
OUTPUT = Path("results/2022_json_audit.csv")
CHUNK_SIZE = 1024 * 1024


def stream_json_array(file_handle):
    """Read a top-level JSON array one object at a time."""
    decoder = json.JSONDecoder()

    if file_handle.read(1) != "[":
        raise ValueError("Expected a JSON array starting with '['")

    buffer = ""
    eof = False

    while True:
        buffer = buffer.lstrip()

        if buffer.startswith(","):
            buffer = buffer[1:].lstrip()

        if buffer.startswith("]"):
            yield None
            return

        while True:
            try:
                obj, end = decoder.raw_decode(buffer)
                buffer = buffer[end:]
                yield obj
                break
            except json.JSONDecodeError:
                if eof:
                    raise ValueError("Invalid or incomplete JSON")
                chunk = file_handle.read(CHUNK_SIZE)
                if not chunk:
                    eof = True
                buffer += chunk
                buffer = buffer.lstrip()


def audit_file(path, index, total):
    started = time.time()
    flows = packets_total = 0
    positive = negative = zero = bad_bytes = 0
    bad_timestamps = missing_packets = non_dict_flows = 0
    flow_keys = Counter()
    packet_keys = Counter()

    print(f"\n[{index}/{total}] START {path.name}", flush=True)

    try:
        with path.open("r", encoding="utf-8") as f:
            for obj in stream_json_array(f):
                if obj is None:
                    break

                flows += 1

                if not isinstance(obj, dict):
                    non_dict_flows += 1
                    continue

                flow_keys.update(obj.keys())
                packet_list = obj.get("x_packets")

                if not isinstance(packet_list, list):
                    missing_packets += 1
                    continue

                packets_total += len(packet_list)

                for packet in packet_list:
                    if not isinstance(packet, dict):
                        bad_bytes += 1
                        continue

                    packet_keys.update(packet.keys())

                    try:
                        value = int(packet["bytes"])
                        if value > 0:
                            positive += 1
                        elif value < 0:
                            negative += 1
                        else:
                            zero += 1
                    except (KeyError, TypeError, ValueError):
                        bad_bytes += 1

                    for field in ("timestamp_start", "timestamp_end"):
                        try:
                            datetime.fromisoformat(packet[field])
                        except (KeyError, TypeError, ValueError):
                            bad_timestamps += 1

                if flows % 10000 == 0:
                    elapsed = time.time() - started
                    print(
                        f"    {flows:,} flows | "
                        f"{packets_total:,} packets | {elapsed:.1f}s",
                        flush=True,
                    )

        status = "OK"

    except Exception as exc:
        status = f"ERROR: {type(exc).__name__}: {exc}"
        print(f"    {status}", flush=True)

    elapsed = round(time.time() - started, 2)
    size_bytes = path.stat().st_size

    row = {
        "relative_path": str(path.relative_to(ROOT)),
        "size_bytes": size_bytes,
        "flows": flows,
        "packet_records": packets_total,
        "positive_bytes": positive,
        "negative_bytes": negative,
        "zero_bytes": zero,
        "missing_or_invalid_bytes": bad_bytes,
        "invalid_timestamp_fields": bad_timestamps,
        "flows_without_packet_list": missing_packets,
        "non_dict_flows": non_dict_flows,
        "flow_fields": ";".join(sorted(flow_keys)),
        "packet_fields": ";".join(sorted(packet_keys)),
        "elapsed_seconds": elapsed,
        "status": status,
    }

    print(
        f"[{index}/{total}] DONE | flows={flows:,} | "
        f"packets={packets_total:,} | status={status} | {elapsed}s",
        flush=True,
    )
    return row


def main():
    if not ROOT.is_dir():
        raise SystemExit(f"Dataset directory not found: {ROOT}")

    files = sorted(
        p for p in ROOT.rglob("*.json")
        if ".ipynb_checkpoints" not in p.parts
    )

    if not files:
        raise SystemExit(f"No JSON files found under {ROOT}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "relative_path", "size_bytes", "flows", "packet_records",
        "positive_bytes", "negative_bytes", "zero_bytes",
        "missing_or_invalid_bytes", "invalid_timestamp_fields",
        "flows_without_packet_list", "non_dict_flows",
        "flow_fields", "packet_fields", "elapsed_seconds", "status",
    ]

    print(f"Dataset root: {ROOT}")
    print(f"JSON files to audit: {len(files)}")
    print(f"Report: {OUTPUT}")
    print("Starting full audit; original data will not be changed.", flush=True)

    overall_start = time.time()

    with OUTPUT.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()

        for index, path in enumerate(files, 1):
            row = audit_file(path, index, len(files))
            writer.writerow(row)
            out.flush()

    print("\nFULL AUDIT FINISHED")
    print(f"Files processed: {len(files)}")
    print(f"Report saved: {OUTPUT}")
    print(f"Total elapsed: {time.time() - overall_start:.1f}s")


if __name__ == "__main__":
    main()
