import csv
import sys
from pathlib import Path

import yaml

CONFIG_PATH = Path("configs/collection.yaml")
TEMPLATE_PATH = Path("configs/session_metadata_template.csv")


def main():
    try:
        config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

        with TEMPLATE_PATH.open(
            "r", newline="", encoding="utf-8-sig"
        ) as file:
            header = next(csv.reader(file), [])

    except (OSError, yaml.YAMLError, csv.Error) as error:
        print(f"FAIL: Could not read configuration or template: {error}")
        return 1

    errors = []

    required = config.get("metadata_required", [])
    missing = sorted(set(required) - set(header))
    if missing:
        errors.append(f"Metadata fields missing from CSV template: {missing}")

    classes = set(config.get("valid_values", {}).get("class_label", []))
    target_classes = set(config.get("collection", {}).get("target_classes", []))
    if classes != target_classes:
        errors.append("Class labels differ between collection and valid_values.")

    features = config.get("model_features", {}).get(
        "initial_candidate_features", []
    )
    excluded = set(
        config.get("privacy", {}).get("exclude_from_model_features", [])
    )

    forbidden = sorted(set(features) & excluded)
    if forbidden:
        errors.append(f"Candidate features are also excluded: {forbidden}")

    if len(features) != len(set(features)):
        errors.append("Candidate feature list contains duplicates.")

    if config.get("model_features", {}).get("target_is_not_a_feature") is not True:
        errors.append("Target must be explicitly excluded from model inputs.")

    if "label" in features:
        errors.append("'label' must not appear in candidate model features.")

    if errors:
        print(f"FAIL: Found {len(errors)} configuration issue(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PASS: Collection configuration and metadata template are consistent.")
    print(f"PASS: {len(required)} required metadata fields are represented.")
    print(f"PASS: {len(target_classes)} target classes match.")
    print(f"PASS: {len(features)} candidate features checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
