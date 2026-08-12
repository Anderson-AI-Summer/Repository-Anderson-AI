"""Command-line interface.

    python -m src.cli setup              # environment check
    python -m src.cli sample             # small, fast, real-data pull for dev/demo
    python -m src.cli refresh            # full NASA FY2020-present refresh
    python -m src.cli build              # rebuild HTML from cached processed data, no network
    python -m pytest                     # test suite
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys

from src.config import ANTHROPIC_API_KEY, DASHBOARD_PATH, FY2020_START, NASA_AGENCY_NAME

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("cli")


def cmd_setup(_args) -> int:
    print("NASA Procurement Intelligence Dashboard -- environment check")
    print(f"  Python: {sys.version.split()[0]}")
    try:
        import httpx, pandas, pydantic, plotly, jinja2, rapidfuzz, anthropic, pytest, dotenv  # noqa: F401
        print("  Dependencies: OK (httpx, pandas, pydantic, plotly, jinja2, rapidfuzz, anthropic, pytest, python-dotenv)")
    except ImportError as exc:
        print(f"  Dependencies: MISSING ({exc}). Run: pip install -r requirements.txt")
        return 1
    print(f"  ANTHROPIC_API_KEY configured: {'yes' if ANTHROPIC_API_KEY else 'no (DETERMINISTIC_FALLBACK mode will be used)'}")
    print(f"  NASA agency scope: {NASA_AGENCY_NAME}")
    print(f"  Default date range: {FY2020_START} .. {dt.date.today().isoformat()}")
    print("  Ready. Try: python -m src.cli sample")
    return 0


def cmd_sample(args) -> int:
    from src.pipeline import run_pipeline

    result = run_pipeline(
        mode="sample",
        start_date=args.start,
        end_date=args.end,
        max_records=args.limit,
        max_workers=args.max_workers,
    )
    _report(result)
    return 0 if result["status"] == "ok" else 1


def cmd_refresh(args) -> int:
    from pathlib import Path

    from src.pipeline import run_pipeline

    if args.limit is None:
        logger.info("No --limit given: this is an unbounded full refresh and may take a long time.")
    extra_csv_paths = [Path(p) for p in (args.extra_csv or [])]
    result = run_pipeline(
        mode="refresh",
        start_date=args.start,
        end_date=args.end,
        max_records=args.limit,
        max_workers=args.max_workers,
        extra_csv_paths=extra_csv_paths,
    )
    _report(result)
    return 0 if result["status"] == "ok" else 1


def cmd_build(_args) -> int:
    from src.pipeline import run_pipeline

    result = run_pipeline(mode="rebuild")
    _report(result)
    return 0 if result["status"] == "ok" else 1


def _report(result: dict) -> None:
    print("\n--- Run summary ---")
    for k, v in result.items():
        print(f"  {k}: {v}")
    if result["status"] == "ok":
        print(f"\nDashboard written to: {DASHBOARD_PATH}")
    else:
        print("\nDashboard generation FAILED validation -- previous known-good file (if any) was kept.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Check environment and dependencies").set_defaults(func=cmd_setup)

    p_sample = sub.add_parser("sample", help="Fast, small real-data pull for development/demo")
    p_sample.add_argument("--start", default=None, help=f"default {FY2020_START}")
    p_sample.add_argument("--end", default=None, help="default today")
    p_sample.add_argument("--limit", type=int, default=300, help="max transactions (default 300; sample mode always caps)")
    p_sample.add_argument("--max-workers", type=int, default=8)
    p_sample.set_defaults(func=cmd_sample)

    p_refresh = sub.add_parser("refresh", help="Full NASA FY2020-present refresh")
    p_refresh.add_argument("--start", default=None, help=f"default {FY2020_START}")
    p_refresh.add_argument("--end", default=None, help="default today")
    p_refresh.add_argument("--limit", type=int, default=None, help="optional cap; full refresh is uncapped by default")
    p_refresh.add_argument("--max-workers", type=int, default=8)
    p_refresh.add_argument("--extra-csv", action="append", default=None,
                            help="additional pre-existing NASA CSV(s) to merge in and dedupe (repeatable)")
    p_refresh.set_defaults(func=cmd_refresh)

    sub.add_parser("build", help="Rebuild dashboard HTML from cached processed data (no network)").set_defaults(func=cmd_build)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
