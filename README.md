# Explainable ML-Based Classification of Modern Encrypted VPN Traffic

## Project Overview

This Final Year Project investigates whether machine learning can classify network traffic as Normal, OpenVPN, or WireGuard using flow-level metadata without inspecting encrypted payload contents.

The project also evaluates how model performance changes across datasets collected in different years and environments.

## Objectives

- Classify Normal, OpenVPN, and WireGuard traffic.
- Extract flow-level features using NFStream.
- Evaluate cross-dataset and temporal generalization.
- Compare Logistic Regression, Decision Tree, Random Forest, and XGBoost.
- Evaluate models using accuracy, precision, recall, macro-F1, and confusion matrices.
- Apply explainable AI techniques to understand model predictions.

## Planned Datasets

- ISCXVPN2016
- USBVPN2022
- Public and self-captured modern traffic datasets

Dataset availability, labels, licensing, and compatibility will be verified before experiments.

## Technology Stack

- Python
- Pandas and NumPy
- NFStream
- Scikit-learn
- XGBoost
- SHAP and other suitable explanation methods
- JupyterLab
- Git and GitHub
- Google Colab for optional cloud computation

## Project Structure

- `data/` — Dataset documentation; large datasets are excluded from Git.
- `notebooks/` — Experiments and exploratory analysis.
- `src/` — Reusable source code.
- `models/` — Generated models; model files are excluded from Git.
- `results/` — Experiment outputs; generated results are excluded from Git.
- `docs/` — Research documentation and project planning.

## Research Methodology

1. Audit and prepare the datasets.
2. Extract and validate flow-level features.
3. Prevent data leakage using appropriate train/test splits.
4. Train baseline machine learning models.
5. Evaluate within-dataset and cross-dataset performance.
6. Explain predictions and document limitations.

## Responsible Research

Experiments will use authorized datasets and network captures. Traffic classification results will be evaluated as research outputs and will not automatically trigger firewall blocking.

## Project Status

Initial development environment and project structure are being prepared. Dataset auditing and model development have not yet started.
