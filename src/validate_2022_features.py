from pathlib import Path

import numpy as np
import pandas as pd

PARQUET = Path("data/processed/2022/2022_three_class_flows.parquet")
MANIFEST = Path("results/2022_source_provenance.csv")
OUT = Path("results")

def main():
    OUT.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(PARQUET)
    manifest = pd.read_csv(MANIFEST)

    if len(df) != len(manifest):
        raise ValueError("Parquet and provenance row counts differ")

    if not np.array_equal(
        df["label"].astype(str).to_numpy(),
        manifest["label"].astype(str).to_numpy(),
    ):
        raise ValueError("Parquet labels do not match provenance")

    features = [c for c in df.columns if c != "label"]
    numeric = df[features].select_dtypes(include="number").columns.tolist()

    missing = df[features].isna().sum().rename("missing_count").to_frame()
    missing["missing_percent"] = (
        missing["missing_count"] / len(df) * 100
    )
    missing.to_csv(OUT / "2022_missingness.csv")

    infinite_counts = pd.Series({
        c: int(np.isinf(df[c].dropna()).sum())
        for c in numeric
    }, name="infinite_count")
    infinite_counts.to_csv(OUT / "2022_infinite_values.csv")

    class_counts = df["label"].value_counts().rename_axis("label").reset_index(
        name="flow_count"
    )
    class_counts["percentage"] = class_counts["flow_count"] / len(df) * 100
    class_counts.to_csv(OUT / "2022_class_balance.csv", index=False)

    class_feature = df.groupby("label")[numeric].agg(
        ["count", "mean", "std", "min", "median", "max"]
    )
    class_feature.to_csv(OUT / "2022_feature_summary_by_class.csv")

    # Exact duplicate rows, including the target label.
    duplicate_rows = int(df.duplicated().sum())
    duplicate_by_class = (
        df.assign(is_duplicate=df.duplicated())
        .groupby("label")["is_duplicate"]
        .sum()
    )

    # Same feature pattern associated with more than one label.
    pattern_label_counts = (
        df.groupby(features, dropna=False)["label"]
        .nunique()
        .rename("distinct_labels")
        .reset_index()
    )
    conflicting = pattern_label_counts[
        pattern_label_counts["distinct_labels"] > 1
    ]
    conflicting.to_csv(
        OUT / "2022_cross_label_patterns.csv", index=False
    )

    # Verify mathematical relationships already observed.
    checks = {
        "total_bytes_equals_forward_plus_backward": bool(
            np.allclose(
                df["total_bytes"],
                df["forward_bytes"] + df["backward_bytes"],
                equal_nan=True,
            )
        ),
        "signed_sum_equals_forward_minus_backward": bool(
            np.allclose(
                df["signed_bytes_sum"],
                df["forward_bytes"] - df["backward_bytes"],
                equal_nan=True,
            )
        ),
        "mean_equals_total_over_record_count": bool(
            np.allclose(
                df["packet_size_mean"],
                df["total_bytes"] / df["packet_record_count"].replace(0, np.nan),
                equal_nan=True,
            )
        ),
    }

    summary = [
        ("row_count", len(df)),
        ("feature_count_excluding_label", len(features)),
        ("exact_duplicate_rows_including_label", duplicate_rows),
        ("distinct_feature_patterns_with_multiple_labels", len(conflicting)),
        ("rows_in_cross_label_patterns", int(
            df.merge(
                conflicting[features],
                on=features,
                how="inner",
            ).shape[0]
        )),
        ("missing_cells_in_features", int(df[features].isna().sum().sum())),
        ("infinite_numeric_values", int(infinite_counts.sum())),
        ("source_files_in_manifest", int(manifest["source_file"].nunique())),
        ("application_groups_in_manifest", int(
            manifest["application_group"].nunique()
        )),
        *[(name, value) for name, value in checks.items()],
    ]

    pd.DataFrame(summary, columns=["check", "result"]).to_csv(
        OUT / "2022_feature_validation_summary.csv", index=False
    )

    print("FEATURE VALIDATION COMPLETE")
    print(f"Rows: {len(df):,}")
    print(f"Features excluding label: {len(features)}")
    print(f"Missing feature cells: {int(df[features].isna().sum().sum()):,}")
    print(f"Exact duplicate rows including label: {duplicate_rows:,}")
    print(f"Cross-label feature patterns: {len(conflicting)}")
    print("\nMathematical relationship checks:")
    for name, value in checks.items():
        print(f"  {name}: {value}")

    print("\nSaved reports:")
    for name in [
        "2022_missingness.csv",
        "2022_infinite_values.csv",
        "2022_class_balance.csv",
        "2022_feature_summary_by_class.csv",
        "2022_cross_label_patterns.csv",
        "2022_feature_validation_summary.csv",
    ]:
        print(f"  results/{name}")

if __name__ == "__main__":
    main()
