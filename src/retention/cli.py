"""Command-line entry point: `retention run` and `retention serve` (D-43).

Spring analogy: the main class / CommandLineRunner of the application.
"""

from __future__ import annotations

import argparse
import logging

from retention.config import load_settings
from retention.pipeline.job import run_pipeline

log = logging.getLogger("retention")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="retention",
        description="External signals x workforce retention: data pipeline and dashboard.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the full data pipeline (ingest -> curate -> metrics -> analysis).")
    mode = run.add_mutually_exclusive_group()
    mode.add_argument(
        "--offline",
        action="store_true",
        help="Use the latest saved raw data, no network calls (default).",
    )
    mode.add_argument(
        "--refresh",
        action="store_true",
        help="Fetch fresh data from Eurostat and the World Bank first, then run.",
    )

    serve = sub.add_parser("serve", help="Start the API and dashboard.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    return parser


def configure_logging(level: int = logging.INFO) -> None:
    """D-49: standard logging with levels. Spring analogy: SLF4J/Logback console appender."""
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging()
    settings = load_settings()

    if args.command == "run":
        mode = "refresh" if args.refresh else "offline"
        log.info(
            "Settings loaded: %d countries, %d indicators", len(settings.countries), len(settings.indicators)
        )
        return run_pipeline(settings, mode)

    if args.command == "serve":
        log.info("API/dashboard are added in Step 6 (would listen on http://%s:%d).", args.host, args.port)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
