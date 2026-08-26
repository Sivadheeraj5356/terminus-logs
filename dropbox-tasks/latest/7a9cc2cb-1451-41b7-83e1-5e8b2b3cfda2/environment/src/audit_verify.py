#!/usr/bin/env python3
"""Cryptographic audit log verifier CLI."""

import argparse

from report_writer import write_report
from validation_pipeline import run_validation


def parse_args():
    parser = argparse.ArgumentParser(description="Cryptographic Audit Segment Verifier")
    parser.add_argument("--data-dir", required=True, help="Path to data directory")
    parser.add_argument("--report", required=True, help="Path to write the report JSON")
    return parser.parse_args()


def main():
    args = parse_args()
    report = run_validation(args.data_dir)
    write_report(report, args.report)


if __name__ == "__main__":
    main()
