"""Shared fixtures for desiccator tray replay tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

BIN = Path("/app/bin/desiccator_tray")
OUT = Path("/app/output/registry.json")
SEED = Path("/app/task_file")
EXAMPLES = SEED / "examples"

EXAMPLE_HELD = EXAMPLES / "held_scope"
EXAMPLE_REGEN = EXAMPLES / "regen_blocked"
EXAMPLE_DUP = EXAMPLES / "duplicate_retry"
EXAMPLE_RETRY = EXAMPLES / "reject_retry"
EXAMPLE_TAB = EXAMPLES / "bad_line_tab"
EXAMPLE_CR = EXAMPLES / "cr_only"
EXAMPLE_LOCKED = EXAMPLES / "locked_scope"
EXAMPLE_BAD_UNITS = EXAMPLES / "bad_units"
EXAMPLE_EMPTY_TRAY = EXAMPLES / "empty_tray"
EXAMPLE_UNDERFLOW = EXAMPLES / "underflow"

PRESERVED = '{"preserved": true}\n'


def run_tray(task_root: Path, *, clear_output: bool = True) -> tuple[int, str, str]:
    """Run desiccator_tray and return exit code with captured stdout/stderr."""
    if clear_output and OUT.exists():
        OUT.unlink()
    proc = subprocess.run(
        [str(BIN), str(task_root)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def assert_quiet_success(code: int, stdout: str, stderr: str) -> None:
    """Assert a successful run is silent on stdio."""
    assert code == 0, stderr
    assert stdout == ""
    assert stderr == ""


def load_registry() -> dict:
    """Load registry.json as a dict."""
    return json.loads(OUT.read_text(encoding="utf-8"))


def canonical_raw() -> str:
    """Return raw registry.json text."""
    return OUT.read_text(encoding="utf-8")


def write_preserved() -> None:
    """Write preserved-output sentinel for fatal tests."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(PRESERVED, encoding="utf-8")


def write_task(root: Path, trays: list[dict], lines: list[tuple[str, ...]]) -> Path:
    """Build a single-shard task tree from tray configs and tab-field event rows.

    Each row is a tuple of the five fields (event_id, op, tray_id, units, lot_tag);
    short tuples are padded with empty trailing fields so callers can omit units/lot.
    """
    (root / "events").mkdir(parents=True, exist_ok=True)
    (root / "trays.json").write_text(json.dumps({"trays": trays}), encoding="utf-8")
    body = ""
    for row in lines:
        fields = list(row) + [""] * (5 - len(row))
        body += "\t".join(fields) + "\n"
    (root / "events" / "only.tray").write_text(body, encoding="utf-8")
    return root
