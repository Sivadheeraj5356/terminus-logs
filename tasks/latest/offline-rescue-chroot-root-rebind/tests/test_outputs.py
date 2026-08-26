"""Outcome checks for the packaging matrix driver with arena recovery."""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output")
TRACE = OUT / "pack_trace.json"
RK_PACK = "/app/environment/tools/rk_pack/rk_pack"
ARENA_CTL = "/app/environment/tools/arena_ctl/arena_ctl"
BUILD_SH = "/app/environment/scripts/build_all.sh"
RESET_BIN = "/app/environment/fx_bins/base/pack_base.bin"
MIG_SH = "/app/environment/migrations/mig_rst.sh"
Q7 = ENV / "fx_bins/interim/q7_v9.json"
ARENA = OUT / ".pack_arena"

PROFILES = ("silt", "kite", "rune", "dale")
CAP_MODES = ("cap_strict", "cap_relaxed")
SIZE_CEILINGS = {"silt": 2048, "kite": 2560, "rune": 3072, "dale": 3584}

PROFILE_META = {
    "silt": {"tree_prefix": "/stage/silt", "epoch": 1, "backend": "bk_a"},
    "kite": {"tree_prefix": "/stage/kite", "epoch": 2, "backend": "bk_b"},
    "rune": {"tree_prefix": "/stage/rune", "epoch": 3, "backend": "bk_c"},
    "dale": {"tree_prefix": "/stage/dale", "epoch": 4, "backend": "bk_d"},
}


def assert_success(result: subprocess.CompletedProcess[str], label: str) -> None:
    if result.returncode != 0:
        raise AssertionError(
            f"{label} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def rebuild() -> None:
    result = subprocess.run(
        ["bash", BUILD_SH],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    assert_success(result, "build_all.sh")


def apply_reset() -> None:
    result = subprocess.run(
        [MIG_SH, "--apply-base", RESET_BIN],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert_success(result, "mig_rst.sh --apply-base")


def corrupt_arena() -> None:
    result = subprocess.run(
        [ARENA_CTL, "--corrupt"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert_success(result, "arena_ctl --corrupt")


def clear_arena() -> None:
    if ARENA.exists():
        ARENA.unlink()


def arena_present() -> bool:
    try:
        with open(ARENA, "rb"):
            return True
    except FileNotFoundError:
        return False


def listing_digest(listing: int) -> str:
    return digest_hex(str(listing).encode())


def run_matrix_at(out_path: str, *, expect_ok: bool = True) -> dict | None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [RK_PACK, "--matrix", "--out", out_path],
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if expect_ok:
        assert_success(result, "rk_pack --matrix")
        payload = json.loads(Path(out_path).read_text(encoding="utf-8"))
        assert isinstance(payload.get("rows"), list)
        return payload
    if result.returncode == 0:
        raise AssertionError("expected rk_pack failure")
    return None


def parse_backend(backend: str) -> tuple[int, list[tuple[int, int]]]:
    spec_path = ENV / "dm5/spec_bins" / f"{backend}.spec"
    count = 0
    pairs: list[tuple[int, int]] = []
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("count="):
            count = int(line.split("=", 1)[1])
        elif line.startswith("dev"):
            _, val = line.split("=", 1)
            maj_s, min_s = val.split(":", 1)
            pairs.append((int(maj_s), int(min_s)))
    return count, pairs[:count]


def expected_gen(cap_mode: str) -> int:
    return 1 if cap_mode == "cap_strict" else 2


def prefix_bytes(public_id: str, cap_mode: str) -> bytes:
    meta = PROFILE_META[public_id]
    gen = expected_gen(cap_mode)
    body = f"PREFIX={meta['tree_prefix']}\nEPOCH={meta['epoch']}\nGEN={gen}\n"
    return body.encode()


def dev_bytes(public_id: str, cap_mode: str) -> bytes:
    meta = PROFILE_META[public_id]
    count, pairs = parse_backend(meta["backend"])
    gen = expected_gen(cap_mode)
    payload = bytearray([count])
    for maj, minor in pairs:
        payload.extend(struct.pack("<HH", maj, minor))
    payload.extend(struct.pack("<I", gen))
    return bytes(payload)


def digest_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_prefix_hash(row: dict, public_id: str, cap_mode: str) -> None:
    material = prefix_bytes(public_id, cap_mode)
    want = digest_hex(material)
    assert row["prefix_digest"] == want
    assert row["prefix_digest"] == hashlib.sha256(material).hexdigest()


def row_for(trace_doc: dict, public_id: str, cap_mode: str) -> dict:
    for row in trace_doc["rows"]:
        if row["public_id"] == public_id and row["cap_mode"] == cap_mode:
            return row
    raise AssertionError(f"missing row for {public_id}/{cap_mode}")


def expected_manifest(trace_doc: dict) -> str:
    h = hashlib.sha256()
    for row in trace_doc["rows"]:
        h.update(row["prefix_digest"].encode())
        h.update(row["dev_digest"].encode())
        h.update(row["replay_digest"].encode())
    return h.hexdigest()


@pytest.fixture(scope="module", autouse=True)
def _build_once() -> None:
    assert Path(RK_PACK).is_file(), "rk_pack binary missing"
    assert Path(ARENA_CTL).is_file(), "arena_ctl binary missing"
    rebuild()


@pytest.fixture(scope="module")
def trace() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    clear_arena()
    apply_reset()
    return run_matrix_at("/app/output/pack_trace.json")


def test_r01_driver_exit(trace: dict) -> None:
    """Matrix driver exits zero and emits eight profile rows."""
    assert len(trace["rows"]) == len(PROFILES) * len(CAP_MODES)


def test_r02_schema_fields(trace: dict) -> None:
    """Graded trace JSON conforms to policy keys including replay and seal."""
    assert "manifest_sha256" in trace
    for row in trace["rows"]:
        for key in (
            "public_id",
            "cap_mode",
            "prefix_digest",
            "dev_digest",
            "replay_digest",
            "size_bytes",
            "gen_seal",
        ):
            assert key in row
        assert len(row["prefix_digest"]) == 64
        assert len(row["dev_digest"]) == 64
        assert len(row["replay_digest"]) == 64


def test_r03_prefix_live(trace: dict) -> None:
    """prefix_digest matches sha256 of rebuilt cache bytes with generation."""
    for public_id in PROFILES:
        for cap_mode in CAP_MODES:
            row = row_for(trace, public_id, cap_mode)
            assert_prefix_hash(row, public_id, cap_mode)


def test_r04_dev_live(trace: dict) -> None:
    """dev_digest matches sha256 of backend nodes plus trailing generation."""
    for public_id in PROFILES:
        for cap_mode in CAP_MODES:
            row = row_for(trace, public_id, cap_mode)
            want = digest_hex(dev_bytes(public_id, cap_mode))
            assert row["dev_digest"] == want


def test_r05_cap_cliff(trace: dict) -> None:
    """cap_strict seals odd generations; cap_relaxed seals even generations."""
    strict = row_for(trace, "kite", "cap_strict")
    relaxed = row_for(trace, "kite", "cap_relaxed")
    assert int(strict["gen_seal"]) % 2 == 1
    assert int(relaxed["gen_seal"]) % 2 == 0
    assert int(strict["gen_seal"]) > 0
    assert int(relaxed["gen_seal"]) > 0
    assert strict["prefix_digest"] != relaxed["prefix_digest"]


def test_r06_replay_seal(trace: dict) -> None:
    """replay_digest equals sha256 over live prefix and device materials."""
    for public_id in PROFILES:
        for cap_mode in CAP_MODES:
            row = row_for(trace, public_id, cap_mode)
            material = prefix_bytes(public_id, cap_mode) + dev_bytes(public_id, cap_mode)
            want = digest_hex(material)
            assert row["replay_digest"] == want


def test_r07_listing_trap(trace: dict) -> None:
    """Interim q7_v9.json totals alone do not satisfy terminal trace grading."""
    with open(Q7) as handle:
        stub = json.load(handle)
    listing = int(stub["listing_totals"]["silt"])
    row = row_for(trace, "silt", "cap_strict")
    assert listing == 3100
    bogus = listing_digest(listing)
    assert row["prefix_digest"] != bogus
    assert row["replay_digest"] != bogus


def test_r08_dirty_hold() -> None:
    """Second matrix without reset recovery fails after a successful pack."""
    clear_arena()
    apply_reset()
    first = run_matrix_at("/tmp/dprep.json")
    assert first is not None
    assert arena_present()
    run_matrix_at("/tmp/dfail.json", expect_ok=False)


def test_r09_idempotent_hold() -> None:
    """Documented reset recovery restores equal matrix manifests across reruns."""
    clear_arena()
    apply_reset()
    first = run_matrix_at("/app/output/seed1.json")
    apply_reset()
    second = run_matrix_at("/app/output/seed2.json")
    assert first is not None and second is not None
    assert first["manifest_sha256"] == second["manifest_sha256"]


def test_r10_corrupt_recover() -> None:
    """Corrupt arena then apply-reset restores graded digests."""
    clear_arena()
    apply_reset()
    baseline = run_matrix_at("/tmp/bcorr.json")
    corrupt_arena()
    run_matrix_at("/tmp/cfail.json", expect_ok=False)
    apply_reset()
    restored = run_matrix_at("/tmp/acorr.json")
    assert baseline is not None and restored is not None
    assert restored["manifest_sha256"] == baseline["manifest_sha256"]
    row = row_for(restored, "dale", "cap_strict")
    assert row["prefix_digest"] == digest_hex(prefix_bytes("dale", "cap_strict"))
    assert row["dev_digest"] == digest_hex(dev_bytes("dale", "cap_strict"))


def test_r11_manifest_aggregate(trace: dict) -> None:
    """manifest_sha256 matches documented aggregation over row digests."""
    assert trace["manifest_sha256"] == expected_manifest(trace)


def test_r12_ceiling_guard(trace: dict) -> None:
    """size_bytes within documented ceilings per profile."""
    for public_id in PROFILES:
        ceiling = SIZE_CEILINGS[public_id]
        for cap_mode in CAP_MODES:
            row = row_for(trace, public_id, cap_mode)
            assert int(row["size_bytes"]) <= ceiling
            assert int(row["size_bytes"]) > 0
