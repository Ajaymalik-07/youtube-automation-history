"""
LLM fallback chain — used when Gemini has no key or every Gemini model is
out of quota. All three speak the OpenAI chat-completions format.

  groq          free key   · very fast Llama models
  openrouter    free key   · ":free" community models
  pollinations  keyless    · last resort so the pipeline never dead-ends
"""
import time
import sys
import urllib.parse
import requests

import config
from apis.http import post_json

# Ensure stdout/stderr handles Unicode on Windows without crashing
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _real_key(value: str) -> bool:
    return bool(value) and not value.upper().startswith("YOUR_")


def providers() -> list:
    """(name, url, model, headers) for each usable fallback, in order."""
    out = []
    groq = getattr(config, "GROQ_API_KEY", "")
    if _real_key(groq):
        out.append(("groq", "https://api.groq.com/openai/v1/chat/completions",
                    getattr(config, "GROQ_MODEL", "llama-3.3-70b-versatile"),
                    {"Authorization": f"Bearer {groq}"}))
    orouter = getattr(config, "OPENROUTER_API_KEY", "")
    if _real_key(orouter):
        out.append(("openrouter", "https://openrouter.ai/api/v1/chat/completions",
                    getattr(config, "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
                    {"Authorization": f"Bearer {orouter}",
                     "HTTP-Referer": "https://github.com/raunakpatil/youtube-agentic-ai-studio",
                     "X-Title": "YT Agentic Studio"}))
    if getattr(config, "KEYLESS_LLM_FALLBACK", True):
        out.append(("pollinations", "https://text.pollinations.ai/openai", "openai", {}))
    return out


def chat(prompt: str, temperature: float = 0.9) -> str:
    errors = []
    for name, url, model, headers in providers():
        for attempt in range(2):
            try:
                print(f"   -> Fallback LLM: {name} ({model})...")
                d = post_json(url, {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                }, timeout=120, headers=headers)
                text = (d["choices"][0]["message"].get("content") or "").strip()
                if text:
                    return text
                errors.append(f"{name}: empty response")
                break
            except Exception as e:
                msg = str(e)
                # If Pollinations POST fails, try direct GET as a resilient alternative
                if name == "pollinations":
                    try:
                        print("   -> Trying Pollinations direct GET endpoint...")
                        encoded = urllib.parse.quote(prompt[:1000])
                        r = requests.get(f"https://text.pollinations.ai/{encoded}", timeout=60)
                        if r.status_code == 200 and r.text.strip():
                            return r.text.strip()
                    except Exception as ge:
                        msg = f"{msg} | GET: {ge}"
                if attempt < 1 and any(c in msg for c in ("402", "429", "503", "Max retries",
                                                           "NameResolution", "timed out", "Connection")):
                    wait = 5 * (attempt + 1)
                    print(f"   [!] {name} rate-limiting or busy -- retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"   [!] {name} failed: {msg[:160]}")
                errors.append(f"{name}: {msg[:160]}")
                break
    raise RuntimeError("All fallback LLMs failed -- " + " | ".join(errors or ["none configured"]))
