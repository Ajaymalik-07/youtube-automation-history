"""
LLM Client — shared across all agents.
Features intelligent multi-model failover across all free Gemini & Gemma models:
1. Immediately shifts to the next Gemini model if quota is exhausted (429) or
   if the model reports high demand / heavy traffic / busy / overloaded (503).
2. Tries modern high-capacity models first (gemini-3.5-flash, gemini-3.5-flash-lite, etc.).
3. Falls back to external providers (Groq -> OpenRouter -> Pollinations) only if
   all Gemini models are unavailable.
"""
import time
import re
import sys
import config

# Ensure stdout/stderr handles Unicode on Windows without crashing
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Prioritized list of active modern Gemini and Gemma models
_ALL_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3.1-pro-preview",
    "gemini-pro-latest",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
]

# Which provider answered the last call — shown in the GUI
last_provider = None
_active_preferred_model = None


def _set_preferred_model(model: str) -> None:
    global _active_preferred_model
    _active_preferred_model = model


def build_chain(starting_model: str | None = None) -> list:
    """
    Return model list rotated so preferred / starting model is tried first,
    followed by all other available models.
    """
    preferred = (_active_preferred_model or starting_model or getattr(config, "GEMINI_MODEL", "")).strip()
    if preferred and preferred in _ALL_MODELS:
        idx = _ALL_MODELS.index(preferred)
        return _ALL_MODELS[idx:] + _ALL_MODELS[:idx]
    return list(_ALL_MODELS)


_client = None
_client_key = None


def gemini_configured() -> bool:
    key = getattr(config, "GEMINI_API_KEY", "") or ""
    return bool(key) and not key.upper().startswith("YOUR_")


def _get_client():
    """Rebuild the client if the key changed in Settings."""
    global _client, _client_key
    if _client is None or _client_key != config.GEMINI_API_KEY:
        from google import genai
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
        _client_key = config.GEMINI_API_KEY
    return _client


def _classify_error(err: Exception) -> tuple[bool, str]:
    """
    Classifies error and returns (should_shift, friendly_reason).
    Returns should_shift=True for quota, heavy traffic, overload, busy, 404 retired models, etc.
    """
    msg = str(err).lower()

    if any(k in msg for k in ("429", "resource_exhausted", "quota", "rate limit")):
        return True, "Quota exhausted (429)"

    if any(k in msg for k in ("503", "unavailable", "high demand", "busy", "heavy traffic", "overloaded", "server error")):
        return True, "High traffic / Busy server (503)"

    if any(k in msg for k in ("404", "not_found", "not found", "is not supported", "no longer available")):
        return True, "Model retired or not available (404)"

    if any(k in msg for k in ("500", "internal", "timed out", "timeout", "connection reset", "connection aborted", "remotedisconnected")):
        return True, "Transient server/network error"

    # Default to shifting on any generation error so pipeline never dead-ends on one model
    return True, f"Model error: {msg[:80]}"


def _is_gone(err: Exception) -> bool:
    msg = str(err).lower()
    return any(k in msg for k in ("404", "not_found", "not found", "is not supported", "no longer available"))


def _should_switch_model(err: Exception) -> bool:
    msg = str(err).lower()
    if "400" in msg or "api_key_invalid" in msg:
        return False
    return any(k in msg for k in ("connection", "timed out", "timeout", "10053", "503", "429"))


def _generate_gemini(prompt: str, starting_model: str | None) -> str:
    global last_provider
    from google.genai import types
    client = _get_client()
    chain = build_chain(starting_model)

    attempted_models = []
    errors = []

    for model in chain:
        attempted_models.append(model)
        try:
            print(f"   -> Trying Gemini model: {model}...")
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.9),
            )
            text = (response.text or "").strip()
            if text:
                last_provider = model
                _set_preferred_model(model)
                print(f"   [OK] Succeeded with {model} ({len(text.split())} words generated)")
                return text

        except Exception as e:
            should_shift, reason = _classify_error(e)
            print(f"   [!] [{model}] {reason} -- immediately shifting to next model...")
            errors.append(f"{model}: {reason}")
            continue

    # If all models in static list failed, attempt dynamic query of available models
    try:
        remote_models = [m.name.replace("models/", "") for m in client.models.list()
                         if ("gemini" in m.name or "gemma" in m.name) and m.name.replace("models/", "") not in attempted_models]
        for dyn_model in remote_models[:5]:
            try:
                print(f"   -> Trying discovered model: {dyn_model}...")
                response = client.models.generate_content(
                    model=dyn_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.9),
                )
                text = (response.text or "").strip()
                if text:
                    last_provider = dyn_model
                    _set_preferred_model(dyn_model)
                    print(f"   [OK] Succeeded with {dyn_model}")
                    return text
            except Exception as e:
                _, reason = _classify_error(e)
                print(f"   [!] [{dyn_model}] {reason} -- shifting...")
                continue
    except Exception:
        pass

    raise RuntimeError(
        f"All {len(attempted_models)} Gemini models failed.\n" +
        "\n".join(f"* {err}" for err in errors[:5])
    )


def generate(prompt: str, starting_model: str | None = None) -> str:
    global last_provider
    from apis import llm

    gemini_err = None
    if gemini_configured():
        try:
            return _generate_gemini(prompt, starting_model)
        except Exception as e:
            gemini_err = e
            if not llm.providers():
                raise
            print("   [!] All Gemini models failed -- switching to fallback LLM stack...")
    else:
        print("   -> No Gemini key set -- using free fallback LLMs")

    try:
        text = llm.chat(prompt)
        last_provider = "fallback"
        return text
    except Exception as e:
        if gemini_err:
            raise RuntimeError(f"Gemini failed:\n{gemini_err}\n\nFallbacks failed:\n{e}") from e
        raise RuntimeError(
            f"{e}\nAdd a free Gemini key in Settings (aistudio.google.com/apikey)."
        ) from e
