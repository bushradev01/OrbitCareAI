# OrbitCare AI

Explainable astronaut health monitoring built on real NASA Open Science Data Repository
data (OSD-575). Built for the NASA Space Apps Challenge.

## What it does
- **Dashboard:** explore 4 blood-biomarker panels (metabolic, cardiovascular, 2 immune panels)
  across 7 mission phases (3 pre-flight, 4 post-flight).
- **Crew alerts:** compares each astronaut with their own pre-flight baseline and flags
  deviations with a plain-language reason and a recovery check.
- **Astronaut check-in:** combines self-reported fatigue, mood, sleep and symptoms with
  biomarker status into one summary.

## Demo
Demo video (30 seconds): <paste your link here>

## Data
NASA OSDR study OSD-575 (https://osdr.nasa.gov/bio/repo/data/studies/OSD-575).
Four processed panels: Comprehensive Metabolic Panel, Cardiovascular Eve panel,
Immune Eve panel and Immune Alamar panel. 28 samples per panel (27 for Alamar) from
4 crew members. Missing values are left empty. Nothing is estimated or invented.

## How alerts work (no black box)
- Baseline = the astronaut's own mean of L-92, L-44, L-3.
- z-score = (value - baseline) / baseline spread (spread floored at 5% of baseline).
- **Alert:** |z| >= 3 and change >= 10%, or a new value outside the lab reference range.
- **Watch:** |z| >= 2 and change >= 5%, or still outside the lab reference range.
- Status per phase: Stable (<5% of markers flagged), Monitor (5-15%), Review (>=15%).
  These are demo thresholds, not clinical limits.

## Limitations
- Only 4 crew members, so this cannot support a reliable predictive model.
- With 3 baseline samples per person, some flags occur by chance.
- Descriptive monitoring only. Not a medical device and not for diagnosis.

## Tech stack
Python, Flask, pandas, NumPy / React (Vite), Recharts.

## Run it
```bash
# 1. backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python backend/process_data.py
python backend/app.py             # http://localhost:5000

# 2. frontend (new terminal)
cd frontend
npm install
npm install recharts
npm run dev                       # http://localhost:5173
```
Place the NASA OSD-575 files in `data/raw/` first.

## Project structure
```
backend/         Flask API, data processing, alert engine
frontend/        React dashboard
data/raw/        original NASA files
data/processed/  cleaned CSVs + data quality report
```

## AI assistance disclosure
Parts of the code (Flask backend, React frontend, data processing script) and this README
were written with help from AI assistants (ChatGPT and Claude). The team reviewed, ran and
tested the code. The analysis uses real NASA OSD-575 data and no AI-generated data.
No NASA logos or branding are used.

## Credits
Data: NASA Open Science Data Repository, OSD-575.
Libraries: Flask, pandas, NumPy, React, Vite, Recharts.