# Code written with AI assistance (ChatGPT, Claude) and reviewed by the OrbitCare AI team.
import os
import re
import json
import datetime
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------------------
# Paths and settings
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
CHECKIN_FILE = os.path.join(BASE_DIR, "data", "checkins.json")

DATASETS = {
    "metabolic": {
        "name": "Comprehensive Metabolic Panel",
        "file": "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv",
        "description": "Metabolic and biochemical measurements",
    },
    "cardiovascular": {
        "name": "Cardiovascular Immunoassay",
        "file": "LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv",
        "description": "Cardiovascular-related biomarkers",
    },
    "immune_eve": {
        "name": "Immune Eve Panel",
        "file": "LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv",
        "description": "Immune-related biomarkers",
    },
    "immune_alamar": {
        "name": "Immune Alamar Panel",
        "file": "LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv",
        "description": "Immune-related biomarkers",
    },
}

PHASE_ORDER = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]
PRE_FLIGHT = ["L-92", "L-44", "L-3"]
POST_PHASES = ["R+1", "R+45", "R+82", "R+194"]
SEVERITY_RANK = {"alert": 2, "watch": 1}

_df_cache = {}
_cols_cache = {}
_ref_cache = {}
_alert_cache = {}


# ------------------------------------------------------------------
# Data helpers
# ------------------------------------------------------------------
def clean(value, digits=4):
    """Make a value JSON-safe (no NaN, no numpy types)."""
    try:
        if value is None or pd.isna(value):
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def get_phase(name):
    m = re.search(r"(L-\d+|R\+\d+)", str(name))
    return m.group(1) if m else None


def get_crew_id(name):
    m = re.search(r"(C\d{3})", str(name))
    return m.group(1) if m else None


def name_column(df):
    return "Sample Name" if "Sample Name" in df.columns else df.columns[0]


def dataset_path(dataset_id):
    """Prefer the processed file (from process_data.py), else the raw one."""
    clean_path = os.path.join(PROCESSED_DIR, dataset_id + "_clean.csv")
    if os.path.exists(clean_path):
        return clean_path
    return os.path.join(RAW_DIR, DATASETS[dataset_id]["file"])


def load_df(dataset_id):
    if dataset_id in _df_cache:
        return _df_cache[dataset_id].copy()

    df = pd.read_csv(dataset_path(dataset_id))
    df.columns = [str(c).strip() for c in df.columns]

    ncol = name_column(df)
    df["_phase"] = df[ncol].astype(str).apply(get_phase)

    crew_ids_series = df[ncol].astype(str).apply(get_crew_id)
    if crew_ids_series.notna().all() and crew_ids_series.nunique() <= 8:
        df["_crew"] = crew_ids_series
    else:
        df["_crew"] = (df.groupby("_phase").cumcount() + 1).apply(lambda n: f"C00{n}")

    _df_cache[dataset_id] = df
    return df.copy()


def crew_ids():
    df = load_df("metabolic")
    return sorted(df["_crew"].dropna().unique().tolist())


def value_columns(dataset_id):
    """Numeric measurement columns (not ranges, not text). Cached."""
    if dataset_id in _cols_cache:
        return _cols_cache[dataset_id]

    df = load_df(dataset_id)
    ncol = name_column(df)
    cols = []
    for c in df.columns:
        low = c.lower()
        if c.startswith("_") or c == ncol:
            continue
        if "range_min" in low or "range_max" in low or "_max_" in low or "_min_" in low:
            continue
        numeric = pd.to_numeric(df[c], errors="coerce")
        if numeric.notna().sum() >= len(df) / 2:
            cols.append(c)
    _cols_cache[dataset_id] = cols
    return cols


def get_ref(dataset_id, df, column):
    """Laboratory reference range (only the metabolic dataset has one)."""
    key = (dataset_id, column)
    if key in _ref_cache:
        return _ref_cache[key]

    ref = None
    if "_value" in column:
        base = column.split("_value")[0]
        lo = next((c for c in df.columns if c.startswith(base + "_range_min")), None)
        hi = next(
            (c for c in df.columns
             if c.startswith(base + "_range_max") or c.startswith(base + "_max_")),
            None,
        )
        if lo and hi:
            lo_vals = pd.to_numeric(df[lo], errors="coerce").dropna()
            hi_vals = pd.to_numeric(df[hi], errors="coerce").dropna()
            if not lo_vals.empty and not hi_vals.empty:
                ref = {"min": clean(lo_vals.iloc[0]), "max": clean(hi_vals.iloc[0])}
    _ref_cache[key] = ref
    return ref


def label_parts(col):
    """'glucose_value_milligram_per_deciliter' -> ('glucose', 'milligram per deciliter')"""
    if "_value" in col:
        base, _, rest = col.partition("_value")
        return base.replace("_", " "), rest.strip("_").replace("_", " ")
    return col.replace("_", " "), ""


# ------------------------------------------------------------------
# Explainable alert engine (NASA crew data)
# ------------------------------------------------------------------
# Each astronaut is compared with THEIR OWN pre-flight baseline
# (mean of L-92, L-44, L-3).
#   z-score = (value - baseline) / baseline_spread
#   baseline_spread = max(std of the 3 pre-flight samples, 5% of baseline value)
#
# ALERT : (|z| >= 3 and |change| >= 10%)  OR  new excursion outside lab range
# WATCH : (|z| >= 2 and |change| >= 5%)   OR  still outside lab range
def compute_alerts(dataset_id, crew):
    key = (dataset_id, crew)
    if key in _alert_cache:
        return _alert_cache[key]

    df = load_df(dataset_id)
    sub = df[df["_crew"] == crew]
    items = []
    evaluated = {p: 0 for p in POST_PHASES}

    for col in value_columns(dataset_id):
        series = pd.to_numeric(sub[col], errors="coerce")
        pre = series[sub["_phase"].isin(PRE_FLIGHT)].dropna()
        if len(pre) < 2:
            continue

        base = float(pre.mean())
        if abs(base) < 1e-9:
            continue
        sd = float(pre.std(ddof=1))
        eff_sd = max(sd if not np.isnan(sd) else 0.0, 0.05 * abs(base))

        ref = get_ref(dataset_id, df, col)
        has_ref = bool(ref and ref["min"] is not None and ref["max"] is not None)
        base_in_range = (ref["min"] <= base <= ref["max"]) if has_ref else True

        end_vals = series[sub["_phase"] == POST_PHASES[-1]].dropna()
        recovered = None
        if len(end_vals):
            recovered = bool(abs((float(end_vals.mean()) - base) / eff_sd) < 2)

        name, unit = label_parts(col)

        for p in POST_PHASES:
            vals = series[sub["_phase"] == p].dropna()
            if vals.empty:
                continue
            evaluated[p] += 1

            v = float(vals.mean())
            z = (v - base) / eff_sd
            pct = (v - base) / abs(base) * 100

            out_ref = bool(has_ref and (v < ref["min"] or v > ref["max"]))
            new_excursion = out_ref and base_in_range

            if (abs(z) >= 3 and abs(pct) >= 10) or new_excursion:
                severity = "alert"
            elif (abs(z) >= 2 and abs(pct) >= 5) or out_ref:
                severity = "watch"
            else:
                continue

            direction = "higher" if v > base else "lower"
            reason = (
                f"{name} was {v:.3g} {unit} at {p}, {abs(pct):.1f}% {direction} than "
                f"{crew}'s pre-flight average ({base:.3g}), which is {abs(z):.1f} "
                f"baseline spreads away."
            ).replace("  ", " ")
            if out_ref:
                reason += f" It is outside the lab reference range ({ref['min']}-{ref['max']})."
                if not new_excursion:
                    reason += " (It was already outside the range before flight.)"

            items.append({
                "dataset": dataset_id,
                "marker": col,
                "marker_label": name,
                "unit": unit,
                "crew": crew,
                "phase": p,
                "baseline": clean(base),
                "value": clean(v),
                "pct_change": clean(pct, 2),
                "z_score": clean(z, 2),
                "severity": severity,
                "outside_reference": out_ref,
                "reference": ref if has_ref else None,
                "recovered_by_end": recovered,
                "reason": reason,
            })

    result = {"items": items, "evaluated": evaluated}
    _alert_cache[key] = result
    return result


def sort_items(items):
    items.sort(key=lambda x: (-SEVERITY_RANK[x["severity"]], -abs(x["z_score"] or 0)))
    return items


def crew_phase_status(crew, phase):
    """Combine all 4 datasets into one status for a crew member at one phase."""
    evaluated = alert = watch = 0
    top = []
    for ds in DATASETS:
        try:
            res = compute_alerts(ds, crew)
        except Exception as e:
            print(f"[warning] could not analyse {ds}: {e}")
            continue
        evaluated += res["evaluated"].get(phase, 0)
        for it in res["items"]:
            if it["phase"] != phase:
                continue
            if it["severity"] == "alert":
                alert += 1
            else:
                watch += 1
            top.append(it)

    share = (alert + watch) / evaluated * 100 if evaluated else 0.0
    # demo thresholds (share of measured markers that deviate), not clinical limits
    status = "Review" if share >= 15 else "Monitor" if share >= 5 else "Stable"
    return {
        "crew": crew,
        "phase": phase,
        "markers_evaluated": evaluated,
        "alerts": alert,
        "watch": watch,
        "flagged_percent": round(share, 1),
        "status": status,
        "top_items": sort_items(top)[:5],
    }


# ------------------------------------------------------------------
# Routes: data
# ------------------------------------------------------------------
@app.route("/")
def home():
    return jsonify({"project": "OrbitCare AI", "status": "running"})


@app.route("/api/overview")
def overview():
    items = []
    for dataset_id, info in DATASETS.items():
        path = dataset_path(dataset_id)
        available = os.path.exists(path)
        records = columns = 0
        if available:
            df = pd.read_csv(path)
            records, columns = int(df.shape[0]), int(df.shape[1])
        items.append({
            "id": dataset_id,
            "name": info["name"],
            "description": info["description"],
            "available": available,
            "records": records,
            "columns": columns,
        })
    return jsonify({
        "project": "OrbitCare AI",
        "source": "NASA OSDR - OSD-575",
        "data_type": "Real research measurements",
        "datasets": items,
    })


@app.route("/api/dataset/<dataset_id>")
def dataset(dataset_id):
    if dataset_id not in DATASETS:
        return jsonify({"error": "Unknown dataset"}), 404
    df = load_df(dataset_id).drop(columns=["_phase", "_crew"])
    df = df.astype(object).where(pd.notna(df), None)
    return jsonify({
        "dataset": dataset_id,
        "columns": list(df.columns),
        "records": df.to_dict(orient="records"),
    })


@app.route("/api/sample-phases")
def sample_phases():
    df = load_df("metabolic")
    counts = df["_phase"].value_counts().to_dict()
    ordered = {p: int(counts[p]) for p in PHASE_ORDER if p in counts}
    return jsonify({"source": "NASA OSD-575 metabolic dataset", "phase_counts": ordered})


@app.route("/api/quality")
def quality():
    path = os.path.join(PROCESSED_DIR, "data_quality_report.json")
    if not os.path.exists(path):
        return jsonify({"available": False,
                        "message": "Run: python backend/process_data.py"})
    with open(path, encoding="utf-8") as f:
        return jsonify({"available": True, "report": json.load(f)})


@app.route("/api/crew")
def crew_list():
    return jsonify({"crew": crew_ids()})


@app.route("/api/biomarkers/<dataset_id>")
def biomarkers(dataset_id):
    if dataset_id not in DATASETS:
        return jsonify({"error": "Unknown dataset"}), 404
    return jsonify({"dataset": dataset_id, "biomarkers": value_columns(dataset_id)})


@app.route("/api/trend/<dataset_id>/<path:column>")
def trend(dataset_id, column):
    if dataset_id not in DATASETS:
        return jsonify({"error": "Unknown dataset"}), 404
    df = load_df(dataset_id)
    if column not in df.columns:
        return jsonify({"error": "Unknown column"}), 404

    df[column] = pd.to_numeric(df[column], errors="coerce")
    ref = get_ref(dataset_id, df, column)

    phases = []
    for p in PHASE_ORDER:
        sub = df[df["_phase"] == p]
        if sub.empty:
            continue
        vals = sub[column].dropna()
        phases.append({
            "phase": p,
            "mean": clean(vals.mean()) if not vals.empty else None,
            "min": clean(vals.min()) if not vals.empty else None,
            "max": clean(vals.max()) if not vals.empty else None,
            "by_crew": {row["_crew"]: clean(row[column]) for _, row in sub.iterrows()},
        })

    crew = sorted({c for p in phases for c in p["by_crew"].keys()})
    return jsonify({"column": column, "reference_range": ref, "crew": crew, "phases": phases})


@app.route("/api/summary/<dataset_id>")
def summary(dataset_id):
    if dataset_id not in DATASETS:
        return jsonify({"error": "Unknown dataset"}), 404

    target_phase = request.args.get("phase", "R+1").replace(" ", "+")
    df = load_df(dataset_id)
    cols = value_columns(dataset_id)

    changes = []
    out_of_range = {p: 0 for p in PHASE_ORDER}
    markers_with_range = 0

    for col in cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

        base = df[df["_phase"].isin(PRE_FLIGHT)][col].dropna()
        post = df[df["_phase"] == target_phase][col].dropna()
        if len(base) and len(post) and abs(base.mean()) > 1e-9:
            pct = (post.mean() - base.mean()) / abs(base.mean()) * 100
            changes.append({
                "column": col,
                "baseline": clean(base.mean()),
                "phase_mean": clean(post.mean()),
                "pct_change": clean(pct, 2),
            })

        ref = get_ref(dataset_id, df, col)
        if ref and ref["min"] is not None and ref["max"] is not None:
            markers_with_range += 1
            for p in PHASE_ORDER:
                vals = df[df["_phase"] == p][col].dropna()
                out_of_range[p] += int(((vals < ref["min"]) | (vals > ref["max"])).sum())

    changes.sort(key=lambda x: abs(x["pct_change"] or 0), reverse=True)

    return jsonify({
        "dataset": dataset_id,
        "target_phase": target_phase,
        "baseline_phases": PRE_FLIGHT,
        "total_biomarkers": len(cols),
        "markers_with_reference_range": markers_with_range,
        "out_of_range_counts": out_of_range if markers_with_range else None,
        "top_changes": changes[:10],
    })


# ------------------------------------------------------------------
# Routes: alerts, crew status, NASA-crew check-ins
# ------------------------------------------------------------------
@app.route("/api/alerts/<dataset_id>")
def alerts(dataset_id):
    if dataset_id not in DATASETS:
        return jsonify({"error": "Unknown dataset"}), 404

    ids = crew_ids()
    crew = request.args.get("crew") or ids[0]
    if crew not in ids:
        return jsonify({"error": "Unknown crew member"}), 404

    phase = (request.args.get("phase") or "").replace(" ", "+")
    limit = int(request.args.get("limit", 40))

    res = compute_alerts(dataset_id, crew)

    by_phase = []
    for p in POST_PHASES:
        by_phase.append({
            "phase": p,
            "evaluated": res["evaluated"].get(p, 0),
            "alert": sum(1 for i in res["items"] if i["phase"] == p and i["severity"] == "alert"),
            "watch": sum(1 for i in res["items"] if i["phase"] == p and i["severity"] == "watch"),
        })

    items = [i for i in res["items"] if not phase or i["phase"] == phase]
    sort_items(items)

    recovery = {
        "recovered": sum(1 for i in items if i["recovered_by_end"] is True),
        "not_recovered": sum(1 for i in items if i["recovered_by_end"] is False),
    }

    return jsonify({
        "dataset": dataset_id,
        "crew": crew,
        "phase": phase or "all",
        "by_phase": by_phase,
        "recovery": recovery,
        "total_flagged": len(items),
        "items": items[:limit],
        "method": {
            "baseline": "Mean of the crew member's own pre-flight samples (L-92, L-44, L-3)",
            "alert": "|z| >= 3 and |change| >= 10%, or a new value outside the lab reference range",
            "watch": "|z| >= 2 and |change| >= 5%, or still outside the lab reference range",
        },
    })


@app.route("/api/crew-status/<crew>")
def crew_status(crew):
    if crew not in crew_ids():
        return jsonify({"error": "Unknown crew member"}), 404
    return jsonify({
        "crew": crew,
        "timeline": [crew_phase_status(crew, p) for p in POST_PHASES],
    })


def read_checkins():
    if not os.path.exists(CHECKIN_FILE):
        return []
    try:
        with open(CHECKIN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def write_checkins(items):
    os.makedirs(os.path.dirname(CHECKIN_FILE), exist_ok=True)
    with open(CHECKIN_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


@app.route("/api/checkins")
def list_checkins():
    crew = request.args.get("crew")
    items = [c for c in read_checkins() if not crew or c.get("crew") == crew]
    return jsonify({"checkins": items[-5:][::-1]})


@app.route("/api/checkin", methods=["POST"])
def submit_checkin():
    data = request.get_json(silent=True) or {}
    crew = data.get("crew")
    phase = str(data.get("phase", "")).replace(" ", "+")

    if crew not in crew_ids() or phase not in POST_PHASES:
        return jsonify({"error": "Choose a valid crew member and phase."}), 400

    try:
        fatigue = int(data.get("fatigue", 3))
        mood = int(data.get("mood", 3))
        sleep = float(data.get("sleep_hours", 7))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid numbers in check-in."}), 400

    symptoms = [str(s)[:40] for s in (data.get("symptoms") or [])][:10]
    notes = str(data.get("notes", ""))[:500]

    flags = []
    if fatigue >= 4:
        flags.append("High fatigue reported")
    if sleep < 6:
        flags.append("Less than 6 hours of sleep")
    if mood <= 2:
        flags.append("Low mood reported")
    if len(symptoms) >= 2:
        flags.append("Multiple symptoms reported")

    bio = crew_phase_status(crew, phase)

    if bio["status"] == "Review" and flags:
        message = ("Both the self-report and the blood biomarkers show changes. "
                   "Recommend discussing these results with the mission medical team soon.")
    elif bio["status"] == "Review" or flags:
        message = ("One of the two signals (biomarkers or self-report) shows a change. "
                   "Keep monitoring and consider mentioning it to the medical team.")
    else:
        message = "No notable signals in this check-in. Continue routine monitoring."

    message += (" OrbitCare AI is a research prototype and does not diagnose "
                "or replace medical advice.")

    record = {
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "crew": crew,
        "phase": phase,
        "fatigue": fatigue,
        "mood": mood,
        "sleep_hours": sleep,
        "symptoms": symptoms,
        "notes": notes,
        "self_report_flags": flags,
        "biomarker_status": bio["status"],
    }
    items = read_checkins()
    items.append(record)
    write_checkins(items)

    return jsonify({
        "saved": True,
        "record": record,
        "biomarker_status": bio,
        "self_report_flags": flags,
        "message": message,
    })


# ------------------------------------------------------------------
# AI assistant routes (live check-ins, LLM chat, AI insight)
# ------------------------------------------------------------------
from assistant import register_assistant  # noqa: E402

register_assistant(app)


if __name__ == "__main__":
    app.run(debug=True, port=5000)