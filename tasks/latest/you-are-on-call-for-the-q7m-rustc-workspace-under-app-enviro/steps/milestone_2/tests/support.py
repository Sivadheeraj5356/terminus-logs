"""Shared verifier helpers for milestone tests."""
from __future__ import annotations

import hashlib
from pathlib import Path

ENV = Path("/app/environment")
OUT = Path("/app/output")

FIXTURE_SHA256 = {
    "seq_r4.pgn": "b17c07d1ad0ec5e639a932537501bd84e2b0b460387b8a02c2942d88c3718883",
    "seq_u8.pgn": "cdfedd5a9c851a403406a622d53ba214f1649db60584e69107ccdfd330e927ad",
    "seq_k2.pgn": "43bfcf170a62682d0e9b9bac10d41a6a77982d268a7aa8ac8b2ce2d78217c81c",
}

OUTPUT_FOR_FIXTURE = {
    "seq_r4.pgn": OUT / "event_trace.jsonl",
    "seq_u8.pgn": OUT / "u8.jsonl",
    "seq_k2.pgn": OUT / "k2.jsonl",
}


def assert_fixture_unmodified(name: str) -> None:
    path = ENV / "fixtures" / name
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = FIXTURE_SHA256[name]
    assert digest == expected, f"fixture tampered or missing: {name}"


def trace_path_for(name: str) -> Path:
    return OUTPUT_FOR_FIXTURE[name]


def assert_complete_trace(name: str, rows: list[dict], move_count: int) -> None:
    assert len(rows) == move_count, (
        f"{name}: trace has {len(rows)} rows, expected {move_count} moves"
    )
    plies = [row["ply"] for row in rows]
    assert plies == list(range(1, move_count + 1)), f"{name}: ply sequence not contiguous"
