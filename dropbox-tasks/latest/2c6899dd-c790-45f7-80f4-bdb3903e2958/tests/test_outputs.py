#!/usr/bin/env python3
"""Behavioral verifier for hex-lattice-capture-symmetry.

Authoring tree environment/ is mounted at /app for rebuild-and-run checks.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
CLI = "/app/target/release/arena_cli"
DATA = APP / "data"
OUT = APP / "output" / "runs"
DOCS = APP / "docs"


def _forge_release_bin() -> None:
    subprocess.run(
        ["cargo", "build", "--release", "--locked"],
        cwd=str(APP),
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(CLI).is_file(), "arena_cli missing after build"


def _drop_scenario_toml(name: str, body: str) -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / f"{name}.toml"
    path.write_text(body, encoding="utf-8")
    return path


def _invoke_arena(args: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [CLI, *args],
        cwd=str(APP),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"cli failed: {args}\n{proc.stderr}\n{proc.stdout}"


def _read_run_json(name: str) -> dict:
    path = OUT / f"{name}.json"
    assert path.is_file(), f"missing record {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _require_run_shape(rec: dict) -> None:
    for key in (
        "scenario_id",
        "seed",
        "mode",
        "final_counts",
        "history_len",
        "rejected_repeats",
        "position_digests",
        "terminal_digest",
    ):
        assert key in rec
    assert isinstance(rec["final_counts"], dict)
    assert "dark" in rec["final_counts"] and "light" in rec["final_counts"]
    assert isinstance(rec["position_digests"], list)
    assert isinstance(rec["terminal_digest"], str)
    assert len(rec["terminal_digest"]) == 64
    for d in rec["position_digests"]:
        assert isinstance(d, str) and len(d) == 64


@pytest.fixture(scope="module", autouse=True)
def build_once() -> None:
    assert (DOCS / "cli.md").is_file()
    assert (DOCS / "trace.md").is_file()
    _forge_release_bin()


def test_wrap_seat_matches_open_control() -> None:
    """Wrapped multi-stone exchange matches flat counterpart for equivalent interiors."""
    moves = "\n".join(
        [
            'move = "2,1,dark"',
            'move = "3,1,dark"',
            'move = "4,1,light"',
            'move = "2,2,light"',
            'move = "3,2,dark"',
            'move = "4,2,dark"',
            'move = "1,1,light"',
        ]
    )
    for mode, name in (("flat", "c1_base"), ("belt", "c1_torus")):
        _drop_scenario_toml(
            name,
            f'id = "{name}"\nseed = 11\nmode = "{mode}"\nw = 7\nh = 5\n\n[[moves]]\n{moves}\n',
        )
        _invoke_arena(["run", "--scenario", name, "--out", str(OUT)])
    a = _read_run_json("c1_base")
    b = _read_run_json("c1_torus")
    _require_run_shape(a)
    _require_run_shape(b)
    assert a["final_counts"] == b["final_counts"]
    assert a["history_len"] == b["history_len"]
    assert a["rejected_repeats"] == b["rejected_repeats"]
    assert a["position_digests"] == b["position_digests"]
    assert a["terminal_digest"] == b["terminal_digest"]


def test_boundary_alias_keeps_pair_equal() -> None:
    """Plane-boundary aliasing: one empty cell contributes multiple slot ids on belt."""
    moves = "\n".join(
        [
            'move = "2,1,dark"',
            'move = "3,1,dark"',
            'move = "2,2,light"',
            'move = "4,1,light"',
            'move = "3,2,dark"',
            'move = "1,1,light"',
        ]
    )
    for mode, name in (("flat", "c2_base"), ("belt", "c2_torus")):
        _drop_scenario_toml(
            name,
            f'id = "{name}"\nseed = 13\nmode = "{mode}"\nw = 6\nh = 4\n\n[[moves]]\n{moves}\n',
        )
        _invoke_arena(["run", "--scenario", name, "--out", str(OUT)])
    a = _read_run_json("c2_base")
    b = _read_run_json("c2_torus")
    _require_run_shape(a)
    _require_run_shape(b)
    assert a["final_counts"] == b["final_counts"]
    assert a["history_len"] == b["history_len"]
    assert a["position_digests"] == b["position_digests"]
    assert a["terminal_digest"] == b["terminal_digest"]
    assert a["rejected_repeats"] == b["rejected_repeats"]


def test_group_shape_across_dimensions() -> None:
    """Different dimensions / group shape still keep flat and belt derived state aligned."""
    moves = "\n".join(
        [
            'move = "1,1,dark"',
            'move = "2,1,dark"',
            'move = "1,2,dark"',
            'move = "3,1,light"',
            'move = "2,2,light"',
            'move = "3,2,dark"',
        ]
    )
    for mode, name in (("flat", "c3_base"), ("belt", "c3_torus")):
        _drop_scenario_toml(
            name,
            f'id = "{name}"\nseed = 17\nmode = "{mode}"\nw = 8\nh = 6\n\n[[moves]]\n{moves}\n',
        )
        _invoke_arena(["run", "--scenario", name, "--out", str(OUT)])
    a = _read_run_json("c3_base")
    b = _read_run_json("c3_torus")
    assert a["final_counts"] == b["final_counts"]
    assert a["terminal_digest"] == b["terminal_digest"]
    assert a["history_len"] == b["history_len"]


def test_immediate_repeat_refused_on_wrap() -> None:
    """Immediate repeated position rejected after a wrapped exchange."""
    moves = "\n".join(
        [
            'move = "3,2,light"',
            'move = "2,2,dark"',
            'move = "3,1,dark"',
            'move = "4,2,dark"',
            'move = "3,3,dark"',
            'move = "4,1,dark"',
            'move = "2,3,dark"',
            # leftover axial label for the just-cleared cell (3+6,2)
            'move = "9,2,light"',
        ]
    )
    _drop_scenario_toml(
        "d1_torus",
        f'id = "d1_torus"\nseed = 21\nmode = "belt"\nw = 6\nh = 5\n\n[[moves]]\n{moves}\n',
    )
    _invoke_arena(["run", "--scenario", "d1_torus", "--out", str(OUT)])
    rec = _read_run_json("d1_torus")
    _require_run_shape(rec)
    assert rec["rejected_repeats"] >= 1
    assert rec["history_len"] >= 1
    assert rec["final_counts"]["light"] == 0


def test_alias_coords_share_history() -> None:
    """Coordinate aliases for the same wrapped cell yield stable derived history."""
    base_moves = "\n".join(
        [
            'move = "1,1,dark"',
            'move = "2,1,light"',
            'move = "1,2,dark"',
        ]
    )
    alias_moves = "\n".join(
        [
            'move = "7,1,dark"',  # 1+w
            'move = "8,1,light"',
            'move = "7,2,dark"',
        ]
    )
    _drop_scenario_toml(
        "d2_a",
        f'id = "d2_a"\nseed = 23\nmode = "belt"\nw = 6\nh = 5\n\n[[moves]]\n{base_moves}\n',
    )
    _drop_scenario_toml(
        "d2_b",
        f'id = "d2_b"\nseed = 23\nmode = "belt"\nw = 6\nh = 5\n\n[[moves]]\n{alias_moves}\n',
    )
    _invoke_arena(["run", "--scenario", "d2_a", "--out", str(OUT)])
    _invoke_arena(["run", "--scenario", "d2_b", "--out", str(OUT)])
    a = _read_run_json("d2_a")
    b = _read_run_json("d2_b")
    assert a["final_counts"] == b["final_counts"]
    assert a["history_len"] == b["history_len"]
    assert a["position_digests"] == b["position_digests"]
    assert a["terminal_digest"] == b["terminal_digest"]


def test_non_repeat_moves_advance() -> None:
    """Allowed non-repeating position still advances (no over-broad rejection)."""
    moves = "\n".join(
        [
            'move = "1,1,dark"',
            'move = "3,1,light"',
            'move = "2,2,dark"',
            'move = "4,2,light"',
            'move = "1,3,dark"',
        ]
    )
    _drop_scenario_toml(
        "d3_ok",
        f'id = "d3_ok"\nseed = 29\nmode = "belt"\nw = 7\nh = 5\n\n[[moves]]\n{moves}\n',
    )
    _invoke_arena(["run", "--scenario", "d3_ok", "--out", str(OUT)])
    rec = _read_run_json("d3_ok")
    _require_run_shape(rec)
    assert rec["rejected_repeats"] == 0
    assert rec["history_len"] == len(rec["position_digests"])
    dark = rec["final_counts"]["dark"]
    light = rec["final_counts"]["light"]
    assert dark + light == rec["history_len"]
    assert rec["history_len"] > 0


def test_resume_matches_full_exchange() -> None:
    """Continued saved exchange matches an uninterrupted run of the same sequence."""
    moves = "\n".join(
        [
            'move = "3,2,light"',
            'move = "2,2,dark"',
            'move = "3,1,dark"',
            'move = "4,2,dark"',
            'move = "3,3,dark"',
            'move = "4,1,dark"',
            'move = "2,3,dark"',  # capture / clear event inside prefix
            'move = "1,1,light"',
            'move = "5,1,dark"',
            'move = "1,2,light"',
        ]
    )
    _drop_scenario_toml(
        "e1_full",
        f'id = "e1_full"\nseed = 31\nmode = "belt"\nw = 6\nh = 5\n\n[[moves]]\n{moves}\n',
    )
    _drop_scenario_toml(
        "e1_journal",
        "id = \"e1_journal\"\nseed = 31\nmode = \"belt\"\nw = 6\nh = 5\n"
        f"journal_prefix = 7\n\n[[moves]]\n{moves}\n",
    )
    _invoke_arena(["run", "--scenario", "e1_full", "--out", str(OUT)])
    _invoke_arena(
        [
            "resume",
            "--journal",
            str(DATA / "e1_journal.toml"),
            "--out",
            str(OUT),
            "--tag",
            "e1_resume",
        ]
    )
    full = _read_run_json("e1_full")
    resumed = _read_run_json("e1_resume")
    _require_run_shape(full)
    _require_run_shape(resumed)
    assert full["final_counts"] == resumed["final_counts"]
    assert full["history_len"] == resumed["history_len"]
    assert full["position_digests"] == resumed["position_digests"]
    assert full["terminal_digest"] == resumed["terminal_digest"]


def test_resume_rewrite_is_stable() -> None:
    """Rerunning continuation rewrites the same record without stale contamination."""
    moves = "\n".join(
        [
            'move = "3,2,light"',
            'move = "2,2,dark"',
            'move = "3,1,dark"',
            'move = "4,2,dark"',
            'move = "3,3,dark"',
            'move = "4,1,dark"',
            'move = "2,3,dark"',
            'move = "0,0,light"',
            'move = "5,4,dark"',
        ]
    )
    _drop_scenario_toml(
        "e2_journal",
        "id = \"e2_journal\"\nseed = 37\nmode = \"belt\"\nw = 6\nh = 5\n"
        f"journal_prefix = 7\n\n[[moves]]\n{moves}\n",
    )
    OUT.mkdir(parents=True, exist_ok=True)
    stale = OUT / "e2_resume.json"
    stale.write_text('{"scenario_id":"stale","seed":0}\n', encoding="utf-8")

    args = [
        "resume",
        "--journal",
        str(DATA / "e2_journal.toml"),
        "--out",
        str(OUT),
        "--tag",
        "e2_resume",
    ]
    _invoke_arena(args)
    first = (OUT / "e2_resume.json").read_text(encoding="utf-8")
    rec = json.loads(first)
    _require_run_shape(rec)
    assert rec["scenario_id"] == "e2_resume"
    # Capture inside the saved prefix must remain visible in reconstructed history.
    assert rec["history_len"] == 9
    assert rec["final_counts"]["light"] == 1
    assert isinstance(rec["position_digests"], list)
    assert len(rec["terminal_digest"]) == len(rec["position_digests"][0])
    assert isinstance(rec["rejected_repeats"], int)
    assert rec["rejected_repeats"] >= 0
    assert all(len(d) == 64 for d in rec["position_digests"])
    assert len(rec["position_digests"]) == rec["history_len"]
    assert "dark" in rec["final_counts"]
    assert "light" in rec["final_counts"]
    assert rec["final_counts"]["dark"] >= 0
    assert isinstance(rec["seed"], int)
    assert isinstance(rec["history_len"], int)
    assert isinstance(rec["rejected_repeats"], int)
    assert isinstance(rec["seed"], int)
    assert isinstance(rec["mode"], str)
    assert isinstance(rec["scenario_id"], str)
    assert rec["history_len"] > 0

    _invoke_arena(args)
    second = (OUT / "e2_resume.json").read_text(encoding="utf-8")
    assert first == second
