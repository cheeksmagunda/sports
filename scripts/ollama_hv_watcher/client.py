"""Minimal Ollama HTTP client for localhost:11434 (#574)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:3b"


def health_check(host: str = DEFAULT_HOST, *, timeout_s: float = 2.0) -> dict[str, Any]:
    """GET /api/tags; returns ``ok`` plus model names when reachable."""

    url = f"{host.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "error": str(exc), "host": host}
    models: list[str] = []
    if isinstance(payload, dict) and isinstance(payload.get("models"), list):
        models = [
            str(m.get("name"))
            for m in payload["models"]
            if isinstance(m, dict) and m.get("name")
        ]
    return {"ok": True, "host": host, "models": models}


def generate(
    prompt: str,
    *,
    host: str = DEFAULT_HOST,
    model: str = DEFAULT_MODEL,
    timeout_s: float = 120.0,
) -> str:
    """POST /api/generate (non-streaming) and return the response text."""

    url = f"{host.rstrip('/')}/api/generate"
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"ollama_generate_failed:{exc}") from exc
    text = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("ollama_generate_empty_response")
    return text.strip()
