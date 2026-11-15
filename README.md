# OrbitCare AI

**Explainable astronaut health monitoring built on real NASA OSD-575 data.**
Rules decide what is flagged. An LLM explains the results in plain language.

Built for the **NASA Space Apps Challenge** by team **<Bushra Ashraf Bhatti>**.

## Demo

- **Demo slides (7 slides):** https://docs.google.com/presentation/d/1nBFrgbh5v5TczuTIJIpIrpWOaB1nCSig/edit?usp=sharing
- **Source code:** https://github.com/YOURNAME/OrbitCareAI

![Dashboard](docs/images/dashboard.png)

## Table of contents

1. [Why OrbitCare AI](#why-orbitcare-ai)
2. [Features](#features)
3. [Screenshots](#screenshots)
4. [NASA data](#nasa-data)
5. [How it works](#how-it-works)
6. [Alert rules](#alert-rules)
7. [Architecture](#architecture)
8. [Folder structure](#folder-structure)
9. [API endpoints](#api-endpoints)
10. [Installation and setup](#installation-and-setup)
11. [Configuring the AI](#configuring-the-ai)
12. [Limitations](#limitations)
13. [AI assistance disclosure](#ai-assistance-disclosure)
14. [Credits and references](#credits-and-references)

## Why OrbitCare AI

On long space missions, real-time medical support from Earth is limited, and spaceflight
blood data is stored in large spreadsheets with hundreds of columns. OrbitCare AI turns NASA's
published data into clear, explainable monitoring, and lets astronauts track their own values
over time.

We chose **transparent rules over a black-box model**. The NASA dataset covers only four crew
members, so a machine-learning model would not be reliable, and in a health setting every flag
should be explainable.

## Features

| Section | What it does |
|---|---|
| **Dashboard** | Explore 4 NASA biomarker panels across 7 mission phases, with lab reference ranges, crew average and per-astronaut lines, biggest changes vs. pre-flight baseline, a data-quality report, and an AI explanation of the table. |
| **Crew alerts** | Compares each NASA crew member with their own pre-flight baseline. Flags are labelled Alert or Watch, with a plain-language reason and a recovery check at R+194. |
| **NASA crew check-in** | Combines a short self-report (fatigue, mood, sleep, symptoms) with the biomarker status of a NASA crew member at a chosen phase. |
| **My health (live)** | An astronaut enters their own blood values and symptoms by typing or voice. Entries are saved, compared with NASA lab reference ranges and the astronaut's own history, and explained by an LLM. |
| **AI assistant** | Chat about the latest saved check-in, with voice input and read-aloud. Emergency wording gets a fixed safety message instead of an LLM answer. |

## Screenshots

### Dashboard
![Dashboard] <img width="1410" height="858" alt="image" src="https://github.com/user-attachments/assets/36829321-e791-4571-a157-8f1f6837e3f5" />


### AI insight
![AI insight](docs/images/ai-insight.png)

### Crew alerts
![Crew alerts](docs/images/crew-alerts.png)

### NASA crew check-in
![NASA crew check-in](docs/images/crew-checkin.png)

### My health (live)
![My health](docs/images/my-health.png)

### My health result with AI explanation
![My health result](docs/images/my-health-result.png)

### AI assistant
![AI assistant](docs/images/assistant.png)

## NASA data

- **Source:** NASA Open Science Data Repository (OSDR), study **OSD-575**
  (https://osdr.nasa.gov/bio/repo/data/studies/OSD-575)
- **Panels used:** Comprehensive Metabolic Panel, Cardiovascular Eve panel, Immune Eve panel,
  Immune Alamar panel (the `*_TRANSFORMED.csv` files)
- **Size:** 28 samples per panel (27 for Alamar) from 4 crew members
- **Mission phases:** L-92, L-44, L-3 (before launch) and R+1, R+45, R+82, R+194
  (days after return)
- **Processing:** `backend/process_data.py` cleans column names, converts numeric text, checks
  for missing values, duplicates and unknown phases, and writes cleaned files plus a quality
  report to `data/processed/`. Missing values stay empty. Nothing is estimated or invented.
- Original files are kept unchanged in `data/raw/`.

## How it works

```
NASA OSD-575 data --> Python cleaning --> Flask API --> React app
                                              |
                          Rule engine (decides Alert / Watch / Stable)
                                              |
                          LLM (explains the flags in plain language)
```

- **NASA data** provides lab reference ranges and the crew's pre-flight values.
- **Rules (statistics)** decide what is flagged. They are fully explainable.
- **The LLM** writes explanations and answers questions using only the results it is given.
  It never decides what is flagged.
- **Fallback:** if no API key is set or the AI service is busy, the app shows a rule-based
  summary and says so.
- **Safety:** messages mentioning emergencies (for example chest pain) get a fixed message
  telling the user to contact the flight surgeon or emergency services.

## Alert rules

**Crew alerts (NASA crew):** each astronaut is compared with their own pre-flight mean
(L-92, L-44, L-3).

- `z = (value - baseline) / spread`, where spread = max(std of pre-flight samples, 5% of baseline)
- **Alert:** |z| >= 3 and change >= 10%, or a new value outside the lab reference range
- **Watch:** |z| >= 2 and change >= 5%, or still outside the lab reference range
- **Recovery:** a marker counts as recovered if the R+194 value is within 2 spread units of baseline
- **Phase status:** Stable (under 5% of markers flagged), Monitor (5 to 15%), Review (15% or more)

**My health (live entries):**

- Outside the lab range: Watch, or Alert if beyond the range by 20% of its width or more
- Change of 10% or more vs. the astronaut's own earlier entries: Watch; 20% or more: Alert
- Far from the NASA crew pre-flight average (|z| >= 3): Watch
- Overall status: Review (any alert, or 3 or more watch items), Monitor (any watch), Stable

All thresholds are **demo values, not clinical limits**.

## Architecture

| Layer | Technology |
|---|---|
| Data processing | Python, pandas, NumPy |
| Backend API | Flask, Flask-CORS |
| LLM client | `requests`, Google Gemini API or Anthropic Claude API, python-dotenv |
| Frontend | React (Vite), Recharts |
| Voice | Browser Web Speech API (speech recognition and speech synthesis) |
| Storage | JSON files created at runtime (not committed) |

## Folder structure

```
OrbitCareAI/
├── README.md                     Project documentation (this file)
├── requirements.txt              Python dependencies
├── .gitignore                    Keeps keys, environments and user entries out of Git
│
├── backend/
│   ├── app.py                    Flask app: data, trend, summary, alerts, NASA crew check-in routes
│   ├── assistant.py              Live check-ins, rule evaluation, AI chat and AI insight routes
│   ├── llm.py                    LLM client (Gemini / Claude) with retries, model fallback
│   ├── process_data.py           Cleans NASA files, writes data/processed + quality report
│   ├── inspect_data.py           Prints columns and samples of each dataset (exploration)
│   ├── test_llm.py               Tests the API key and lists models the key can use
│   └── .env                      API key (create it yourself; NOT in the repository)
│
├── data/
│   ├── raw/                      Original NASA OSD-575 files (unchanged)
│   │   ├── LSDS-8_*_TRANSFORMED.csv     Processed panels used by the app
│   │   ├── LSDS-8_*_SUBMITTED.*         Submitted versions of the panels
│   │   ├── a_OSD-575_*.txt              Assay metadata
│   │   ├── i_Investigation.txt          Study investigation metadata
│   │   ├── s_OSD-575.txt                Sample metadata
│   │   └── OSD-575_metadata_OSD-575-ISA.zip
│   ├── processed/                Created by process_data.py
│   │   ├── metabolic_clean.csv
│   │   ├── cardiovascular_clean.csv
│   │   ├── immune_eve_clean.csv
│   │   ├── immune_alamar_clean.csv
│   │   └── data_quality_report.json
│   ├── astronaut_entries.json    Created at runtime (live check-ins; not committed)
│   └── checkins.json             Created at runtime (NASA crew check-ins; not committed)
│
├── docs/
│   └── images/                   Screenshots used in this README
│       ├── dashboard.png
│       ├── ai-insight.png
│       ├── crew-alerts.png
│       ├── crew-checkin.png
│       ├── my-health.png
│       ├── my-health-result.png
│       └── assistant.png
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── public/
    └── src/
        ├── main.jsx              App entry point
        ├── App.jsx               Tabs and astronaut profile bar
        ├── App.css               Styles
        ├── index.css             Page background
        ├── config.js             API address, shared constants and fetch helpers
        ├── voice.js              Voice input, read-aloud, spoken-value parsing
        └── components/
            ├── Dashboard.jsx     NASA data dashboard + AI insight
            ├── Alerts.jsx        Crew alerts
            ├── CheckIn.jsx       NASA crew check-in
            ├── MyHealth.jsx      Live data entry, results, history
            └── Assistant.jsx     AI chat
```

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/overview` | Datasets, sample and column counts |
| GET | `/api/dataset/<id>` | Cleaned dataset records |
| GET | `/api/sample-phases` | Samples per mission phase |
| GET | `/api/quality` | Data-quality report |
| GET | `/api/crew` | Crew member IDs |
| GET | `/api/biomarkers/<id>` | Biomarker columns of a dataset |
| GET | `/api/trend/<id>/<column>` | Values per phase, per crew member, with reference range |
| GET | `/api/summary/<id>?phase=R+1` | Biggest changes vs. pre-flight baseline, out-of-range counts |
| GET | `/api/alerts/<id>?crew=C001&phase=R+1` | Alerts and watch items with reasons |
| GET | `/api/crew-status/<crew>` | Status timeline for a NASA crew member |
| POST | `/api/checkin` | NASA crew check-in |
| GET | `/api/my/markers` | Markers available for live entry |
| POST | `/api/my/entry` | Save a live check-in, evaluate it, explain it |
| GET / DELETE | `/api/my/entries?name=...` | Read or delete a saved history |
| POST | `/api/assistant/chat` | AI assistant chat |
| POST | `/api/ai/insight` | AI explanation of the Dashboard table |
| GET | `/api/assistant/status` | Whether an LLM key is configured |

## Installation and setup

**Requirements:** Python 3.10 or newer, Node.js 18 or newer, Git, and Chrome or Edge (for voice).

```bash
# 1. clone
git clone https://github.com/YOURNAME/OrbitCareAI.git
cd OrbitCareAI

# 2. backend
python -m venv .venv
.venv\Scripts\activate            # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python backend/process_data.py    # cleans the data -> data/processed
python backend/app.py             # http://localhost:5000
```

Open a **second terminal**:

```bash
# 3. frontend
cd OrbitCareAI/frontend
npm install
npm install recharts
npm run dev                       # http://localhost:5173
```

Open http://localhost:5173 in Chrome.

The NASA files are included in `data/raw/`. If you use your own copy, download the OSD-575
files from NASA OSDR and place them there.

## Configuring the AI

The app works without an API key (rule-based text is used), but the AI explanations and
assistant need one. Create `backend/.env` (never commit it):

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-3.8-flash
```

or

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key
```

Restart the backend after changing `.env`. Model names change over time: run
`python backend/test_llm.py` to list the models your key can use. If a model is busy, the
client retries and tries other models automatically.

Open `http://localhost:5000/api/assistant/status` to check that a key is detected.

## Limitations

- The NASA dataset has only **4 crew members**, so it cannot support a reliable predictive
  model. Results are descriptive, not proof.
- With 3 pre-flight samples per person, some flags can occur by chance.
- Only the metabolic panel has lab reference ranges, so live entry covers those markers.
- Thresholds and status labels are demo values, not clinical limits.
- The LLM can make mistakes. OrbitCare AI is a **research prototype, not a medical device**,
  and is not for diagnosis or treatment.
- Do not enter real personal health data: values are sent to the LLM provider you configure.
- Voice features depend on the browser (Chrome or Edge recommended).

## AI assistance disclosure

**During development:** parts of the code (Flask backend, React frontend, data processing)
and this README were written with help from AI assistants (ChatGPT and Claude). The team
reviewed, ran and tested the code.

**Inside the app:** an LLM (Google Gemini or Anthropic Claude, through their APIs) writes
plain-language explanations and answers questions in the Dashboard, My health and AI assistant
sections. The LLM never decides what is flagged. Voice input and read-aloud use the browser's
built-in Web Speech API.

No AI-generated data is used in the NASA charts. No NASA logos or branding are used.

## Credits and references

- **Data:** NASA Open Science Data Repository, OSD-575 (https://osdr.nasa.gov)
- **Libraries:** [Flask](https://flask.palletsprojects.com), [pandas](https://pandas.pydata.org),
  NumPy, requests, python-dotenv, [React](https://react.dev), [Vite](https://vite.dev),
  [Recharts](https://recharts.org)
- **AI services:** [Google Gemini API](https://ai.google.dev),
  [Anthropic API](https://docs.anthropic.com)
- **Browser API:** [Web Speech API](https://developer.mozilla.org/docs/Web/API/Web_Speech_API)

---

*OrbitCare AI is a research prototype created for the NASA Space Apps Challenge. It is not
affiliated with or endorsed by NASA.*
