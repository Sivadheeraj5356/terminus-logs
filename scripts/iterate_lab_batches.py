"""Iterate frozen batches 01–05: oracle (02+), cheap k=5 measure, ingest.

Stops after batch 05, or when run_lab_batch writes a credit/quota stop file.
Does not start a second harbor run (the measure runner waits for idle).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lab_common import (  # noqa: E402
    JOBS_DIR,
    batch_jsonl_path,
    collect_trials,
    load_jsonl,
)
from select_lab_batch import replace_failed_oracles  # noqa: E402

RUNNER = ROOT / "scripts" / "run_lab_batch.py"
INGEST = ROOT / "scripts" / "ingest_lab_jobs.py"
NOTES = ROOT / "scripts" / "write_loss_notes.py"
BRANCH = "cursor/applied-work-lab-batch-01-826a"


def run(argv: list[str]) -> int:
    print(">>", " ".join(argv), flush=True)
    proc = subprocess.run(argv)
    return proc.returncode


def stopped(batch: int) -> bool:
    path = ROOT / "docs" / f"lab_batch_{batch:02d}_stop.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    # Missing key: treat legacy credit-stop files as a hard halt.
    return bool(data.get("halt_iterate", True))


def archive_stale_stops() -> None:
    """Move prior credit-stop files aside so a funded resume can continue."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for batch in range(1, 6):
        path = ROOT / "docs" / f"lab_batch_{batch:02d}_stop.json"
        if not path.is_file():
            continue
        dest = ROOT / "docs" / f"lab_batch_{batch:02d}_stop.{stamp}.json"
        shutil.move(str(path), str(dest))
        print(f"archived stale stop {path.name} -> {dest.name}", flush=True)


def oracle_failed_slugs(batch: int) -> list[str]:
    rows = load_jsonl(batch_jsonl_path(batch))
    trials = collect_trials(JOBS_DIR)
    failed = []
    for row in rows:
        slug = row["slug"]
        hits = []
        seen = set()
        for key in (slug, row.get("uuid") or ""):
            for trial in trials.get(key) or []:
                marker = trial.get("trial_dir")
                if marker in seen:
                    continue
                seen.add(marker)
                agent = (trial.get("agent") or "").lower()
                if agent == "oracle" or agent.startswith("oracle"):
                    hits.append(trial)
        if not any(t.get("classification") == "solved" for t in hits):
            failed.append(slug)
    return failed


def commit_docs(message: str) -> None:
    subprocess.run(["git", "add", "docs", "lab", "README.md", "scripts"], cwd=ROOT, check=False)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if not (status.stdout or "").strip():
        print("no git changes to commit", flush=True)
        return
    code = subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=False)
    if code.returncode != 0:
        print("git commit skipped or failed", flush=True)
        return
    push = subprocess.run(["git", "push", "-u", "origin", BRANCH], cwd=ROOT, check=False)
    if push.returncode != 0:
        print("git push failed; will retry later", flush=True)


def commit_batch(batch: int) -> None:
    commit_docs(f"Ingest Worlds Lab batch {batch:02d} cheap k=5 (oracle + measure)")


def ensure_oracles(py: str, batch: int) -> int:
    for attempt in range(1, 4):
        code = run([py, str(RUNNER), "--phase", "oracle", "--batch", str(batch)])
        if code != 0:
            return code
        failed = oracle_failed_slugs(batch)
        if not failed:
            print(f"oracle 10/10 for batch {batch:02d}", flush=True)
            return 0
        print(f"oracle miss attempt {attempt}: {failed}", flush=True)
        if batch == 1:
            (ROOT / "docs" / f"lab_batch_{batch:02d}_stop.json").write_text(
                json.dumps(
                    {
                        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "batch": batch,
                        "reason": "oracle reward != 1.0",
                        "halt_iterate": True,
                        "failed_slugs": failed,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            return 2
        new_slugs = replace_failed_oracles(batch, failed)
        print(f"replaced with {new_slugs}; re-running oracle", flush=True)
    print(f"oracle still not 10/10 after replacements for batch {batch:02d}", flush=True)
    return 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-batch", type=int, default=1)
    parser.add_argument("--end-batch", type=int, default=5)
    parser.add_argument("--skip-oracle-batch1", action="store_true", default=True)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="archive stale credit-stop files and continue remaining k",
    )
    args = parser.parse_args()
    py = sys.executable
    if args.resume:
        archive_stale_stops()
    probe = run([py, str(RUNNER), "--phase", "probe", "--batch", str(args.start_batch)])
    if probe != 0:
        print("probe failed; not starting Harbor measure", flush=True)
        run([py, str(INGEST)])
        run([py, str(NOTES)])
        commit_docs(
            f"Record Batch {args.start_batch:02d} dual-provider credit/quota stop (no Harbor)"
        )
        return
    for batch in range(args.start_batch, args.end_batch + 1):
        print(f"\n===== batch {batch:02d} =====", flush=True)
        if batch > 1 or not args.skip_oracle_batch1:
            code = ensure_oracles(py, batch)
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
        commit_batch(batch)
        if stopped(batch) or code != 0:
            print(f"stopping iterate at batch {batch:02d}", flush=True)
            break
    print("iterate finished", flush=True)


if __name__ == "__main__":
    main()
