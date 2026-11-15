import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { getJSON, POST_PHASES } from "../config";

function recoveryText(v) {
  if (v === true) return "Back to baseline by R+194";
  if (v === false) return "Still different at R+194";
  return "No R+194 value";
}

export default function Alerts() {
  const [crewList, setCrewList] = useState([]);
  const [crew, setCrew] = useState("");
  const [datasets, setDatasets] = useState([]);
  const [datasetId, setDatasetId] = useState("metabolic");
  const [phase, setPhase] = useState("R+1");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getJSON("/api/crew")
      .then((d) => {
        setCrewList(d.crew);
        setCrew(d.crew[0] || "");
      })
      .catch(() => setError("Cannot reach Flask. Is python backend/app.py running?"));
    getJSON("/api/overview").then((d) => setDatasets(d.datasets)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!crew) return;
    setLoading(true);
    getJSON(
      `/api/alerts/${datasetId}?crew=${encodeURIComponent(crew)}&phase=${encodeURIComponent(phase)}`
    )
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch(() => setError("Could not load alerts."))
      .finally(() => setLoading(false));
  }, [crew, datasetId, phase]);

  const current = data?.by_phase?.find((p) => p.phase === phase);

  return (
    <div>
      {error && <div className="error">{error}</div>}

      <div className="panel">
        <h2>Crew alerts: each astronaut vs their own baseline</h2>
        <div className="controls">
          <select value={crew} onChange={(e) => setCrew(e.target.value)}>
            {crewList.map((c) => (
              <option key={c} value={c}>
                Crew member {c}
              </option>
            ))}
          </select>
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
          <select value={phase} onChange={(e) => setPhase(e.target.value)}>
            {POST_PHASES.map((p) => (
              <option key={p} value={p}>
                Phase {p}
              </option>
            ))}
          </select>
        </div>

        {current && (
          <div className="cards">
            <div className="card">
              <h3>Alerts at {phase}</h3>
              <div className="big" style={{ color: "#ff6b6b" }}>{current.alert}</div>
              <div className="small">of {current.evaluated} markers measured</div>
            </div>
            <div className="card">
              <h3>Watch at {phase}</h3>
              <div className="big" style={{ color: "#ffb74d" }}>{current.watch}</div>
              <div className="small">smaller deviations</div>
            </div>
            <div className="card">
              <h3>Recovered by R+194</h3>
              <div className="big" style={{ color: "#4ade80" }}>{data.recovery.recovered}</div>
              <div className="small">
                {data.recovery.not_recovered} still different (among shown flags)
              </div>
            </div>
          </div>
        )}

        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer>
            <BarChart data={data?.by_phase || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#22305f" />
              <XAxis dataKey="phase" stroke="#8f9bc4" />
              <YAxis stroke="#8f9bc4" allowDecimals={false} />
              <Tooltip contentStyle={{ background: "#111a33", border: "1px solid #2d3f7a" }} />
              <Legend />
              <Bar dataKey="alert" name="Alert" stackId="a" fill="#ff6b6b" />
              <Bar dataKey="watch" name="Watch" stackId="a" fill="#ffb74d" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="note">Flags per phase for {crew || "…"} in the selected dataset.</p>
      </div>

      <div className="panel">
        <h2>
          Flagged biomarkers at {phase}
          {data ? ` (${data.total_flagged} total, top ${data.items.length} shown)` : ""}
        </h2>
        {loading && <p className="note">Loading…</p>}
        {data?.items?.length === 0 && (
          <p className="note">No alerts or watch items for this selection.</p>
        )}
        {data?.items?.map((it) => (
          <div className="alert-row" key={it.marker + it.phase}>
            <span className={`badge ${it.severity}`}>{it.severity.toUpperCase()}</span>
            <div className="alert-body">
              <b>{it.marker_label}</b>
              <div className="small">{it.reason}</div>
              <div className="small tag">{recoveryText(it.recovered_by_end)}</div>
            </div>
          </div>
        ))}
      </div>

      {data?.method && (
        <div className="panel">
          <h2>How these alerts are decided</h2>
          <p className="note">
            <b>Baseline:</b> {data.method.baseline}.
          </p>
          <p className="note">
            <b>Alert:</b> {data.method.alert}.
          </p>
          <p className="note">
            <b>Watch:</b> {data.method.watch}.
          </p>
          <p className="note">
            This is rule-based and fully explainable. With only 3 pre-flight samples per person,
            some flags can happen by chance, so treat them as prompts for review, not diagnoses.
          </p>
        </div>
      )}
    </div>
  );
}