"""Domain checks for overlay rescue guard-log matrix convergence."""

import json
import subprocess
from pathlib import Path

ROOT = Path("/app/environment")
OUT = Path("/app/output/invariant_proof_log.json")
OG_CHECK = ROOT / "bin" / "og_check"
BUILD = ROOT / "scripts" / "build_all.sh"
MIG = ROOT / "migrations" / "mig_ov.sh"

ARMS = ("train_a", "train_b", "adv_c", "adv_d")


def _sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _u16(b: bytes, off: int) -> int:
    return b[off] | (b[off + 1] << 8)


def _pack_u32(n: int) -> bytes:
    n &= 0xFFFFFFFF
    return bytes((n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF, (n >> 24) & 0xFF))


def _pack_u16(n: int) -> bytes:
    n &= 0xFFFF
    return bytes((n & 0xFF, (n >> 8) & 0xFF))


def _slice_for(arm: str) -> bytes:
    name = "tc.mnt" if arm in ("train_a", "train_b") else "td.mnt"
    return (ROOT / "kit" / "blk" / name).read_bytes()


def _expected_plan(slice_b: bytes):
    flags = slice_b[4]
    id_a = _u16(slice_b, 5)
    id_b = _u16(slice_b, 7)
    id_c = _u16(slice_b, 9)
    pair_gap = _u16(slice_b, 11)
    merge = flags
    if flags & 1:
        merge ^= slice_b[4] ^ 0xA5
    if flags & 2:
        merge ^= slice_b[5] ^ 0x5A
    plan = (
        _pack_u32(id_a)
        + _pack_u32(id_b)
        + _pack_u32(id_c)
        + _pack_u32(flags)
        + _pack_u32(merge)
        + slice_b[13:25]
    )
    slots = [0, 1, 2]
    if flags & 2:
        slots[0], slots[1] = slots[1], slots[0]
    if (flags & 4) and id_c > id_b:
        slots[1], slots[2] = slots[2], slots[1]
    seq = _pack_u16(len(slots)) + b"".join(_pack_u16(s) for s in slots)
    first = slots[0]
    bw = (17 if flags & 1 else 0) + (merge & 0xFF) % 13
    bo = (19 if flags & 2 else 0) + first
    bn = (23 if flags & 4 else 0) + pair_gap
    bs = ((id_b ^ id_c) & 0xFFFF) if flags & 4 else 0
    return plan, seq, bw, bo, bn, bs, slice_b[13:29]


def _ensure_built():
    if not OG_CHECK.is_file():
        subprocess.run(["bash", "/app/environment/scripts/build_all.sh"], check=True)


def _run_matrix():
    _ensure_built()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["bash", "/app/environment/migrations/mig_ov.sh", "--restore-anchors"], check=True)
    proc = subprocess.run(
        [
            "/app/environment/bin/og_check",
            "--full-matrix",
            "--out",
            "/app/output/invariant_proof_log.json",
        ],
        capture_output=True,
        text=True,
    )
    err_text = proc.stderr or proc.stdout
    return proc.returncode, err_text


def _load_log():
    assert OUT.is_file(), "missing invariant_proof_log.json"
    return json.loads(OUT.read_text())


def _by_arm_kind(log):
    out = {}
    for row in log["instances"]:
        out[(row["arm_id"], row["path_kind"])] = row
    return out


def test_harness_exit_zero():
    """Full-matrix checker exits 0 for training and held-out arms."""
    rc, err_text = _run_matrix()
    assert rc == 0, err_text
    log = _load_log()
    assert log.get("schema_id") == "ov7"
    kinds = {(r["arm_id"], r["path_kind"]) for r in log["instances"]}
    for arm in ARMS:
        assert (arm, "uninterrupted") in kinds
        assert (arm, "recovered") in kinds


def test_log_hash_stable():
    """Proof-log digests match sha256 of rebuilt slice/plan/seq/anchor bytes."""
    rc, err_text = _run_matrix()
    assert rc == 0, err_text
    log = _load_log()
    for row in log["instances"]:
        slice_b = _slice_for(row["arm_id"])
        plan, seq, _bw, _bo, _bn, _bs, anchor = _expected_plan(slice_b)
        assert row["slice_digest"] == _sha(slice_b)
        assert row["anchor_digest"] == _sha(anchor)
        assert row["plan_hex"] == plan.hex()
        assert row["seq_hex"] == seq.hex()
        assert row["guard_trace"] == _sha(slice_b + plan + seq + anchor)


def test_public_smoke_rows():
    """Public train_a/train_b remain converging after generalization fixes."""
    rc, err_text = _run_matrix()
    assert rc == 0, err_text
    by = _by_arm_kind(_load_log())
    for arm in ("train_a", "train_b"):
        u = by[(arm, "uninterrupted")]
        r = by[(arm, "recovered")]
        assert u["guard_trace"] == r["guard_trace"]
        slice_b = _slice_for(arm)
        assert slice_b[4] == 0
        _plan, _seq, bw, bo, bn, bs, _anchor = _expected_plan(slice_b)
        assert u["band_w"] == bw
        assert u["band_o"] == bo
        assert u["band_n"] == bn
        assert u["band_s"] == bs


def test_w_merge_span():
    """Held-out adv_c requires whiteout merge_coord in the layer plan."""
    rc, err_text = _run_matrix()
    assert rc == 0, err_text
    by = _by_arm_kind(_load_log())
    row = by[("adv_c", "uninterrupted")]
    slice_b = _slice_for("adv_c")
    plan, seq, bw, bo, bn, bs, anchor = _expected_plan(slice_b)
    assert slice_b[4] & 1
    assert row["plan_hex"] == plan.hex()
    assert row["band_w"] == bw
    assert row["band_w"] >= 17


def test_opacity_span():
    """Opaque-directory arms require opacity-first entry ordering."""
    rc, err_text = _run_matrix()
    assert rc == 0, err_text
    by = _by_arm_kind(_load_log())
    row = by[("adv_c", "uninterrupted")]
    slice_b = _slice_for("adv_c")
    plan, seq, bw, bo, bn, bs, anchor = _expected_plan(slice_b)
    assert slice_b[4] & 2
    assert row["seq_hex"] == seq.hex()
    assert row["band_o"] == bo
    assert row["band_o"] >= 19


def test_nest_lane_trap():
    """Nested bind under chroot requires sibling-hold slot reordering."""
    rc, err_text = _run_matrix()
    assert rc == 0, err_text
    by = _by_arm_kind(_load_log())
    row = by[("adv_d", "uninterrupted")]
    slice_b = _slice_for("adv_d")
    plan, seq, bw, bo, bn, bs, anchor = _expected_plan(slice_b)
    assert slice_b[4] & 4
    assert row["plan_hex"] == plan.hex()
    assert row["seq_hex"] == seq.hex()
    assert row["band_n"] == bn
    assert row["band_n"] >= 23


def test_sib_pair_hold():
    """workdir/upperdir sibling band binds through emit anchor digest."""
    rc, err_text = _run_matrix()
    assert rc == 0, err_text
    by = _by_arm_kind(_load_log())
    row = by[("adv_d", "recovered")]
    slice_b = _slice_for("adv_d")
    plan, seq, bw, bo, bn, bs, anchor = _expected_plan(slice_b)
    assert row["band_s"] == bs
    assert row["band_s"] != 0
    assert row["anchor_digest"] == _sha(anchor)
    scratch = ROOT / "kit" / "scratch" / "anchor.bin"
    assert scratch.exists()
    assert scratch.read_bytes() == anchor


def test_cycle_preserve():
    """Repeat migration with restore keeps digests stable across cycles."""
    rc, err_text = _run_matrix()
    assert rc == 0, err_text
    first = _load_log()
    first_guards = {
        (r["arm_id"], r["path_kind"]): r["guard_trace"] for r in first["instances"]
    }

    subprocess.run(["bash", "/app/environment/migrations/mig_ov.sh"], check=True)
    subprocess.run(
        ["bash", "/app/environment/migrations/mig_ov.sh", "--restore-anchors"],
        check=True,
    )
    rc2, err2 = _run_matrix()
    assert rc2 == 0, err2
    second = _load_log()
    for row in second["instances"]:
        key = (row["arm_id"], row["path_kind"])
        assert row["guard_trace"] == first_guards[key]
    u = next(
        r
        for r in second["instances"]
        if r["arm_id"] == "adv_d" and r["path_kind"] == "uninterrupted"
    )
    r = next(
        r for r in second["instances"] if r["arm_id"] == "adv_d" and r["path_kind"] == "recovered"
    )
    assert u["guard_trace"] == r["guard_trace"]
