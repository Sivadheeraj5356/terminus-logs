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

# Milestone 1 is observation-only: the engine must be replayed exactly as
# shipped. Every Rust source and manifest that feeds the verifier's own
# `cargo build` is pinned byte-for-byte so a mismatch report generated from a
# modified (still-broken-differently) engine cannot pass this milestone.
# Later milestones intentionally do NOT pin these files - the agent must edit
# them there.
ENGINE_SOURCE_SHA256 = {
    "Cargo.lock": "e75f45e5d1c46dc15c6016e2c256e3f672db15bf965657166717d085aee54f23",
    "Cargo.toml": "8f90037ab1d062c892e3c48764083ef5de37b7a5a7098a7a8265c3d3a913e728",
    "h1/t3/Cargo.toml": "780c7c45ac07d446e68b7883c62c6aea176a0e7cba95c41b4f8014a3eb9e6fcb",
    "h1/t3/pkg/board_grid.rs": "53b2e7184b15dac19a9a4f7b6cf7ecf53791e3b72411b319e9e67cb4c79edbae",
    "h1/t3/pkg/move_apply.rs": "5154873c86a7ab34f7cdd832a07cd14de909a1b5bf500370a3838aa4423c4782",
    "h1/t3/pkg/op_b3.rs": "93cee07b6b4fe94714c8fb0731ce7940c55368e5078826247f11dff82fd4c877",
    "h1/t3/pkg/op_z2.rs": "e119eb9551d57525ebc5311f7b50bca927b7684c2890b7f92cd20a694479f1b0",
    "m2/p5/Cargo.toml": "ff990a1bb2c0dc46ed60470a51e88322a5a7eb36d5c20b009eed0179d591642e",
    "m2/p5/internal/ledger.rs": "89732aa2468215e23759843ab9804effe72c741df507ec0101b88b9791ac45f5",
    "m2/p5/internal/op_k1.rs": "b9e4d161f42529d2dc513367896ad1b09243c5784b37327250fde668ddfacdd8",
    "m2/p5/internal/op_y7.rs": "6993992b250d265a6c79b6e33d23a9bbee137c7eb1d742f6eed0f7af845bbda6",
    "m2/p5/src/lib.rs": "b2e650193802741206b77213bdbb87c808ac06a8ac5a296067d155c463417fbd",
    "q7m/Cargo.toml": "86f881c077b81db897191517944ce4475594739f53642eb8c893887548015019",
    "q7m/src/cli.rs": "8e6563a7924131f1d1428473b23a64a5aca7f2c861aae1d22ae185038484b8cc",
    "q7m/src/digest_stage.rs": "9732d7a93980d8ca0a4194eee025524276f0a3cf6968d98ea6b87d010a69a024",
    "q7m/src/lib.rs": "168d4b54b7070120d70b9f741478cd008b4be8d6e5766ce977c3fdb1004ecced",
    "q7m/src/main.rs": "36e8290ca7e0a31ca2264833d867bb6ce63c8323dbcecddbc52cd3c87f7981ea",
    "q7m/src/pipeline.rs": "9fc0dcc0c630c6dc13e00203c42becc9e65a6d687939209eaed177e507d1a924",
    "r3/n8/Cargo.toml": "d17dca2fb0599a59f6b4c711588306e209d018ed1348b47c3e4221cc8ff2e7fa",
    "r3/n8/src/lib.rs": "89453b612b73de194079a030e92626ba3b3515fd37b0bfbf681af79a38fbbd23",
    "r3/n8/src/op_j0.rs": "24447c5770e707ae0bc3ce118e26de0155d4ddbf037d9a490244fda87a44c715",
    "r3/n8/src/op_k4.rs": "77bdf9166219527f5b3f24701030989ff111a7a368d13217999694cdc4f52727",
}


def assert_engine_sources_unmodified() -> None:
    """Fail if any shipped engine source/manifest was edited, removed, or if
    extra Rust sources were smuggled into the workspace tree."""
    for rel, expected in ENGINE_SOURCE_SHA256.items():
        path = ENV / rel
        assert path.is_file(), f"engine source missing: {rel}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == expected, (
            f"engine source modified during observation-only milestone: {rel}"
        )
    pinned_rs = {rel for rel in ENGINE_SOURCE_SHA256 if rel.endswith(".rs")}
    found_rs = {
        str(p.relative_to(ENV))
        for p in ENV.rglob("*.rs")
        if "target" not in p.relative_to(ENV).parts
    }
    extra = found_rs - pinned_rs
    assert not extra, f"unexpected Rust sources added to workspace: {sorted(extra)}"


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
