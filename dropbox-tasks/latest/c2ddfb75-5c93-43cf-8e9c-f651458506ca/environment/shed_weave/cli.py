from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from shed_weave.journal_store import read_journal, write_journal
from shed_weave.report_builder import build_pattern_genealogy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shed_weave")
    sub = parser.add_subparsers(dest="command", required=True)

    value = sub.add_parser("trace", help="Compute fair values for a ledger")
    value.add_argument("--bundle", required=True, type=Path)
    value.add_argument("--out", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "trace":
        if os.environ.get("TRACE_HALT") == "1":
            report = build_pattern_genealogy(args.bundle)
            write_journal(report)
            return 0

        if os.environ.get("TRACE_RESUME") == "1":
            report = read_journal()
            if report is None:
                report = build_pattern_genealogy(args.bundle)
        else:
            report = build_pattern_genealogy(args.bundle)

        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
