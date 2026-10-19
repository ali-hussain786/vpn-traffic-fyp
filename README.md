# Explainable ML-Based Classification of Modern Encrypted VPN Traffic

**Final Year Project (BSIT)**
**Research focus:** Flow-level classification of Normal, OpenVPN, and WireGuard traffic without inspecting encrypted payload contents.

## 1. Project Overview

This project investigates whether machine-learning models can distinguish ordinary network traffic from traffic carried through OpenVPN and WireGuard using flow-level network metadata. It also aims to evaluate how well models generalize across datasets collected in different years and environments.

The research uses a staged workflow: dataset auditing, schema and feature validation, controlled traffic collection, baseline model training, evaluation, and explainability. Results must be reported only after the corresponding experiment has actually run.

## 2. Research Objectives

- Classify traffic into **Normal**, **OpenVPN**, and **WireGuard**.
- Use flow-level metadata rather than encrypted application payload contents.
- Audit dataset structure, labels, missing values, duplicates, and provenance.
- Validate candidate features and document compatibility limitations.
- Compare Logistic Regression, Decision Tree, Random Forest, and XGBoost baselines.
- Evaluate accuracy, precision, recall, macro-F1, and confusion matrices.
- Investigate within-dataset, cross-dataset, and temporal generalization.
- Use suitable explainability methods, such as SHAP, after a validated model is available.
- Maintain reproducible records of data sources, transformations, experiments, and limitations.

## 3. Current Research Status

**Completed or present in the repository**
- Initial Python/project environment and project structure.
- Streaming audit pipeline for the USBVPN 2022 JSON flow data.
- Conversion and validation pipeline for the selected 2022 flow records.
- Notebooks for environment checking, dataset auditing, and 2022 feature validation.
- CSV audit/validation outputs under `results/`.
- Cross-platform collection configuration and a 21-session capture plan.
- Automated capture and repeatable browser-workload scripts.
- NFStream compatibility notes.

**Still in progress**
- The 21-session self-capture plan is not complete. The latest recorded status had three Telenor sessions captured: Normal, OpenVPN, and WireGuard. Their metadata status was `Needs_review`; they must be reviewed before being treated as training data.
- Dataset schema inventory and exact per-dataset field mapping should be regenerated from the actual files.
- Model training, final metrics, cross-dataset evaluation, SHAP analysis, and any final presentation/UI are not claimed as complete by this README.
- GitHub/Colab/Drive synchronization must be checked independently; local terminal work does not automatically mean that remote copies are updated.

Update this section whenever a new experiment or capture session is verified. Do not report planned work as completed work.

## 4. Dataset Inventory

| Source | Original/source format | Current known handling | Role and cautions |
|---|---|---|---|
| ISCXVPN2016 | PCAP packet captures | Flow extraction/compatibility must be verified against the actual local files and pipeline | Candidate historical benchmark; do not assume a flow count or final schema until audited |
| USBVPN 2022 | JSON flow records | Audited and converted/validated through the repository's 2022 pipeline; audit summaries are in `results/` | Historical flow-level data; check labels, provenance, missingness, duplicates, and class balance |
| Modern/self-captured traffic | PCAP/PCAPNG captures plus session metadata/logs | Automated capture scripts and a 21-session plan are present | Controlled modern data; review metadata and capture quality before model use |
| 2026 Parquet archive | Multiple Parquet artifacts, including session flows, NFStream inner flows, and packet-match artifacts | Archive/checksum inspection has been performed in earlier work; schemas and artifact roles differ | Do not concatenate all files blindly; inspect each schema and determine whether each artifact is appropriate for training or analysis |

Dataset versions, licensing, label definitions, and exact feature names should be recorded in the dataset inventory and schema outputs. The table above is a high-level summary, not a substitute for inspecting the data files.

## 5. Candidate Model Features vs. Analysis Fields

The intended model inputs are **flow-level metadata features** that are available consistently and can be justified for the research question. The exact final feature list must come from the executed feature-validation notebook and the schema of the dataset used in each experiment.

Examples of common flow-metadata categories to evaluate include:
- Flow duration and packet/byte totals.
- Forward/reverse packet and byte counts, where consistently defined.
- Packet-length summaries.
- Inter-arrival-time (IAT) summaries.
- Directional or protocol-derived flow statistics, if present and valid.

These are examples of feature categories, **not a declaration that every dataset contains every field**.

Keep the following out of model inputs unless a specific, leakage-safe experiment explicitly justifies them:
- Ground-truth class/label.
- Dataset name, source file, capture/session ID, and other provenance identifiers.
- File paths, timestamps, or identifiers that could reveal the label or split.
- Post-capture review status and operational notes.
- Fields derived from the label or from future information.

Such fields are often valuable for auditing, grouping, stratified evaluation, provenance, and error analysis even when they are not model features. Record the exact final feature names, definitions, units, missing-value handling, and exclusions in the feature dictionary before training.

## 6. Repository Structure

```text
vpn-traffic-fyp/
├── configs/
│   ├── collection.yaml
│   ├── capture_plan_21.csv
│   └── session_metadata_template.csv
├── data/                 # Dataset documentation; large/raw data should stay out of Git
├── docs/
│   └── validation/
├── models/               # Generated model artifacts; normally excluded from Git
├── notebooks/
│   ├── 01_environment_check.ipynb
│   ├── 02_dataset_audit.ipynb
│   ├── 03_2022_feature_validation.ipynb
│   └── 04_dataset_schema_inventory.ipynb  # Add after reviewing/running the notebook
├── results/              # Small, intentional summaries; avoid committing large/generated data
├── scripts/
│   ├── automated_capture.sh
│   ├── automated_three_session_capture.sh
│   ├── browser_workload.py
│   └── pilot_browse.sh
├── src/
├── requirements_capture.txt
└── README.md
```

The tree is representative; actual files may differ. Keep temporary files, backups, Python caches, raw captures, large datasets, credentials, and environment files out of version control.

## 7. Reproducible Workflow

1. **Check the environment.** Activate the project's virtual environment and run the environment-check notebook.
2. **Audit each source.** Record file formats, schemas, labels, missing values, duplicates, class balance, and provenance.
3. **Validate transformations.** Preserve original source files and write converted/cleaned data to separate locations.
4. **Inspect features.** Confirm feature definitions and compatibility across datasets; document fields that cannot be mapped reliably.
5. **Collect controlled traffic.** Follow `configs/capture_plan_21.csv` and the collection configuration. Record each session's label, VPN state, interface, duration, and review status.
6. **Review captures.** Do not use a session for training while its metadata or capture quality remains `Needs_review`.
7. **Create leakage-safe splits.** Group related flows by capture/session where appropriate; do not let near-duplicate flows from the same session leak between train and test.
8. **Train baselines.** Fit preprocessing only on training data and save configuration, feature list, random seed, and model version.
9. **Evaluate.** Report per-class metrics, macro-F1, confusion matrices, and class support. For generalization, test on held-out datasets/sessions where possible.
10. **Explain and document.** Apply explainability only to a validated model and state its limitations.
11. **Sync and verify.** Commit code, notebooks, small result summaries, and documentation. Check remote repository and cloud notebook copies separately.

## 8. Useful Commands

Run from the project root on Fedora:

```bash
cd ~/vpn-traffic-fyp
source .venv/bin/activate
git status --short
git log -8 --oneline
```

To list the main project files without traversing the virtual environment:

```bash
find configs docs notebooks results scripts src -maxdepth 2 -type f 2>/dev/null | sort
```

Before committing, inspect exactly what will be included:

```bash
git diff -- README.md
git diff --cached --stat
git status --short
```

Do not add raw data or large capture files just to make GitHub look complete. Use `.gitignore` and data documentation for those files.

## 9. Technology Stack

- Python 3.12 virtual environment (verify the interpreter used for each run).
- Pandas, NumPy, and PyArrow for data handling.
- NFStream for flow extraction/metadata.
- Scikit-learn and XGBoost for classification baselines.
- JupyterLab for analysis and reproducible experiments.
- SHAP or another suitable method for model explanations.
- Git/GitHub for version control.
- Google Colab as an optional compute environment, provided data access and notebook execution are verified.

Exact package versions should be recorded from the active environment and associated with each experiment.

## 10. Responsible Research and Limitations

Use only datasets and network captures that are authorized for this research. The objective is traffic classification from metadata, not decryption or inspection of application payloads. Capture labels can be wrong or incomplete; dataset artifacts can use incompatible schemas; class imbalance, duplicate flows, missing IAT values, and cross-label patterns can affect evaluation. These limitations must be measured and documented rather than hidden.

A high score on one dataset does not establish reliable generalization to another network, VPN configuration, or collection period.

## 11. Progress Log

- **2026-10-19 documentation checkpoint:** Repository contains the 2022 audit/conversion/feature-validation work, result CSV summaries, capture configuration, 21-session plan, and automated collection/workload scripts. At the last verified capture checkpoint, three Telenor sessions existed and were marked `Needs_review`. Git status showed the capture plan, validation note directory, capture requirements file, and scripts as untracked; these need review before being committed. The README was still describing only initial setup and was out of date.

Record future progress with the date, files/notebooks changed, commands or cells run, output paths, validation status, and next action.

## 12. Immediate Next Steps

1. Review the three existing capture sessions and update their metadata only after checking the actual files.
2. Inspect and run the dataset-schema inventory notebook against the actual local datasets.
3. Finalize the exact model feature dictionary from the executed validation notebook and per-dataset schemas.
4. Verify `.gitignore` and inspect all untracked files/backups before staging anything.
5. Commit the reviewed documentation, scripts, configs, and small audit summaries; push and verify the GitHub `main` branch.
6. Update the Colab notebook from the same committed version and confirm execution/output paths; cloud synchronization is a separate verification step.
7. Start baseline modeling only after labels, feature mappings, session quality, and split strategy have been checked.
