"""Unit tests for public exception hierarchy (no browser)."""

from __future__ import annotations

import builtins

import agent_browser as ab
from agent_browser.exceptions import (
    AgentBrowserError,
    BrowserAlreadyStartedError,
    BrowserNotStartedError,
    ElementNotFoundError,
    NavigationError,
    NetworkTimeoutError,
    SnapshotError,
    TimeoutError,
    VisionError,
)


def test_all_exceptions_subclass_base():
    for cls in (
        BrowserNotStartedError,
        BrowserAlreadyStartedError,
        ElementNotFoundError,
        NavigationError,
        SnapshotError,
        TimeoutError,
        VisionError,
        NetworkTimeoutError,
    ):
        assert issubclass(cls, AgentBrowserError)
        assert issubclass(cls, Exception)


def test_network_timeout_is_timeout_subclass():
    assert issubclass(NetworkTimeoutError, TimeoutError)
    err = NetworkTimeoutError("api timed out")
    assert isinstance(err, TimeoutError)
    assert isinstance(err, AgentBrowserError)
    assert "api timed out" in str(err)


def test_timeout_error_is_not_builtins_timeout():
    assert TimeoutError is not builtins.TimeoutError
    lib_err = TimeoutError("library")
    builtin_err = builtins.TimeoutError("builtin")
    assert isinstance(lib_err, AgentBrowserError)
    assert not isinstance(builtin_err, AgentBrowserError)


def test_public_exports_include_new_exceptions():
    assert ab.TimeoutError is TimeoutError
    assert ab.BrowserAlreadyStartedError is BrowserAlreadyStartedError
    assert "TimeoutError" in ab.__all__
    assert "BrowserAlreadyStartedError" in ab.__all__
