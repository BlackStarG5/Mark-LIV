"""Shared Ollama transport. All reasoning stays on the configured home server."""
import base64
import json
import os
import threading
from pathlib import Path
from urllib.parse import urlsplit

import requests

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
_MODEL_LOCK = threading.RLock()


def load_config():
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def settings():
    cfg = load_config()
    url = os.environ.get("HOMEAI_OLLAMA_URL", cfg.get("llm_url", "http://localhost:11434")).rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Enter an http(s) Ollama server address without credentials or query parameters.")
    return url, cfg.get("llm_model", "qwen3:8b")


def _headers():
    token = os.environ.get("HOMEAI_OLLAMA_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def models():
    url, _ = settings()
    response = requests.get(f"{url}/api/tags", headers=_headers(), timeout=10)
    response.raise_for_status()
    return response.json().get("models", [])


def normalize_schema(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(exclude_none=True)
    if isinstance(value, list):
        return [normalize_schema(v) for v in value]
    if not isinstance(value, dict):
        return value
    return {k: (str(v).split(".")[-1].lower() if k == "type" and isinstance(v, str) else normalize_schema(v))
            for k, v in value.items() if v is not None and k not in ("behavior", "property_ordering")}


def tool_specs(declarations):
    return [{"type": "function", "function": normalize_schema(d)} for d in declarations]


def identity_instruction(model=None):
    configured = model or settings()[1]
    return (
        "[RUNTIME MODEL IDENTITY — authoritative application configuration]\n"
        f"Your underlying language model is {configured}, served by Ollama on the user's home server. "
        "JARVIS (or the user's configured assistant name) is your app/persona name, not your model name. "
        "Ollama is the serving software, not the Llama model family. "
        "When asked which model you are, give the exact configured model name above. "
        "Do not claim to be a proprietary model, Gemini, or Llama unless that is the configured model. "
        "Speech recognition is local Whisper; speech synthesis is local Kokoro on the user's PC."
    )


def chat(messages, tools=None, timeout=180, model=None, think=None, on_text=None, cancelled=None, warmup=False,
         max_tokens=None, format_schema=None):
    cfg = load_config()
    url, default = settings()
    messages = [dict(message) for message in messages]
    identity = identity_instruction(model or default)
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] = identity + "\n\n" + messages[0].get("content", "")
    else:
        messages.insert(0, {"role": "system", "content": identity})
    payload = {"model": model or default, "messages": messages, "stream": on_text is not None,
               "think": cfg.get("thinking_enabled", False) if think is None else think,
               "keep_alive": cfg.get("llm_keep_alive", "30m"),
               "options": {"num_ctx": int(cfg.get("llm_context", 16384)),
                           "num_predict": 1 if warmup else int(max_tokens or cfg.get("llm_max_tokens", 2048))}}
    if format_schema is not None:
        payload["format"] = format_schema
    if tools:
        payload["tools"] = tools
    # Serialize requests rather than concurrently loading two models on the RX 580.
    with _MODEL_LOCK:
        if cancelled is not None and cancelled.is_set():
            return {"role": "assistant", "content": ""}
        response = requests.post(f"{url}/api/chat", json=payload, headers=_headers(), timeout=(10, timeout),
                                 stream=on_text is not None)
        if response.status_code >= 400:
            raise RuntimeError(f"Ollama returned {response.status_code}: {response.text[:400]}")
        response.raise_for_status()
        if on_text is None:
            body = response.json()
        else:
            message = {"role": "assistant", "content": ""}
            body = {}
            try:
                for line in response.iter_lines(chunk_size=1):
                    if cancelled is not None and cancelled.is_set():
                        return message
                    if not line:
                        continue
                    body = json.loads(line)
                    if body.get("error"):
                        raise RuntimeError(body["error"])
                    part = body.get("message", {})
                    content = part.get("content", "")
                    if content:
                        message["content"] += content
                        on_text(content)
                    if part.get("tool_calls"):
                        message.setdefault("tool_calls", []).extend(part["tool_calls"])
                    if body.get("done"):
                        break
                if not body.get("done"):
                    raise RuntimeError("Ollama stream ended before the response was complete.")
                body["message"] = message
            finally:
                response.close()
    if body.get("error"):
        raise RuntimeError(body["error"])
    if "total_duration" in body:
        seconds = lambda key: body.get(key, 0) / 1_000_000_000
        print(f"[TIMING] Ollama load={seconds('load_duration'):.2f}s "
              f"prompt={seconds('prompt_eval_duration'):.2f}s "
              f"generate={seconds('eval_duration'):.2f}s "
              f"input_tokens={body.get('prompt_eval_count', 0)} "
              f"output_tokens={body.get('eval_count', 0)}", flush=True)
    if body.get("done_reason") == "length" and not warmup:
        raise RuntimeError("Model response reached its output limit; increase llm_max_tokens or shorten the request.")
    message = body.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("Ollama returned no assistant message.")
    return message


def text(prompt, system=None, timeout=180):
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    return chat(messages, timeout=timeout).get("content", "").strip()


def describe_images(parts, timeout=180):
    model = load_config().get("vision_model", "qwen3.5:9b")
    if not model:
        raise RuntimeError("Screen/camera interpretation requires a vision_model; qwen3:8b is text-only.")
    texts, images = [], []
    for part in parts:
        if part.get("text"):
            texts.append(part["text"])
        blob = part.get("inline_data")
        if blob:
            if not blob.get("mime_type", "").startswith("image/"):
                raise ValueError("The local backend accepts images and text, not embedded audio or documents.")
            data = blob["data"]
            images.append(base64.b64encode(data).decode("ascii") if isinstance(data, bytes) else data)
    return chat([{"role": "user", "content": "\n".join(texts), "images": images}],
                model=model, timeout=timeout, think=False).get("content", "")
