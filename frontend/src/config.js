// Code written with AI assistance (ChatGPT, Claude) and reviewed by the OrbitCare AI team.
export const API = "http://localhost:5000";

export const PHASES = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"];
export const POST_PHASES = ["R+1", "R+45", "R+82", "R+194"];

export const COLORS = ["#4fc3f7", "#ffb74d", "#ba68c8", "#81c784", "#f06292", "#fff176"];

export const prettyName = (col) => col.replace(/_/g, " ");

export async function getJSON(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error("Request failed: " + path);
  return res.json();
}

export async function postJSON(path, body) {
  const res = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

export async function deleteJSON(path) {
  const res = await fetch(API + path, { method: "DELETE" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}