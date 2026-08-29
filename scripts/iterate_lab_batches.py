"""Iterate frozen batches 01–05: oracle (02+), cheap k=5 measure, ingest.

Stops after batch 05, or when run_lab_batch writes a credit/quota stop file.
Does not start a second harbor run (the measure runner waits for idle).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_lab_batch.py"
INGEST = ROOT / "scripts" / "ingest_lab_jobs.py"
NOTES = ROOT / "scripts" / "write_loss_notes.py"


def run(argv: list[str]) -> int:
    print(">>", " ".join(argv), flush=True)
    proc = subprocess.run(argv)
    return proc.returncode


def stopped(batch: int) -> bool:
    return (ROOT / "docs" / f"lab_batch_{batch:02d}_stop.json").is_file()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-batch", type=int, default=1)
    parser.add_argument("--end-batch", type=int, default=5)
    parser.add_argument("--skip-oracle-batch1", action="store_true", default=True)
    args = parser.parse_args()
    py = sys.executable
    for batch in range(args.start_batch, args.end_batch + 1):
        print(f"\n===== batch {batch:02d} =====", flush=True)
        if batch > 1 or not args.skip_oracle_batch1:
            code = run([py, str(RUNNER), "--phase", "oracle", "--batch", str(batch)])
            if code != 0:
                print(f"oracle failed for batch {batch:02d}; stopping iterate", flush=True)
                break
        code = run(
            [
                py,
                str(RUNNER),
                "--phase",
                "measure",
                "--batch",
                str(batch),
                "--yes-measure",
            ]
        )
        run([py, str(INGEST)])
        run([py, str(NOTES)])
        if stopped(batch) or code != 0:
            print(f"stopping iterate at batch {batch:02d}", flush=True)
            break
    print("iterate finished", flush=True)


if __name__ == "__main__":
    main()
