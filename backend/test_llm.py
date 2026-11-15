# Code written with AI assistance (ChatGPT, Claude) and reviewed by the OrbitCare AI team.
import os
import requests
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
print("\n===== OrbitCare AI: LLM TEST =====")
print(".env file exists:", os.path.exists(env_path))
load_dotenv(env_path)

provider = os.getenv("LLM_PROVIDER", "")
gem = os.getenv("GEMINI_API_KEY", "")
ant = os.getenv("ANTHROPIC_API_KEY", "")
print("LLM_PROVIDER      :", repr(provider))
print("GEMINI_API_KEY    :", f"set, {len(gem)} characters" if gem else "NOT SET")
print("ANTHROPIC_API_KEY :", f"set, {len(ant)} characters" if ant else "NOT SET")
print("GEMINI_MODEL      :", repr(os.getenv("GEMINI_MODEL", "")))

if gem and (gem != gem.strip() or '"' in gem or "'" in gem):
    print("WARNING: the Gemini key has spaces or quotes. Remove them in .env")

if provider.strip().lower() == "gemini" or (gem and not ant):
    print("\n--- Models your Gemini key can use ---")
    try:
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": gem.strip()},
            params={"pageSize": 100},
            timeout=30,
        )
        print("HTTP status:", r.status_code)
        if r.status_code == 200:
            names = []
            for m in r.json().get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    names.append(m["name"].replace("models/", ""))
            flash = [n for n in names if "flash" in n]
            print("Flash models:", flash if flash else "none found")
            print("All text models (first 25):", names[:25])

            pick = None
            wanted = os.getenv("GEMINI_MODEL", "").strip()
            if wanted in names:
                pick = wanted
            elif flash:
                pick = flash[0]
            elif names:
                pick = names[0]

            if pick:
                print(f"\n--- Test call with model: {pick} ---")
                r2 = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{pick}:generateContent",
                    headers={"x-goog-api-key": gem.strip(), "Content-Type": "application/json"},
                    json={"contents": [{"role": "user", "parts": [{"text": "Say hello in 5 words."}]}]},
                    timeout=40,
                )
                print("HTTP status:", r2.status_code)
                print("Reply:", r2.text[:400])
                if r2.status_code == 200:
                    print(f"\nSUCCESS. Put this line in backend/.env:\nGEMINI_MODEL={pick}")
        else:
            print("Error:", r.text[:400])
    except Exception as e:
        print("Network problem:", e)

if provider.strip().lower() == "anthropic" or (ant and not gem):
    print("\n--- Test call to Claude ---")
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ant.strip(),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": model, "max_tokens": 50,
                  "messages": [{"role": "user", "content": "Say hello in 5 words."}]},
            timeout=40,
        )
        print("Model:", model)
        print("HTTP status:", r.status_code)
        print("Reply:", r.text[:400])
    except Exception as e:
        print("Network problem:", e)

print("\n===== END =====\n")