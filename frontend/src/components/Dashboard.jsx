// Code written with AI assistance (ChatGPT, Claude) and reviewed by the OrbitCare AI team.
import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { getJSON, postJSON, PHASES, POST_PHASES, COLORS, prettyName } from "../config";

export default function Dashboard() {
  const [datasets, setDatasets] = useState([]);
  const [datasetId, setDatasetId] = useState("metabolic");
  const [biomarkers, setBiomarkers] = useState([]);
  const [marker, setMarker] = useState("");
  const [trend, setTrend] = useState(null);
  const [summary, setSummary] = useState(null);
  const [phase, setPhase] = useState("R+1");
  const [phaseCounts, setPhaseCounts] = useState({});
  const [quality, setQuality] = useState(null);
  const [error, setError] = useState("");
  const [insight, setInsight] = useState(null);
  const [insightBusy, setInsightBusy] = useState(false);

  // overview, phases, quality (once)
  useEffect(() => {
    getJSON("/api/overview")
      .then((d) => setDatasets(d.datasets))
      .catch(() => setError("Cannot reach Flask. Is python backend/app.py running?"));
    getJSON("/api/sample-phases").then((d) => setPhaseCounts(d.phase_counts)).catch(() => {});
    getJSON("/api/quality").then(setQuality).catch(() => {});
  }, []);

  // biomarker list when the dataset changes
  useEffect(() => {
    let cancelled = false;
    setTrend(null);
    setMarker("");
    setBiomarkers([]);
    setError("");
    getJSON(`/api/biomarkers/${datasetId}`)
      .then((d) => {
        if (cancelled) return;
        setBiomarkers(d.biomarkers);
        setMarker(d.biomarkers[0] || "");
      })
      .catch(() => !cancelled && setError("Could not load biomarkers."));
    return () => {
      cancelled = true;
    };
  }, [datasetId]);

  // summary table when dataset or phase changes
  useEffect(() => {
    let cancelled = false;
    getJSON(`/api/summary/${datasetId}?phase=${encodeURIComponent(phase)}`)
      .then((d) => {
        if (cancelled) return;
        setSummary(d);
        setError("");
      })
      .catch(() => !cancelled && setError("Could not load summary."));
    return () => {
      cancelled = true;
    };
  }, [datasetId, phase]);

  // trend chart (only when the marker belongs to the current dataset)
  useEffect(() => {
    if (!marker || !biomarkers.includes(marker)) return;
    let cancelled = false;
    getJSON(`/api/trend/${datasetId}/${encodeURIComponent(marker)}`)
      .then((d) => {
        if (cancelled) return;
        setTrend(d);
        setError("");
      })
      .catch(() => !cancelled && setError("Could not load trend."));
    return () => {
      cancelled = true;
    };
  }, [datasetId, marker, biomarkers]);

  // clear the AI explanation when the data on screen changes
  useEffect(() => {
    setInsight(null);
  }, [datasetId, phase]);

  const explainWithAI = async () => {
    if (!summary?.top_changes?.length) return;
    setInsightBusy(true);
    try {
      const d = await postJSON("/api/ai/insight", {
        dataset: datasets.find((x) => x.id === datasetId)?.name || datasetId,
        phase,
        changes: summary.top_changes,
      });
      setInsight(d);
    } catch (e) {
      setInsight({ text: "Could not get an explanation: " + e.message, ai_used: false });
    } finally {
      setInsightBusy(false);
    }
  };

  const chartData = trend
    ? trend.phases.map((p) => ({ phase: p.phase, Mean: p.mean, ...p.by_crew }))
    : [];
  const ref = trend?.reference_range;
  const oor = summary?.out_of_range_counts;
  const biggest = summary?.top_changes?.[0];

  return (
    <div>
      {error && <div className="error">{error}</div>}

      <div className="cards">
        {datasets.map((d) => (
          <div
            key={d.id}
            className={`card clickable ${d.id === datasetId ? "active" : ""}`}
            onClick={() => setDatasetId(d.id)}
          >
            <h3>{d.name}</h3>
            <div className="big">{d.records}</div>
            <div className="small">
              samples · {d.columns} columns · {d.available ? "available" : "missing"}
            </div>
          </div>
        ))}
      </div>

      {summary && (
        <div className="cards">
          <div className="card">
            <h3>Biomarkers measured</h3>
            <div className="big">{summary.total_biomarkers}</div>
            <div className="small">in this dataset</div>
          </div>
          <div className="card">
            <h3>With lab reference range</h3>
            <div className="big">{summary.markers_with_reference_range}</div>
            <div className="small">only the metabolic panel has ranges</div>
          </div>
          {biggest && (
            <div className="card">
              <h3>Biggest change at {phase}</h3>
              <div className="big">{Math.abs(biggest.pct_change)}%</div>
              <div className="small">{prettyName(biggest.column)}</div>
            </div>
          )}
        </div>
      )}

      <div className="panel">
        <h2>Mission timeline (samples per phase)</h2>
        <div className="phase-grid">
          {PHASES.map((p) => (
            <div key={p} className={`phase-chip ${p.startsWith("L") ? "pre" : "post"}`}>
              <b>{p}</b>
              <span>{phaseCounts[p] ?? 0} samples</span>
            </div>
          ))}
        </div>
        <p className="note">
          L = days before launch (green) · R = days after return to Earth (red)
        </p>
      </div>

      <div className="panel">
        <h2>Biomarker trend across the mission</h2>
        <div className="controls">
          <select value={marker} onChange={(e) => setMarker(e.target.value)}>
            {biomarkers.map((b) => (
              <option key={b} value={b}>
                {prettyName(b)}
              </option>
            ))}
          </select>
        </div>

        <div style={{ width: "100%", height: 380 }}>
          <ResponsiveContainer>
            <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#22305f" />
              <XAxis dataKey="phase" stroke="#8f9bc4" />
              <YAxis stroke="#8f9bc4" domain={["auto", "auto"]} />
              <Tooltip contentStyle={{ background: "#111a33", border: "1px solid #2d3f7a" }} />
              <Legend />
              {ref && ref.min !== null && ref.max !== null && (
                <ReferenceArea
                  y1={ref.min}
                  y2={ref.max}
                  fill="#4ade80"
                  fillOpacity={0.12}
                  ifOverflow="extendDomain"
                  label={{ value: "Reference range", fill: "#4ade80", fontSize: 11 }}
                />
              )}
              <ReferenceLine
                x="R+1"
                stroke="#ff6b6b"
                strokeDasharray="4 4"
                label={{ value: "Return to Earth", fill: "#ff6b6b", fontSize: 11 }}
              />
              {trend?.crew.map((c, i) => (
                <Line
                  key={c}
                  type="linear"
                  dataKey={c}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={1.5}
                  dot={{ r: 3 }}
                  connectNulls
                />
              ))}
              <Line
                type="linear"
                dataKey="Mean"
                stroke="#ffffff"
                strokeWidth={3}
                dot={{ r: 4 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="note">
          White line = crew average. Colored lines = individual crew members. Lines connect
          measured points only.
          {ref ? "" : " This dataset has no built-in reference range."}
        </p>
      </div>

      {oor && (
        <div className="panel">
          <h2>Out-of-range measurements per phase</h2>
          <div className="phase-grid">
            {PHASES.map((p) => (
              <div key={p} className={`phase-chip ${p.startsWith("L") ? "pre" : "post"}`}>
                <b>{oor[p]}</b>
                <span>{p}</span>
              </div>
            ))}
          </div>
          <p className="note">
            Counted across {summary.markers_with_reference_range} metabolic markers with a
            laboratory reference range. Some values are out of range even before launch, so
            these counts are not all caused by spaceflight.
          </p>
        </div>
      )}

      <div className="panel">
        <h2>AI insight</h2>
        <p className="note">
          An LLM explains the table of biggest changes below in plain language. The numbers come
          from the NASA data. The AI only explains them.
        </p>
        <div className="controls">
          <button className="btn" onClick={explainWithAI} disabled={insightBusy || !summary}>
            {insightBusy ? "Thinking…" : "Explain with AI"}
          </button>
        </div>
        {insight && (
          <div className="ai-box">
            <span className={`ai-badge ${insight.ai_used ? "on" : ""}`}>
              {insight.ai_used
                ? `AI explanation (${insight.provider})`
                : "Rule-based summary (AI not connected)"}
            </span>
            <p style={{ lineHeight: 1.55 }}>{insight.text}</p>
            {insight.llm_error && <p className="note">AI unavailable: {insight.llm_error}</p>}
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Biggest changes vs pre-flight baseline (crew average)</h2>
        <div className="controls">
          <select value={phase} onChange={(e) => setPhase(e.target.value)}>
            {POST_PHASES.map((p) => (
              <option key={p} value={p}>
                Compare {p} with baseline
              </option>
            ))}
          </select>
        </div>
        <table>
          <thead>
            <tr>
              <th>Biomarker</th>
              <th>Baseline (L-92, L-44, L-3)</th>
              <th>{phase}</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            {summary?.top_changes?.map((c) => (
              <tr className="row" key={c.column} onClick={() => setMarker(c.column)}>
                <td>{prettyName(c.column)}</td>
                <td>{c.baseline}</td>
                <td>{c.phase_mean}</td>
                <td className={c.pct_change > 0 ? "up" : "down"}>
                  {c.pct_change > 0 ? "▲" : "▼"} {Math.abs(c.pct_change)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note">Click a row to see its trend in the chart above.</p>
      </div>

      {quality?.available && (
        <div className="panel">
          <h2>Data quality report</h2>
          <table>
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Samples</th>
                <th>Columns</th>
                <th>Missing values</th>
                <th>Empty columns</th>
                <th>Duplicate rows</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(quality.report).map(([id, r]) => (
                <tr key={id}>
                  <td>{id}</td>
                  <td>{r.samples}</td>
                  <td>{r.columns}</td>
                  <td>{r.missing_percent}%</td>
                  <td>{r.fully_empty_columns}</td>
                  <td>{r.duplicate_rows}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="note">Missing values are left empty. Nothing is estimated or invented.</p>
        </div>
      )}
    </div>
  );
}