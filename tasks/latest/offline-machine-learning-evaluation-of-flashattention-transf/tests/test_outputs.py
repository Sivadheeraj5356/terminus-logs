"""Behavioral tests for KV-tile residency coordinator."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from kvtile_recompute import (
    compute_compiler_epoch,
    compute_rebuild_nonce,
    crc32_ieee,
    expect_after_plan,
    expect_after_release_compact,
    expect_seal,
    fold_residue_after_advances,
    fold_tip_after_advances,
    load_compiler_epoch,
    load_json,
    load_rebuild_nonce,
    prior_fold,
    residue_seed,
    schedule_crc_from_visits,
    seal_digest,
)

APP = os.environ.get("KVTILE_APP_ROOT", "/app")
TEST_DIR = os.environ.get("TEST_DIR", "/tests")
PROFILE = f"{APP}/config/attn-profile.json"
PUBLIC = Path(f"{APP}/fixtures/public")
HIDDEN = Path(f"{TEST_DIR}/fixtures")
DATA = Path(f"{APP}/data")
OUT = Path(f"{APP}/output")
PRIOR = Path(f"{APP}/var/prior_seal.hex")
TRAILER = Path(f"{APP}/var/spine_trailer.hex")
BIN = f"{APP}/bin"
# Candidate-facing path must stay empty of recompute helpers (see test.sh).
OPT_VERIFIER_STUB = "/opt/kvtile-verifier"
# Real helpers live only where pytest PYTHONPATH points (never under /opt/kvtile-verifier).
VERIFIER_LIB = os.environ.get("KVTILE_VERIFIER_LIB", "/logs/verifier/kvtile-private")


def _clean():
    if DATA.exists():
        for p in DATA.iterdir():
            if p.is_file():
                p.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()
    PRIOR.parent.mkdir(parents=True, exist_ok=True)
    if PRIOR.exists():
        PRIOR.unlink()
    if TRAILER.exists():
        TRAILER.unlink()


def _cli_env() -> dict[str, str]:
    """Minimal env for candidate binaries — no PYTHONPATH / verifier private path."""
    return {
        "PATH": "/app/bin:/usr/local/cargo/bin:/usr/bin:/bin",
        "HOME": "/tmp/kvtile-cli-home",
        "KVTILE_APP_ROOT": APP,
        "TZ": "UTC",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    Path("/tmp/kvtile-cli-home").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
        env=_cli_env(),
        cwd="/app",
    )


def plan(pack: str):
    return run([f"{BIN}/kvtile-plan", "--pack", pack, "--profile", PROFILE])


def advance(compact: bool = False, release: list[int] | None = None):
    cmd = [f"{BIN}/kvtile-advance", "--profile", PROFILE]
    if release:
        for logical in release:
            cmd += ["--release-logical", str(logical)]
    if compact:
        cmd.append("--compact")
    return run(cmd)


def seal(seq_id: str, out: str | None = None):
    cmd = [f"{BIN}/kvtile-seal", "--seq-id", seq_id]
    if out:
        cmd += ["--out", out]
    return run(cmd, check=False)


@pytest.fixture(autouse=True)
def _isolate():
    _clean()
    yield
    _clean()


def test_binaries_are_native_elf():
    """Entry points must be native ELF images — not interpreter wrappers over /tests helpers."""
    for b in ("kvtile-plan", "kvtile-advance", "kvtile-seal"):
        raw = Path(f"{BIN}/{b}").read_bytes()[:8]
        assert raw[:4] == b"\x7fELF", f"{b} is not an ELF binary (got {raw!r})"
        assert not raw.startswith(b"#!"), f"{b} must not be a script wrapper"


def test_candidate_cli_cannot_read_verifier_lib():
    """Candidate-visible /opt/kvtile-verifier must not expose seal_digest / expect_seal helpers."""
    stub = Path(OPT_VERIFIER_STUB)
    assert stub.is_dir()
    py_hits = list(stub.rglob("*.py"))
    assert py_hits == [], f"reference .py under {OPT_VERIFIER_STUB}: {py_hits}"
    # Direct open the documented candidate path — no recompute API names.
    target = stub / "kvtile_recompute.py"
    r = subprocess.run(
        ["/bin/cat", str(target)],
        capture_output=True,
        text=True,
        check=False,
        env=_cli_env(),
        cwd="/app",
    )
    assert r.returncode != 0 or "def seal_digest" not in (r.stdout or "")
    assert "def expect_seal" not in (r.stdout or "")
    # CLI env must not advertise the private expect tree.
    assert "KVTILE_VERIFIER_LIB" not in _cli_env()
    assert "PYTHONPATH" not in _cli_env()


def test_public_demo_seal_matches_expect():
    """Public demo pack plan+advance+seal matches independent recompute."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    r = seal("demo")
    assert r.returncode == 0
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "demo", advances=1)
    assert got == exp


def test_tiny_pack_pages_and_mask():
    """Tiny pack produces coherent pages_resident and mask_bits."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    r = seal("tiny")
    assert r.returncode == 0
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "tiny", advances=1)
    assert got["pages_resident"] == exp["pages_resident"]
    assert got["mask_bits"] == exp["mask_bits"]
    assert got["seal_digest"] == exp["seal_digest"]


def test_default_seal_path():
    """Seal without --out writes default path."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    r = seal("defpath")
    assert r.returncode == 0
    assert (OUT / "kvtile-residency-seal.json").is_file()


def test_seal_refuses_empty_ledger():
    """Seal exits 2 when no pages resident."""
    r = seal("empty")
    assert r.returncode == 2


def test_multi_run_epoch_increments():
    """Two advances bump run_epoch to 2."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    advance()
    r = seal("mr")
    assert r.returncode == 0
    got = load_json(OUT / "kvtile-residency-seal.json")
    assert got["run_epoch"] == 2
    assert got["seal_digest"] == expect_seal(pack, PROFILE, "mr", advances=2)["seal_digest"]


def test_cross_run_replan_resets_then_reseal():
    """Cross-run: first seal, replan same pack, advance once, seal again."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    seal("cr1")
    first = load_json(OUT / "kvtile-residency-seal.json")
    plan(pack)
    advance()
    seal("cr2")
    second = load_json(OUT / "kvtile-residency-seal.json")
    assert first["run_epoch"] == 1
    assert second["run_epoch"] == 1
    assert second["seal_digest"] == expect_seal(
        pack, PROFILE, "cr2", advances=1, replan_lifo=True
    )["seal_digest"]


def test_multi_artifact_primary_and_mirror_seal():
    """Two seal artifacts: default path and mirror --out path (chained prior_fold)."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    assert seal("prim").returncode == 0
    mirror = str(OUT / "kvtile-mirror-seal.json")
    r = seal("mirr", out=mirror)
    assert r.returncode == 0
    assert (OUT / "kvtile-residency-seal.json").is_file()
    assert Path(mirror).is_file()
    a = load_json(OUT / "kvtile-residency-seal.json")
    b = load_json(mirror)
    assert a["pages_resident"] == b["pages_resident"]
    assert a["run_epoch"] == b["run_epoch"]
    assert len(a["seal_digest"]) == 64
    assert a["seal_digest"] != b["seal_digest"]
    assert b["seal_digest"] == expect_seal(pack, PROFILE, "mirr", 1, prior_digest=a["seal_digest"])[
        "seal_digest"
    ]


def test_preseed_binary_ledger_then_plan_overwrites():
    """preseed residency.bin with junk magic; plan must rewrite coherent ledger."""
    DATA.mkdir(parents=True, exist_ok=True)
    preseed = DATA / "residency.bin"
    preseed.write_bytes(b"XXXX" + b"\x00" * 32)
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    r = seal("pre")
    assert r.returncode == 0
    raw = preseed.read_bytes()
    assert raw[:4] == b"KVT1"
    got = load_json(OUT / "kvtile-residency-seal.json")
    assert got["seal_digest"] == expect_seal(pack, PROFILE, "pre", advances=1)["seal_digest"]


def test_hidden_a_seal():
    """Hidden fixture A matches expect."""
    pack = str(HIDDEN / "hidden_a.kvpack")
    plan(pack)
    advance()
    r = seal("ha")
    assert r.returncode == 0
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "ha", advances=1)
    assert got == exp


def test_hidden_b_seal():
    """Hidden fixture B matches expect."""
    pack = str(HIDDEN / "hidden_b.kvpack")
    plan(pack)
    advance()
    r = seal("hb")
    assert r.returncode == 0
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "hb", advances=1)
    assert got == exp


def test_m_stats_and_ell_six_decimals():
    """m_stats and ell_stats entries use exactly six fractional digits."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("m6")
    got = load_json(OUT / "kvtile-residency-seal.json")
    for s in got["m_stats"]:
        assert "." in s and len(s.split(".")[1]) == 6
    for s in got["ell_stats"]:
        assert "." in s and len(s.split(".")[1]) == 6


def test_top_level_key_order():
    """Seal JSON top-level keys follow schema order."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("keys")
    raw = (OUT / "kvtile-residency-seal.json").read_text(encoding="utf-8")
    obj = json.loads(raw)
    assert list(obj.keys()) == [
        "seq_id",
        "run_epoch",
        "tiles_planned",
        "pages_resident",
        "mask_bits",
        "m_stats",
        "ell_stats",
        "seal_digest",
    ]


def test_ledger_persists_across_commands():
    """Residency.bin survives between plan and seal."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    assert (DATA / "residency.bin").is_file()
    advance()
    assert (DATA / "residency.bin").stat().st_size > 8


def test_coupling_store_scheduler_pages_drive_seal():
    """Seal pages_resident equals allocated K-tile pages from schedule."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("cpl")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "cpl", advances=1)
    assert got["pages_resident"] == exp["pages_resident"]


def test_coupling_hash_softmax_affects_digest():
    """Changing pack scales changes seal_digest via m/ell stats."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    seal("s1")
    d1 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    _clean()
    p = json.loads(Path(pack).read_text())
    p["heads"][0]["scale"] = 9.9
    tmp = "/tmp/mut_scale.kvpack"
    Path(tmp).write_text(json.dumps(p))
    plan(tmp)
    advance()
    seal("s2")
    d2 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    assert d1 != d2


def test_coupling_crc_mask_bits_in_digest():
    """mask_bits participates in seal_digest payload."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("mb")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "mb", advances=1)
    assert got["mask_bits"] == exp["mask_bits"]
    assert got["seal_digest"] == exp["seal_digest"]


def test_integration_plan_advance_seal():
    """Full plan→advance→seal integration against expect."""
    pack = str(HIDDEN / "hidden_ooo.kvpack")
    plan(pack)
    advance()
    r = seal("integ")
    assert r.returncode == 0
    assert load_json(OUT / "kvtile-residency-seal.json") == expect_seal(pack, PROFILE, "integ", 1)


def test_integration_second_trace_seq_isolation():
    """Re-plan after clean isolates second sequence seal."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("a")
    d1 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    _clean()
    plan(str(PUBLIC / "tiny.kvpack"))
    advance()
    seal("b")
    d2 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    assert d1 != d2


def test_wiring_tile_schedule_counts():
    """tiles_planned equals n_heads * n_q * n_k."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("tp")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "tp", 1)
    assert got["tiles_planned"] == exp["tiles_planned"]


def test_wiring_online_softmax_nonzero_ell():
    """At least one head has non-zero ell after kept tiles."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("ell")
    got = load_json(OUT / "kvtile-residency-seal.json")
    assert any(float(x) > 0 for x in got["ell_stats"])


def test_wiring_block_table_page_count():
    """pages_resident equals n_heads * n_k."""
    pack = str(PUBLIC / "tiny.kvpack")
    profile = load_json(PROFILE)
    p = load_json(pack)
    bc = min(profile["bc_cap"], profile["head_dim"])
    n_k = (p["seq_len"] + bc - 1) // bc
    plan(pack)
    advance()
    seal("pg")
    got = load_json(OUT / "kvtile-residency-seal.json")
    assert got["pages_resident"] == profile["n_heads"] * n_k


def test_wiring_run_epoch_in_digest():
    """Different run_epoch changes seal_digest."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("e1")
    d1 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    advance()
    seal("e1")
    d2 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    assert d1 != d2


def test_partial_fix_epoch_plan_only_fails_seal():
    """Plan without advance leaves run_epoch 0 — digest mismatches advanced expect."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    r = seal("po")
    assert r.returncode == 0
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "po", advances=1)
    assert got["run_epoch"] == 0
    assert got["seal_digest"] != exp["seal_digest"]


def test_partial_fix_hash_wrong_seq_id():
    """seq_id is part of digest payload."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("alpha")
    d1 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    seal("beta")
    d2 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    assert d1 != d2


def test_partial_fix_store_softmax_scale_only():
    """Scale-only mutation without pager still changes digest."""
    pack = str(PUBLIC / "tiny.kvpack")
    p = load_json(pack)
    p["heads"][1]["scale"] = 3.3
    tmp = "/tmp/pf_scale.kvpack"
    Path(tmp).write_text(json.dumps(p))
    plan(tmp)
    advance()
    seal("pfs")
    got = load_json(OUT / "kvtile-residency-seal.json")
    base = expect_seal(pack, PROFILE, "pfs", 1)
    assert got["seal_digest"] != base["seal_digest"]


def test_partial_fix_crc_mask_flip_bits():
    """Flipping packed mask bits changes mask_bits and digest."""
    pack = str(PUBLIC / "demo.kvpack")
    p = load_json(pack)
    b = bytearray(bytes.fromhex(p["packed_mask_hex"]))
    b[0] ^= 0xFF
    p["packed_mask_hex"] = b.hex()
    tmp = "/tmp/pf_mask.kvpack"
    Path(tmp).write_text(json.dumps(p))
    plan(tmp)
    advance()
    seal("pfm")
    got = load_json(OUT / "kvtile-residency-seal.json")
    base = expect_seal(pack, PROFILE, "pfm", 1)
    assert got["mask_bits"] != base["mask_bits"] or got["seal_digest"] != base["seal_digest"]


def test_partial_fix_txn_advance_without_plan():
    """Advance on empty ledger then seal must exit 2."""
    advance()
    r = seal("nopages")
    assert r.returncode == 2


def test_partial_fix_reload_compact_noop():
    """Compact with empty free stack does not drop pages_resident."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance(compact=True)
    seal("cmp")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "cmp", 1)
    assert got["pages_resident"] == exp["pages_resident"]


def test_partial_fix_reload_hidden_compact():
    """Hidden compact fixture still seals correctly after compact advance."""
    pack = str(HIDDEN / "hidden_compact.kvpack")
    plan(pack)
    advance(compact=True)
    r = seal("hc")
    assert r.returncode == 0
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "hc", 1)
    assert got["seal_digest"] == exp["seal_digest"]


def test_partial_fix_audit_head_count_stats():
    """m_stats length equals n_heads."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("hlen")
    got = load_json(OUT / "kvtile-residency-seal.json")
    assert len(got["m_stats"]) == load_json(PROFILE)["n_heads"]


def test_partial_fix_export_custom_out_path():
    """--out writes seal to custom path."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    custom = "/tmp/custom-seal.json"
    r = seal("cust", out=custom)
    assert r.returncode == 0
    assert Path(custom).is_file()
    assert load_json(custom)["seq_id"] == "cust"


def test_partial_fix_reload_replan_resets_stats():
    """Second plan on same ledger path after clean recomputes stats."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("r1")
    d1 = load_json(OUT / "kvtile-residency-seal.json")["m_stats"]
    _clean()
    plan(str(PUBLIC / "tiny.kvpack"))
    advance()
    seal("r2")
    d2 = load_json(OUT / "kvtile-residency-seal.json")["m_stats"]
    assert d1 != d2


def test_partial_fix_hash_digest_no_newline():
    """Expect helper digest (no trailing newline) matches CLI seal."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("nl")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "nl", 1)
    assert got["seal_digest"] == exp["seal_digest"]


def test_partial_fix_sort_ooo_indices_order():
    """Stored (possibly reversed) indices order still matches expand_pairs expect."""
    pack = str(HIDDEN / "hidden_ooo.kvpack")
    plan(pack)
    advance()
    seal("ooo")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "ooo", 1)
    assert got == exp


def test_interlock_pager_and_softmax():
    """Pages and softmax stats must both match expect simultaneously."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("il")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "il", 1)
    assert got["pages_resident"] == exp["pages_resident"]
    assert got["m_stats"] == exp["m_stats"]
    assert got["ell_stats"] == exp["ell_stats"]


def test_cross_layer_epoch_and_pages():
    """run_epoch and pages_resident jointly determine digest."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    advance()
    seal("xl")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "xl", 2)
    assert got == exp


def test_coupling_epoch_advance_changes_digest():
    """Second advance after replan bumps run_epoch and changes seal_digest."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    seal("e1")
    d1 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    plan(pack)
    advance()
    advance()
    seal("e2")
    d2 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    assert d1 != d2
    assert d2 == expect_seal(pack, PROFILE, "e2", advances=2, replan_lifo=True)["seal_digest"]


def test_multi_run_consecutive_advance_epochs():
    """Three advances yield run_epoch 3 in seal."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    advance()
    advance()
    seal("c3")
    got = load_json(OUT / "kvtile-residency-seal.json")
    assert got["run_epoch"] == 3
    assert got == expect_seal(pack, PROFILE, "c3", 3)


def test_double_plan_resets_pages():
    """Double plan without clean reallocates via LIFO reuse then seals."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    plan(pack)
    seal("dp")
    got = load_json(OUT / "kvtile-residency-seal.json")
    assert got == expect_seal(pack, PROFILE, "dp", advances=0, replan_lifo=True)


def test_coupling_prior_fold_chain_without_replan():
    """Second seal without replan folds prior digest into seal_digest."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("pf1")
    d1 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    seal("pf2")
    d2 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    assert d1 != d2
    assert d2 == expect_seal(pack, PROFILE, "pf2", 1, prior_digest=d1)["seal_digest"]


def test_incomplete_integration_prior_cleared_on_plan():
    """Plan after a seal clears prior_fold chain back to zero-material baseline."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    seal("pr1")
    plan(pack)
    advance()
    seal("pr2")
    got = load_json(OUT / "kvtile-residency-seal.json")
    assert got["seal_digest"] == expect_seal(
        pack, PROFILE, "pr2", advances=1, replan_lifo=True
    )["seal_digest"]


def test_two_trace_hidden_a_then_b():
    """Two hidden fixtures after clean produce distinct seals."""
    plan(str(HIDDEN / "hidden_a.kvpack"))
    advance()
    seal("t1")
    d1 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    _clean()
    plan(str(HIDDEN / "hidden_b.kvpack"))
    advance()
    seal("t2")
    d2 = load_json(OUT / "kvtile-residency-seal.json")["seal_digest"]
    assert d1 != d2


def test_page_reuse_lifo_on_replan():
    """Second plan on live ledger reallocates via LIFO free-stack reuse (reversed phys)."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    first = expect_after_plan(load_json(pack), load_json(PROFILE), replan_lifo=False)
    plan(pack)
    advance()
    seal("reuse")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "reuse", advances=1, replan_lifo=True)
    assert got == exp
    assert (
        exp["seal_digest"]
        != expect_seal(pack, PROFILE, "reuse", advances=1, replan_lifo=False)["seal_digest"]
    )
    assert first["phys"] != expect_after_plan(
        load_json(pack), load_json(PROFILE), replan_lifo=True
    )["phys"]


def test_successful_compaction_releases_and_densifies():
    """Release enough logicals then --compact densifies map and drops pages_resident."""
    pack = str(PUBLIC / "demo.kvpack")
    profile = load_json(PROFILE)
    p = load_json(pack)
    base = expect_after_plan(p, profile)
    n_release = max(3, int(base["pages_resident"] * 0.25) + 1)
    release = list(range(n_release))
    plan(pack)
    advance(compact=True, release=release)
    seal("cmpok")
    got = load_json(OUT / "kvtile-residency-seal.json")
    sim = expect_after_release_compact(p, profile, release, do_compact=True, advances=1)
    exp = expect_seal(
        pack,
        PROFILE,
        "cmpok",
        advances=1,
        phys=sim["phys"],
        pages_resident=sim["pages_resident"],
        compact_gen=sim["compact_gen"],
        residue_u64=sim["residue_u64"],
        merkle_tip=sim["merkle_tip"],
    )
    assert sim["compact_gen"] == 1
    assert got["pages_resident"] == sim["pages_resident"]
    assert got["pages_resident"] < base["pages_resident"]
    assert got["seal_digest"] == exp["seal_digest"]


def test_coupling_compact_gen_in_seal_digest():
    """compact_gen after successful compact participates in seal_digest payload."""
    pack = str(PUBLIC / "demo.kvpack")
    profile = load_json(PROFILE)
    p = load_json(pack)
    base = expect_after_plan(p, profile)
    n_release = max(3, int(base["pages_resident"] * 0.25) + 1)
    release = list(range(n_release))
    plan(pack)
    advance(compact=True, release=release)
    seal("cg")
    got = load_json(OUT / "kvtile-residency-seal.json")
    sim = expect_after_release_compact(p, profile, release, do_compact=True, advances=1)
    with_gen = expect_seal(
        pack,
        PROFILE,
        "cg",
        1,
        phys=sim["phys"],
        pages_resident=sim["pages_resident"],
        compact_gen=1,
        residue_u64=sim["residue_u64"],
        merkle_tip=sim["merkle_tip"],
    )
    without = expect_seal(
        pack,
        PROFILE,
        "cg",
        1,
        phys=sim["phys"],
        pages_resident=sim["pages_resident"],
        compact_gen=0,
        residue_u64=sim["residue_u64"],
        merkle_tip=sim["merkle_tip"],
    )
    assert got["seal_digest"] == with_gen["seal_digest"]
    assert got["seal_digest"] != without["seal_digest"]


def test_partial_fix_advance_no_reuse_without_plan():
    """Advance with --release-logical frees pages but does not reallocate; pages_resident drops."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance(release=[0, 1])
    seal("nru")
    got = load_json(OUT / "kvtile-residency-seal.json")
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    assert got["pages_resident"] == base["pages_resident"] - 2
    assert got["run_epoch"] == 1


def test_compact_gen_persists_across_replan():
    """Successful compact_gen survives a later densified-replan and still folds into seal_digest."""
    from kvtile_recompute import expect_after_compact_then_replan, seal_digest

    pack = str(PUBLIC / "demo.kvpack")
    profile = load_json(PROFILE)
    p = load_json(pack)
    base = expect_after_plan(p, profile)
    n_release = max(3, int(base["pages_resident"] * 0.25) + 1)
    release = list(range(n_release))
    plan(pack)
    advance(compact=True, release=release)
    plan(pack)
    advance()
    seal("cgpersist")
    got = load_json(OUT / "kvtile-residency-seal.json")
    sim = expect_after_compact_then_replan(p, profile, release, advances=1)
    with_gen = expect_seal(
        pack,
        PROFILE,
        "cgpersist",
        1,
        phys=sim["phys"],
        pages_resident=sim["pages_resident"],
        compact_gen=1,
        residue_u64=sim["residue_u64"],
        merkle_tip=sim["merkle_tip"],
    )
    without = expect_seal(
        pack,
        PROFILE,
        "cgpersist",
        1,
        phys=sim["phys"],
        pages_resident=sim["pages_resident"],
        compact_gen=0,
    )
    assert sim["compact_gen"] == 1
    assert got["seal_digest"] == with_gen["seal_digest"]
    assert got["seal_digest"] != without["seal_digest"]
    sorted_digest = seal_digest(
        "cgpersist",
        1,
        sim["pages_resident"],
        sorted(sim["phys"]),
        sim["mask_bits"],
        sim["m_stats"],
        sim["ell_stats"],
        compact_gen=1,
        visit_checksum=sim["visit_checksum"],
    )
    assert got["seal_digest"] != sorted_digest


def test_release_without_compact_keeps_compact_gen_zero():
    """Releasing pages without crossing compact threshold leaves compact_gen at 0."""
    pack = str(PUBLIC / "demo.kvpack")
    profile = load_json(PROFILE)
    p = load_json(pack)
    base = expect_after_plan(p, profile)
    # One logical free is below compact_threshold 0.25 for typical demo page counts.
    plan(pack)
    advance(compact=True, release=[0])
    seal("nocmp")
    got = load_json(OUT / "kvtile-residency-seal.json")
    sim = expect_after_release_compact(p, profile, [0], do_compact=True, advances=1)
    assert sim["compact_gen"] == 0
    exp = expect_seal(
        pack,
        PROFILE,
        "nocmp",
        1,
        phys=sim["phys"],
        pages_resident=sim["pages_resident"],
        compact_gen=0,
    )
    assert got["seal_digest"] == exp["seal_digest"]
    assert got["pages_resident"] == base["pages_resident"] - 1


def test_second_successful_compact_bumps_compact_gen():
    """Two densifying compacts bump compact_gen to 2 and change seal_digest vs gen=1."""
    pack = str(PUBLIC / "demo.kvpack")
    profile = load_json(PROFILE)
    p = load_json(pack)
    base = expect_after_plan(p, profile)
    n1 = max(3, int(base["pages_resident"] * 0.25) + 1)
    release1 = list(range(n1))
    plan(pack)
    advance(compact=True, release=release1)
    sim1 = expect_after_release_compact(p, profile, release1, do_compact=True, advances=1)
    surviving = sorted(sim1["mapping"].keys())
    n2 = max(1, int(len(surviving) * 0.25) + 1)
    release2 = surviving[:n2]
    advance(compact=True, release=release2)
    seal("cmp2")
    got = load_json(OUT / "kvtile-residency-seal.json")
    sim2 = expect_after_release_compact(
        p,
        profile,
        release2,
        do_compact=True,
        advances=2,
        start_compact_gen=sim1["compact_gen"],
        mapping=sim1["mapping"],
        page_count=sim1["page_count"],
        prior_tip=sim1["merkle_tip"],
        start_residue=sim1["residue_u64"],
    )
    assert sim2["compact_gen"] == 2
    with2 = expect_seal(
        pack,
        PROFILE,
        "cmp2",
        2,
        phys=sim2["phys"],
        pages_resident=sim2["pages_resident"],
        compact_gen=2,
        merkle_tip=sim2["merkle_tip"],
        residue_u64=sim2["residue_u64"],
    )
    with1 = expect_seal(
        pack,
        PROFILE,
        "cmp2",
        2,
        phys=sim2["phys"],
        pages_resident=sim2["pages_resident"],
        compact_gen=1,
        merkle_tip=sim2["merkle_tip"],
        residue_u64=sim2["residue_u64"],
    )
    assert got["seal_digest"] == with2["seal_digest"]
    assert got["seal_digest"] != with1["seal_digest"]


def test_seal_phys_logical_order_after_lifo_replan():
    """After LIFO replan, seal uses logical-order phys (reversed), not phys-sorted ids."""
    from kvtile_recompute import seal_digest

    pack = str(PUBLIC / "tiny.kvpack")
    p = load_json(pack)
    plan(pack)
    plan(pack)
    advance()
    seal("logord")
    got = load_json(OUT / "kvtile-residency-seal.json")
    lifo = expect_after_plan(p, load_json(PROFILE), replan_lifo=True)
    assert lifo["phys"] == list(reversed(range(lifo["pages_resident"])))
    assert got == expect_seal(pack, PROFILE, "logord", 1, replan_lifo=True)
    wrong = seal_digest(
        "logord",
        1,
        lifo["pages_resident"],
        sorted(lifo["phys"]),
        lifo["mask_bits"],
        lifo["m_stats"],
        lifo["ell_stats"],
        compact_gen=0,
        visit_checksum=lifo["visit_checksum"],
    )
    assert got["seal_digest"] != wrong


def test_coupling_visit_checksum_in_digest():
    """Seal digest must fold plan visit_checksum; zero checksum is a different digest."""
    from kvtile_recompute import seal_digest

    pack = str(PUBLIC / "demo.kvpack")
    p = load_json(pack)
    plan(pack)
    advance()
    seal("vcouple")
    got = load_json(OUT / "kvtile-residency-seal.json")
    base = expect_after_plan(p, load_json(PROFILE))
    assert base["visit_checksum"] != 0
    good = expect_seal(pack, PROFILE, "vcouple", 1)
    assert got["seal_digest"] == good["seal_digest"]
    zeroed = seal_digest(
        "vcouple",
        1,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=0,
    )
    assert got["seal_digest"] != zeroed


def test_incomplete_integration_pages_unconditional_vs_mask():
    """pages_resident is n_heads*n_k even when sparse mask keeps fewer schedule visits."""
    from kvtile_recompute import br_bc, decode_bits, expand_pairs

    pack = str(PUBLIC / "demo.kvpack")
    p = load_json(pack)
    profile = load_json(PROFILE)
    base = expect_after_plan(p, profile)
    _br, bc = br_bc(profile)
    n_k = (p["seq_len"] + bc - 1) // bc
    n_heads = profile["n_heads"]
    assert base["pages_resident"] == n_heads * n_k
    bits = decode_bits(p["packed_mask_hex"], len(p["indices"]))
    kept = expand_pairs(p["indptr"], p["indices"], bits)
    assert len(kept) < base["tiles_planned"]
    assert base["mask_bits"] < base["tiles_planned"]
    plan(pack)
    advance()
    seal("pagescope")
    got = load_json(OUT / "kvtile-residency-seal.json")
    assert got["pages_resident"] == base["pages_resident"]
    assert got == expect_seal(pack, PROFILE, "pagescope", 1)


def test_incomplete_integration_visit_checksum_survives_advance():
    """Advance must preserve visit_checksum so seal matches plan-time custody fold."""
    pack = str(PUBLIC / "demo.kvpack")
    p = load_json(pack)
    base = expect_after_plan(p, load_json(PROFILE))
    plan(pack)
    advance()
    advance()
    seal("vcpersist")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "vcpersist", 2)
    assert got["seal_digest"] == exp["seal_digest"]
    # Recompute with mutated visit_checksum must diverge.
    from kvtile_recompute import seal_digest

    bad = seal_digest(
        "vcpersist",
        2,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"] ^ 0xA5A5A5A5,
    )
    assert got["seal_digest"] != bad


def test_incomplete_integration_merkle_tip_advances_with_epoch():
    """Advance parent-chains merkle_tip into seal_digest; tip=0 (plan-only) digest must differ."""
    from kvtile_recompute import seal_digest, expect_after_plan

    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("tip1")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "tip1", advances=1)
    assert got["seal_digest"] == exp["seal_digest"]
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    zero_tip = seal_digest(
        "tip1",
        1,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"],
        merkle_tip=0,
    )
    assert got["seal_digest"] != zero_tip


def test_incomplete_integration_merkle_tip_after_compact():
    """Densifying compact remaps phys ids so tip fold and seal_digest change vs uncompacted map."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    n = expect_after_plan(load_json(pack), load_json(PROFILE))["pages_resident"]
    release = list(range(max(1, n // 2)))
    advance(compact=True, release=release)
    seal("tipc")
    got = load_json(OUT / "kvtile-residency-seal.json")
    sim = expect_after_release_compact(load_json(pack), load_json(PROFILE), release, advances=1)
    exp = expect_seal(
        pack,
        PROFILE,
        "tipc",
        advances=1,
        compact_gen=sim["compact_gen"],
        phys=sim["phys"],
        pages_resident=sim["pages_resident"],
    )
    assert got["seal_digest"] == exp["seal_digest"]
    unc = expect_seal(pack, PROFILE, "tipc", advances=1)
    assert got["seal_digest"] != unc["seal_digest"] or sim["compact_gen"] >= 1


def test_incomplete_integration_spine_trailer_blocks_stale_replan():
    """Seal writes spine_trailer.hex; corrupting it makes the next plan exit non-zero."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("tr")
    assert TRAILER.is_file()
    TRAILER.write_text("deadbeefdeadbeef")
    r = run([f"{BIN}/kvtile-plan", "--pack", pack, "--profile", PROFILE], check=False)
    assert r.returncode != 0


def test_incomplete_integration_spine_trailer_cleared_on_valid_plan():
    """Valid trailer passes plan validation and is removed; tip resets for the next epoch."""
    from kvtile_recompute import trailer_mark, fold_tip_after_advances, expect_after_plan

    pack = str(PUBLIC / "demo.kvpack")
    profile = load_json(PROFILE)
    plan(pack)
    advance()
    seal("oktr")
    tip = fold_tip_after_advances(expect_after_plan(load_json(pack), profile)["phys"], 1)
    assert TRAILER.read_text().strip() == trailer_mark(tip, profile["spine_salt"])
    plan(pack)
    assert not TRAILER.exists()
    advance()
    seal("oktr2")
    got = load_json(OUT / "kvtile-residency-seal.json")
    assert (
        got["seal_digest"]
        == expect_seal(pack, PROFILE, "oktr2", advances=1, replan_lifo=True)["seal_digest"]
    )


def test_coupling_merkle_tip_in_seal_digest():
    """Changing only merkle_tip in the payload desyncs seal_digest."""
    from kvtile_recompute import seal_digest, expect_after_plan, fold_tip_after_advances

    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("mtip")
    got = load_json(OUT / "kvtile-residency-seal.json")
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    tip = fold_tip_after_advances(base["phys"], 1)
    good = expect_seal(pack, PROFILE, "mtip", 1)
    assert got["seal_digest"] == good["seal_digest"]
    flipped = seal_digest(
        "mtip",
        1,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        visit_checksum=base["visit_checksum"],
        merkle_tip=tip ^ 1,
    )
    assert got["seal_digest"] != flipped


def test_coupling_compact_changes_merkle_tip():
    """Compact remapping changes tip even when visit_checksum is unchanged."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    n = expect_after_plan(load_json(pack), load_json(PROFILE))["pages_resident"]
    release = list(range(max(1, n // 2)))
    advance(compact=True, release=release)
    seal("cmt")
    got = load_json(OUT / "kvtile-residency-seal.json")
    sim = expect_after_release_compact(load_json(pack), load_json(PROFILE), release, advances=1)
    assert sim["compact_gen"] >= 1
    plain = expect_seal(pack, PROFILE, "cmt", advances=1)
    assert got["seal_digest"] != plain["seal_digest"]


def test_coupling_spine_salt_desyncs_digest():
    """Trailer mark binds tip XOR spine_salt; wrong salt leaves a mark plan cannot clear with prior tip."""
    pack = str(PUBLIC / "tiny.kvpack")
    if not Path(pack).is_file():
        pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("salt")
    mark = TRAILER.read_text().strip()
    assert len(mark) == 16
    # Fake a mismatched trailer as if spine_salt differed.
    TRAILER.write_text(f"{(int(mark, 16) ^ 0x1111111111111111):016x}")
    bad = run([f"{BIN}/kvtile-plan", "--pack", pack, "--profile", PROFILE], check=False)
    assert bad.returncode != 0


def test_coupling_build_writes_compiler_epoch_matches_profile():
    """build.sh must materialize epoch_u64 from profile spine_salt with rebuild_nonce 0."""
    epoch_path = Path(f"{APP}/var/compiler-epoch.json")
    if epoch_path.is_file():
        epoch_path.unlink()
    run(["bash", f"{APP}/scripts/build.sh"])
    assert epoch_path.is_file()
    salt = int(load_json(PROFILE).get("spine_salt", 0) or 0)
    blob = json.loads(epoch_path.read_text(encoding="utf-8"))
    got = int(blob["epoch_u64"])
    assert got == compute_compiler_epoch(salt)
    assert int(blob.get("rebuild_nonce", -1)) == 0
    assert got != 0 or salt == 0


def test_rebuild_sh_writes_nonzero_rebuild_nonce_and_seal_matches():
    """rebuild.sh must rewrite compiler-epoch with non-zero rebuild_nonce folded into seal."""
    epoch_path = Path(f"{APP}/var/compiler-epoch.json")
    run(["bash", f"{APP}/scripts/build.sh"])
    assert load_rebuild_nonce() == 0
    Path("/tmp/kvtile-cli-home").mkdir(parents=True, exist_ok=True)
    env = dict(_cli_env())
    env["KVTILE_VERIFIER_EPOCH_ONLY"] = "1"
    r = subprocess.run(
        ["bash", f"{APP}/scripts/rebuild.sh"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd="/app",
    )
    assert r.returncode == 0, r.stderr
    assert epoch_path.is_file()
    epoch = load_compiler_epoch()
    nonce = load_rebuild_nonce()
    assert nonce == compute_rebuild_nonce(epoch)
    assert nonce != 0
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("reb")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "reb", advances=1)
    assert got["seal_digest"] == exp["seal_digest"]


def test_partial_fix_seal_omits_compiler_epoch_desyncs():
    """Seal that drops |compiler_epoch / |rebuild_nonce from the pipe cannot match recompute."""
    pack = str(PUBLIC / "demo.kvpack")
    run(["bash", f"{APP}/scripts/write-compiler-epoch.sh", PROFILE, "rebuild"])
    plan(pack)
    advance()
    seal("epoch")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "epoch", advances=1)
    assert got["seal_digest"] == exp["seal_digest"]
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    use_tip = fold_tip_after_advances(base["phys"], 1, compact_gen=0, prior_tip=0)
    pages = ",".join(str(p) for p in base["phys"])
    pf = prior_fold(None)
    legacy = (
        f"epoch|1|{base['pages_resident']}|{pages}|{base['mask_bits']}|"
        f"{','.join(base['m_stats'])}|{','.join(base['ell_stats'])}|{pf}|0|"
        f"{base['visit_checksum']}|{use_tip}"
    )
    legacy_digest = hashlib.sha256(legacy.encode()).hexdigest()
    assert got["seal_digest"] != legacy_digest
    salt = int(load_json(PROFILE).get("spine_salt", 0) or 0)
    wrong = seal_digest(
        "epoch",
        1,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"],
        merkle_tip=use_tip,
        compiler_epoch=load_compiler_epoch(spine_salt=salt) ^ 0x1,
        rebuild_nonce=load_rebuild_nonce(),
    )
    assert got["seal_digest"] != wrong


def test_partial_fix_seal_omits_rebuild_nonce_desyncs():
    """Folding compiler_epoch but omitting rebuild_nonce cannot match independent recompute."""
    pack = str(PUBLIC / "tiny.kvpack")
    run(["bash", f"{APP}/scripts/write-compiler-epoch.sh", PROFILE, "rebuild"])
    epoch = load_compiler_epoch()
    nonce = load_rebuild_nonce()
    assert nonce == compute_rebuild_nonce(epoch) and nonce != 0
    plan(pack)
    advance()
    seal("nonce")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "nonce", advances=1)
    assert got["seal_digest"] == exp["seal_digest"]
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    use_tip = fold_tip_after_advances(base["phys"], 1, compact_gen=0, prior_tip=0)
    pages = ",".join(str(p) for p in base["phys"])
    pf = prior_fold(None)
    epoch_only = (
        f"nonce|1|{base['pages_resident']}|{pages}|{base['mask_bits']}|"
        f"{','.join(base['m_stats'])}|{','.join(base['ell_stats'])}|{pf}|0|"
        f"{base['visit_checksum']}|{use_tip}|{epoch}"
    )
    assert got["seal_digest"] != hashlib.sha256(epoch_only.encode()).hexdigest()
    zero_nonce = seal_digest(
        "nonce",
        1,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"],
        merkle_tip=use_tip,
        compiler_epoch=epoch,
        rebuild_nonce=0,
    )
    assert got["seal_digest"] != zero_nonce


def test_incomplete_integration_schedule_mir_written_on_plan():
    """Plan must materialize /app/data/schedule.mir with SCH1 magic and visit triples."""
    pack = str(PUBLIC / "demo.kvpack")
    _clean()
    plan(pack)
    mir = DATA / "schedule.mir"
    assert mir.is_file()
    raw = mir.read_bytes()
    assert raw[:4] == b"SCH1"
    assert len(raw) >= 8
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    assert crc32_ieee(raw) == base["schedule_crc"]


def test_incomplete_integration_schedule_crc_matches_mir():
    """schedule_crc folded into seal must equal IEEE CRC of on-disk mir bytes."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    seal("sch")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "sch", advances=1)
    assert got["seal_digest"] == exp["seal_digest"]
    mir = (DATA / "schedule.mir").read_bytes()
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    assert crc32_ieee(mir) == base["schedule_crc"]
    wrong = seal_digest(
        "sch",
        1,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"],
        merkle_tip=fold_tip_after_advances(base["phys"], 1),
        compiler_epoch=load_compiler_epoch(),
        rebuild_nonce=load_rebuild_nonce(),
        schedule_crc=base["schedule_crc"] ^ 1,
        residue_u64=fold_residue_after_advances(
            base["residue_u64"], base["phys"], 1
        )[1],
    )
    assert got["seal_digest"] != wrong


def test_incomplete_integration_missing_mir_desyncs_seal():
    """Deleting schedule.mir before seal forces schedule_crc=0 and breaks digest match."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    mir = DATA / "schedule.mir"
    assert mir.is_file()
    mir.unlink()
    seal("nomir")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "nomir", advances=1)
    assert got["seal_digest"] != exp["seal_digest"]


def test_incomplete_integration_residue_seeds_on_plan():
    """After plan with no advance, residue_u64 equals packed visit_checksum||mask_bits seed."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    seal("seed")
    got = load_json(OUT / "kvtile-residency-seal.json")
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    assert base["residue_u64"] == residue_seed(base["visit_checksum"], base["mask_bits"])
    exp = expect_seal(pack, PROFILE, "seed", advances=0)
    assert got["seal_digest"] == exp["seal_digest"]


def test_incomplete_integration_residue_advances_with_epoch():
    """Advance must parent-chain residue after tip; seal seed without chain must desync."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("res")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "res", advances=1)
    assert got["seal_digest"] == exp["seal_digest"]
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    tip, resid = fold_residue_after_advances(base["residue_u64"], base["phys"], 1)
    stale = seal_digest(
        "res",
        1,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"],
        merkle_tip=tip,
        compiler_epoch=load_compiler_epoch(),
        rebuild_nonce=load_rebuild_nonce(),
        schedule_crc=base["schedule_crc"],
        residue_u64=base["residue_u64"],
    )
    assert got["seal_digest"] != stale
    assert resid != base["residue_u64"]


def test_incomplete_integration_residue_resets_on_replan():
    """Second plan must reseed residue from new visit/mask custody, not keep prior chain."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    advance()
    plan(pack)
    seal("rp")
    got = load_json(OUT / "kvtile-residency-seal.json")
    # Live ledger after advance→replan uses LIFO phys (not identity map).
    exp = expect_seal(pack, PROFILE, "rp", advances=0, replan_lifo=True)
    assert got["seal_digest"] == exp["seal_digest"]
    base = expect_after_plan(load_json(pack), load_json(PROFILE), replan_lifo=True)
    _, chained = fold_residue_after_advances(base["residue_u64"], base["phys"], 2)
    wrongly_chained = seal_digest(
        "rp",
        0,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"],
        merkle_tip=0,
        compiler_epoch=load_compiler_epoch(),
        rebuild_nonce=load_rebuild_nonce(),
        schedule_crc=base["schedule_crc"],
        residue_u64=chained,
    )
    assert got["seal_digest"] != wrongly_chained


def test_incomplete_integration_zero_residue_after_advance_fails():
    """Folding residue_u64=0 after a successful advance cannot match independent recompute."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    seal("zr")
    got = load_json(OUT / "kvtile-residency-seal.json")
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    tip, _ = fold_residue_after_advances(base["residue_u64"], base["phys"], 1)
    zeroed = seal_digest(
        "zr",
        1,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"],
        merkle_tip=tip,
        compiler_epoch=load_compiler_epoch(),
        rebuild_nonce=load_rebuild_nonce(),
        schedule_crc=base["schedule_crc"],
        residue_u64=0,
    )
    assert got["seal_digest"] != zeroed


def test_coupling_schedule_crc_in_seal_digest():
    """Seal digest must change when schedule_crc flips while other pipe fields stay fixed."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    seal("csch")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "csch", advances=1)
    assert got["seal_digest"] == exp["seal_digest"]
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    tip, resid = fold_residue_after_advances(base["residue_u64"], base["phys"], 1)
    flipped = seal_digest(
        "csch",
        1,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"],
        merkle_tip=tip,
        compiler_epoch=load_compiler_epoch(),
        rebuild_nonce=load_rebuild_nonce(),
        schedule_crc=schedule_crc_from_visits(base["visits"]) ^ 0xA5A5A5A5,
        residue_u64=resid,
    )
    assert got["seal_digest"] != flipped


def test_coupling_residue_u64_in_seal_digest():
    """Residue field is part of seal_digest; omitting residue after rebuild_nonce desyncs."""
    pack = str(PUBLIC / "tiny.kvpack")
    plan(pack)
    advance()
    seal("cres")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "cres", advances=1)
    assert got["seal_digest"] == exp["seal_digest"]
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    tip, resid = fold_residue_after_advances(base["residue_u64"], base["phys"], 1)
    pages = ",".join(str(p) for p in base["phys"])
    pf = prior_fold(None)
    epoch = load_compiler_epoch()
    nonce = load_rebuild_nonce()
    truncated = (
        f"cres|1|{base['pages_resident']}|{pages}|{base['mask_bits']}|"
        f"{','.join(base['m_stats'])}|{','.join(base['ell_stats'])}|{pf}|0|"
        f"{base['visit_checksum']}|{tip}|{epoch}|{nonce}|{base['schedule_crc']}"
    )
    assert got["seal_digest"] != hashlib.sha256(truncated.encode()).hexdigest()
    assert resid != 0


def test_coupling_schedule_and_residue_cross_layer():
    """Mir CRC and residue chain must both match; either wrong layer alone fails seal."""
    pack = str(PUBLIC / "demo.kvpack")
    plan(pack)
    advance()
    advance()
    seal("cross")
    got = load_json(OUT / "kvtile-residency-seal.json")
    exp = expect_seal(pack, PROFILE, "cross", advances=2)
    assert got["seal_digest"] == exp["seal_digest"]
    base = expect_after_plan(load_json(pack), load_json(PROFILE))
    tip, resid = fold_residue_after_advances(base["residue_u64"], base["phys"], 2)
    bad_sch = seal_digest(
        "cross",
        2,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"],
        merkle_tip=tip,
        compiler_epoch=load_compiler_epoch(),
        rebuild_nonce=load_rebuild_nonce(),
        schedule_crc=0,
        residue_u64=resid,
    )
    bad_res = seal_digest(
        "cross",
        2,
        base["pages_resident"],
        base["phys"],
        base["mask_bits"],
        base["m_stats"],
        base["ell_stats"],
        compact_gen=0,
        visit_checksum=base["visit_checksum"],
        merkle_tip=tip,
        compiler_epoch=load_compiler_epoch(),
        rebuild_nonce=load_rebuild_nonce(),
        schedule_crc=base["schedule_crc"],
        residue_u64=base["residue_u64"],
    )
    assert got["seal_digest"] != bad_sch
    assert got["seal_digest"] != bad_res
