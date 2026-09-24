"""Legacy local-model API, routed through the same home server as the main UI."""
from core.home_llm import chat, load_config as _load_config, settings as get_llm_settings, models


def get_llm_provider():
    return "ollama"


def ensure_ollama_running(timeout=15):
    try:
        models()
        return True
    except Exception:
        return False


def check_model_available(log=None):
    _, model = get_llm_settings()
    found = any(m.get("name") == model for m in models())
    if not found and log:
        log(f"Model {model} is missing on the configured server.")
    return found


def warmup_model(system_prompt=None):
    return check_model_available()


def call_llm(messages, tools=None, timeout=180):
    return chat(messages, tools, timeout)


def call_llm_text(prompt, system=None, model=None, timeout=180):
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    return chat(messages, timeout=timeout, model=model).get("content", "").strip()


def stream_llm(messages, tools=None, timeout=180):
    msg = chat(messages, tools, timeout)
    if msg.get("content"):
        yield {"type": "sentence", "text": msg["content"]}
    yield {"type": "done", "content": msg.get("content", ""), "tool_calls": msg.get("tool_calls", [])}
