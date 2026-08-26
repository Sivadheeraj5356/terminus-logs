"""Verifier for d8 domain-transition observation rows."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
OUT = APP / "output" / "d8_observations.json"
RAW = APP / "var" / "d8_raw.jsonl"
STAMP = APP / "var" / "d8_stamp.txt"
JOURNAL = APP / "var" / "d8_pivot.jnl"
CASES = ("c_row_a", "c_row_b", "c_row_c")
PIVOT_BY_CASE = {
    "c_row_a": "k_a",
    "c_row_b": "k_b",
    "c_row_c": "k_c",
}
GATE_ALLOW = "A"
GATE_DENY = "D"

K_ROWS = "rows"
K_DIGEST = "gate_digest"
K_PROFILE = "profile"
K_CASE = "case_id"
K_IDX = "entry_idx"
K_GATE = "gate_code"
K_CFG = "cfg_mask"
K_SAMPLE = "sample_mask"
K_LIVE = "live_mask"
K_ROLE = "role_sample"
K_ROW_FP = "row_digest"
K_ROLE_TEXT = "role_text"
K_LINE = "line_text"


@pytest.fixture(scope="session", autouse=True)
def _build_environment_once() -> None:
    subprocess.run(["make", "-C", "/app/environment", "all", "-j2"], check=True)


def _tag_from_pair(name: str, line: str, slot: int) -> int:
    body = f"{name}|{line}|{slot}"
    h = 2166136261
    for byte in body.encode("utf-8"):
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _sha256_hex(data: bytes) -> str:
    proc = subprocess.run(
        ["python3", "/app/environment/lib/digest_check.py"],
        input=data,
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode("utf-8").strip()


def _row_fp(row: dict) -> str:
    body = "|".join(
        [
            row[K_CASE],
            str(row[K_IDX]),
            row[K_GATE],
            str(row[K_CFG]),
            str(row[K_SAMPLE]),
            str(row[K_LIVE]),
            row[K_ROLE],
        ]
    )
    return _sha256_hex(body.encode("utf-8"))[:8]


def _gate_digest(rows: list[dict]) -> str:
    ordered = sorted(rows, key=lambda r: (r[K_CASE], int(r[K_IDX])))
    blob = "\n".join(r[K_ROW_FP] for r in ordered)
    return _sha256_hex(blob.encode("utf-8"))


def _clear_artifacts() -> None:
    for path in (OUT, RAW, STAMP, JOURNAL):
        if path.exists():
            path.unlink()


def _run_pipeline() -> None:
    _clear_artifacts()
    subprocess.run(["/app/tools/h2_runner"], check=True)
    subprocess.run(["/app/tools/q1_emit"], check=True)


def _load() -> dict:
    _run_pipeline()
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    assert isinstance(doc[K_ROWS], list)
    return doc


def _rows(doc: dict, case_id: str) -> list[dict]:
    return sorted(
        [r for r in doc[K_ROWS] if r[K_CASE] == case_id],
        key=lambda r: int(r[K_IDX]),
    )


def _pivot_line(pivot_name: str) -> str:
    return (APP / "work" / "pivot" / f"{pivot_name}.txt").read_text(encoding="utf-8").strip()


def _split_tokens(line: str) -> list[str]:
    return [tok for tok in line.split(",") if tok]


def _slot_for_role(name: str, pivot_line: str) -> int:
    for slot, tok in enumerate(_split_tokens(pivot_line)):
        if name == tok:
            return slot
    return -1


def _expected_snap_mask(name: str, pivot_line: str) -> int:
    slot = _slot_for_role(name, pivot_line)
    if slot < 0:
        return 0
    tok = _split_tokens(pivot_line)[slot]
    return _tag_from_pair(name, tok, slot)


def _raw_lines() -> list[dict]:
    if not RAW.exists():
        return []
    out: list[dict] = []
    for line in RAW.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _journal_lines() -> list[dict]:
    if not JOURNAL.exists():
        return []
    out: list[dict] = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _surfaces_agree(row: dict) -> bool:
    return row[K_CFG] == row[K_SAMPLE] == row[K_LIVE]


def _tgt_row(case_id: str) -> str:
    return (
        APP / "environment" / "d8_cases" / case_id / "h7_fixture" / "tgt.te"
    ).read_text(encoding="utf-8")


def _row_bits(case_id: str) -> int:
    for line in _tgt_row(case_id).splitlines():
        if line.startswith("ROWBITS:"):
            return int(line.split(":", 1)[1], 16)
    return 0


def test_m00_a() -> None:
    """Accepted rows keep cfg_mask, sample_mask, and live_mask aligned."""
    doc = _load()
    assert doc[K_PROFILE] == "security_authority_split"
    assert len(doc[K_ROWS]) == 6
    for case_id in CASES:
        pivot_line = _pivot_line(PIVOT_BY_CASE[case_id])
        for row in _rows(doc, case_id):
            if row[K_GATE] == GATE_ALLOW:
                expect = _expected_snap_mask(row[K_ROLE_TEXT], pivot_line)
                assert int(row[K_CFG]) == expect
                assert int(row[K_SAMPLE]) == expect
                assert int(row[K_LIVE]) == expect
                assert _surfaces_agree(row)


def test_m01_b() -> None:
    """First batch entry 0 must deny with zeroed masks."""
    doc = _load()
    row = _rows(doc, "c_row_a")[0]
    assert row[K_GATE] == GATE_DENY
    assert int(row[K_CFG]) == 0
    assert int(row[K_SAMPLE]) == 0
    assert int(row[K_LIVE]) == 0


def test_m02_c() -> None:
    """First batch entry 1 accept mask must follow target row bits."""
    doc = _load()
    row = _rows(doc, "c_row_a")[1]
    assert row[K_GATE] == GATE_ALLOW
    expect = _tag_from_pair(row[K_ROLE_TEXT], row[K_LINE], 0)
    assert int(row[K_CFG]) == expect
    assert int(row[K_CFG]) != _row_bits("c_row_a")


def test_m03_d() -> None:
    """Third batch entry 0 must deny despite identical role label in prior batch."""
    doc = _load()
    row = _rows(doc, "c_row_c")[0]
    assert row[K_ROLE_TEXT] == "worker_u"
    assert row[K_GATE] == GATE_DENY
    assert int(row[K_CFG]) == 0


def test_m04_e() -> None:
    """Gate digest matches recomputed row fingerprints and is stable across reruns."""
    doc = _load()
    dig0 = doc[K_DIGEST]
    assert dig0 == _gate_digest(doc[K_ROWS])
    doc2 = _load()
    assert doc2[K_DIGEST] == dig0
    assert len(doc2[K_ROWS]) == 6


def test_m05_f() -> None:
    """Row text and fingerprints are preserved with disjoint accept masks per batch."""
    doc = _load()
    masks: list[set[int]] = []
    for case_id in CASES:
        row_line = ""
        for line in _tgt_row(case_id).splitlines():
            if line.startswith("ROW:"):
                row_line = line.split(":", 1)[1]
        for row in _rows(doc, case_id):
            assert row[K_LINE] == row_line
            assert row[K_ROW_FP] == _row_fp(row)
        masks.append({int(r[K_CFG]) for r in _rows(doc, case_id) if r[K_GATE] == GATE_ALLOW})
    for i in range(len(masks)):
        for j in range(i + 1, len(masks)):
            assert masks[i].isdisjoint(masks[j])


def test_m06_g() -> None:
    """Second batch entry 0 denies while entry 1 accepts."""
    doc = _load()
    row = _rows(doc, "c_row_b")[0]
    assert row[K_ROLE_TEXT] == "worker_u"
    assert row[K_GATE] == GATE_DENY
    row_ok = _rows(doc, "c_row_b")[1]
    assert row_ok[K_GATE] == GATE_ALLOW


def test_m07_h() -> None:
    """Raw trace fields and observation rows stay aligned across all six entries."""
    doc = _load()
    assert len(doc[K_ROWS]) == 6
    raw = _raw_lines()
    assert len(raw) == 6
    obs_by_key = {(r[K_CASE], int(r[K_IDX])): r for r in doc[K_ROWS]}
    for obj in raw:
        key = (obj["case_id"], int(obj["entry_idx"]))
        row = obs_by_key[key]
        assert row[K_GATE] == obj["gate_code"]
        assert row[K_ROLE] == obj["role_sample"]
    epochs = [int(obj["epoch"]) for obj in raw]
    batch_epochs = [epochs[0], epochs[2], epochs[4]]
    assert batch_epochs == sorted(batch_epochs)
    assert batch_epochs[0] < batch_epochs[1] < batch_epochs[2]


def test_m08_h() -> None:
    """Third batch accept tag must match the pivot token slot, not slot zero."""
    doc = _load()
    pivot_line = _pivot_line("k_c")
    row = _rows(doc, "c_row_c")[1]
    assert row[K_GATE] == GATE_ALLOW
    slot = _slot_for_role(row[K_ROLE_TEXT], pivot_line)
    assert slot == 2
    expect = _tag_from_pair(row[K_ROLE_TEXT], row[K_LINE], slot)
    assert int(row[K_SAMPLE]) == expect
    assert int(row[K_LIVE]) == expect


def test_m09_i() -> None:
    """Stamp file records gate_digest with a trailing newline."""
    doc = _load()
    assert STAMP.is_file()
    assert STAMP.read_text(encoding="utf-8").strip() == doc[K_DIGEST]


def test_m10_j() -> None:
    """Pivot journal records batch pivots in replay order."""
    _load()
    journal = _journal_lines()
    assert len(journal) == 3
    pivots = [entry["pivot"] for entry in journal]
    assert pivots == ["k_a", "k_b", "k_c"]
    batches = [int(entry["batch"]) for entry in journal]
    assert batches == sorted(batches)
    assert batches[0] < batches[1] < batches[2]


def test_m11_k() -> None:
    """Identical role labels under different pivot keys must yield different live masks."""
    doc = _load()
    row_b = _rows(doc, "c_row_b")[1]
    row_c = _rows(doc, "c_row_c")[1]
    assert row_b[K_ROLE_TEXT] == row_c[K_ROLE_TEXT] == "worker_u"
    assert row_b[K_GATE] == row_c[K_GATE] == GATE_ALLOW
    pivot_b = _pivot_line("k_b")
    pivot_c = _pivot_line("k_c")
    expect_b = _expected_snap_mask("worker_u", pivot_b)
    expect_c = _expected_snap_mask("worker_u", pivot_c)
    assert expect_b != expect_c
    assert int(row_b[K_LIVE]) == expect_b
    assert int(row_c[K_LIVE]) == expect_c


def test_m12_l() -> None:
    """Second pipeline run on a clean rebuild reproduces the same gate_digest."""
    doc = _load()
    dig0 = doc[K_DIGEST]
    subprocess.run(["make", "-C", "/app/environment", "clean"], check=True)
    subprocess.run(["make", "-C", "/app/environment", "all", "-j2"], check=True)
    doc2 = _load()
    assert doc2[K_DIGEST] == dig0


def test_m13_m() -> None:
    """Trap rows must deny in the raw trace before observation assembly."""
    _load()
    raw = _raw_lines()
    trap_keys = {
        ("c_row_a", 0),
        ("c_row_b", 0),
        ("c_row_c", 0),
    }
    raw_by_key = {(obj["case_id"], int(obj["entry_idx"])): obj for obj in raw}
    for key in trap_keys:
        assert raw_by_key[key]["gate_code"] == GATE_DENY


def test_m14_n() -> None:
    """Multi-token pivot accepts must not copy listing tags into live_mask."""
    doc = _load()
    row = _rows(doc, "c_row_c")[1]
    pivot_line = _pivot_line("k_c")
    slot = _slot_for_role(row[K_ROLE_TEXT], pivot_line)
    listing_tag = _tag_from_pair(row[K_ROLE_TEXT], row[K_LINE], 0)
    expect = _tag_from_pair(row[K_ROLE_TEXT], row[K_LINE], slot)
    assert slot > 0
    assert listing_tag != expect
    assert int(row[K_LIVE]) == expect
    assert int(row[K_LIVE]) != listing_tag
