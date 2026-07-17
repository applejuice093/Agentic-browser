"""CLI unit tests (no browser launch except version / help)."""

from __future__ import annotations

import pytest

from agent_browser.cli import build_parser, main


def test_parser_open():
    parser = build_parser()
    args = parser.parse_args(["open", "https://example.com", "--raw-html", "--compact"])
    assert args.command == "open"
    assert args.url == "https://example.com"
    assert args.raw_html is True
    assert args.compact is True


def test_parser_version_subcommand():
    parser = build_parser()
    args = parser.parse_args(["version"])
    assert args.command == "version"


def test_main_version(capsys):
    with pytest.raises(SystemExit) as ei:
        main(["version"])
    assert ei.value.code == 0
    out = capsys.readouterr().out.strip()
    assert out == "0.2.0"


def test_main_help_no_command(capsys):
    with pytest.raises(SystemExit) as ei:
        main([])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "agent-browser" in out
