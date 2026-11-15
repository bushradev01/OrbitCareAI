// Code written with AI assistance (ChatGPT, Claude) and reviewed by the OrbitCare AI team.
// Uses the browser's built-in Web Speech API (works best in Chrome or Edge).

export function speechSupported() {
  return typeof window !== "undefined" &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function startListening({ onResult, onEnd, onError, lang = "en-US" }) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    onError && onError("Voice input is not supported in this browser. Use Chrome or Edge.");
    onEnd && onEnd();
    return null;
  }
  const rec = new SR();
  rec.lang = lang;
  rec.interimResults = false;
  rec.continuous = false;
  rec.onresult = (e) => {
    const text = Array.from(e.results).map((r) => r[0].transcript).join(" ");
    onResult && onResult(text);
  };
  rec.onerror = (e) => onError && onError(e.error || "voice error");
  rec.onend = () => onEnd && onEnd();
  try {
    rec.start();
  } catch (err) {
    onError && onError("Could not start the microphone.");
    onEnd && onEnd();
    return null;
  }
  return rec;
}

export function speak(text, lang = "en-US") {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const clean = String(text).replace(/[*#_`]/g, "");
  const u = new SpeechSynthesisUtterance(clean);
  u.lang = lang;
  u.rate = 1;
  window.speechSynthesis.speak(u);
}

export function stopSpeaking() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

// "glucose 95 sodium 140" -> { glucose_column_key: "95", sodium_column_key: "140" }
export function parseSpoken(text, markers) {
  const t = String(text).toLowerCase().replace(/,/g, "");
  const out = {};
  markers.forEach((m) => {
    const label = m.label.toLowerCase();
    const idx = t.indexOf(label);
    if (idx < 0) return;
    const after = t.slice(idx + label.length, idx + label.length + 25);
    const num = after.match(/-?\d+(\.\d+)?/);
    if (num) out[m.key] = num[0];
  });
  return out;
}