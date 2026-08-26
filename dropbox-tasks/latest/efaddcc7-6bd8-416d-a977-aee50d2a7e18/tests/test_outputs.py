"""Behavioral checks for the sealed-turn lattice play outputs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path("/app")
SHEET = APP / "output" / "sheet.json"
VLOG = APP / "output" / "vlog.jsonl"
MOD = 1000003
CASES_PATH = "/app/environment/fixtures/cases.toml"

# Frozen copies of public fixtures so expectations are not editable via env maps.
FROZEN_CASES = [{'id': 'grid_a', 'map': 'grid_a', 'epoch': 7, 'salt': 11, 'weight': 3}, {'id': 'grid_b', 'map': 'grid_b', 'epoch': 9, 'salt': 13, 'weight': 5}, {'id': 'grid_c', 'map': 'grid_c', 'epoch': 4, 'salt': 17, 'weight': 2}, {'id': 'grid_x', 'map': 'grid_x', 'epoch': 12, 'salt': 19, 'weight': 4}, {'id': 'grid_y', 'map': 'grid_y', 'epoch': 15, 'salt': 23, 'weight': 7}]
FROZEN_MAPS = {'grid_a': {'width': 5, 'height': 5, 'walls': [[2, 2]], 'players': [{'id': 0, 'start': [0, 0], 'intent': [1, 0]}, {'id': 1, 'start': [4, 4], 'intent': [3, 4]}]}, 'grid_b': {'width': 5, 'height': 5, 'walls': [[1, 3], [3, 1]], 'players': [{'id': 0, 'start': [0, 1], 'intent': [0, 2]}, {'id': 1, 'start': [4, 3], 'intent': [4, 2]}]}, 'grid_c': {'width': 6, 'height': 4, 'walls': [[2, 1], [3, 2]], 'players': [{'id': 0, 'start': [0, 0], 'intent': [1, 1]}, {'id': 1, 'start': [5, 3], 'intent': [4, 2]}]}, 'grid_x': {'width': 7, 'height': 5, 'walls': [[3, 2], [3, 3], [1, 4]], 'players': [{'id': 0, 'start': [0, 2], 'intent': [2, 2]}, {'id': 1, 'start': [6, 2], 'intent': [5, 1]}, {'id': 2, 'start': [0, 4], 'intent': [0, 3]}]}, 'grid_y': {'width': 6, 'height': 6, 'walls': [[2, 2], [2, 3], [3, 2]], 'players': [{'id': 0, 'start': [0, 0], 'intent': [1, 2]}, {'id': 1, 'start': [5, 5], 'intent': [4, 3]}]}}


def _is_hex16(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 16:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _sha16(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _cell(width: int, x: int, y: int) -> int:
    return y * width + x


def _locked_cells(m: dict) -> list[int]:
    players = sorted(m["players"], key=lambda p: p["id"])
    return [_cell(m["width"], p["intent"][0], p["intent"][1]) for p in players]


def _expected_digest(slots: list[int], salt: int) -> str:
    ordered = sorted(v & 0xFFFFFFFF for v in slots)
    parts = [f"{v:08x}" for v in ordered]
    payload = ":".join(parts) + "#" + format(salt, "x")
    return _sha16(payload)


def _expected_mix(cells: list[int], weight: int) -> int:
    acc = 0
    for cell in sorted(cells):
        acc = (acc + cell * weight) % MOD
    return acc


def _expected_cert(digest: str, epoch: int, cells: list[int]) -> str:
    payload = digest + "|" + str(epoch) + "|" + ",".join(str(c) for c in sorted(cells))
    return _sha16(payload)


def _expected_lit(m: dict, cells: list[int]) -> list[int]:
    walls = {(w[0], w[1]) for w in m["walls"]}
    lit: set[int] = set()
    for cell in cells:
        x0 = cell % m["width"]
        y0 = cell // m["width"]
        for y in range(m["height"]):
            for x in range(m["width"]):
                if (x, y) in walls:
                    continue
                if abs(x - x0) + abs(y - y0) <= 2:
                    lit.add(_cell(m["width"], x, y))
    return sorted(lit)


def _expect_case(c: dict) -> dict:
    m = FROZEN_MAPS[c["map"]]
    cells = _locked_cells(m)
    digest = _expected_digest(cells, c["salt"])
    mix = _expected_mix(cells, c["weight"])
    cert = _expected_cert(digest, c["epoch"], cells)
    lit = _expected_lit(m, cells)
    return {
        "id": c["id"],
        "epoch": c["epoch"],
        "digest": digest,
        "mix": mix,
        "cert": cert,
        "cells": sorted(cells),
        "lit": lit,
    }


def _run_play() -> None:
    if SHEET.exists():
        SHEET.unlink()
    if VLOG.exists():
        VLOG.unlink()
    APP.joinpath("output").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["npm", "run", "play", "--", "--cases", CASES_PATH],
        cwd="/app/environment",
        check=True,
        capture_output=True,
        text=True,
    )


def _load_sheet() -> dict:
    assert SHEET.is_file(), "sheet.json missing"
    return json.loads(SHEET.read_text(encoding="utf-8"))


def _load_vlog() -> list[dict]:
    assert VLOG.is_file(), "vlog.jsonl missing"
    rows = []
    for line in VLOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


@pytest.fixture(scope="module")
def artifacts():
    _run_play()
    sheet = _load_sheet()
    vlog = _load_vlog()
    want_by_id = {c["id"]: _expect_case(c) for c in FROZEN_CASES}
    return SimpleNamespace(sheet=sheet, vlog=vlog, cases=FROZEN_CASES, exp=want_by_id)


def test_f3_row_shape(artifacts):
    """Sheet/vlog shapes are valid and mix values follow k_rules accounting."""
    sheet = artifacts.sheet
    assert "cases" in sheet and "run_digest" in sheet
    assert _is_hex16(sheet["run_digest"])
    ids = [row["id"] for row in sheet["cases"]]
    assert ids == [c["id"] for c in artifacts.cases]
    for row in sheet["cases"]:
        for key in ("epoch", "digest", "mix", "cert", "cells", "lit"):
            assert key in row
        assert _is_hex16(row["digest"])
        assert _is_hex16(row["cert"])
        assert isinstance(row["mix"], int)
        assert row["cells"] == sorted(row["cells"])
        assert row["lit"] == sorted(row["lit"])
        exp = artifacts.exp[row["id"]]
        assert row["mix"] == exp["mix"]
    v_ids = [row["id"] for row in artifacts.vlog]
    assert v_ids == ids
    for row in artifacts.vlog:
        for key in ("epoch", "digest", "cert", "cells"):
            assert key in row


def test_m2_qz_order(artifacts):
    """Digests follow sorted-slot + salt rules from k_rules.md."""
    by_id = {row["id"]: row for row in artifacts.sheet["cases"]}
    for cid, exp in artifacts.exp.items():
        assert by_id[cid]["digest"] == exp["digest"]


def test_n4_pl_rerun(artifacts):
    """Mix values follow intent-cell ascending charge from k_rules.md."""
    by_id = {row["id"]: row for row in artifacts.sheet["cases"]}
    for cid, exp in artifacts.exp.items():
        assert by_id[cid]["mix"] == exp["mix"]


def test_k8_edge_bind(artifacts):
    """Certificates bind digest, epoch, and sorted cells."""
    by_id = {row["id"]: row for row in artifacts.sheet["cases"]}
    for cid, exp in artifacts.exp.items():
        assert by_id[cid]["cert"] == exp["cert"]
        assert by_id[cid]["cells"] == exp["cells"]
        assert by_id[cid]["lit"] == exp["lit"]


def test_r6_perm_x(artifacts):
    """Held-out geometry case grid_x matches digest and lit contract."""
    row = next(r for r in artifacts.sheet["cases"] if r["id"] == "grid_x")
    exp = artifacts.exp["grid_x"]
    assert row["digest"] == exp["digest"]
    assert row["lit"] == exp["lit"]
    assert row["cert"] == exp["cert"]


def test_w1_perm_y(artifacts):
    """Held-out budget-mask case grid_y matches mix and cert contract."""
    row = next(r for r in artifacts.sheet["cases"] if r["id"] == "grid_y")
    exp = artifacts.exp["grid_y"]
    assert row["mix"] == exp["mix"]
    assert row["cert"] == exp["cert"]
    assert row["digest"] == exp["digest"]


def test_h9_idempo(artifacts):
    """Idempotent regenerate after delete matches contract digests."""
    first = artifacts.sheet
    if SHEET.exists():
        SHEET.unlink()
    if VLOG.exists():
        VLOG.unlink()
    _run_play()
    second = _load_sheet()
    assert first["run_digest"] == second["run_digest"]
    assert [r["digest"] for r in first["cases"]] == [r["digest"] for r in second["cases"]]
    assert [r["cert"] for r in first["cases"]] == [r["cert"] for r in second["cases"]]
    for row in second["cases"]:
        exp = artifacts.exp[row["id"]]
        assert row["digest"] == exp["digest"]
        assert row["cert"] == exp["cert"]


def test_s5_static_trap(artifacts):
    """Hand-written sheet without rebuild is overwritten by play and must match rules."""
    junk = format(0x1111222233334444, "016x")
    bogus = {
        "cases": [
            {
                "id": "grid_a",
                "epoch": 0,
                "digest": junk,
                "mix": 0,
                "cert": format(0x5555666677778888, "016x"),
                "cells": [],
                "lit": [],
            }
        ],
        "run_digest": format(0x9999aaaabbbbcccc, "016x"),
    }
    SHEET.write_text(json.dumps(bogus), encoding="utf-8")
    _run_play()
    sheet = _load_sheet()
    exp = artifacts.exp["grid_a"]
    row = next(r for r in sheet["cases"] if r["id"] == "grid_a")
    assert row["digest"] == exp["digest"]
    assert row["cert"] == exp["cert"]
    assert row["mix"] == exp["mix"]
    joined = "|".join(r["digest"] for r in sheet["cases"])
    assert sheet["run_digest"] == _sha16(joined)
