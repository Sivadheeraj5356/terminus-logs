"""Behavioral verifier for the offline MLflow Maze recovery pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import fastjsonschema
import pytest


APP = Path("/app/mlflow-maze")
BIN = APP / "bin/maze-recover"
SCRIPT = APP / "scripts/recover-and-replay.sh"
FIXTURE_DB = APP / "fixtures/tracking.sqlite"
SCHEMA_SQL = APP / "fixtures/schema.sql"
BOARD_PATH = APP / "config/maze.yaml"
PUZZLES_PATH = APP / "config/puzzles.toml"
MANIFEST_SCHEMA = APP / "schema/level-manifest.schema.json"
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001


BASELINE_MANIFEST_SEAL = "1fa2910c6d51187e79a42261a5fe12d7d1ddcb123a2fae3705a47e7834b08dcb"
NOVEL_MANIFEST_SEAL = "d2556c3ccb58b0229b2b97d81f74664e53cfa0ff97e5e6dc6a6f5a9528d1656d"


def candidate_run(
    args: list[str | Path],
    *,
    cwd: Path = APP,
    timeout: int = 45,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run candidate-controlled code under an identity that cannot inspect tests."""
    command = ["runuser", "-u", "candidate", "--"]
    if env:
        command.extend(["env", *[f"{key}={value}" for key, value in env.items()]])
    command.extend(str(value) for value in args)
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def hand_off_generated_build_tree() -> None:
    """Reset agent-built artifacts as candidate-owned verifier workspaces."""
    for path in (APP / "build", APP / "bin"):
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)
        path.mkdir(mode=0o750)
        os.chown(path, CANDIDATE_UID, CANDIDATE_GID)


def workspace(prefix: str = "mlflow-maze-") -> Path:
    """Create a private candidate-owned verifier workspace."""
    path = Path(tempfile.mkdtemp(prefix=prefix, dir="/tmp"))
    os.chown(path, CANDIDATE_UID, CANDIDATE_GID)
    path.chmod(0o750)
    return path


def candidate_file(path: Path, data: bytes, mode: int = 0o440) -> Path:
    """Write one verifier fixture that candidate code can read but not alter."""
    path.write_bytes(data)
    os.chown(path, CANDIDATE_UID, CANDIDATE_GID)
    path.chmod(mode)
    return path


def file_sha(path: Path) -> str:
    """Return a lowercase SHA-256 for one verifier input."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fresh_baseline() -> tuple[Path, Path, Path, Path, Path]:
    """Copy all published inputs into a writable-parent isolated workspace."""
    root = workspace("mlflow maze's baseline ")
    database = candidate_file(root / "tracking store.sqlite", FIXTURE_DB.read_bytes())
    board = candidate_file(root / "damaged board.yaml", BOARD_PATH.read_bytes())
    puzzles = candidate_file(root / "puzzles.toml", PUZZLES_PATH.read_bytes())
    output = root / "level manifest.json"
    return root, database, board, puzzles, output


def run_recover(database: Path, board: Path, puzzles: Path, output: Path) -> subprocess.CompletedProcess[str]:
    """Invoke recovery through its complete absolute-path CLI surface."""
    return candidate_run([
        BIN, "recover", "--tracking-db", database, "--maze-yaml", board,
        "--puzzles-toml", puzzles, "--output", output,
    ])


def write_board(path: Path, board: dict[str, Any]) -> Path:
    """Render a deliberately reordered but contract-compatible YAML board."""
    lines = [
        f"goal_room: {json.dumps(board['goal_room'])}",
        f"format: {board['format']}",
        "direction_order: [" + ", ".join(board["direction_order"]) + "]",
        f"experiment_name: {json.dumps(board['experiment_name'])}",
        f"start_room: {json.dumps(board['start_room'])}",
        f"level_id: {json.dumps(board['level_id'])}",
        "rooms:",
    ]
    for room_id in reversed(list(board["rooms"])):
        room = board["rooms"][room_id]
        lines.append(f"  - id: {json.dumps(room_id)}")
        lines.append(
            "    prompt_id: "
            + ("null" if room.get("prompt_id") is None else json.dumps(room["prompt_id"]))
        )
        lines.append(
            "    title: "
            + ("null" if room.get("title") is None else json.dumps(room["title"]))
        )
        if room.get("exits"):
            lines.append("    exits:")
            for direction, target in reversed(list(room["exits"].items())):
                lines.append(f"      {direction}: {json.dumps(target)}")
        else:
            lines.append("    exits: {}")
    return candidate_file(path, ("\n".join(lines) + "\n").encode())


def write_puzzles(path: Path, puzzles: dict[str, Any]) -> Path:
    """Render the damaged puzzle catalog using comments and TOML basic escapes."""
    lines = ['format = "mlflow-maze-puzzles-v1" # generated verifier level', ""]
    for puzzle_id in reversed(list(puzzles)):
        puzzle = puzzles[puzzle_id]
        lines.append(f"[puzzle.{puzzle_id}]")
        if "answer_sha256" in puzzle:
            lines.append(f"answer_sha256 = {json.dumps(puzzle['answer_sha256'])}")
        if "prompt" in puzzle:
            lines.append(f"prompt = {json.dumps(puzzle['prompt'])}")
        lines.append("")
    return candidate_file(path, "\n".join(lines).encode())


def new_store(path: Path, experiment_id: int, experiment_name: str) -> sqlite3.Connection:
    """Create a fresh MLflow-compatible store with no seeded identifiers."""
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA_SQL.read_text())
    connection.execute(
        "INSERT INTO experiments VALUES(?,?,?)",
        (experiment_id, experiment_name, "active"),
    )
    return connection


def add_run(
    connection: sqlite3.Connection,
    *,
    experiment_id: int,
    level_id: str,
    run_id: str,
    kind: str,
    target: str,
    revision: int,
    patch: dict[str, Any],
    timestamp: int,
    parent: str | None = None,
    split: int | None = None,
    status: str = "FINISHED",
    lifecycle: str = "active",
) -> None:
    """Insert one committed patch run with digest-bound contiguous chunks."""
    raw = json.dumps(patch, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode()).hexdigest()
    connection.execute(
        "INSERT INTO runs VALUES(?,?,?,?,?,?)",
        (run_id, experiment_id, status, lifecycle, timestamp - 10, timestamp),
    )
    connection.executemany(
        "INSERT INTO tags VALUES(?,?,?)",
        [
            (run_id, "maze.level_id", level_id),
            (run_id, "maze.record_kind", kind),
            (run_id, "maze.target_id", target),
            (run_id, "maze.patch_sha256", digest),
        ] + ([(run_id, "maze.parent_run_id", parent)] if parent else []),
    )
    connection.execute(
        "INSERT INTO params VALUES(?,?,?)", (run_id, "maze.revision", str(revision))
    )
    chunks = [raw] if split is None else [raw[:split], raw[split:]]
    connection.executemany(
        "INSERT INTO params VALUES(?,?,?)",
        [(run_id, f"maze.patch.{index:03d}", value) for index, value in enumerate(chunks)],
    )
    connection.execute(
        "INSERT INTO metrics VALUES(?,?,?,?,?)",
        (run_id, "maze.commit", 0.0, timestamp - 1, revision),
    )
    connection.execute(
        "INSERT INTO metrics VALUES(?,?,?,?,?)",
        (run_id, "maze.commit", 1.0, timestamp, revision),
    )


def generated_case() -> tuple[Path, Path, Path, Path, dict[str, Any], dict[str, Any]]:
    """Build a novel level whose feasible optimum requires global branch backtracking."""
    root = workspace("novel MLflow maze ")
    board: dict[str, Any] = {
        "format": "mlflow-maze-board-v1",
        "level_id": "cobalt-labyrinth-73",
        "experiment_name": "maze/cobalt-labyrinth-73",
        "start_room": "alpha-17",
        "goal_room": "omega-91",
        "direction_order": ["west", "south", "east", "north"],
        "rooms": {
            "alpha-17": {"id": "alpha-17", "title": "Alpha Dock", "prompt_id": None,
                         "exits": {}, "_revision": 0, "_run_id": None},
            "beta-29": {"id": "beta-29", "title": None, "prompt_id": None,
                        "exits": {}, "_revision": 0, "_run_id": None},
            "gamma-44": {"id": "gamma-44", "title": "Gamma Hall", "prompt_id": "prism-8",
                         "exits": {}, "_revision": 0, "_run_id": None},
            "omega-91": {"id": "omega-91", "title": None, "prompt_id": None,
                         "exits": {}, "_revision": 0, "_run_id": None},
        },
    }
    puzzles = {
        "prism-8": {
            "id": "prism-8", "answer_sha256": hashlib.sha256(b"violet-31").hexdigest(),
            "_revision": 0, "_run_id": None,
        }
    }
    board_path = write_board(root / "board reordered.yaml", board)
    puzzle_path = write_puzzles(root / "puzzle's catalog.toml", puzzles)
    database = root / "novel tracking.sqlite"
    connection = new_store(database, 731, board["experiment_name"])
    add_run(connection, experiment_id=731, level_id=board["level_id"],
            run_id="run-alpha-root", kind="room", target="alpha-17", revision=1,
            patch={"exits": {"west": "beta-29"}}, timestamp=100)
    add_run(connection, experiment_id=731, level_id=board["level_id"],
            run_id="run-alpha-local", kind="room", target="alpha-17", revision=2,
            patch={"exits": {"west": "gamma-44"}}, timestamp=900,
            parent="run-alpha-root")
    add_run(connection, experiment_id=731, level_id=board["level_id"],
            run_id="run-alpha-global", kind="room", target="alpha-17", revision=2,
            patch={"exits": {"west": "beta-29"}}, timestamp=800,
            parent="run-alpha-root", split=11)
    add_run(connection, experiment_id=731, level_id=board["level_id"],
            run_id="run-beta-root", kind="room", target="beta-29", revision=1,
            patch={"title": "Beta Relay", "exits": {"south": "gamma-44"}}, timestamp=200)
    add_run(connection, experiment_id=731, level_id=board["level_id"],
            run_id="run-beta-local", kind="room", target="beta-29", revision=2,
            patch={"exits": {"south": "omega-91"}}, timestamp=700,
            parent="run-beta-root")
    add_run(connection, experiment_id=731, level_id=board["level_id"],
            run_id="run-beta-global", kind="room", target="beta-29", revision=2,
            patch={"exits": {"south": "gamma-44"}}, timestamp=600,
            parent="run-beta-root")
    add_run(connection, experiment_id=731, level_id=board["level_id"],
            run_id="run-gamma", kind="room", target="gamma-44", revision=1,
            patch={"exits": {"east": "omega-91"}}, timestamp=300)
    add_run(connection, experiment_id=731, level_id=board["level_id"],
            run_id="run-omega", kind="room", target="omega-91", revision=1,
            patch={"title": "Omega Vault"}, timestamp=400)
    add_run(connection, experiment_id=731, level_id=board["level_id"],
            run_id="run-prism", kind="puzzle", target="prism-8", revision=1,
            patch={"prompt": "Rotate the cobalt prism to the violet index."},
            timestamp=500, split=23)
    connection.commit()
    connection.close()
    os.chown(database, CANDIDATE_UID, CANDIDATE_GID)
    database.chmod(0o440)
    output = root / "normalized level.json"
    return database, board_path, puzzle_path, output, board, puzzles


def manifest_seal(manifest: dict[str, Any]) -> str:
    """Hash a result after masking only the three fixture-byte provenance values."""
    normalized = json.loads(json.dumps(manifest))
    for key in ("maze_yaml_sha256", "puzzles_toml_sha256", "tracking_store_sha256"):
        normalized["source"][key] = "<input-sha256>"
    encoded = (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(encoded).hexdigest()


def assert_published_manifest(
    output: Path,
    database: Path,
    board: Path,
    puzzles: Path,
    seal: str,
) -> dict[str, Any]:
    """Check canonical bytes, direct input provenance, schema, and a sealed holdout result."""
    manifest = json.loads(output.read_text())
    canonical = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    assert output.read_bytes() == canonical
    assert manifest["source"]["tracking_store_sha256"] == file_sha(database)
    assert manifest["source"]["maze_yaml_sha256"] == file_sha(board)
    assert manifest["source"]["puzzles_toml_sha256"] == file_sha(puzzles)
    fastjsonschema.compile(json.loads(MANIFEST_SCHEMA.read_text()))(manifest)
    assert manifest_seal(manifest) == seal
    return manifest


def test_clean_native_build_links_required_libraries_and_isolates_tests() -> None:
    """A clean offline build yields a native SQLite/YAML JSON engine isolated from tests."""
    hand_off_generated_build_tree()
    clean = candidate_run(["make", "clean"], timeout=30)
    assert clean.returncode == 0, clean.stderr
    build = candidate_run(["make", "all"], timeout=90)
    assert build.returncode == 0, build.stderr
    assert (APP / "build").stat().st_uid == CANDIDATE_UID
    assert (APP / "bin").stat().st_uid == CANDIDATE_UID
    assert BIN.read_bytes()[:4] == b"\x7fELF"
    linked = subprocess.run(["ldd", BIN], text=True, capture_output=True, check=True).stdout
    assert "libsqlite3.so" in linked
    assert "libyaml" in linked
    assert "libjansson" in linked
    assert "libcrypto" in linked
    unreadable = candidate_run(["test", "!", "-r", "/tests/test_outputs.py"])
    assert unreadable.returncode == 0, unreadable.stderr


def test_baseline_pipeline_recovers_exact_manifest_and_deterministic_replay() -> None:
    """The published damaged level resolves globally and replays its canonical shortest path."""
    _, database, board, puzzles, output = fresh_baseline()
    result = candidate_run([SCRIPT, database, board, puzzles, output])
    assert result.returncode == 0, result.stderr
    manifest = assert_published_manifest(
        output, database, board, puzzles, BASELINE_MANIFEST_SEAL)
    lines = manifest["walkthrough"]["transcript"] + [
        f"sha256 {manifest['walkthrough']['sha256']}"
    ]
    assert result.stdout == "".join(f"{line}\n" for line in lines)
    selected = [item["run_id"] for item in manifest["source"]["selected_runs"]]
    assert "atrium-r2-good" in selected
    assert "atrium-r2-bad" not in selected
    assert manifest["walkthrough"]["moves"] == ["east", "east"]


def test_novel_store_reordered_configs_and_coupled_branches_drive_every_field() -> None:
    """Novel IDs and two coupled branch decisions must be derived rather than fixture-matched."""
    database, board_path, puzzle_path, output, board, puzzles = generated_case()
    before = (file_sha(database), file_sha(board_path), file_sha(puzzle_path))
    result = run_recover(database, board_path, puzzle_path, output)
    assert result.returncode == 0, result.stderr
    manifest = assert_published_manifest(
        output, database, board_path, puzzle_path, NOVEL_MANIFEST_SEAL)
    assert before == (file_sha(database), file_sha(board_path), file_sha(puzzle_path))
    selected = [run["run_id"] for run in manifest["source"]["selected_runs"]]
    assert "run-alpha-global" in selected and "run-alpha-local" not in selected
    assert "run-beta-global" in selected and "run-beta-local" not in selected
    assert manifest["walkthrough"]["moves"] == ["west", "south", "east"]


def test_repeated_runs_replace_stale_output_byte_for_byte_with_special_paths() -> None:
    """Recovery remains stable in paths with spaces and apostrophes and replaces stale bytes."""
    _, database, board, puzzles, output = fresh_baseline()
    first = run_recover(database, board, puzzles, output)
    assert first.returncode == 0, first.stderr
    expected = output.read_bytes()
    output.write_bytes(b"stale manifest bytes\n")
    os.chown(output, CANDIDATE_UID, CANDIDATE_GID)
    second = run_recover(database, board, puzzles, output)
    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == expected


def test_direct_recovery_does_not_depend_on_database_or_format_helpers() -> None:
    """Core recovery still succeeds when common helper command names are hostile traps."""
    _, database, board, puzzles, output = fresh_baseline()
    trap_dir = workspace("maze helper traps ")
    for name in ["sqlite3", "mlflow", "python3", "yq", "jq", "tomlq"]:
        trap = trap_dir / name
        trap.write_text("#!/bin/sh\nexit 97\n")
        os.chown(trap, CANDIDATE_UID, CANDIDATE_GID)
        trap.chmod(0o755)
    result = candidate_run(
        [BIN, "recover", "--tracking-db", database, "--maze-yaml", board,
         "--puzzles-toml", puzzles, "--output", output],
        env={"PATH": f"{trap_dir}:/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mutation", ["duplicate_tag", "chunk_gap", "digest", "parent", "metric"])
def test_malformed_eligible_tracking_records_fail_closed_and_preserve_output(mutation: str) -> None:
    """Every malformed eligible-run surface aborts before replacing an existing manifest."""
    database, board, puzzles, output, _, _ = generated_case()
    database.chmod(0o660)
    connection = sqlite3.connect(database)
    if mutation == "duplicate_tag":
        connection.execute(
            "INSERT INTO tags VALUES(?,?,?)",
            ("run-gamma", "maze.target_id", "gamma-44"),
        )
    elif mutation == "chunk_gap":
        connection.execute(
            "UPDATE params SET key='maze.patch.003' WHERE run_uuid='run-prism' "
            "AND key='maze.patch.001'"
        )
    elif mutation == "digest":
        connection.execute(
            "UPDATE tags SET value=? WHERE run_uuid='run-gamma' "
            "AND key='maze.patch_sha256'", ("0" * 64,),
        )
    elif mutation == "parent":
        connection.execute(
            "UPDATE tags SET value='absent-parent' WHERE run_uuid='run-beta-global' "
            "AND key='maze.parent_run_id'"
        )
    else:
        connection.execute(
            "INSERT INTO metrics VALUES(?,?,?,?,?)",
            ("run-gamma", "maze.commit", 0.0, 99999, 1),
        )
    connection.commit()
    connection.close()
    database.chmod(0o440)
    sentinel = b"keep-this-manifest-exactly\n"
    output.write_bytes(sentinel)
    os.chown(output, CANDIDATE_UID, CANDIDATE_GID)
    result = run_recover(database, board, puzzles, output)
    assert result.returncode == 3
    assert output.read_bytes() == sentinel
    assert not list(output.parent.glob(output.name + ".tmp.*"))


def test_ineligible_broken_runs_and_old_metric_history_are_ignored() -> None:
    """Deleted, running, foreign-level, and superseded metric history never poison recovery."""
    database, board_path, puzzle_path, output, board, puzzles = generated_case()
    database.chmod(0o660)
    connection = sqlite3.connect(database)
    add_run(connection, experiment_id=731, level_id="foreign-level",
            run_id="foreign-malformed", kind="room", target="alpha-17", revision=1,
            patch={"exits": {"west": "never"}}, timestamp=999)
    add_run(connection, experiment_id=731, level_id=board["level_id"],
            run_id="running-malformed", kind="room", target="alpha-17", revision=1,
            patch={"exits": {"west": "never"}}, timestamp=1000, status="RUNNING")
    connection.execute(
        "UPDATE params SET value='not-a-revision' WHERE run_uuid='running-malformed' "
        "AND key='maze.revision'"
    )
    connection.commit()
    connection.close()
    database.chmod(0o440)
    result = run_recover(database, board_path, puzzle_path, output)
    assert result.returncode == 0, result.stderr
    manifest = assert_published_manifest(
        output, database, board_path, puzzle_path, NOVEL_MANIFEST_SEAL)
    selected = [run["run_id"] for run in manifest["source"]["selected_runs"]]
    assert "foreign-malformed" not in selected
    assert "running-malformed" not in selected


@pytest.mark.parametrize("kind", ["yaml", "toml"])
def test_malformed_configuration_is_exit_two_and_transactional(kind: str) -> None:
    """Syntax failures in either damaged configuration are classified before publication."""
    _, database, board, puzzles, output = fresh_baseline()
    if kind == "yaml":
        board = candidate_file(board.parent / "broken.yaml", b"rooms: [\n")
    else:
        puzzles = candidate_file(
            puzzles.parent / "broken.toml",
            b'format = "mlflow-maze-puzzles-v1"\nformat = "mlflow-maze-puzzles-v1"\n',
        )
    sentinel = b"configuration-sentinel\n"
    output.write_bytes(sentinel)
    os.chown(output, CANDIDATE_UID, CANDIDATE_GID)
    result = run_recover(database, board, puzzles, output)
    assert result.returncode == 2
    assert output.read_bytes() == sentinel


def test_relative_duplicate_unknown_and_input_alias_arguments_are_rejected() -> None:
    """The exact CLI shape rejects ambiguous paths and options without touching inputs."""
    _, database, board, puzzles, output = fresh_baseline()
    commands = [
        [BIN, "recover", "--tracking-db", "relative.sqlite", "--maze-yaml", board,
         "--puzzles-toml", puzzles, "--output", output],
        [BIN, "recover", "--tracking-db", database, "--tracking-db", database,
         "--puzzles-toml", puzzles, "--output", output],
        [BIN, "recover", "--tracking-db", database, "--maze-yaml", board,
         "--puzzles-toml", puzzles, "--mystery", output],
        [BIN, "recover", "--tracking-db", database, "--maze-yaml", board,
         "--puzzles-toml", puzzles, "--output", database],
    ]
    before = file_sha(database)
    for command in commands:
        result = candidate_run(command)
        assert result.returncode == 2
    assert file_sha(database) == before
    assert not output.exists()


def test_no_globally_solvable_revision_set_returns_four_without_partial_output() -> None:
    """A structurally valid store with no complete playable graph is not published."""
    database, board, puzzles, output, _, _ = generated_case()
    database.chmod(0o660)
    connection = sqlite3.connect(database)
    for table in ["params", "metrics", "tags"]:
        connection.execute(f"DELETE FROM {table} WHERE run_uuid='run-gamma'")
    connection.execute("DELETE FROM runs WHERE run_uuid='run-gamma'")
    connection.commit()
    connection.close()
    database.chmod(0o440)
    sentinel = b"unsolved-output-sentinel\n"
    output.write_bytes(sentinel)
    os.chown(output, CANDIDATE_UID, CANDIDATE_GID)
    result = run_recover(database, board, puzzles, output)
    assert result.returncode == 4
    assert output.read_bytes() == sentinel


@pytest.mark.parametrize("tamper", ["move", "transcript", "digest"])
def test_replay_rejects_tampered_walkthrough_without_printing_partial_transcript(tamper: str) -> None:
    """Replay independently binds graph transitions, transcript lines, and the SHA commitment."""
    _, database, board, puzzles, output = fresh_baseline()
    recovered = run_recover(database, board, puzzles, output)
    assert recovered.returncode == 0, recovered.stderr
    manifest = json.loads(output.read_text())
    if tamper == "move":
        manifest["walkthrough"]["moves"][0] = "west"
    elif tamper == "transcript":
        manifest["walkthrough"]["transcript"][0] = "enter 0 counterfeit"
    else:
        manifest["walkthrough"]["sha256"] = "0" * 64
    output.write_text(json.dumps(manifest))
    os.chown(output, CANDIDATE_UID, CANDIDATE_GID)
    result = candidate_run([BIN, "replay", "--manifest", output])
    assert result.returncode == 2
    assert result.stdout == ""
