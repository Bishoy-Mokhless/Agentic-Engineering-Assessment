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


def test_run_exits_successfully():
    assert main(["run"]) == 0
