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


def _post_generate(
    prompt: str,
    *,
    host: str,
    model: str,
    timeout_s: float,
    response_format: str | None = None,
) -> dict[str, Any]:
    """POST /api/generate and return the decoded JSON body."""

    url = f"{host.rstrip('/')}/api/generate"
    body_obj: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if response_format is not None:
        body_obj["format"] = response_format
    body = json.dumps(body_obj).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        # URLError/OSError: daemon down; TimeoutError: slow model; ValueError:
        # malformed JSON. All surface as one RuntimeError for callers.
        raise RuntimeError(f"ollama_generate_failed:{exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("ollama_generate_empty_response")  # noqa: TRY004
    return payload


def _response_text(payload: dict[str, Any]) -> str:
    text = payload.get("response")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("ollama_generate_empty_response")
    return text.strip()


def _parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object, including a fenced block or surrounding prose."""

    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("ollama_generate_json_not_object") from None
        try:
            value = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("ollama_generate_json_not_object") from exc
    if not isinstance(value, dict):
        raise RuntimeError("ollama_generate_json_not_object")  # noqa: TRY004
    return value


def generate(
    prompt: str,
    *,
    host: str = DEFAULT_HOST,
    model: str = DEFAULT_MODEL,
    timeout_s: float = 120.0,
) -> str:
    """POST /api/generate (non-streaming) and return the response text."""

    payload = _post_generate(
        prompt,
        host=host,
        model=model,
        timeout_s=timeout_s,
    )
    return _response_text(payload)


def generate_json(
    prompt: str,
    *,
    host: str = DEFAULT_HOST,
    model: str = DEFAULT_MODEL,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """POST /api/generate with ``format=json`` and return one JSON object.

    This is transport only. Callers decide which ids are legal. A timeout,
    transport error, or non-object body raises ``RuntimeError``.
    """

    try:
        payload = _post_generate(
            prompt,
            host=host,
            model=model,
            timeout_s=timeout_s,
            response_format="json",
        )
    except RuntimeError as exc:
        raise RuntimeError(f"ollama_generate_json_failed:{exc}") from exc
    return _parse_json_object(_response_text(payload))
