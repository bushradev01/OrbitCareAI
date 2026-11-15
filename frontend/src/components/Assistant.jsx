// Code written with AI assistance (ChatGPT, Claude) and reviewed by the OrbitCare AI team.
import { useEffect, useRef, useState } from "react";
import { getJSON, postJSON } from "../config";
import { startListening, speak, stopSpeaking } from "../voice";

const SUGGESTIONS = [
  "Explain my latest results in simple words",
  "What could explain my fatigue?",
  "What does a high glucose value mean?",
  "What should I discuss with the flight surgeon?",
];

export default function Assistant({ name }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hi, I am OrbitCare Assistant. Submit a check-in on the My health tab, then ask me about your results. You can type or use the microphone.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState(null);
  const [voiceMsg, setVoiceMsg] = useState("");
  const recRef = useRef(null);
  const endRef = useRef(null);

  useEffect(() => {
    getJSON("/api/assistant/status").then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    endRef.current && endRef.current.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    const next = [...messages, { role: "user", content: q }];
    setMessages(next);
    setInput("");
    setBusy(true);
    try {
      const history = next.slice(-10).map((m) => ({ role: m.role, content: m.content }));
      const d = await postJSON("/api/assistant/chat", { name, messages: history });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: d.reply,
          ai_used: d.ai_used,
          provider: d.provider,
          note: d.llm_error,
          emergency: d.emergency,
        },
      ]);
      if (autoSpeak) speak(d.reply);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I could not reach the server. Is the Flask backend running?" },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const listen = () => {
    if (listening) {
      recRef.current && recRef.current.stop();
      return;
    }
    setVoiceMsg("");
    setListening(true);
    recRef.current = startListening({
      onResult: (text) => send(text),
      onError: (e) => setVoiceMsg("Voice problem: " + e),
      onEnd: () => setListening(false),
    });
  };

  return (
    <div>
      <div className="panel">
        <h2>AI assistant {name ? `for ${name}` : ""}</h2>
        <p className="note">
          {status?.configured
            ? `Connected to an LLM (${status.provider}). Answers use your latest saved check-in as context.`
            : "No LLM key found in backend/.env, so answers fall back to a simple rule-based text."}{" "}
          It is not a doctor and does not diagnose.
        </p>

        <div className="chat-box">
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role} ${m.emergency ? "emergency" : ""}`}>
              {m.content}
              {m.role === "assistant" && i > 0 && (
                <div className="bubble-meta">
                  {m.emergency
                    ? "Safety message"
                    : m.ai_used
                    ? `AI (${m.provider})`
                    : "Rule-based fallback"}
                  {" · "}
                  <span className="link" onClick={() => speak(m.content)}>
                    read aloud
                  </span>
                  {m.note && <div>AI unavailable: {m.note}</div>}
                </div>
              )}
            </div>
          ))}
          {busy && <div className="bubble assistant">Thinking…</div>}
          <div ref={endRef} />
        </div>

        <div className="chips">
          {SUGGESTIONS.map((s) => (
            <span key={s} className="chip" onClick={() => send(s)}>
              {s}
            </span>
          ))}
        </div>

        <div className="chat-input">
          <input
            className="text-input"
            style={{ flex: 1 }}
            placeholder="Ask about your results…"
            value={input}
            maxLength={500}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button className="btn small" onClick={() => send()} disabled={busy}>
            Send
          </button>
          <button className="btn small" onClick={listen}>
            {listening ? "Listening…" : "Speak"}
          </button>
          <button className="btn small ghost" onClick={stopSpeaking}>
            Stop voice
          </button>
        </div>
        {voiceMsg && <p className="note">{voiceMsg}</p>}
        <label className="inline-check" style={{ marginTop: 8 }}>
          <input type="checkbox" checked={autoSpeak}
            onChange={(e) => setAutoSpeak(e.target.checked)} />
          Read every answer aloud
        </label>
      </div>
    </div>
  );
}