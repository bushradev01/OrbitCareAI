# OrbitCare AI

Explainable astronaut health monitoring built on real NASA Open Science Data Repository
data (OSD-575). Rules decide what is flagged. An LLM explains the results in plain language.
Built for the NASA Space Apps Challenge.

## What it does
- **Dashboard:** explore 4 NASA blood-biomarker panels (metabolic, cardiovascular, two immune
  panels) across 7 mission phases (3 pre-flight, 4 post-flight), plus an AI explanation of the
  biggest changes.
- **Crew alerts:** compares each NASA crew member with their own pre-flight baseline and flags
  deviations with a plain-language reason and a recovery check.
- **My health (live):** an astronaut enters blood values and symptoms (typing or voice). Entries
  are saved, checked against NASA lab reference ranges and the astronaut's own history, and
  explained by an LLM.
- **AI assistant:** chat about your latest results, with voice input and read-aloud.

## Demo
Demo (30 seconds): <paste your link here>

## Data
NASA OSDR study OSD-575 (https://osdr.nasa.gov/bio/repo/data/studies/OSD-575).
Four processed panels: Comprehensive Metabolic Panel, Cardiovascular Eve panel, Immune Eve
panel, Immune Alamar panel. 28 samples per panel (27 for Alamar) from 4 crew members.
Missing values are left empty. Nothing is estimated or invented.

## How it works (no black box for the decisions)
- **Rules decide the flags.** Baseline = the astronaut's own pre-flight mean. Flags use
  z-scores, percent change and the lab reference ranges in the NASA data.
- **The LLM only explains** the flags it is given and answers questions using that context.
  It never decides what is flagged.
- If no LLM key is set, or the AI service is busy, the app falls back to rule-based text.
- Safety: messages that mention emergencies (for example chest pain) get a fixed message
  telling the user to contact the flight surgeon or emergency services. The LLM is not used.
- Status thresholds (10% / 20% change, 3 spread units) are demo values, not clinical limits.

## Limitations
- The NASA dataset has only 4 crew members, so it cannot support a reliable predictive model.
- Only the metabolic panel has lab reference ranges, so live entry covers those markers.
- The LLM can make mistakes. This is a research prototype, not a medical device, and not for
  diagnosis. Do not enter real personal health data: values are sent to the LLM provider.

## Tech stack
Python, Flask, pandas, NumPy, requests / React (Vite), Recharts / Google Gemini API or
Anthropic Claude API / browser Web Speech API.

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
Put the NASA OSD-575 files in `data/raw/` first.

For the AI features, create `backend/.env` (never commit it):
```
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-3.8-flash
```
or `LLM_PROVIDER=anthropic` with `ANTHROPIC_API_KEY=your_key`.
Model names change over time. Run `python backend/test_llm.py` to list the models your key
can use.

## Project structure
```
backend/         Flask API, data processing, alert engine, LLM client
frontend/        React app
data/raw/        original NASA files
data/processed/  cleaned CSVs + data quality report
```

## AI assistance disclosure
**During development:** parts of the code (Flask backend, React frontend, data processing)
and this README were written with help from AI assistants (ChatGPT and Claude). The team
reviewed, ran and tested the code.

**Inside the app:** an LLM (Google Gemini or Anthropic Claude, via their APIs) writes
plain-language explanations and answers questions in the Dashboard, My health and AI
assistant sections. The LLM never decides what is flagged. Voice input and read-aloud use the
browser's built-in Web Speech API. No AI-generated data is used in the NASA charts.
No NASA logos or branding are used.

## Credits
Data: NASA Open Science Data Repository, OSD-575.
Libraries: Flask, pandas, NumPy, requests, python-dotenv, React, Vite, Recharts.