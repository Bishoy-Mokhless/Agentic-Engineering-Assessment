"""The `retention` command parses its subcommands and options (D-43)."""

import pytest

from retention.cli import build_parser, main


def test_run_defaults_to_offline():
    args = build_parser().parse_args(["run"])
    assert args.command == "run" and not args.refresh


def test_offline_and_refresh_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", "--offline", "--refresh"])


def test_serve_port_option():
    args = build_parser().parse_args(["serve", "--port", "9000"])
    assert args.port == 9000


def test_run_calls_pipeline_with_offline_mode(monkeypatch):
    calls = []
    monkeypatch.setattr("retention.cli.run_pipeline", lambda settings, mode: calls.append(mode) or 0)
    assert main(["run"]) == 0
    assert calls == ["offline"]


def test_run_refresh_passes_refresh_mode(monkeypatch):
    calls = []
    monkeypatch.setattr("retention.cli.run_pipeline", lambda settings, mode: calls.append(mode) or 0)
    main(["run", "--refresh"])
    assert calls == ["refresh"]
