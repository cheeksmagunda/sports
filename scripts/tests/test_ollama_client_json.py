"""JSON generate contract for the shared Ollama HTTP client (#595)."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Self

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from ollama_hv_watcher.client import generate, generate_json


class _Body:
    def __init__(self, payload: dict[str, object]) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def test_generate_json_posts_format_and_parses_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_urlopen(req: urllib.request.Request, timeout: float = 0) -> _Body:
        seen["timeout"] = timeout
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _Body({"response": '{"utilities": [{"utility": 1.5}]}'})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    parsed = generate_json("score these ids", timeout_s=3.5, model="llama3.2:3b")
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["format"] == "json"
    assert body["stream"] is False
    assert body["model"] == "llama3.2:3b"
    assert seen["timeout"] == 3.5
    assert parsed == {"utilities": [{"utility": 1.5}]}


def test_generate_json_strips_fences(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: urllib.request.Request, timeout: float = 0) -> _Body:
        return _Body({"response": '```json\n{"ok": true}\n```'})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert generate_json("prompt", timeout_s=1) == {"ok": True}


def test_generate_json_timeout_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req: urllib.request.Request, timeout: float = 0) -> _Body:
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="ollama_generate_json_failed"):
        generate_json("prompt", timeout_s=1)


def test_generate_text_path_still_returns_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(req: urllib.request.Request, timeout: float = 0) -> _Body:
        body = json.loads(req.data.decode("utf-8"))
        assert "format" not in body
        return _Body({"response": "notes only"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert generate("prompt", timeout_s=2) == "notes only"
