// Code written with AI assistance (ChatGPT, Claude) and reviewed by the OrbitCare AI team.
import { useEffect, useRef, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ResponsiveContainer,
} from "recharts";
import { getJSON, postJSON, deleteJSON } from "../config";
import { startListening, speak, stopSpeaking, parseSpoken } from "../voice";

const SYMPTOMS = [
  "Headache",
  "Nausea",
  "Dizziness",
  "Muscle weakness",
  "Back pain",
  "Vision changes",
];

export default function MyHealth({ name }) {
  const [markers, setMarkers] = useState([]);
  const [values, setValues] = useState({});
  const [label, setLabel] = useState("");
  const [fatigue, setFatigue] = useState(3);
  const [mood, setMood] = useState(3);
  const [sleep, setSleep] = useState(7);
  const [symptoms, setSymptoms] = useState([]);
  const [notes, setNotes] = useState("");
  const [entries, setEntries] = useState([]);
  const [result, setResult] = useState(null);
  const [trendKey, setTrendKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [listening, setListening] = useState("");
  const [voiceMsg, setVoiceMsg] = useState("");
  const [autoSpeak, setAutoSpeak] = useState(false);
  const recRef = useRef(null);

  useEffect(() => {
    getJSON("/api/my/markers")
      .then((d) => {
        setMarkers(d.markers);
        setTrendKey(d.markers[0]?.key || "");
      })
      .catch(() => setError("Cannot reach Flask. Is python backend/app.py running?"));
  }, []);

  const loadEntries = () => {
    if (!name) {
      setEntries([]);
      return;
    }
    getJSON(`/api/my/entries?name=${encodeURIComponent(name)}`)
      .then((d) => setEntries(d.entries))
      .catch(() => {});
  };

  useEffect(() => {
    setResult(null);
    loadEntries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);

  const setValue = (key, v) => setValues((prev) => ({ ...prev, [key]: v }));

  const fillNormal = () => {
    const v = {};
    markers.forEach((m) => (v[m.key] = String(Number(m.nasa_mean.toPrecision(4)))));
    setValues(v);
  };

  const fillDemo = () => {
    const v = {};
    markers.forEach((m, i) => {
      let x = m.nasa_mean;
      if (i % 4 === 0) x *= 1.3;
      else if (i % 4 === 2) x *= 0.8;
      v[m.key] = String(Number(x.toPrecision(4)));
    });
    setValues(v);
  };

  const toggleSymptom = (s) =>
    setSymptoms((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));

  const listenFor = (target) => {
    if (listening) {
      recRef.current && recRef.current.stop();
      return;
    }
    setVoiceMsg("");
    setListening(target);
    recRef.current = startListening({
      onResult: (text) => {
        if (target === "notes") {
          setNotes((prev) => (prev ? prev + " " : "") + text);
          setVoiceMsg(`Added to notes: "${text}"`);
        } else {
          const parsed = parseSpoken(text, markers);
          const n = Object.keys(parsed).length;
          if (n === 0) {
            setVoiceMsg(`Heard: "${text}". No marker and number found. Try: "glucose 95 sodium 140".`);
          } else {
            setValues((prev) => ({ ...prev, ...parsed }));
            setVoiceMsg(`Heard: "${text}". Filled ${n} value(s). Please check them.`);
          }
        }
      },
      onError: (e) => setVoiceMsg("Voice problem: " + e),
      onEnd: () => setListening(""),
    });
  };

  const submit = async () => {
    setError("");
    if (!name) {
      setError("Enter your astronaut name or ID at the top and press Save first.");
      return;
    }
    const filled = Object.fromEntries(
      Object.entries(values).filter(([, v]) => v !== "" && !isNaN(Number(v)))
    );
    setBusy(true);
    try {
      const d = await postJSON("/api/my/entry", {
        name,
        label,
        values: filled,
        fatigue,
        mood,
        sleep_hours: sleep,
        symptoms,
        notes,
      });
      setResult(d);
      loadEntries();
      if (autoSpeak) speak(d.summary);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const resetHistory = async () => {
    if (!name) return;
    if (!window.confirm(`Delete all saved check-ins for ${name}?`)) return;
    try {
      await deleteJSON(`/api/my/entries?name=${encodeURIComponent(name)}`);
      setResult(null);
      setEntries([]);
    } catch (e) {
      setError(e.message);
    }
  };

  const meta = markers.find((m) => m.key === trendKey);
  const chartData = entries.map((e, i) => ({
    label: `${i + 1}. ${e.label || "check-in"}`,
    value: e.values?.[trendKey] ?? null,
  }));
  const flagged = result ? result.results.filter((r) => r.severity !== "normal") : [];

  return (
    <div>
      {error && <div className="error">{error}</div>}

      <div className="panel">
        <h2>My health: enter today's check-in {name ? `for ${name}` : ""}</h2>
        <p className="note">
          Enter only the blood values you have. Each check-in is saved, compared with NASA
          reference ranges and with your own earlier readings, then explained by the AI
          assistant. Use made-up demo values: do not enter real personal health data.
        </p>

        <div className="controls">
          <input
            className="text-input"
            placeholder="Label, e.g. Day 12"
            maxLength={30}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          <button className="btn small ghost" onClick={fillNormal}>
            Fill NASA average values
          </button>
          <button className="btn small ghost" onClick={fillDemo}>
            Fill demo values with changes
          </button>
          <button className="btn small ghost" onClick={() => setValues({})}>
            Clear
          </button>
          <button className="btn small" onClick={() => listenFor("values")}>
            {listening === "values" ? "Listening… (click to stop)" : "Speak values"}
          </button>
        </div>
        {voiceMsg && <p className="note">{voiceMsg}</p>}

        <div className="marker-grid">
          {markers.map((m) => (
            <label key={m.key} className="marker-input">
              <span>
                <b style={{ textTransform: "capitalize" }}>{m.label}</b>{" "}
                <span className="small">({m.unit})</span>
              </span>
              <input
                type="number"
                step="any"
                value={values[m.key] ?? ""}
                placeholder={`${m.ref_min} to ${m.ref_max}`}
                onChange={(e) => setValue(m.key, e.target.value)}
              />
              <span className="small">
                Lab range: {m.ref_min} to {m.ref_max}
              </span>
            </label>
          ))}
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
          placeholder="Optional notes (you can also use the microphone)…"
          value={notes}
          maxLength={500}
          onChange={(e) => setNotes(e.target.value)}
        />

        <div className="controls">
          <button className="btn" onClick={submit} disabled={busy}>
            {busy ? "Analysing…" : "Submit check-in"}
          </button>
          <button className="btn small" onClick={() => listenFor("notes")}>
            {listening === "notes" ? "Listening… (click to stop)" : "Speak notes"}
          </button>
          <label className="inline-check">
            <input type="checkbox" checked={autoSpeak}
              onChange={(e) => setAutoSpeak(e.target.checked)} />
            Read result aloud
          </label>
        </div>
      </div>

      {result && (
        <div className="panel">
          <h2>Result</h2>
          <div className={`status-big status-${result.status}`}>
            Status: <b>{result.status}</b>
            <span>
              {" "}
              ({result.counts.alert} alerts, {result.counts.watch} watch,{" "}
              {result.counts.normal} normal)
            </span>
          </div>

          <div className="ai-box">
            <span className={`ai-badge ${result.ai_used ? "on" : ""}`}>
              {result.ai_used
                ? `AI explanation (${result.provider})`
                : "Rule-based summary (AI not connected)"}
            </span>
            <p style={{ lineHeight: 1.55 }}>{result.summary}</p>
            <div className="controls">
              <button className="btn small" onClick={() => speak(result.summary)}>
                Read aloud
              </button>
              <button className="btn small ghost" onClick={stopSpeaking}>
                Stop
              </button>
            </div>
            {result.llm_error && <p className="note">AI unavailable: {result.llm_error}</p>}
          </div>

          {flagged.length === 0 && result.results.length > 0 && (
            <p className="note">All entered blood values look normal against the checks used.</p>
          )}
          {flagged.map((f) => (
            <div className="alert-row" key={f.key}>
              <span className={`badge ${f.severity}`}>{f.severity.toUpperCase()}</span>
              <div className="alert-body">
                <b>{f.label}</b>
                <div className="small">{f.reasons.join(" ")}</div>
              </div>
            </div>
          ))}
          <p className="note">
            Rule-based flags decide what is highlighted. The AI only explains them. This is a
            research prototype, not medical advice.
          </p>
        </div>
      )}

      {entries.length > 0 && (
        <div className="panel">
          <h2>My history ({entries.length} check-ins)</h2>
          <div className="controls">
            <select value={trendKey} onChange={(e) => setTrendKey(e.target.value)}>
              {markers.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label} ({m.unit})
                </option>
              ))}
            </select>
            <button className="btn small ghost" onClick={resetHistory}>
              Delete my history
            </button>
          </div>
          <div style={{ width: "100%", height: 300 }}>
            <ResponsiveContainer>
              <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#22305f" />
                <XAxis dataKey="label" stroke="#8f9bc4" />
                <YAxis stroke="#8f9bc4" domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "#111a33", border: "1px solid #2d3f7a" }} />
                {meta && (
                  <ReferenceArea
                    y1={meta.ref_min}
                    y2={meta.ref_max}
                    fill="#4ade80"
                    fillOpacity={0.12}
                    ifOverflow="extendDomain"
                  />
                )}
                <Line
                  type="linear"
                  dataKey="value"
                  name={meta?.label}
                  stroke="#4fc3f7"
                  strokeWidth={2.5}
                  dot={{ r: 4 }}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="note">Green band = lab reference range.</p>

          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Label</th>
                <th>Time</th>
                <th>Values</th>
                <th>Sleep</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {[...entries].reverse().map((e) => (
                <tr key={e.id}>
                  <td>{e.id}</td>
                  <td>{e.label || "-"}</td>
                  <td>{e.time.replace("T", " ")}</td>
                  <td>{Object.keys(e.values).length}</td>
                  <td>{e.sleep_hours} h</td>
                  <td>{e.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}