#!/usr/bin/env python3
"""
bench.py — benchmark runner for the Markdown converter.

Runs the converter on the input files and prints a summary of the report.
Also performs a quick sanity check on link counts.

Usage:
    python3 /app/utils/bench.py
"""

import subprocess
import json
import os
import sys
import re

BINARY = "/app/target/release/md_convert"
REPORT_PATH = "/app/output/report.json"
INPUT_DIR = "/app/input"

def run_converter():
    """Build and run the converter."""
    build = subprocess.run(
        ["cargo", "build", "--release"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        print("Build failed:")
        print(build.stderr)
        sys.exit(1)

    run = subprocess.run([BINARY], capture_output=True, text=True)
    if run.returncode != 0:
        print("Runtime error:")
        print(run.stderr)
        sys.exit(1)

def count_links_in_files():
    """Count [text](url) patterns in all input .md files."""
    total = 0
    for fname in sorted(os.listdir(INPUT_DIR)):
        if fname.endswith(".md"):
            with open(os.path.join(INPUT_DIR, fname)) as f:
                content = f.read()
            # Simple regex for markdown links outside code blocks
            # Per DMS-v3 §2.4: only count links in paragraphs and headings,
            # not inside fenced code blocks. This simplified counter counts
            # ALL occurrences which may overcount if links appear in code.
            matches = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
            total += len(matches)
    return total

def print_summary():
    with open(REPORT_PATH) as f:
        report = json.load(f)
    print("=== Conversion Report ===")
    print(f"Files processed: {report['total_files']}")
    print(f"Total lines    : {report['total_lines']}")
    print(f"Headings       : {report['heading_count']}")
    print(f"Code blocks    : {report['code_block_count']}")
    print(f"List items     : {report['list_item_count']}")
    print(f"Paragraphs     : {report['paragraph_count']}")
    print(f"Links          : {report['link_count']}")
    print(f"Avg blocks/file: {report['average_blocks_per_file']}")
    print(f"Heading dist   : {report['heading_distribution']}")

if __name__ == "__main__":
    run_converter()
    print_summary()
    raw_link_count = count_links_in_files()
    print(f"\nRaw link count (all occurrences in source): {raw_link_count}")
