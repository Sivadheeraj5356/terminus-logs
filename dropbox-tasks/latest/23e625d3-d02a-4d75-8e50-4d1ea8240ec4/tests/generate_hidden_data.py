"""Isolate the candidate inputs for each competing-risks case.

The committed fixtures under ``tests/fixtures/<case>/`` hold a shipped
``registry_input.csv`` (with a deterministic ~30% of patients holdout-blanked)
and a secret ``registry_truth.csv`` (full outcomes, read only by the verifier).
At verification time this copies each case's blanked input registry and its
configuration to a candidate-writable per-case path. The truth fixtures are
never exposed to the candidate.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

CASES = ("public", "hidden", "scaled")


def isolate_inputs(fixtures_dir: Path, case_root: Path) -> None:
    if case_root.exists():
        shutil.rmtree(case_root)
    for case in CASES:
        source = fixtures_dir / case
        target = case_root / "inputs" / case
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / "registry_input.csv", target / "registry.csv")
        shutil.copyfile(source / "analysis.csv", target / "analysis.csv")
    (case_root / "outputs").mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "fixtures",
    )
    parser.add_argument("--case-root", type=Path, default=Path("/tmp/mgus-cases"))
    args = parser.parse_args()
    isolate_inputs(args.fixtures_dir, args.case_root)


if __name__ == "__main__":
    main()
