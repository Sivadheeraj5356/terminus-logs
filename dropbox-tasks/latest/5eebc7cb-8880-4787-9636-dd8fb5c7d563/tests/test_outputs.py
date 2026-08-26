#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output" / "sync_record.json"
BIN = Path("/tmp/fxctl")
SCHEMA = ENV / "contracts" / "sync_record.schema.json"

sys.path.insert(0, "/tests")
import fx_expect as dr  # noqa: E402

_COMPUTE = (
    dr.compute_a,
    dr.compute_b,
    dr.compute_c,
    dr.compute_d,
    dr.compute_e,
    dr.compute_f,
    dr.compute_g,
    dr.compute_h,
    dr.compute_i,
    dr.compute_j,
)
_REPLAY = dr.compute_k
_HELD = (
    dr.compute_n,
    dr.compute_o,
    dr.compute_p,
    dr.compute_l,
    dr.compute_r,
)
_TRAP = (
    dr.compute_s,
)
_cross_plain = dr.f7_cross_plain
_part_sig_f7 = dr.f7_part_sig
_byte_stable = dr.stable_hex


@pytest.fixture(scope="session", autouse=True)
def build_binary():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("GOMODCACHE", "/opt/gomodcache")
    subprocess.run(["bash", "/tests/compile_verifier_binary.sh"], check=True, env=env)


def _purge():
    subprocess.run(["bash", str(ENV / "scripts" / "purge_state.sh")], check=True)
    if OUT.exists():
        OUT.unlink()


def _run(case_id, phase):
    if OUT.exists():
        OUT.unlink()
    env = os.environ.copy()
    env.setdefault("GOMODCACHE", "/opt/gomodcache")
    proc = subprocess.run(
        [str(BIN), "--case", case_id, "--phase", phase, "--out", str(OUT)],
        cwd=str(APP),
        text=True,
        capture_output=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(OUT.read_text(encoding="utf-8"))
    dr.validate_record(data, SCHEMA)
    assert data["record_digest"] == dr.record_digest(data)
    return data


def test_k4_w9_dual_lane_shift():
    """k4 seal plus held-out w9 verify requires lane table idx shift and seed endian coupling."""
    k4 = _COMPUTE[0]()
    w9 = _HELD[0]()
    _purge()
    doc = _run("k4", "seal")
    assert doc["run_meta"]["case_id"] == k4["case_id"]
    for got, want in zip(doc["bind_rows"], k4["rows"], strict=True):
        assert got["key_idx"] == want["key_idx"]
        assert got["row_hex"] == want["row_hex"]
    shifted = _run("w9", "verify")
    assert shifted["bind_rows"][0]["key_idx"] == w9["key_idx"]
    assert shifted["bind_rows"][0]["row_hex"] == w9["row_hex"]
    assert shifted["bind_rows"][1]["aad_hex"] == w9["aad_hex"]
    assert shifted["cross_aad_digest"] == w9["cross_aad_digest"]


def test_b2_slice_offset_ladder():
    """b2 held-out arm couples footer chunk offset parsing with AAD lane rotation and slice part_sig."""
    exp = _HELD[1]()
    _purge()
    _run("k4", "seal")
    doc = _run("b2", "verify")
    assert doc["bind_rows"][0]["aad_hex"] == exp["aad_hex"]
    assert doc.get("part_sig") == exp["part_sig"]


def test_f7_cross_seed_sidecar():
    """f7 sidecar cross_seed mixes into cross-group digest when sidecar is loaded."""
    exp = _COMPUTE[9]()
    _purge()
    doc = _run("f7", "verify")
    assert doc["cross_aad_digest"] == exp["cross_aad_digest"]
    assert doc["cross_aad_digest"] != _cross_plain()


def test_v5_c9_slice_context():
    """Isolated part decrypt must not pass as full verify when AAD context omits footer-bound group lane."""
    exp_full, exp_iso = _COMPUTE[3]()
    _purge()
    doc = _run("r2", "verify")
    assert doc.get("part_sig") == exp_full
    assert doc.get("part_sig") != exp_iso


def test_n1_h3_dual_phase():
    """h3 dual-phase arm requires hard store flush before footer reread on verify."""
    exp = _COMPUTE[4]()
    _purge()
    _run("h3", "append")
    first = _run("h3", "verify")
    assert first["bind_rows"][0]["row_hex"] == exp["row_hex"]
    assert first["record_digest"] == exp["record_digest"]
    first_bytes = OUT.read_bytes()
    second = _run("h3", "verify")
    assert first["record_digest"] == second["record_digest"]
    assert _byte_stable(first_bytes) == _byte_stable(OUT.read_bytes())


def test_p8_n3_lane_rotation():
    """Held-out n3 arm requires epoch journal aad_epoch projection, not global tip."""
    exp = _COMPUTE[6]()
    _purge()
    _run("k4", "seal")
    doc = _run("n3", "verify")
    assert doc["bind_rows"][1]["aad_hex"] == exp["aad_hex"]
    assert doc["cross_aad_digest"] == exp["cross_aad_digest"]


def test_z5_composite_shift():
    """Held-out z5 arm combines lane table shift with non-default aad_lane rotation."""
    exp = _COMPUTE[8]()
    _purge()
    doc = _run("z5", "verify")
    assert doc["bind_rows"][0]["key_idx"] == exp["key_idx"]
    assert doc["bind_rows"][1]["aad_hex"] == exp["aad_hex"]
    assert doc["cross_aad_digest"] == exp["cross_aad_digest"]


def test_r2_replay_stable():
    """Consecutive r2 verify invocations yield identical record_digest, advancing seq, and byte-stable output."""
    exp_digest, exp_part = _REPLAY()
    _purge()
    first = _run("r2", "verify")
    assert first.get("part_sig") == exp_part
    first_bytes = OUT.read_bytes()
    second = _run("r2", "verify")
    assert second["record_digest"] == exp_digest
    assert _byte_stable(first_bytes) == _byte_stable(OUT.read_bytes())


def test_flip_guard_matrix():
    """Cross-case matrix rows must all align for the composite guard check."""
    exp = _COMPUTE[7]()
    _purge()
    _run("k4", "seal")
    _run("f7", "verify")
    doc = _run("j6", "verify")
    assert doc["cross_aad_digest"] == exp["cross_aad_digest"]
    assert doc["bind_rows"][0]["row_hex"] == exp["row_hex"]


def test_c8_sidecar_lane_seed():
    """c8 inline lane override must retain sidecar cross_seed and zero slot index bind rows."""
    exp = _HELD[2]()
    _purge()
    doc = _run("c8", "verify")
    assert doc["bind_rows"][0]["key_idx"] == exp["key_idx"]
    assert doc["bind_rows"][1]["aad_hex"] == exp["aad_hex"]
    assert doc["cross_aad_digest"] == exp["cross_aad_digest"]


def test_y2_f7_part_slice():
    """f7 verify arm emits part_sig from footer-bound slice decrypt context."""
    _purge()
    doc = _run("f7", "verify")
    assert doc.get("part_sig") == _part_sig_f7()


def test_q7_sidecar_blend():
    """Held-out q7 arm blends sidecar lanes, cross_seed, and non-default aad_lane."""
    exp = _HELD[3]()
    _purge()
    doc = _run("q7", "verify")
    assert doc["bind_rows"][0]["key_idx"] == exp["key_idx"]
    assert doc["bind_rows"][0]["aad_hex"] == exp["aad_hex"]
    assert doc["cross_aad_digest"] == exp["cross_aad_digest"]


def test_u4_h3_purge_ladder():
    """h3 append survives work-state purge when verify rereads blob footer bytes."""
    exp = _COMPUTE[4]()
    _purge()
    _run("h3", "append")
    _purge()
    _run("h3", "append")
    doc = _run("h3", "verify")
    assert doc["bind_rows"][0]["row_hex"] == exp["row_hex"]
    assert doc["record_digest"] == exp["record_digest"]


def test_g4_z5_dual_verify_stable():
    """Consecutive z5 verify invocations keep cross_aad_digest and byte-stable output."""
    exp = _COMPUTE[8]()
    _purge()
    first = _run("z5", "verify")
    assert first["cross_aad_digest"] == exp["cross_aad_digest"]
    assert first["bind_rows"][0]["key_idx"] == exp["key_idx"]
    first_bytes = OUT.read_bytes()
    second = _run("z5", "verify")
    assert second["cross_aad_digest"] == exp["cross_aad_digest"]
    assert _byte_stable(first_bytes) == _byte_stable(OUT.read_bytes())


def test_h5_q7_after_k4_cross_blend():
    """q7 sidecar blend after k4 seal combines shift lane, cross_seed, and session prefixes."""
    exp = _HELD[3]()
    _purge()
    _run("k4", "seal")
    doc = _run("q7", "verify")
    assert doc["bind_rows"][0]["key_idx"] == exp["key_idx"]
    assert doc["bind_rows"][0]["aad_hex"] == exp["aad_hex"]
    assert doc["cross_aad_digest"] == exp["cross_aad_digest"]


def test_w9_state_isolation_after_f7():
    """w9 verify after f7 session must not reuse stale cross_seed from prior sidecar table."""
    w9 = _HELD[0]()
    _purge()
    _run("f7", "verify")
    doc = _run("w9", "verify")
    assert doc["cross_aad_digest"] == w9["cross_aad_digest"]
    assert doc["bind_rows"][0]["key_idx"] == w9["key_idx"]
    assert doc["bind_rows"][0]["row_hex"] == w9["row_hex"]


def test_v8_j6_after_f7_fresh_cross():
    """j6 verify after f7 must bind cross_aad_digest from current rows, not stale session prefixes."""
    exp = _COMPUTE[7]()
    _purge()
    _run("f7", "verify")
    doc = _run("j6", "verify")
    assert doc["cross_aad_digest"] == exp["cross_aad_digest"]
    assert doc["bind_rows"][0]["row_hex"] == exp["row_hex"]


def test_t4_q7_sidecar_base_octets():
    """q7 inline lane override must retain sidecar base octets alongside cross_seed."""
    exp = _HELD[3]()
    _purge()
    doc = _run("q7", "verify")
    assert doc["bind_rows"][0]["aad_hex"] == exp["aad_hex"]
    assert doc["cross_aad_digest"] == exp["cross_aad_digest"]


def test_d6_second_group_zero_idx():
    """d6 held-out arm binds grp2 at lane table slot zero with non-default aad_lane rotation."""
    exp = _HELD[4]()
    _purge()
    doc = _run("d6", "verify")
    assert doc["bind_rows"][1]["key_idx"] == exp["key_idx"]
    assert doc["bind_rows"][1]["row_hex"] == exp["row_hex"]
    assert doc["bind_rows"][1]["aad_hex"] == exp["aad_hex"]
    assert doc["cross_aad_digest"] == exp["cross_aad_digest"]


def test_d6_after_k4_lane_shift():
    """d6 after k4 seal must resolve grp2 zero slot without falling back to footer key slot."""
    exp = _HELD[4]()
    _purge()
    _run("k4", "seal")
    doc = _run("d6", "verify")
    assert doc["bind_rows"][1]["key_idx"] == exp["key_idx"]
    assert doc["bind_rows"][1]["row_hex"] == exp["row_hex"]


def test_n3_heldout_lane_isolation():
    """n3 bind must follow epoch 3 aad_epoch; global journal tip (epoch 99) must not match."""
    trap = _TRAP[0]()
    _purge()
    doc = _run("n3", "verify")
    assert doc["bind_rows"][1]["aad_hex"] == trap["aad_hex"]
    assert doc["cross_aad_digest"] == trap["cross_aad_digest"]
    assert doc["bind_rows"][1]["aad_hex"] != trap["row_hex"]
