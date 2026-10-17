import csv
import sys
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from convert_2022_flows_clean import ROOT, END_ARRAY, stream_json_array

PARQUET = Path("data/processed/2022/2022_three_class_flows.parquet")
OUTPUT = Path("results/2022_source_provenance.csv")


def selected_files():
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

    return selected


def main():
    if not PARQUET.is_file():
        sys.exit(f"Parquet not found: {PARQUET}")

    if not ROOT.is_dir():
        sys.exit(f"Raw dataset not found: {ROOT}")

    table = pq.read_table(PARQUET, columns=["label"])
    parquet_labels = table.column("label").to_pylist()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    row_index = 0
    counts = Counter()
    file_counts = Counter()

    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "row_index",
            "label",
            "source_file",
            "application_group",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()

        for path, label in selected_files():
            relative = path.relative_to(ROOT).as_posix()
            application = path.stem

            with path.open("r", encoding="utf-8") as source:
                for flow in stream_json_array(source):
                    if flow is END_ARRAY:
                        break

                    # Match the current converter's row inclusion rules.
                    if not isinstance(flow, dict):
                        continue
                    if not isinstance(flow.get("x_packets"), list):
                        continue

                    if row_index >= len(parquet_labels):
                        sys.exit(
                            "Mismatch: raw source produces more rows "
                            "than the current Parquet."
                        )

                    if parquet_labels[row_index] != label:
                        sys.exit(
                            f"Label/order mismatch at row {row_index}: "
                            f"manifest={label}, "
                            f"Parquet={parquet_labels[row_index]}"
                        )

                    writer.writerow({
                        "row_index": row_index,
                        "label": label,
                        "source_file": relative,
                        "application_group": application,
                    })

                    row_index += 1
                    counts[label] += 1
                    file_counts[relative] += 1

    if row_index != len(parquet_labels):
        OUTPUT.unlink(missing_ok=True)
        sys.exit(
            f"Row-count mismatch: manifest={row_index}, "
            f"Parquet={len(parquet_labels)}. Manifest removed."
        )

    print("PROVENANCE VALIDATION PASSED")
    print(f"Parquet rows: {len(parquet_labels):,}")
    print(f"Manifest rows: {row_index:,}")
    print(f"Class counts: {dict(counts)}")
    print(f"Source files: {len(file_counts)}")
    print(f"Saved: {OUTPUT}")
    print("\nRows by source file:")
    for filename, count in sorted(file_counts.items()):
        print(f"  {filename}: {count:,}")


if __name__ == "__main__":
    main()
