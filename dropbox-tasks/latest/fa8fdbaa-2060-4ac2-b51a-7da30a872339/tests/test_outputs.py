"""Bootstrap checks for the labyrinth-oracle build artifact and the
bundled labyrinth world it ships with. These confirm the environment the
rest of the suite depends on is actually in place before any HTTP
contract test runs.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

BIN = "/app/bin/labyrinth-oracle"
BUNDLED_WORLD = Path("/app/data/worlds/labyrinth/world.json")
BUNDLED_CHRONICLE = Path("/app/docs/gm-chronicle.md")


def reference_bundled_world_id() -> str:
    """Independent reference helper naming the bundled playtest world."""
    return "labyrinth"


def test_playtest_oracle_binary_exists_and_executable() -> None:
    """Playtest oracle binary ships at /app/bin for session rematch clients."""
    bin_path = Path(BIN)
    assert bin_path.exists()
    assert bin_path.stat().st_mode & 0o111
    # Subprocess smoke: the binary exits non-zero without a subcommand.
    completed = subprocess.run([BIN], capture_output=True, check=False)
    assert completed.returncode != 0


def test_playtest_world_json_matches_schema() -> None:
    """Bundled playtest world.json has rooms, exits, items, and actions
    for the labyrinth route atlas.
    """
    payload = json.loads(BUNDLED_WORLD.read_text(encoding="utf-8"))
    assert payload["world_id"] == reference_bundled_world_id()
    assert payload["start_room"]
    assert len(payload["rooms"]) >= 5
    assert len(payload["exits"]) >= 3
    assert len(payload["items"]) >= 3
    assert len(payload["actions"]) >= 3


def test_bundled_chronicle_contains_forbidden_rules() -> None:
    """/app/docs/gm-chronicle.md exists and embeds at least two @RULE
    forbidden lines, matching /app/docs/rules-format.md.
    """
    text = BUNDLED_CHRONICLE.read_text(encoding="utf-8")
    rule_lines = [line for line in text.splitlines() if line.startswith("@RULE forbidden")]
    assert len(rule_lines) >= 2


def test_cited_docs_are_present() -> None:
    """Every doc instruction.md cites under /app/docs actually exists."""
    for name in (
        "oracle-contract.md",
        "world-schema.md",
        "probe-assemble-pipeline.md",
        "snapshot-attestation.md",
        "rules-format.md",
        "playtest-workflow.md",
    ):
        assert Path("/app/docs", name).exists(), name
