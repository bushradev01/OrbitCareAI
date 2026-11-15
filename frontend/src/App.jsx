// Code written with AI assistance (ChatGPT, Claude) and reviewed by the OrbitCare AI team.
import { useState } from "react";
import Dashboard from "./components/Dashboard";
import Alerts from "./components/Alerts";
import CheckIn from "./components/CheckIn";
import MyHealth from "./components/MyHealth";
import Assistant from "./components/Assistant";
import "./App.css";

const TABS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "alerts", label: "Crew alerts" },
  { id: "checkin", label: "NASA crew check-in" },
  { id: "myhealth", label: "My health (live)" },
  { id: "assistant", label: "AI assistant" },
];

function loadName() {
  try {
    return localStorage.getItem("orbitcare_name") || "";
  } catch {
    return "";
  }
}

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const [name, setName] = useState(loadName());
  const [draft, setDraft] = useState(name);

  const saveName = () => {
    const n = draft.trim();
    setName(n);
    try {
      localStorage.setItem("orbitcare_name", n);
    } catch {
      /* ignore */
    }
  };

  const needsName = tab === "myhealth" || tab === "assistant";

  return (
    <div className="app">
      <div className="header">
        <h1>
          Orbit<span>Care</span> AI
        </h1>
        <p>
          Astronaut health monitoring built on real NASA OSDR data (OSD-575). Rule-based flags,
          explained by an AI assistant.
        </p>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {needsName && (
        <div className="name-bar">
          <label>
            Astronaut name or ID:
            <input
              className="text-input"
              value={draft}
              maxLength={40}
              placeholder="e.g. Astronaut-1"
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveName()}
            />
          </label>
          <button className="btn small" onClick={saveName}>
            Save
          </button>
          <span className="small">{name ? `Active profile: ${name}` : "No profile saved yet"}</span>
        </div>
      )}

      {tab === "dashboard" && <Dashboard />}
      {tab === "alerts" && <Alerts />}
      {tab === "checkin" && <CheckIn />}
      {tab === "myhealth" && <MyHealth name={name} />}
      {tab === "assistant" && <Assistant name={name} />}

      <div className="panel" style={{ marginTop: 20 }}>
        <h2>Research limitations</h2>
        <p className="note" style={{ fontSize: "0.9rem" }}>
          The NASA dataset has only 4 crew members (about 28 samples per panel). Flags are
          rule-based and descriptive, not diagnoses. The AI assistant only explains what the
          rules found and can make mistakes. OrbitCare AI is a research prototype and not a
          medical device.
        </p>
      </div>
    </div>
  );
}