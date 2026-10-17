import csv
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path("data/raw/extracted/2022_json/encrypted_vpn_dataset")
OUTPUT = Path("data/processed/2022/2022_three_class_flows.parquet")
TEMP = OUTPUT.with_suffix(".tmp")
SUMMARY = Path("results/2022_conversion_summary.csv")

CHUNK_SIZE = 1024 * 1024
BATCH_SIZE = 2000
END_ARRAY = object()

SCHEMA = pa.schema([
    ("label", pa.string()),
    ("packet_record_count", pa.int64()),
    ("forward_bytes", pa.int64()),
    ("backward_bytes", pa.int64()),
    ("signed_bytes_sum", pa.int64()),
    ("total_bytes", pa.int64()),
    ("packet_size_mean", pa.float64()),
    ("packet_size_std", pa.float64()),
    ("packet_size_min", pa.int64()),
    ("packet_size_max", pa.int64()),
    ("duration_s", pa.float64()),
    ("iat_mean_s", pa.float64()),
    ("iat_std_s", pa.float64()),
    ("iat_max_s", pa.float64()),
])


def stream_json_array(handle):
    """Stream a top-level JSON array without loading the whole file."""
    decoder = json.JSONDecoder()

    if handle.read(1) != "[":
        raise ValueError("Expected a top-level JSON array")

    buffer = ""
    eof = False

    while True:
        buffer = buffer.lstrip()

        if not buffer:
            if eof:
                raise ValueError("Unexpected end of JSON")
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                eof = True
            else:
                buffer = chunk
            continue

        if buffer.startswith(","):
            buffer = buffer[1:]
            continue

        if buffer.startswith("]"):
            yield END_ARRAY
            return

        try:
            obj, end = decoder.raw_decode(buffer)
        except json.JSONDecodeError:
            if eof:
                raise ValueError("Invalid or incomplete JSON")
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                eof = True
            else:
                buffer += chunk
            continue

        buffer = buffer[end:]
        yield obj


def to_int(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (ValueError, TypeError, OverflowError):
        return None


def to_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def make_flow_features(flow, label):
    packets = flow.get("x_packets")
    if not isinstance(packets, list):
        return None, 1, 0

    sizes = []
    starts = []
    ends = []
    forward_bytes = 0
    backward_bytes = 0
    signed_sum = 0
    invalid_bytes = 0

    for packet in packets:
        if not isinstance(packet, dict):
            invalid_bytes += 1
            continue

        value = to_int(packet.get("bytes"))

        if value is None:
            invalid_bytes += 1
        else:
            size = abs(value)
            sizes.append(size)
            signed_sum += value

            if value > 0:
                forward_bytes += value
            elif value < 0:
                backward_bytes += size

        start = to_timestamp(packet.get("timestamp_start"))
        end = to_timestamp(packet.get("timestamp_end"))

        if start is not None:
            starts.append(start)
        if end is not None:
            ends.append(end)

    size_count = len(sizes)
    total_bytes = sum(sizes)
    size_mean = total_bytes / size_count if size_count else None

    size_std = (
        math.sqrt(max(
            0.0,
            sum(x * x for x in sizes) / size_count - size_mean**2
        ))
        if size_count else None
    )

    duration = None
    if starts and ends:
        candidate = max(ends) - min(starts)
        if candidate >= 0:
            duration = candidate

    ordered_starts = sorted(starts)
    intervals = [
        current - previous
        for previous, current in zip(
            ordered_starts, ordered_starts[1:]
        )
        if current >= previous
    ]

    iat_mean = (
        sum(intervals) / len(intervals) if intervals else None
    )
    iat_std = (
        math.sqrt(sum(
            (value - iat_mean) ** 2 for value in intervals
        ) / len(intervals))
        if intervals else None
    )

    row = {
        "label": label,
        "packet_record_count": len(packets),
        "forward_bytes": forward_bytes,
        "backward_bytes": backward_bytes,
        "signed_bytes_sum": signed_sum,
        "total_bytes": total_bytes,
        "packet_size_mean": size_mean,
        "packet_size_std": size_std,
        "packet_size_min": min(sizes) if sizes else None,
        "packet_size_max": max(sizes) if sizes else None,
        "duration_s": duration,
        "iat_mean_s": iat_mean,
        "iat_std_s": iat_std,
        "iat_max_s": max(intervals) if intervals else None,
    }

    return row, 0, invalid_bytes


def main():
    if not ROOT.is_dir():
        raise SystemExit(f"Dataset directory not found: {ROOT}")

    if OUTPUT.exists():
        raise SystemExit(
            f"Output already exists: {OUTPUT}\n"
            "Inspect it first; this script will not overwrite it."
        )

    selected = []
    for path in sorted(ROOT.rglob("*.json")):
        relative = path.relative_to(ROOT)

        if ".ipynb_checkpoints" in relative.parts:
            continue

        parts = relative.parts

        if parts[0] == "Non VPN":
            selected.append((path, "Normal"))
        elif len(parts) >= 3 and parts[0] == "VPN":
            if parts[1] in ("OpenVPN", "WireGuard"):
                selected.append((path, parts[1]))

    if not selected:
        raise SystemExit("No selected class files found")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    TEMP.unlink(missing_ok=True)

    class_counts = Counter()
    invalid_flows = Counter()
    invalid_bytes = Counter()
    batch = []
    total_rows = 0
    started = time.time()

    print(f"Selected files: {len(selected)}")
    print(f"Output: {OUTPUT}")
    print("Starting streaming conversion...")

    writer = pq.ParquetWriter(TEMP, SCHEMA, compression="zstd")

    try:
        for index, (path, label) in enumerate(selected, start=1):
            file_rows = 0
            print(
                f"\n[{index}/{len(selected)}] {label}: {path.name}",
                flush=True,
            )

            with path.open("r", encoding="utf-8") as handle:
                for flow in stream_json_array(handle):
                    if flow is END_ARRAY:
                        break

                    if not isinstance(flow, dict):
                        invalid_flows[label] += 1
                        continue

                    row, bad_flow, bad_bytes = make_flow_features(
                        flow, label
                    )
                    invalid_flows[label] += bad_flow
                    invalid_bytes[label] += bad_bytes

                    if row is None:
                        continue

                    batch.append(row)
                    class_counts[label] += 1
                    file_rows += 1
                    total_rows += 1

                    if len(batch) >= BATCH_SIZE:
                        writer.write_table(
                            pa.Table.from_pylist(batch, schema=SCHEMA)
                        )
                        batch.clear()

                    if file_rows % 10000 == 0:
                        print(
                            f"    {file_rows:,} flows processed",
                            flush=True,
                        )

            print(f"    File complete: {file_rows:,} flows", flush=True)

        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=SCHEMA))
            batch.clear()

    except Exception:
        writer.close()
        raise
    else:
        writer.close()

    if total_rows == 0:
        TEMP.unlink(missing_ok=True)
        raise SystemExit("No valid flows produced")

    TEMP.replace(OUTPUT)

    with SUMMARY.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "label", "flow_rows", "invalid_flow_records",
            "invalid_byte_records", "selected_files",
        ]
        report = csv.DictWriter(handle, fieldnames=fields)
        report.writeheader()

        for label in ("Normal", "OpenVPN", "WireGuard"):
            report.writerow({
                "label": label,
                "flow_rows": class_counts[label],
                "invalid_flow_records": invalid_flows[label],
                "invalid_byte_records": invalid_bytes[label],
                "selected_files": sum(
                    1 for _, class_name in selected
                    if class_name == label
                ),
            })

    print("\nCONVERSION COMPLETE")
    print(f"Rows: {total_rows:,}")
    print(f"Class counts: {dict(class_counts)}")
    print(f"Parquet size: {OUTPUT.stat().st_size / (1024**2):.2f} MiB")
    print(f"Summary: {SUMMARY}")
    print(f"Elapsed: {time.time() - started:.1f} seconds")


if __name__ == "__main__":
    main()
