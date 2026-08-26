#!/usr/bin/env python3
"""Operational integrity checks for the CI runner cgroup attach service."""

import json
import re
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output/protocol_transcript.json")
BIN = Path("/app/bin/cg_xmit")
BUILD = ENV / "k4m" / "build_wrap.sh"
SEG = ENV / "engine" / "seg_v"
CLAIM_JRNL = SEG / "c7.jrnl"
ACCEPT = SEG / "a2.stamp"


def _round12(x: float) -> float:
    return float(f"{x:.12g}")


def _hex_alphabet() -> str:
    return "".join(chr(c) for c in list(range(48, 58)) + list(range(97, 103)))


def _fmt16(v: int) -> str:
    return format(v, "0" + str(16) + "x")


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def _rebuild_and_run() -> None:
    Path("/app/output").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["/app/environment/k4m/build_wrap.sh", "/app/environment", "/app/bin/cg_xmit"],
        check=True,
        text=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "/app/bin/cg_xmit",
            "run",
            "--pin",
            "49",
            "--env",
            "/app/environment",
            "--out",
            "/app/output/protocol_transcript.json",
        ],
        check=True,
        text=True,
        capture_output=True,
    )


def _load() -> dict:
    assert OUT.exists(), f"missing {OUT}"
    return json.loads(OUT.read_text(encoding="utf-8"))


def _arms() -> dict:
    text = (ENV / "fixtures" / "arm_tbl.toml").read_text(encoding="utf-8")
    arms = {}
    chunks = re.split(r"\[\[arm\]\]", text)
    for chunk in chunks[1:]:
        key = re.search(r'key\s*=\s*"([^"]*)"', chunk)
        held = re.search(r"held\s*=\s*(true|false)", chunk)
        assert key and held
        arms[key.group(1)] = held.group(1) == "true"
    return arms


def _arm_order() -> list[str]:
    text = (ENV / "fixtures" / "arm_tbl.toml").read_text(encoding="utf-8")
    keys = []
    for chunk in re.split(r"\[\[arm\]\]", text)[1:]:
        key = re.search(r'key\s*=\s*"([^"]*)"', chunk)
        assert key
        keys.append(key.group(1))
    return keys


def _annex_lane_count() -> int:
    ids = set()
    for line in (ENV / "fixtures" / "fx_h49.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        ids.add(json.loads(line)["lane_id"])
    return len(ids)


def _fnv64(s: str) -> int:
    h = 0xCBF29CE484222325
    for b in bytes(s, "utf-8"):
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def _parse_claim_jrnl() -> tuple[int, int, int]:
    assert CLAIM_JRNL.exists(), "missing durable latch journal c7.jrnl"
    parts = CLAIM_JRNL.read_text(encoding="utf-8").split()
    assert len(parts) >= 4 and parts[0] == "lat"
    latch = int(parts[1], 16)
    stamp = int(parts[2])
    bits = int(parts[3], 16)
    return latch, stamp, bits


@pytest.fixture(autouse=True)
def _fresh_pipeline():
    """Rematerialize the attach transcript before each check so order does not leak state."""
    _rebuild_and_run()
    yield


def test_u1_slot_hex():
    """Row vec_core hex slots match bag_a bytes and core shape."""
    doc = _load()
    assert doc["pin"] == 49
    assert isinstance(doc["rows"], list) and doc["rows"]
    for row in doc["rows"]:
        assert len(row["vec_core"]) == 4
        assert len(row["bag_a"]) == 4
        for hx, b in zip(row["vec_core"], row["bag_a"]):
            assert len(hx) == 2 and all(c in _hex_alphabet() for c in hx)
            assert int(hx, 16) == b


def test_u2_pair_width():
    """Mirror observation bags agree under coherent durable claim."""
    doc = _load()
    for row in doc["rows"]:
        assert row["bag_a"] == row["bag_b"]
        assert len(row["bag_a"]) == len(row["bag_b"]) == 4


def test_u3_rc_fields():
    """mag equals max abs res_delta; residual bands match fixture policy."""
    doc = _load()
    mags = [abs(float(r["res_delta"])) for r in doc["rows"]]
    expect = max(mags) if mags else 0.0
    for row in doc["rows"]:
        assert _round12(float(row["mag"])) == _round12(expect)
        assert _round12(float(row["band_lo"])) == _round12(-1.0)
        assert _round12(float(row["band_hi"])) == _round12(1.0)
        assert _round12(-1.0) <= _round12(float(row["res_delta"])) <= _round12(1.0)


def test_u4_label_text():
    """summary label and lane_n match annex distinct lane count."""
    doc = _load()
    assert doc["summary"]["label"] == "protocol"
    assert int(doc["rows"][0]["lane_n"]) == _annex_lane_count()
    for row in doc["rows"]:
        assert int(row["lane_n"]) == _annex_lane_count()


def test_u5_emit_fresh():
    """emit_hx and wit_hx follow REDUCE_HOME digest reduction."""
    doc = _load()
    for row in doc["rows"]:
        assert len(row["emit_hx"]) == 16 and all(c in _hex_alphabet() for c in row["emit_hx"])
    wit = 0
    for row in doc["rows"]:
        wit ^= int(row["emit_hx"], 16)
    assert doc["summary"]["wit_hx"] == _fmt16(wit)


def test_u6_twice_same():
    """Consecutive rematerialization runs emit identical operational transcripts."""
    first = _load()
    _rebuild_and_run()
    second = _load()
    assert first == second


def _alter_blob(text: str, old: list[int], new: list[int]) -> str:
    raw = _as_raw(text)
    pat = _seq(old)
    rep = _seq(new)
    if pat not in raw:
        return text
    return _from_raw(raw.replace(pat, rep, 1))


def _seq(xs: list[int]):
    return bytes(xs)


def _as_raw(text: str) -> bytes:
    return text.encode()


def _from_raw(raw: bytes) -> str:
    return raw.decode()


def _ops_mod_src(root: str) -> Path:
    d = ENV / root
    return next(p for p in d.iterdir() if p.suffix == ".rs" and p.stem.startswith("mod_"))


def _seg_files() -> list[Path]:
    return [p for p in SEG.iterdir() if p.suffix == ".seg"]


def test_u7_migrate_integrity():
    """Attach transcript digests track hierarchy migrate packing under rematerialization."""
    src = _ops_mod_src("r2v")
    original = src.read_text(encoding="utf-8")
    try:
        altered = original.replace("149", "148")
        if altered == original:
            altered = original.replace("23", "22")
        src.write_text(altered, encoding="utf-8")
        before = _load()
        _rebuild_and_run()
        after = _load()
        assert before["summary"]["wit_hx"] != after["summary"]["wit_hx"] or before["rows"] != after["rows"]
    finally:
        src.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_u8_claim_integrity():
    """Durable-first bag coherence is enforced when claim packing drifts from policy."""
    src = _ops_mod_src("t6n")
    original = src.read_text(encoding="utf-8")
    try:
        altered = _alter_blob(
            original,
            [62, 61],
            [60, 32],
        )
        if altered == original:
            altered = _alter_blob(original, [60, 60, 32, 49], [60, 60, 32, 50])
        src.write_text(altered, encoding="utf-8")
        _rebuild_and_run()
        doc = _load()
        bags_diverge = any(r["bag_a"] != r["bag_b"] for r in doc["rows"])
        assert bags_diverge or int(doc["summary"]["viol"]) > 0
    finally:
        src.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_u9_combine_integrity():
    """Held-out nesting arm digests track nest combine ordering under rematerialization."""
    src = _ops_mod_src("u9p")
    original = src.read_text(encoding="utf-8")
    try:
        g = [103, 97, 116, 101, 40, 41, 59]
        s = [115, 105, 100, 101, 40, 41, 59]
        raw = _as_raw(original)
        raw2 = (
            raw.replace(_seq(g), _seq([1, 2, 3, 4, 5, 6, 7]), 1)
            .replace(_seq(s), _seq(g), 1)
            .replace(_seq([1, 2, 3, 4, 5, 6, 7]), _seq(s), 1)
        )
        altered = _from_raw(raw2)
        if altered == original:
            altered = _alter_blob(original, [32, 49, 10], [32, 48, 10])
        src.write_text(altered, encoding="utf-8")
        before_arms = {r["arm_key"]: r["emit_hx"] for r in _load()["rows"]}
        _rebuild_and_run()
        after = _load()
        after_arms = {r["arm_key"]: r["emit_hx"] for r in after["rows"]}
        assert set(after_arms) == set(_arms())
        assert before_arms != after_arms
    finally:
        src.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_u10_rematerialize_overwrite():
    """Planted transcript is replaced by the documented build and run rematerialization."""
    fake = {
        "pin": 49,
        "rows": [
            {
                "arm_key": ("for" + "ged"),
                "vec_core": ["00"] * 4,
                "bag_a": [0, 0, 0, 0],
                "bag_b": [0, 0, 0, 0],
                "mag": 0.0,
                "lane_n": 1,
                "emit_hx": "00" * 8,
                "held": 0.0,
                "band_lo": -1.0,
                "band_hi": 1.0,
                "res_delta": 0.0,
            }
        ],
        "summary": {
            "label": "protocol",
            "n_rows": 99,
            "wit_hx": "00" * 8,
            "viol": 0,
        },
    }
    OUT.write_text(json.dumps(fake), encoding="utf-8")
    src = _ops_mod_src("w3h")
    original = src.read_text(encoding="utf-8")
    try:
        needle = _seq([102, 111, 114, 32, 116, 32, 105, 110, 32, 116, 97, 114, 103, 101, 116, 115])
        rep = needle + _seq([46, 105, 116, 101, 114, 40, 41, 46, 116, 97, 107, 101, 40, 48, 41])
        raw = _as_raw(original)
        if needle in raw:
            altered = _from_raw(raw.replace(needle, rep, 1))
        else:
            altered = original
        src.write_text(altered, encoding="utf-8")
        _rebuild_and_run()
        doc = _load()
        assert doc != fake
        assert int(doc["summary"]["n_rows"]) == 0
        marker = "for" + "ged"
        assert all(r.get("arm_key") != marker for r in doc["rows"])
    finally:
        src.write_text(original, encoding="utf-8")
        _rebuild_and_run()
        doc = _load()
        assert len(doc["rows"]) == len(_arms())


def test_u11_all_extras():
    """Every arm_tbl arm including held-out arms is present."""
    doc = _load()
    arms = _arms()
    keys = {r["arm_key"] for r in doc["rows"]}
    assert keys == set(arms)
    for row in doc["rows"]:
        expect = 1.0 if arms[row["arm_key"]] else 0.0
        assert _round12(float(row["held"])) == _round12(expect)
    held_keys = [k for k, h in arms.items() if h]
    assert held_keys
    for k in held_keys:
        assert k in keys


def test_u12_premature():
    """Gauge steady alone does not satisfy attach integrity without viol=0 convergence."""
    gauge = _run([str(BIN), "gauge", "--env", str(ENV)])
    assert "status=steady" in gauge.stdout
    doc = _load()
    assert int(doc["summary"]["viol"]) == 0
    assert int(doc["summary"]["n_rows"]) == len(_arms())
    segs = _seg_files()
    assert segs
    assert CLAIM_JRNL.exists()
    assert ACCEPT.exists()


def test_u13_cmd_order():
    """Documented build then attach-run sequence is required for rematerialization."""
    _run(
        [str(BIN), "run", "--env", str(ENV), "--out", str(Path("/app/output/protocol_transcript.json"))],
        check=False,
    )
    _rebuild_and_run()
    doc = _load()
    assert doc["pin"] == 49
    assert BUILD.exists()
    assert BIN.exists()


def test_u14_durable_first():
    """Durable journal stamp wins over runtime progress after nest cut."""
    doc = _load()
    assert int(doc["summary"]["viol"]) == 0
    for row in doc["rows"]:
        assert row["bag_a"] == row["bag_b"]
    segs = _seg_files()
    assert any(p.read_text(encoding="utf-8").strip().startswith("9 ") for p in segs)
    latch, stamp, _bits = _parse_claim_jrnl()
    assert stamp == 9
    assert ACCEPT.read_text(encoding="utf-8").strip() == f"{latch:08x}"


def test_u15_sens_steps():
    """Residual deltas stay inside documented band_lo/band_hi."""
    doc = _load()
    for row in doc["rows"]:
        rd = _round12(float(row["res_delta"]))
        assert _round12(-1.0) <= rd <= _round12(1.0)
        assert _round12(float(row["band_lo"])) <= rd <= _round12(float(row["band_hi"]))


def test_u16_known_good():
    """Summary wit_hx equals the reduction of row emit_hx values as defined by REDUCE_HOME."""
    doc = _load()
    wit = 0
    for row in doc["rows"]:
        wit ^= int(row["emit_hx"], 16)
        assert row["emit_hx"] != _fmt16(0) or _fnv64(row["arm_key"]) == 0
    assert doc["summary"]["wit_hx"] == _fmt16(wit)
    assert int(doc["summary"]["viol"]) == 0


def test_u17_latch_journal_authority():
    """On-disk latch journal is required and matches the accept stamp body."""
    latch, stamp, bits = _parse_claim_jrnl()
    assert stamp >= 1
    assert bits >= 0
    body = ACCEPT.read_text(encoding="utf-8").strip()
    assert body == f"{latch:08x}"
    CLAIM_JRNL.unlink()
    ACCEPT.unlink()
    _rebuild_and_run()
    assert CLAIM_JRNL.exists(), "rematerialize must rewrite latch journal"
    assert ACCEPT.exists(), "rematerialize must rewrite accept stamp"


def test_u18_accept_stamp_lifecycle():
    """Removing the accept stamp must not leave a coherent finished attach."""
    assert ACCEPT.exists()
    ACCEPT.unlink()
    _rebuild_and_run()
    assert ACCEPT.exists()
    latch, _, _ = _parse_claim_jrnl()
    assert ACCEPT.read_text(encoding="utf-8").strip() == f"{latch:08x}"


def test_u19_temporal_arm_cascade():
    """Arm digests are order-sensitive under the documented temporal packing chain."""
    arm_path = ENV / "fixtures" / "arm_tbl.toml"
    original = arm_path.read_text(encoding="utf-8")
    order = _arm_order()
    assert len(order) >= 2
    second_key = order[1]
    before = {r["arm_key"]: r["emit_hx"] for r in _load()["rows"]}
    try:
        chunks = re.split(r"(?=\[\[arm\]\])", original)
        header = chunks[0]
        blocks = [c for c in chunks[1:] if c.strip()]
        assert len(blocks) >= 2
        swapped = header + blocks[1] + blocks[0] + "".join(blocks[2:])
        arm_path.write_text(swapped, encoding="utf-8")
        _rebuild_and_run()
        after = {r["arm_key"]: r["emit_hx"] for r in _load()["rows"]}
        # Moving an arm to the head changes its prior-arm mix from nonzero to zero.
        assert after[second_key] != before[second_key]
        assert after != before
    finally:
        arm_path.write_text(original, encoding="utf-8")
        _rebuild_and_run()


def test_u20_journal_tamper_surfaces():
    """Tampering the latch journal after a run leaves stamp/journal disagreeing until rematerialize."""
    latch, stamp, bits = _parse_claim_jrnl()
    forged = (latch ^ 0xA5A5A5A5) & 0xFFFFFFFF
    CLAIM_JRNL.write_text(f"lat {forged:08x} {stamp} {bits:016x}\n", encoding="utf-8")
    stamp_body = ACCEPT.read_text(encoding="utf-8").strip()
    assert stamp_body != f"{forged:08x}"
    _rebuild_and_run()
    new_latch, _, _ = _parse_claim_jrnl()
    assert ACCEPT.read_text(encoding="utf-8").strip() == f"{new_latch:08x}"
    doc = _load()
    assert int(doc["summary"]["viol"]) == 0
    for row in doc["rows"]:
        assert row["bag_a"] == row["bag_b"]
