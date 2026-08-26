from __future__ import annotations
import hashlib
import json
import os
import shutil
import struct
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import lmdb
import pytest

APP = Path("/app")
BIN = APP / "bin/telreplay"
CONFIG = APP / "config/replayer.toml"
PACK = APP / "data/scenarios.json"
STATE = APP / "state_verifier"
OUT = APP / "output"
SEMANTIC = (
    "samples_scanned",
    "errors_seen",
    "restarts_seen",
    "correlated_triples",
    "affected_pids",
    "loops_run",
    "scenario_id",
)


def rows():
    return json.loads(PACK.read_text())["scenarios"]


def row(sid):
    return next(x for x in rows() if x["id"] == sid)


def run(sid="lane_delta", *, loops=None, state=STATE, no_resume=False, output=None):
    r = row(sid)
    loops = r["loops"] if loops is None else loops
    output = output or OUT / f"{sid}-{time.time_ns()}.json"
    cmd = [
        str(BIN),
        "--db",
        r["db_path"],
        "--scenario",
        sid,
        "--loops",
        str(loops),
        "--state-dir",
        str(state),
        "--output",
        str(output),
    ]
    if no_resume:
        cmd.append("--no-resume")
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    assert p.returncode == 0, p.stderr or p.stdout
    return json.loads(output.read_text())


def semantic(x):
    return {k: x[k] for k in SEMANTIC}


def body_hash(rep):
    body = {k: v for k, v in rep.items() if k != "body_sha256"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.fixture(autouse=True)
def clean():
    shutil.rmtree(STATE, ignore_errors=True)
    STATE.mkdir(parents=True)
    subprocess.run(["bash", "/app/scripts/build.sh"], check=True, timeout=180)
    yield
    shutil.rmtree(STATE, ignore_errors=True)


def test_cold_warm_replay_is_semantically_identical_and_persistent():
    """Verify a cold replay persists one generation and an identical warm replay reuses it."""
    cold = run("lane_epsilon")
    warm = run("lane_epsilon")
    assert cold["cache_hit"] is False and cold["generation"] == 1
    assert warm["cache_hit"] is True and warm["generation"] == 1
    assert semantic(cold) == semantic(warm)
    assert cold["input_fingerprint"] == warm["input_fingerprint"]
    assert warm["fd_delta"] == 0 and warm["journal_bytes"] > 0


def test_forced_replay_appends_generation_but_preserves_result():
    """Verify --no-resume appends a new generation without changing semantic results."""
    first = run("lane_alpha")
    forced = run("lane_alpha", no_resume=True)
    warm = run("lane_alpha")
    assert [first["generation"], forced["generation"], warm["generation"]] == [1, 2, 2]
    assert forced["cache_hit"] is False and warm["cache_hit"] is True
    assert semantic(first) == semantic(forced) == semantic(warm)
    assert forced["journal_bytes"] > first["journal_bytes"]


def test_config_bytes_participate_in_fingerprint_and_invalidate_cache():
    """Verify configuration byte changes alter the fingerprint and invalidate cached results."""
    original = CONFIG.read_text()
    first = run("lane_delta")
    try:
        changed = original.replace(
            "correlation_window_ns = 30000000000", "correlation_window_ns = 20000000000"
        )
        assert changed != original
        CONFIG.write_text(changed)
        second = run("lane_delta")
        assert second["cache_hit"] is False and second["generation"] == 2
        assert second["input_fingerprint"] != first["input_fingerprint"]
        assert second["correlated_triples"] < first["correlated_triples"]
    finally:
        CONFIG.write_text(original)


def test_lmdb_content_change_invalidates_cache_and_reconstruction_is_live():
    """Verify live LMDB mutations invalidate the cache and are reflected in reconstruction."""
    sid = "lane_eta"
    r = row(sid)
    first = run(sid)
    env = lmdb.open(r["db_path"], max_dbs=4)
    samples = env.open_db(b"samples")
    key = struct.pack(">QQ", 999999, 1770000000000000000)
    try:
        with env.begin(write=True) as txn:
            txn.put(key, b'{"cpu_pct":1,"rss_kb":1,"state":"new"}', db=samples)
        env.sync()
        second = run(sid)
        assert second["cache_hit"] is False and second["generation"] == 2
        assert second["samples_scanned"] == first["samples_scanned"] + 1
        assert second["input_fingerprint"] != first["input_fingerprint"]
    finally:
        with env.begin(write=True) as txn:
            txn.delete(key, db=samples)
        env.close()


def test_torn_tail_is_truncated_to_last_valid_record_and_reused():
    """Verify an incomplete journal tail is truncated and the last valid record is reused."""
    first = run("lane_gamma")
    jp = STATE / "lane_gamma.journal"
    good = jp.stat().st_size
    with jp.open("ab") as f:
        f.write(b"\x54\x45\x4c")
    recovered = run("lane_gamma")
    assert recovered["cache_hit"] is True
    assert recovered["generation"] == first["generation"] == 1
    assert recovered["recovered_records"] == 1
    assert jp.stat().st_size == good
    assert semantic(recovered) == semantic(first)


def test_corrupt_complete_latest_record_falls_back_to_prior_generation():
    """Verify a CRC-corrupt latest record is discarded in favor of the prior generation."""
    one = run("lane_beta")
    two = run("lane_beta", no_resume=True)
    jp = STATE / "lane_beta.journal"
    data = bytearray(jp.read_bytes())
    data[-1] ^= 0xA5
    jp.write_bytes(data)
    rep = run("lane_beta")
    assert one["generation"] == 1 and two["generation"] == 2
    assert rep["cache_hit"] is True and rep["generation"] == 1
    assert rep["recovered_records"] == 1
    assert semantic(rep) == semantic(one)


def test_loop_count_is_part_of_cache_identity():
    """Verify loop count participates in cache identity and generation selection."""
    a = run("lane_alpha", loops=2)
    b = run("lane_alpha", loops=3)
    c = run("lane_alpha", loops=3)
    assert a["generation"] == 1 and b["generation"] == 2 and c["generation"] == 2
    assert b["cache_hit"] is False and c["cache_hit"] is True
    assert a["input_fingerprint"] != b["input_fingerprint"]
    assert b["loops_run"] == 3


def test_scenario_journals_are_isolated_and_do_not_cross_replay():
    """Verify each scenario uses an isolated journal and cannot reuse another scenario cache."""
    a = run("lane_alpha")
    b = run("lane_beta")
    a2 = run("lane_alpha")
    assert a["generation"] == b["generation"] == a2["generation"] == 1
    assert a2["cache_hit"] is True and b["cache_hit"] is False
    assert (STATE / "lane_alpha.journal").is_file() and (
        STATE / "lane_beta.journal"
    ).is_file()
    assert (
        a["scenario_id"] != b["scenario_id"]
        and a["input_fingerprint"] != b["input_fingerprint"]
    )


def test_concurrent_cold_start_serializes_to_one_committed_generation():
    """Verify concurrent cold starts serialize so exactly one generation is committed."""
    sid = "lane_eta"
    outputs = [OUT / f"parallel-{i}.json" for i in range(6)]

    def one(i):
        return run(sid, state=STATE, output=outputs[i])

    with ThreadPoolExecutor(max_workers=6) as ex:
        reps = list(ex.map(one, range(6)))
    assert {r["generation"] for r in reps} == {1}
    assert sum(not r["cache_hit"] for r in reps) == 1
    assert len({json.dumps(semantic(r), sort_keys=True) for r in reps}) == 1


def test_report_hash_covers_recovery_metadata_and_is_canonical():
    """Verify the canonical report hash covers metadata and preserves sorted lossless PIDs."""
    rep = run("lane_iota")
    assert rep["body_sha256"] == body_hash(rep)
    assert (
        len(rep["body_sha256"]) == 64
        and rep["body_sha256"] == rep["body_sha256"].lower()
    )
    assert rep["affected_pids"] == sorted(rep["affected_pids"])
    assert max(rep["affected_pids"]) > 2**63 - 1


def test_no_resume_still_recovers_corrupt_tail_before_appending():
    """Verify forced replay repairs a corrupt tail before appending the next generation."""
    first = run("lane_zeta")
    jp = STATE / "lane_zeta.journal"
    with jp.open("ab") as f:
        f.write(os.urandom(31))
    rep = run("lane_zeta", no_resume=True)
    assert rep["cache_hit"] is False and rep["generation"] == 2
    assert rep["recovered_records"] == 1
    assert semantic(rep) == semantic(first)
