import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

OUTPUT = Path("/app/output")
ENV = Path("/app/environment")
PREFIX_PATH = ENV / "data" / "seed_extents.bin"
PHASE_PATH = ENV / "data" / "window.phase"
CHECKPOINT_PATH = ENV / "data" / "checkpoint.seq"
STAGING_PATH = ENV / "data" / "staging.rev"
FIXTURES = ENV / "fixtures"
REPRO_SCRIPT = "/app/environment/scripts/repro_trim_cycle.sh"


def _run_repro(extra_env: dict | None = None, *, reset_state: bool = True) -> subprocess.CompletedProcess:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    if reset_state:
        CHECKPOINT_PATH.write_text("0\n")
        STAGING_PATH.write_text("0\n")
        PHASE_PATH.write_bytes(bytes([0, 0]))
    env = os.environ.copy()
    env.setdefault("OUTPUT_DIR", str(OUTPUT))
    env.setdefault("TRIM_CYCLES", "2")
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", REPRO_SCRIPT],
        cwd="/app",
        env=env,
        check=False,
    )


def _load(name: str):
    path = OUTPUT / name
    assert path.exists(), f"missing {path}"
    if name.endswith(".jsonl"):
        lines = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        return lines
    payload = json.loads(path.read_text())
    if name == "trim_transcript.json":
        return payload["rows"]
    return payload


def _prefix_bytes() -> bytes:
    return PREFIX_PATH.read_bytes()[:8]


def _body_digest(epoch: int) -> str:
    canon = _prefix_bytes() + bytes([epoch & 0xFF])
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", "-hex"],
        input=canon,
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode().strip().split()[-1]


def _row_units() -> int:
    for line in (ENV / "config" / "volume.toml").read_text().splitlines():
        parts = line.strip().split()
        if parts and parts[0] == "row_units":
            return int(parts[-1])
    raise AssertionError("row_units missing")


def _peer_count() -> int:
    return (ENV / "config" / "replay.toml").read_text().count("peer_tag")


def _active_profile() -> str:
    for line in (ENV / "config" / "bind_policy.toml").read_text().splitlines():
        line = line.strip()
        if line.startswith("active_profile"):
            return line.split("=", 1)[1].strip().strip('"')
    raise AssertionError("active_profile missing")


def _profile_series() -> tuple[int, int]:
    profile = _active_profile()
    num_field = den_field = None
    section = f"[profiles.{profile}]"
    in_section = False
    for line in (ENV / "config" / "series_profiles.toml").read_text().splitlines():
        line = line.strip()
        if line.startswith("[profiles."):
            in_section = line == section
        elif in_section and "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"')
            if key == "num_field":
                num_field = val
            elif key == "den_field":
                den_field = val
    assert num_field and den_field, f"profile {profile} missing num_field or den_field"
    fields = {}
    for line in (ENV / "config" / "volume.toml").read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            fields[key.strip()] = int(val.strip())
    return fields[num_field], fields[den_field]


def _decoy_series() -> tuple[int, int]:
    ratio = json.loads((FIXTURES / "util_ratio.json").read_text())
    return ratio["series_num"], ratio["series_den"]


def _volume_tick(cycle: int) -> int:
    suffix = chr(ord("a") + cycle - 1)
    snap = json.loads((FIXTURES / f"volume_slots_{suffix}.json").read_text())
    return snap["rows"][0]["tick"]


def _volume_slots_free(cycle: int) -> int:
    suffix = chr(ord("a") + cycle - 1)
    snap = json.loads((FIXTURES / f"volume_slots_{suffix}.json").read_text())
    return snap["rows"][0]["slots_free"]


def _array_cleared(cycle: int) -> int:
    suffix = chr(ord("a") + cycle - 1)
    snap = json.loads((FIXTURES / f"array_slots_{suffix}.json").read_text())
    return snap["rows"][0]["cleared_units"]


def _trim_tick() -> int:
    evt = json.loads((FIXTURES / "trim_event.json").read_text())
    return evt["tick"]


def _phase_coordinator() -> int:
    return PHASE_PATH.read_bytes()[0]


def _phase_window() -> int:
    return PHASE_PATH.read_bytes()[1]


def _checkpoint_seq() -> int:
    return int(CHECKPOINT_PATH.read_text().strip())


def _staging_rev() -> int:
    return int(STAGING_PATH.read_text().strip())


def _view_by_peer(digest: dict, peer: str) -> dict:
    for view in digest["views"]:
        if view["peer_id"] == peer:
            return view
    raise AssertionError(f"missing peer {peer}")


def _latest_window_trace(trace: list, peers: int) -> list:
    assert len(trace) >= peers, "trace shorter than peer count"
    return trace[-peers:]


def _artifact_bundle() -> dict:
    return {
        "trim_transcript.json": _load("trim_transcript.json"),
        "slot_map_digest.json": _load("slot_map_digest.json"),
        "propagation_trace.jsonl": _load("propagation_trace.jsonl"),
        "convergence_report.json": _load("convergence_report.json"),
    }


def test_transcript_latest_window_scope():
    """trim_transcript lists only the active replay-window rows after two cycles."""
    assert _run_repro({"TRIM_CYCLES": "2"}).returncode == 0
    transcript = _load("trim_transcript.json")
    peers = _peer_count()
    assert len(transcript) == peers, (
        f"expected {peers} latest-window transcript rows, got {len(transcript)}"
    )
    conv = _load("convergence_report.json")
    assert len(conv["cycles"]) >= 2


def test_trace_cleared_ordinal_not_span_offset():
    """Propagation trace a_val follows array cleared ordinals, not span byte offsets."""
    assert _run_repro({"TRIM_CYCLES": "2"}).returncode == 0
    trace = _load("propagation_trace.jsonl")
    peers = _peer_count()
    window = trace[-peers:]
    cleared = _array_cleared(2)
    span_start = _row_units()
    for row in window:
        assert row["a_val"] == cleared, (
            f"a_val {row['a_val']} should be cleared ordinal {cleared}, not span offset"
        )
        assert row["a_val"] != span_start or cleared == span_start


def test_bootstrap_above_prior_digest_ceiling():
    """Second-window lane ticks must clear the prior-window digest ceiling."""
    assert _run_repro({"TRIM_CYCLES": "1"}).returncode == 0
    peers = _peer_count()
    prior_trace = _load("propagation_trace.jsonl")[:peers]
    ceiling = max(row["tick"] for row in prior_trace)
    prior_epoch = _load("slot_map_digest.json")["views"][0]["epoch"]
    assert _run_repro({"TRIM_CYCLES": "2"}, reset_state=False).returncode == 0
    trace = _load("propagation_trace.jsonl")
    window_two = trace[peers : peers * 2]
    assert min(row["tick"] for row in window_two) > ceiling
    assert min(row["tick"] for row in window_two) > prior_epoch
    digest = _load("slot_map_digest.json")
    assert digest["views"][0]["epoch"] > prior_epoch
    assert digest["views"][0]["epoch"] > _volume_tick(2)


def test_series_from_profile_chain():
    """Dashboard series follows bind_policy profile chain, not util_ratio decoy counts."""
    assert _run_repro({"TRIM_CYCLES": "2"}).returncode == 0
    digest = _load("slot_map_digest.json")
    expected = _profile_series()
    decoy = _decoy_series()
    assert expected != decoy, "profile and decoy series must differ for this fixture"
    for view in digest["views"]:
        assert view["series_num"] == expected[0]
        assert view["series_den"] == expected[1]
        assert (view["series_num"], view["series_den"]) != decoy


def test_body_digest_usage_epoch():
    """body_hex binds to usage-line epoch bytes, not lane tick or trim fixture alone."""
    assert _run_repro({"TRIM_CYCLES": "2"}).returncode == 0
    digest = _load("slot_map_digest.json")
    trim_tick = _trim_tick()
    for view in digest["views"]:
        assert view["body_hex"] == _body_digest(view["epoch"])[:16]
        if view["epoch"] != trim_tick:
            assert view["body_hex"] != _body_digest(trim_tick)[:16]
        if view["epoch"] != view["lane_tick"]:
            assert view["body_hex"] != _body_digest(view["lane_tick"])[:16]


def test_lane_stride_between_peers():
    """Lane ticks increase between peers within each replay window."""
    assert _run_repro({"TRIM_CYCLES": "2"}).returncode == 0
    trace = _load("propagation_trace.jsonl")
    transcript = _load("trim_transcript.json")
    peers = _peer_count()
    for window_idx in range(2):
        chunk = trace[window_idx * peers : (window_idx + 1) * peers]
        ticks = [row["tick"] for row in chunk]
        for prev, cur in zip(ticks, ticks[1:]):
            assert cur > prev, f"peer lane ticks not increasing in window {window_idx + 1}"
    for prev, cur in zip(transcript, transcript[1:]):
        assert cur["lane_tick"] > prev["lane_tick"]


def test_resume_matches_fresh_run():
    """Interrupted replay resumed from retained output matches a fresh two-window run."""
    assert _run_repro({"TRIM_CYCLES": "1"}).returncode == 0
    with tempfile.TemporaryDirectory() as tmp:
        saved = Path(tmp) / "partial"
        shutil.copytree(OUTPUT, saved)
        shutil.rmtree(OUTPUT)
        shutil.copytree(saved, OUTPUT)
        env = os.environ.copy()
        env.update({"OUTPUT_DIR": str(OUTPUT), "CYCLE": "2", "APPEND_EXPORT": "1"})
        assert (
            subprocess.run(["/app/bin/volutil", "run", "/app/output"], cwd="/app", env=env, check=False).returncode
            == 0
        )
        resumed = _artifact_bundle()
        resumed_ckpt = _checkpoint_seq()
        resumed_staging = _staging_rev()
    assert _run_repro({"TRIM_CYCLES": "2"}).returncode == 0
    assert resumed == _artifact_bundle()
    assert _checkpoint_seq() == resumed_ckpt
    assert _staging_rev() == resumed_staging


def test_second_window_skew_surfaces():
    """A single-window replay can look aligned while two-window convergence still drifts."""
    assert _run_repro({"TRIM_CYCLES": "1"}).returncode == 0
    w1 = _load("slot_map_digest.json")["views"][0]
    assert _run_repro({"TRIM_CYCLES": "2"}, reset_state=False).returncode == 0
    digest = _load("slot_map_digest.json")
    epoch = digest["views"][0]["epoch"]
    assert epoch > w1["epoch"]
    assert epoch > _volume_tick(1)
    assert epoch > _trim_tick()
    probe = subprocess.run(["/app/bin/volutil", "try"], cwd="/app", check=False)
    assert probe.returncode == 0


def test_idempotent_append_no_ceiling_rewind():
    """Append rerun of a finished window does not duplicate rows or lower ceilings."""
    assert _run_repro({"TRIM_CYCLES": "1"}).returncode == 0
    before_rows = len(_load("trim_transcript.json"))
    first_digest = _load("slot_map_digest.json")
    first_ckpt = _checkpoint_seq()
    first_staging = _staging_rev()
    env = os.environ.copy()
    env.update({"OUTPUT_DIR": str(OUTPUT), "CYCLE": "1", "APPEND_EXPORT": "1"})
    subprocess.run(["/app/bin/volutil", "run", "/app/output"], cwd="/app", env=env, check=True)
    assert len(_load("trim_transcript.json")) == before_rows
    assert _load("slot_map_digest.json") == first_digest
    assert _checkpoint_seq() == first_ckpt
    assert _staging_rev() == first_staging


def test_persistence_triple_lockstep():
    """checkpoint.seq, staging.rev, and coordinator phase track converged digest epoch."""
    assert _run_repro({"TRIM_CYCLES": "2"}).returncode == 0
    digest = _load("slot_map_digest.json")
    epoch = digest["views"][0]["epoch"]
    assert _checkpoint_seq() == epoch
    assert _staging_rev() == epoch
    assert epoch > 2
    assert _phase_coordinator() == 2
    assert _phase_window() == 2
    transcript = _load("trim_transcript.json")
    assert epoch == max(row["lane_tick"] for row in transcript)
    trace = _load("propagation_trace.jsonl")
    assert trace[-1]["tick"] == epoch
    for view in digest["views"]:
        assert view["slots_free"] == _volume_slots_free(2)
        assert view["skipped_bytes"] == 0
    conv = _load("convergence_report.json")
    final = max(conv["cycles"], key=lambda r: r["cycle"])
    assert final["applied_bytes"] > final["skipped_bytes"]
    subprocess.run(["/app/bin/volutil", "try"], cwd="/app", check=True)
