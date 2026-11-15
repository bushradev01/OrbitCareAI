import { useEffect, useState } from "react";
import { API, getJSON, POST_PHASES } from "../config";

const SYMPTOMS = [
  "Headache",
  "Nausea",
  "Dizziness",
  "Muscle weakness",
  "Back pain",
  "Vision changes",
];

export default function CheckIn() {
  const [crewList, setCrewList] = useState([]);
  const [crew, setCrew] = useState("");
  const [phase, setPhase] = useState("R+1");
  const [fatigue, setFatigue] = useState(3);
  const [mood, setMood] = useState(3);
  const [sleep, setSleep] = useState(7);
  const [symptoms, setSymptoms] = useState([]);
  const [notes, setNotes] = useState("");
  const [timeline, setTimeline] = useState([]);
  const [history, setHistory] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJSON("/api/crew")
      .then((d) => {
        setCrewList(d.crew);
        setCrew(d.crew[0] || "");
      })
      .catch(() => setError("Cannot reach Flask. Is python backend/app.py running?"));
  }, []);

  useEffect(() => {
    if (!crew) return;
    setResult(null);
    getJSON(`/api/crew-status/${encodeURIComponent(crew)}`)
      .then((d) => setTimeline(d.timeline))
      .catch(() => setError("Could not load crew status."));
    getJSON(`/api/checkins?crew=${encodeURIComponent(crew)}`)
      .then((d) => setHistory(d.checkins))
      .catch(() => {});
  }, [crew]);

  const toggleSymptom = (s) =>
    setSymptoms((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));

  const submit = async () => {
    setError("");
    try {
      const res = await fetch(`${API}/api/checkin`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          crew,
          phase,
          fatigue,
          mood,
          sleep_hours: sleep,
          symptoms,
          notes,
        }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || "Check-in failed");
      setResult(d);
      getJSON(`/api/checkins?crew=${encodeURIComponent(crew)}`)
        .then((h) => setHistory(h.checkins))
        .catch(() => {});
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div>
      {error && <div className="error">{error}</div>}

      {/* Biomarker status timeline */}
      <div className="panel">
        <h2>Biomarker status timeline for crew member {crew}</h2>
        <div className="phase-grid">
          {timeline.map((t) => (
            <div key={t.phase} className={`status-chip status-${t.status}`}>
              <b>{t.phase}</b>
              <span>{t.status}</span>
              <span>{t.flagged_percent}% flagged</span>
            </div>
          ))}
        </div>
        <p className="note">
          Combines all 4 NASA datasets. Status is the share of measured markers that deviate from
          this person's own pre-flight baseline: Stable under 5%, Monitor 5 to 15%, Review 15% or more.
          These are demo thresholds, not clinical limits.
        </p>
      </div>

      {/* Form */}
      <div className="panel">
        <h2>Astronaut check-in</h2>

        <div className="controls">
          <select value={crew} onChange={(e) => setCrew(e.target.value)}>
            {crewList.map((c) => (
              <option key={c} value={c}>
                Crew member {c}
              </option>
            ))}
          </select>
          <select value={phase} onChange={(e) => setPhase(e.target.value)}>
            {POST_PHASES.map((p) => (
              <option key={p} value={p}>
                Check-in at {p}
              </option>
            ))}
          </select>
        </div>

        <div className="form-grid">
          <label>
            Fatigue: <b>{fatigue}</b> / 5
            <input type="range" min="1" max="5" value={fatigue}
              onChange={(e) => setFatigue(Number(e.target.value))} />
          </label>
          <label>
            Mood: <b>{mood}</b> / 5 (5 = great)
            <input type="range" min="1" max="5" value={mood}
              onChange={(e) => setMood(Number(e.target.value))} />
          </label>
          <label>
            Sleep last night: <b>{sleep}</b> hours
            <input type="range" min="0" max="12" step="0.5" value={sleep}
              onChange={(e) => setSleep(Number(e.target.value))} />
          </label>
        </div>

        <p className="note" style={{ marginBottom: 6 }}>Symptoms today:</p>
        <div className="symptoms">
          {SYMPTOMS.map((s) => (
            <label key={s} className={`symptom ${symptoms.includes(s) ? "on" : ""}`}>
              <input type="checkbox" checked={symptoms.includes(s)}
                onChange={() => toggleSymptom(s)} />
              {s}
            </label>
          ))}
        </div>

        <textarea
          className="notes"
          placeholder="Optional notes…"
          value={notes}
          maxLength={500}
          onChange={(e) => setNotes(e.target.value)}
        />

        <button className="btn" onClick={submit}>
          Submit check-in
        </button>
      </div>

      {/* Result */}
      {result && (
        <div className="panel">
          <h2>Check-in result</h2>
          <div className={`status-big status-${result.biomarker_status.status}`}>
            Biomarker status at {result.record.phase}: <b>{result.biomarker_status.status}</b>
            <span>
              {" "}
              ({result.biomarker_status.alerts} alerts, {result.biomarker_status.watch} watch of{" "}
              {result.biomarker_status.markers_evaluated} markers)
            </span>
          </div>

          {result.self_report_flags.length > 0 && (
            <p className="note">
              Self-report flags: {result.self_report_flags.join(" · ")}
            </p>
          )}

          <p style={{ lineHeight: 1.5 }}>{result.message}</p>

          <h3 style={{ marginBottom: 6 }}>Top biomarker changes</h3>
          {result.biomarker_status.top_items.map((it) => (
            <div className="alert-row" key={it.dataset + it.marker}>
              <span className={`badge ${it.severity}`}>{it.severity.toUpperCase()}</span>
              <div className="alert-body">
                <b>{it.marker_label}</b>
                <div className="small">{it.reason}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div className="panel">
          <h2>Recent check-ins for {crew}</h2>
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Phase</th>
                <th>Fatigue</th>
                <th>Mood</th>
                <th>Sleep</th>
                <th>Biomarkers</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={i}>
                  <td>{h.time.replace("T", " ")}</td>
                  <td>{h.phase}</td>
                  <td>{h.fatigue}</td>
                  <td>{h.mood}</td>
                  <td>{h.sleep_hours} h</td>
                  <td>{h.biomarker_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}