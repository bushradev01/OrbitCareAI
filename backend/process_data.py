import os
import re
import json
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

DATASETS = {
    "metabolic": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
    "cardiovascular": "LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
    "immune_eve": "LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
    "immune_alamar": "LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv",
}

PHASE_ORDER = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]


def get_phase(name):
    m = re.search(r"(L-\d+|R\+\d+)", str(name))
    return m.group(1) if m else None


def get_crew(name):
    m = re.search(r"(C\d{3})", str(name))
    return m.group(1) if m else None


os.makedirs(PROCESSED_DIR, exist_ok=True)
report = {}

print("\n========== ORBITCARE AI: DATA PROCESSING ==========\n")

for dataset_id, filename in DATASETS.items():
    path = os.path.join(RAW_DIR, filename)
    print("-" * 60)
    print("DATASET:", dataset_id)

    if not os.path.exists(path):
        print("  File not found:", filename)
        report[dataset_id] = {"available": False}
        continue

    df = pd.read_csv(path)
    rows_raw, cols_raw = df.shape

    # 1. clean column names and text cells
    df.columns = [str(c).strip() for c in df.columns]
    name_col = "Sample Name" if "Sample Name" in df.columns else df.columns[0]

    for c in df.columns:
        if df[c].dtype == object:
            df[c] = (
                df[c].astype(str).str.strip()
                .replace({"": np.nan, "nan": np.nan, "NaN": np.nan,
                          "NA": np.nan, "N/A": np.nan, "None": np.nan})
            )

    # 2. convert text columns that are really numbers
    converted = 0
    for c in df.columns:
        if c == name_col or df[c].dtype != object:
            continue
        non_null = int(df[c].notna().sum())
        if non_null == 0:
            continue
        parsed = pd.to_numeric(df[c], errors="coerce")
        if parsed.notna().sum() / non_null >= 0.9:
            df[c] = parsed
            converted += 1

    # 3. quality checks (nothing is imputed or invented)
    total_cells = int(df.shape[0] * df.shape[1])
    missing_cells = int(df.isna().sum().sum())
    col_missing = df.isna().mean()
    empty_cols = [c for c in df.columns if col_missing[c] == 1.0]
    high_missing = col_missing[(col_missing > 0.2) & (col_missing < 1.0)] \
        .sort_values(ascending=False).head(10)

    phases = df[name_col].astype(str).apply(get_phase)
    crew = df[name_col].astype(str).apply(get_crew)

    numeric_cols = df.select_dtypes(include="number").columns
    constant_cols = [c for c in numeric_cols if df[c].nunique(dropna=True) <= 1]

    info = {
        "available": True,
        "samples": int(rows_raw),
        "columns": int(cols_raw),
        "numeric_columns": int(len(numeric_cols)),
        "text_columns_converted_to_numeric": converted,
        "missing_cells": missing_cells,
        "missing_percent": round(missing_cells / total_cells * 100, 2) if total_cells else 0,
        "fully_empty_columns": len(empty_cols),
        "columns_over_20_percent_missing": {
            c: round(float(v) * 100, 1) for c, v in high_missing.items()
        },
        "constant_columns": len(constant_cols),
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_sample_names": int(df[name_col].duplicated().sum()),
        "samples_without_recognised_phase": int(phases.isna().sum()),
        "phase_counts": {p: int((phases == p).sum()) for p in PHASE_ORDER},
        "crew_members": sorted(crew.dropna().unique().tolist()),
        "cleaned_file": dataset_id + "_clean.csv",
    }
    report[dataset_id] = info

    df.to_csv(os.path.join(PROCESSED_DIR, dataset_id + "_clean.csv"), index=False)

    print(f"  samples: {info['samples']}   columns: {info['columns']}")
    print(f"  missing values: {info['missing_cells']} ({info['missing_percent']}%)")
    print(f"  fully empty columns: {info['fully_empty_columns']}")
    print(f"  constant columns: {info['constant_columns']}")
    print(f"  duplicate rows: {info['duplicate_rows']}")
    print(f"  samples with unknown phase: {info['samples_without_recognised_phase']}")
    print(f"  crew: {info['crew_members']}")
    print(f"  saved -> data/processed/{info['cleaned_file']}")

with open(os.path.join(PROCESSED_DIR, "data_quality_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print("\nDone. Report saved to data/processed/data_quality_report.json\n")