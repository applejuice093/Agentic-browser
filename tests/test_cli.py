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
    assert out == "0.4.0"


def test_main_help_no_command(capsys):
    with pytest.raises(SystemExit) as ei:
        main([])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "agent-browser" in out


@pytest.mark.parametrize("value", ["-1", "abc", "1.5"])
def test_timeout_rejects_bad_values(value, capsys):
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--timeout", value, "open", "https://example.com"])
    assert exc.value.code == 2
    assert "--timeout" in capsys.readouterr().err


def test_timeout_accepts_zero():
    args = build_parser().parse_args(["--timeout", "0", "open", "https://example.com"])
    assert args.timeout == 0
