from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/app/environment/tools")
from digest_ops import edge_hash_raw, witness_hex

OUT = Path("/app/output/coverage_map.json")
BIN = Path("/app/bin/lane_matrix")
FIXTURES = Path("/app/fixtures")
SPEC = Path("/app/spec")
BONDS = SPEC / "pin43" / "bonds.bin.meta.json"


def _edge_hash() -> bytes:
    data = json.loads(BONDS.read_text(encoding="utf-8"))
    lines = [f"{e['from']}\t{e['to']}" for e in data["edges"]]
    return edge_hash_raw(lines)


def _rebuild() -> None:
    proc = subprocess.run(
        ["bash", "/app/environment/tools/rebuild_bin.sh"],
        cwd="/app",
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert BIN.is_file(), "release binary missing"


def _regen() -> dict:
    if OUT.exists():
        OUT.unlink()
    _rebuild()
    proc = subprocess.run(
        [
            str(BIN),
            "--fixtures",
            str(FIXTURES),
            "--spec",
            str(SPEC),
            "--out",
            str(OUT),
        ],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert OUT.is_file(), "coverage_map.json was not written"
    return json.loads(OUT.read_text(encoding="utf-8"))


def _pack_ids() -> list[str]:
    ids = []
    for split in ("train", "held_out"):
        d = FIXTURES / split
        for p in sorted(d.glob("*.json")):
            ids.append(json.loads(p.read_text(encoding="utf-8"))["id"])
    return ids


def _row(doc: dict, pack_id: str) -> dict:
    inst = doc["instances"][pack_id]
    assert "rows" in inst and inst["rows"], f"missing rows for {pack_id}"
    return inst["rows"][0]


def _expected_visits(pack_path: Path) -> list[int]:
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    bonds = json.loads(BONDS.read_text(encoding="utf-8"))["edges"]
    n = len(pack["cells"])
    visits = [0] * n
    active = set()
    for o in pack["obs"]:
        visits[int(o["ix"])] += int(o.get("weight", 1))
        active.add(int(o["zone"]))
    for e in bonds:
        if int(e["from_zone"]) in active:
            visits[int(e["to_ix"])] += int(e.get("w", 1))
    return visits


def _residual(pack_path: Path, visits: list[int]) -> float:
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    bonds = json.loads(BONDS.read_text(encoding="utf-8"))["edges"]
    active = {int(o["zone"]) for o in pack["obs"]}
    edges = [e for e in bonds if int(e["from_zone"]) in active]
    if not edges:
        return 0.0
    unmet = sum(1 for e in edges if visits[int(e["to_ix"])] == 0)
    return unmet / len(edges)


def test_slate_roundtrip_latch():
    """Training packs expose required observation fields and obs frontier coverage."""
    doc = _regen()
    train_dir = FIXTURES / "train"
    for p in sorted(train_dir.glob("*.json")):
        pack = json.loads(p.read_text(encoding="utf-8"))
        row = _row(doc, pack["id"])
        assert "visits" in row and "residual_risk" in row
        assert "witness" in row and "seal_ok" in row
        assert "frontier_ids" in row and "cells" in row
        assert len(row["visits"]) == len(pack["cells"])
        obs_ix = {int(o["ix"]) for o in pack["obs"]}
        frontier = set(int(x) for x in row["frontier_ids"])
        assert obs_ix <= frontier


def test_arm_gap_absence():
    """Held-out and train packs accumulate zero annex frontier violations."""
    doc = _regen()
    assert int(doc["violation_count"]) == 0
    for pack_id in _pack_ids():
        row = _row(doc, pack_id)
        bonds = json.loads(BONDS.read_text(encoding="utf-8"))["edges"]
        pack = None
        for split in ("train", "held_out"):
            for p in (FIXTURES / split).glob("*.json"):
                data = json.loads(p.read_text(encoding="utf-8"))
                if data["id"] == pack_id:
                    pack = data
                    break
        assert pack is not None
        active = {int(o["zone"]) for o in pack["obs"]}
        frontier = {int(x) for x in row["frontier_ids"]}
        for e in bonds:
            if int(e["from_zone"]) in active:
                assert int(e["to_ix"]) in frontier


def test_order_stable_rows():
    """Visit vectors stay identical across two regenerations."""
    a = _regen()
    b = _regen()
    for pack_id in _pack_ids():
        assert _row(a, pack_id)["visits"] == _row(b, pack_id)["visits"]


def test_edge_hash_latch():
    """Visit vectors reflect annex edge application for each pack."""
    doc = _regen()
    for split in ("train", "held_out"):
        for p in sorted((FIXTURES / split).glob("*.json")):
            pack = json.loads(p.read_text(encoding="utf-8"))
            row = _row(doc, pack["id"])
            assert row["visits"] == _expected_visits(p)
            expected_risk = _residual(p, row["visits"])
            assert float(row["residual_risk"]) == expected_risk
            if split == "held_out":
                assert float(row["residual_risk"]) == 0.0


def test_partial_green_trap():
    """Populated visit rows must carry a complete non-zero sealed witness."""
    doc = _regen()
    edge_hash = _edge_hash()
    for pack_id in _pack_ids():
        row = _row(doc, pack_id)
        assert row["seal_ok"] is True
        assert row["witness"] != "0" * 64
        assert row["witness"] == witness_hex(row["visits"], edge_hash)


def test_idempotent_rewrite():
    """Second rewrite keeps artifact bytes and violation counters unchanged."""
    _regen()
    first = OUT.read_bytes()
    doc1 = json.loads(first.decode("utf-8"))
    _regen()
    second = OUT.read_bytes()
    doc2 = json.loads(second.decode("utf-8"))
    assert first == second
    assert doc1["violation_count"] == doc2["violation_count"]
