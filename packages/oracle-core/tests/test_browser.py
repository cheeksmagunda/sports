from __future__ import annotations

import asyncio
from typing import Any

import pytest

from oracle_core.browser import DEFAULT_LAUNCH_ARGS, launch_chromium_session


class _FakePage:
    pass


class _FakeContext:
    def __init__(self) -> None:
        self.closed = False
        self.new_page_calls = 0

    async def new_page(self) -> _FakePage:
        self.new_page_calls += 1
        return _FakePage()

    async def close(self) -> None:
        self.closed = True


class _FakeBrowser:
    def __init__(self, *, fail_context: bool = False) -> None:
        self.closed = False
        self.launch_kwargs: dict[str, Any] = {}
        self._fail_context = fail_context
        self.context: _FakeContext | None = None

    async def new_context(self, **kwargs: Any) -> _FakeContext:
        self.launch_kwargs = kwargs
        if self._fail_context:
            raise RuntimeError("boom")
        self.context = _FakeContext()
        return self.context

    async def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser) -> None:
        self._browser = browser
        self.launch_calls: list[dict[str, Any]] = []

    async def launch(self, *, headless: bool, args: list[str]) -> _FakeBrowser:
        self.launch_calls.append({"headless": headless, "args": args})
        return self._browser


class _FakePlaywright:
    def __init__(self, browser: _FakeBrowser) -> None:
        self.chromium = _FakeChromium(browser)

    async def __aenter__(self) -> _FakePlaywright:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


def _patch_playwright(monkeypatch: pytest.MonkeyPatch, browser: _FakeBrowser) -> None:
    import playwright.async_api as playwright_module

    def fake_async_playwright() -> _FakePlaywright:
        return _FakePlaywright(browser)

    monkeypatch.setattr(playwright_module, "async_playwright", fake_async_playwright)


def test_launch_chromium_session_closes_browser_and_context_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _FakeBrowser()
    _patch_playwright(monkeypatch, browser)

    async def run() -> None:
        async with launch_chromium_session() as session:
            assert session.browser is browser
            assert isinstance(session.page, _FakePage)

    asyncio.run(run())

    assert browser.closed is True
    assert browser.context is not None
    assert browser.context.closed is True
    assert browser.launch_kwargs == {}


def test_launch_chromium_session_closes_browser_when_caller_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _FakeBrowser()
    _patch_playwright(monkeypatch, browser)

    async def run() -> None:
        async with launch_chromium_session():
            raise ValueError("caller failure")

    with pytest.raises(ValueError, match="caller failure"):
        asyncio.run(run())

    assert browser.closed is True
    assert browser.context is not None
    assert browser.context.closed is True


def test_launch_chromium_session_closes_browser_when_new_context_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _FakeBrowser(fail_context=True)
    _patch_playwright(monkeypatch, browser)

    async def run() -> None:
        async with launch_chromium_session():
            pass  # pragma: no cover - never reached

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(run())

    assert browser.closed is True


def test_launch_chromium_session_forwards_context_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _FakeBrowser()
    _patch_playwright(monkeypatch, browser)

    async def run() -> None:
        async with launch_chromium_session(
            viewport={"width": 1, "height": 2},
            storage_state="state.json",
            user_agent="test-agent",
        ):
            pass

    asyncio.run(run())

    assert browser.launch_kwargs == {
        "viewport": {"width": 1, "height": 2},
        "storage_state": "state.json",
        "user_agent": "test-agent",
    }


def test_default_launch_args_include_container_safety_flags() -> None:
    assert "--no-sandbox" in DEFAULT_LAUNCH_ARGS
    assert "--disable-dev-shm-usage" in DEFAULT_LAUNCH_ARGS
