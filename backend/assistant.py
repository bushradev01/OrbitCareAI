# Code written with AI assistance (ChatGPT, Claude) and reviewed by the OrbitCare AI team.
import os
import re
import json
import datetime
import threading
import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request

from llm import ask_llm, provider_name, SYSTEM_PROMPT, LLMError

bp = Blueprint("assistant", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_FILE = os.path.join(
    BASE_DIR, "data", "raw", "LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv"
)
CLEAN_FILE = os.path.join(BASE_DIR, "data", "processed", "metabolic_clean.csv")
ENTRY_FILE = os.path.join(BASE_DIR, "data", "astronaut_entries.json")
PRE_FLIGHT = ["L-92", "L-44", "L-3"]

_lock = threading.Lock()
_markers = None

EMERGENCY_WORDS = [
    "chest pain", "can't breathe", "cannot breathe", "difficulty breathing",
    "unconscious", "severe bleeding", "heart attack", "stroke", "seizure",
    "suicide", "suicidal", "kill myself", "want to die", "end my life",
]
EMERGENCY_REPLY = (
    "This could be urgent. Please contact your flight surgeon or local emergency services "
    "right now. If you are having thoughts of harming yourself, please reach out to someone "
    "you trust or a crisis line immediately. You do not have to handle this alone. "
    "OrbitCare AI is a research prototype and cannot help with emergencies."
)


# ------------------------------------------------------------------
# Reference data from NASA OSD-575 (metabolic panel)
# ------------------------------------------------------------------
def get_phase(name):
    m = re.search(r"(L-\d+|R\+\d+)", str(name))
    return m.group(1) if m else None


def label_parts(col):
    if "_value" in col:
        base, _, rest = col.partition("_value")
        return base.replace("_", " "), rest.strip("_").replace("_", " ")
    return col.replace("_", " "), ""


def find_ref(df, column):
    base = column.split("_value")[0]
    lo = next((c for c in df.columns if c.startswith(base + "_range_min")), None)
    hi = next(
        (c for c in df.columns
         if c.startswith(base + "_range_max") or c.startswith(base + "_max_")),
        None,
    )
    if not lo or not hi:
        return None
    lo_v = pd.to_numeric(df[lo], errors="coerce").dropna()
    hi_v = pd.to_numeric(df[hi], errors="coerce").dropna()
    if lo_v.empty or hi_v.empty:
        return None
    a, b = float(lo_v.iloc[0]), float(hi_v.iloc[0])
    return (a, b) if b > a else None


def get_markers():
    """Blood markers that have a lab reference range and NASA pre-flight statistics."""
    global _markers
    if _markers is not None:
        return _markers

    path = CLEAN_FILE if os.path.exists(CLEAN_FILE) else RAW_FILE
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    ncol = "Sample Name" if "Sample Name" in df.columns else df.columns[0]
    df["_phase"] = df[ncol].astype(str).apply(get_phase)
    pre = df[df["_phase"].isin(PRE_FLIGHT)]

    markers = {}
    for col in df.columns:
        low = col.lower()
        if col.startswith("_") or col == ncol or "_value" not in col:
            continue
        if any(s in low for s in ("range_min", "range_max", "_max_", "_min_")):
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().sum() < len(df) / 2:
            continue
        ref = find_ref(df, col)
        if not ref:
            continue
        pv = pd.to_numeric(pre[col], errors="coerce").dropna()
        if len(pv) < 3 or abs(float(pv.mean())) < 1e-9:
            continue
        sd = float(pv.std(ddof=1))
        label, unit = label_parts(col)
        markers[col] = {
            "key": col,
            "label": label,
            "unit": unit,
            "ref_min": ref[0],
            "ref_max": ref[1],
            "nasa_mean": float(pv.mean()),
            "nasa_sd": 0.0 if np.isnan(sd) else sd,
        }
    _markers = markers
    return markers


# ------------------------------------------------------------------
# Saving entries
# ------------------------------------------------------------------
def read_all():
    if not os.path.exists(ENTRY_FILE):
        return {}
    try:
        with open(ENTRY_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_all(data):
    os.makedirs(os.path.dirname(ENTRY_FILE), exist_ok=True)
    with open(ENTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def safe_name(raw):
    display = re.sub(r"[^A-Za-z0-9 _-]", "", str(raw or "")).strip()[:40]
    return display, display.lower()


def rnd(x, d=3):
    return float(round(float(x), d))


# ------------------------------------------------------------------
# Rule-based evaluation (explainable; this decides the flags)
# ------------------------------------------------------------------
# Per marker:
#   outside lab range            -> WATCH, or ALERT if beyond the range by >= 20% of its width
#   change >= 10% vs own earlier -> WATCH, >= 20% -> ALERT   (own average of first 3 entries)
#   |z| >= 3 vs NASA crew        -> WATCH
# Overall: Review (any alert or 3+ watch), Monitor (any watch), Stable.
def evaluate(values, prev_entries):
    markers = get_markers()
    results = []
    for key, v in values.items():
        m = markers[key]
        lo, hi = m["ref_min"], m["ref_max"]
        width = hi - lo

        prev_vals = [e["values"][key] for e in prev_entries if key in e.get("values", {})]
        base = pct = None
        if prev_vals:
            base = float(np.mean(prev_vals[:3]))
            if abs(base) > 1e-9:
                pct = (v - base) / abs(base) * 100

        eff_sd = max(m["nasa_sd"], 0.05 * abs(m["nasa_mean"]), 1e-9)
        z = (v - m["nasa_mean"]) / eff_sd

        severity = 0
        reasons = []

        if v < lo or v > hi:
            beyond = ((lo - v) if v < lo else (v - hi)) / width
            severity = 2 if beyond >= 0.2 else 1
            side = "below" if v < lo else "above"
            reasons.append(f"{v:g} {m['unit']} is {side} the lab reference range ({lo:g} to {hi:g}).")

        if pct is not None and abs(pct) >= 10:
            severity = max(severity, 2 if abs(pct) >= 20 else 1)
            reasons.append(f"It changed {pct:+.1f}% compared with your own earlier average ({base:.3g}).")

        if abs(z) >= 3:
            severity = max(severity, 1)
            side = "above" if z > 0 else "below"
            reasons.append(
                f"It is {abs(z):.1f} spread units {side} the NASA crew pre-flight average ({m['nasa_mean']:.3g})."
            )

        results.append({
            "key": key,
            "label": m["label"],
            "unit": m["unit"],
            "value": rnd(v, 4),
            "ref_min": m["ref_min"],
            "ref_max": m["ref_max"],
            "pct_vs_own": None if pct is None else rnd(pct, 1),
            "z_vs_nasa": rnd(z, 2),
            "severity": ["normal", "watch", "alert"][severity],
            "reasons": reasons,
        })

    order = {"alert": 0, "watch": 1, "normal": 2}
    results.sort(key=lambda r: (order[r["severity"]], -abs(r["z_vs_nasa"])))
    return results


def self_report_flags(fatigue, mood, sleep, symptoms):
    flags = []
    if fatigue >= 4:
        flags.append("high fatigue")
    if sleep < 6:
        flags.append("less than 6 hours of sleep")
    if mood <= 2:
        flags.append("low mood")
    if len(symptoms) >= 2:
        flags.append("multiple symptoms")
    return flags


def overall_status(results, flags):
    alerts = sum(1 for r in results if r["severity"] == "alert")
    watches = sum(1 for r in results if r["severity"] == "watch")
    status = "Review" if (alerts >= 1 or watches >= 3) else "Monitor" if watches >= 1 else "Stable"
    if flags:
        if status == "Stable":
            status = "Monitor"
        elif status == "Monitor" and len(flags) >= 2:
            status = "Review"
    return status, {
        "alert": alerts,
        "watch": watches,
        "normal": sum(1 for r in results if r["severity"] == "normal"),
    }


# ------------------------------------------------------------------
# Text for the LLM (grounded in the rule results)
# ------------------------------------------------------------------
def describe_entry(name, entry, flagged):
    lines = [
        f"Astronaut: {name}",
        f"Check-in label: {entry.get('label') or 'n/a'}",
        f"Overall status: {entry['status']}",
        f"Blood values entered: {len(entry['values'])}",
    ]
    if flagged:
        lines.append("Flagged blood markers:")
        for f in flagged[:8]:
            lines.append(f"- [{f['severity'].upper()}] {f['label']}: {' '.join(f['reasons'])}")
    else:
        lines.append("No blood markers were flagged.")
    lines.append(
        f"Self-report: fatigue {entry['fatigue']}/5, mood {entry['mood']}/5, "
        f"sleep {entry['sleep_hours']} h, symptoms: {', '.join(entry['symptoms']) or 'none'}"
    )
    if entry["self_report_flags"]:
        lines.append("Self-report flags: " + ", ".join(entry["self_report_flags"]))
    if entry.get("notes"):
        lines.append(f"<astronaut_notes>{entry['notes']}</astronaut_notes>")
    return "\n".join(lines)


def fallback_summary(status, flagged, flags):
    parts = [f"Overall status: {status}."]
    if flagged:
        names = "; ".join(f"{f['label']} ({f['severity']})" for f in flagged[:5])
        parts.append(f"Blood markers to look at: {names}.")
    else:
        parts.append("No blood markers were flagged.")
    if flags:
        parts.append("Self-report: " + ", ".join(flags) + ".")
    parts.append(
        "Consider repeating the test and discussing flagged items with the flight surgeon "
        "or a doctor. This is a research prototype, not medical advice."
    )
    return " ".join(parts)


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@bp.route("/api/assistant/status")
def assistant_status():
    p = provider_name()
    return jsonify({"configured": p is not None, "provider": p})


@bp.route("/api/my/markers")
def my_markers():
    return jsonify({"markers": list(get_markers().values())})


@bp.route("/api/my/entries", methods=["GET", "DELETE"])
def my_entries():
    display, key = safe_name(request.args.get("name"))
    if not key:
        return jsonify({"error": "Name required"}), 400

    if request.method == "DELETE":
        with _lock:
            data = read_all()
            data.pop(key, None)
            write_all(data)
        return jsonify({"deleted": True})

    data = read_all()
    return jsonify({"name": display, "entries": data.get(key, {}).get("entries", [])})


@bp.route("/api/my/entry", methods=["POST"])
def my_entry():
    data = request.get_json(silent=True) or {}
    display, key = safe_name(data.get("name"))
    if not key:
        return jsonify({"error": "Enter your astronaut name or ID first."}), 400

    markers = get_markers()
    values = {}
    raw_values = data.get("values") or {}
    if isinstance(raw_values, dict):
        for k, raw in raw_values.items():
            if k in markers:
                try:
                    v = float(raw)
                except (TypeError, ValueError):
                    continue
                if np.isfinite(v):
                    values[k] = v

    def num(field, default, lo, hi, cast):
        try:
            x = cast(data.get(field, default))
        except (TypeError, ValueError):
            x = default
        return max(lo, min(hi, x))

    fatigue = num("fatigue", 3, 1, 5, int)
    mood = num("mood", 3, 1, 5, int)
    sleep = num("sleep_hours", 7.0, 0.0, 16.0, float)
    symptoms_raw = data.get("symptoms")
    symptoms = [str(s)[:40] for s in symptoms_raw][:10] if isinstance(symptoms_raw, list) else []
    notes = str(data.get("notes", ""))[:500]
    label = str(data.get("label", ""))[:30]

    with _lock:
        history = read_all().get(key, {}).get("entries", [])

    results = evaluate(values, history)
    flags = self_report_flags(fatigue, mood, sleep, symptoms)
    status, counts = overall_status(results, flags)
    flagged = [r for r in results if r["severity"] != "normal"]

    entry = {
        "id": len(history) + 1,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "values": {k: rnd(v, 4) for k, v in values.items()},
        "fatigue": fatigue,
        "mood": mood,
        "sleep_hours": rnd(sleep, 1),
        "symptoms": symptoms,
        "notes": notes,
        "self_report_flags": flags,
        "status": status,
        "flagged": [
            {"label": f["label"], "severity": f["severity"], "reasons": f["reasons"]}
            for f in flagged
        ],
    }

    # LLM explanation (falls back to rules if the AI is unavailable)
    summary, ai_used, provider, llm_error = None, False, None, None
    prompt = (
        "Write a short, calm summary (under 120 words) of this check-in for the astronaut. "
        "Mention the most important flagged items and one or two sensible next steps.\n\n"
        + describe_entry(display, entry, flagged)
    )
    try:
        res = ask_llm(SYSTEM_PROMPT, [{"role": "user", "content": prompt}], 350)
        summary, ai_used, provider = res["text"], True, res["provider"]
    except LLMError as e:
        llm_error = str(e)[:200]
        summary = fallback_summary(status, flagged, flags)

    entry["summary"] = summary

    with _lock:
        all_data = read_all()
        record = all_data.setdefault(key, {"name": display, "entries": []})
        entry["id"] = len(record["entries"]) + 1
        record["entries"].append(entry)
        write_all(all_data)

    return jsonify({
        "saved": True,
        "entry": entry,
        "results": results,
        "status": status,
        "counts": counts,
        "summary": summary,
        "ai_used": ai_used,
        "provider": provider,
        "llm_error": llm_error,
    })


@bp.route("/api/assistant/chat", methods=["POST"])
def assistant_chat():
    data = request.get_json(silent=True) or {}
    display, key = safe_name(data.get("name"))
    messages = data.get("messages") or []
    if not isinstance(messages, list):
        messages = []
    messages = messages[-12:]

    last_user = ""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") != "assistant":
            last_user = str(m.get("content", ""))
            break

    if any(w in last_user.lower() for w in EMERGENCY_WORDS):
        return jsonify({"reply": EMERGENCY_REPLY, "ai_used": False, "provider": None,
                        "emergency": True, "llm_error": None})

    entries = read_all().get(key, {}).get("entries", []) if key else []
    if entries:
        latest = entries[-1]
        flagged = latest.get("flagged", [])
        ctx_entry = {
            "label": latest.get("label"), "status": latest["status"], "values": latest["values"],
            "fatigue": latest["fatigue"], "mood": latest["mood"],
            "sleep_hours": latest["sleep_hours"], "symptoms": latest["symptoms"],
            "self_report_flags": latest["self_report_flags"], "notes": latest.get("notes", ""),
        }
        context = f"This astronaut has {len(entries)} saved check-ins. Latest check-in:\n" \
                  + describe_entry(display, ctx_entry, flagged)
    else:
        context = "This astronaut has no saved check-ins yet. Answer general questions carefully."

    system = SYSTEM_PROMPT + "\n\nContext from the app:\n" + context

    try:
        res = ask_llm(system, messages, 450)
        return jsonify({"reply": res["text"], "ai_used": True, "provider": res["provider"],
                        "emergency": False, "llm_error": None})
    except LLMError as e:
        if entries:
            reply = ("The AI assistant is not available right now. From your latest check-in: "
                     + entries[-1].get("summary", ""))
        else:
            reply = ("The AI assistant is not available right now, and you have no saved "
                     "check-ins yet. Submit a check-in on the My health tab first.")
        return jsonify({"reply": reply, "ai_used": False, "provider": None,
                        "emergency": False, "llm_error": str(e)[:200]})


@bp.route("/api/ai/insight", methods=["POST"])
def ai_insight():
    data = request.get_json(silent=True) or {}
    dataset = re.sub(r"[^A-Za-z0-9 _-]", "", str(data.get("dataset", "")))[:60]
    phase = re.sub(r"[^A-Za-z0-9+-]", "", str(data.get("phase", "")))[:10]

    rows = []
    raw_changes = data.get("changes")
    for r in (raw_changes if isinstance(raw_changes, list) else [])[:8]:
        try:
            name = str(r.get("column", ""))[:80].replace("_", " ")
            rows.append(
                f"- {name}: baseline {float(r['baseline']):.4g}, at {phase} "
                f"{float(r['phase_mean']):.4g} ({float(r['pct_change']):+.1f}%)"
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            continue

    if not rows:
        return jsonify({"error": "No data to explain"}), 400

    prompt = (
        f"These are the biggest changes in the NASA OSD-575 dataset '{dataset}', comparing the "
        f"crew average at {phase} with the pre-flight baseline (4 astronauts):\n"
        + "\n".join(rows)
        + "\n\nIn under 120 words, explain in simple language what stands out, mention that "
        "only 4 astronauts were studied so this is descriptive and not proof, and name one "
        "possible reason a change like this can happen after spaceflight, without claiming "
        "certainty."
    )

    try:
        res = ask_llm(SYSTEM_PROMPT, [{"role": "user", "content": prompt}], 350)
        return jsonify({"text": res["text"], "ai_used": True, "provider": res["provider"],
                        "llm_error": None})
    except LLMError as e:
        biggest = rows[0][2:]
        text = (f"Biggest change at {phase}: {biggest}. Only 4 astronauts were studied, so "
                "these are descriptive changes, not proof. (AI is not connected, so this is "
                "a rule-based summary.)")
        return jsonify({"text": text, "ai_used": False, "provider": None,
                        "llm_error": str(e)[:200]})


def register_assistant(app):
    app.register_blueprint(bp)