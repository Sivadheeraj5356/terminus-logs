"""Shared helpers for wincontam validation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_oracle_opt = Path("/opt/wincontam-verifier-oracle")
_local_oracle = Path(__file__).resolve().parent / "verifier_private"
if _oracle_opt.is_dir():
    sys.path.insert(0, str(_oracle_opt))
elif _local_oracle.is_dir():
    sys.path.insert(0, str(_local_oracle))

APP = Path("/app")
BIN = Path("/app/target/release/wincontam")
DATA = APP / "data"
STORE = APP / "store"
WORK = Path("/tmp/wincontam-work")
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CUTOFF = "2024-06-01T00:00:00Z"
EMITTED_AT = "2024-06-01T12:00:00Z"

MANIFESTS = (
    "conversation_sessions.json",
    "prompt_turn_log.json",
    "retrieval_injections.json",
    "tool_execution_outputs.json",
    "system_instruction_versions.json",
    "model_output_failures.json",
    "contamination_policy.json",
    "session_order_timeline.json",
)

HIDDEN = (
    "hidden_instruction_conflict",
    "hidden_stale_retrieval",
    "hidden_stale_post_failure",
    "hidden_stale_equal_timestamps",
    "hidden_tool_artifact_bleed",
    "hidden_repeated_fact",
    "hidden_residual_contam",
    "hidden_future_turn_excluded",
    "hidden_stable_no_contam",
    "hidden_sim_clock_inclusive",
    "hidden_last_wins_failure",
    "hidden_score_precision",
    "hidden_instruction_over_stale",
)


def fixture_root() -> Path:
    opt = Path("/opt/verifier-fixtures")
    return opt if opt.is_dir() else FIXTURES


def run_wincontam(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [str(BIN), *args],
        cwd=str(APP),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def reset_workspace() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)
    if STORE.exists():
        shutil.rmtree(STORE)
    STORE.mkdir(parents=True, exist_ok=True)


def mirror_corpus(folder: str, target: Path) -> Path:
    src = fixture_root() / folder
    assert src.is_dir(), f"fixture missing: {src}"
    target.mkdir(parents=True, exist_ok=True)
    for name in MANIFESTS:
        shutil.copy(src / name, target / name)
    return target


def score_bulletin(
    data_dir: Path,
    out_path: Path,
    cutoff: str = CUTOFF,
    emitted_at: str = EMITTED_AT,
) -> dict:
    proc = run_wincontam(["absorb-context-hold", "--corpus", str(data_dir), "--store", str(STORE)])
    assert proc.returncode == 0, proc.stderr
    proc = run_wincontam(
        [
            "score-contam-window",
            "--corpus",
            str(data_dir),
            "--store",
            str(STORE),
            "--cutoff",
            cutoff,
            "--emitted-at",
            emitted_at,
            "--out",
            str(out_path),
        ]
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return json.loads(out_path.read_text())
