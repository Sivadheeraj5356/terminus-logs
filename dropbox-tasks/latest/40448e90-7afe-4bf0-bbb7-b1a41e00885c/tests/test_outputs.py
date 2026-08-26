"""Behavioral checks for promotion export, mirror recovery, and session retention."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output" / "kv_export.json"
STATE = APP / "state"
BIN_PULL = APP / "bin" / "pull_gate"
BIN_SYNC = APP / "bin" / "sync_probe"
BIN_META = APP / "bin" / "meta_walk"
BIN_COLLECT = APP / "bin" / "collect_stage"


def _sha(data: bytes) -> str:
    proc = subprocess.run(
        [
            "python3",
            "-c",
            "import hashlib,sys; sys.stdout.write(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())",
        ],
        input=data,
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode()


def _load_seed(profile: str) -> dict[str, Any]:
    path = ENV / "fixtures" / "seed" / profile / "seed_steps.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _step_doc(profile: str, step: int) -> dict[str, Any]:
    seed = _load_seed(profile)
    return next((s for s in seed["steps"] if s["idx"] == step), seed["steps"][0])


def _active_targets_gen(profile: str, step: int) -> int:
    seed = _load_seed(profile)
    return int(_step_doc(profile, step).get("targets_gen", seed["targets_gen"]))


def _active_expiry(profile: str, step: int) -> int:
    seed = _load_seed(profile)
    return int(_step_doc(profile, step).get("expiry", seed["expiry"]))


def _active_admission(profile: str, step: int) -> str:
    seed = _load_seed(profile)
    return str(_step_doc(profile, step).get("admission_snap", seed["admission_snap"]))


def _active_pull_mode(profile: str, step: int) -> int:
    seed = _load_seed(profile)
    return int(_step_doc(profile, step).get("pull_mode", seed["pull_mode"]))


def _active_walk_mode(profile: str, step: int) -> int:
    seed = _load_seed(profile)
    step_mode = int(_step_doc(profile, step).get("walk_mode", seed["walk_mode"]))
    if seed.get("proxy_required") == 1:
        return _active_pull_mode(profile, step)
    return step_mode


def _manifest_bytes(tag: str) -> bytes:
    cat = json.loads((ENV / "fixtures" / "store" / "catalog.json").read_text(encoding="utf-8"))
    obj_key = cat["tags"][tag]
    ref = cat["objects"][obj_key]["bytes_ref"]
    return (ENV / "fixtures" / "store" / "blobs" / f"{ref}.bin").read_bytes()


def _targets_bytes(gen: int) -> bytes:
    name = "targets.v2.json" if gen >= 2 else "targets.v1.json"
    return (ENV / "fixtures" / "meta" / name).read_bytes()


def _role_version(gen: int) -> int:
    name = "targets.v2.json" if gen >= 2 else "targets.v1.json"
    doc = json.loads((ENV / "fixtures" / "meta" / name).read_text(encoding="utf-8"))
    return int(doc["signed"]["version"])


def _bound_bytes(profile: str, step: int, prior_transcript: str | None = None) -> bytes:
    seed = _load_seed(profile)
    active_gen = _active_targets_gen(profile, step)
    raw = _manifest_bytes(seed["image_tag"]) + _targets_bytes(active_gen)
    if prior_transcript:
        raw = prior_transcript.encode() + raw
    hint = f"t{active_gen}"
    seq = _active_expiry(profile, step) - step
    if seq < 1_000_000_000:
        seq = 1_000_000_000
    return hint.encode() + bytes([seq & 0xFF]) + raw


def _expected_content(profile: str, step: int, prior_transcript: str | None = None) -> str:
    return _sha(_bound_bytes(profile, step, prior_transcript))


def _lane_digest(profile: str, step: int) -> str:
    return _sha(
        _targets_bytes(_active_targets_gen(profile, step))
        + str(_active_walk_mode(profile, step)).encode()
    )


def _admit_digest(profile: str, step: int, prior_transcript: str | None = None) -> str:
    bound = _bound_bytes(profile, step, prior_transcript)
    return _sha(
        bound
        + _active_admission(profile, step).encode()
        + str(_active_pull_mode(profile, step)).encode()
    )


def _effective_mirror_tier(profile: str, step: int) -> int:
    seed = _load_seed(profile)
    step_doc = _step_doc(profile, step)
    tier = int(step_doc.get("mirror_tier", 2))
    if seed.get("replica_flip"):
        cat = json.loads((ENV / "fixtures" / "store" / "catalog.json").read_text(encoding="utf-8"))
        if cat.get("replicas", {}).get(seed["image_tag"]):
            return 1
    return tier


def _expected_sync_ready(profile: str, step: int) -> bool:
    return _effective_mirror_tier(profile, step) >= 2


def _expected_transcript(
    profile: str,
    step: int,
    sync_ready: bool,
    prior_transcript: str | None = None,
) -> str:
    content = _expected_content(profile, step, prior_transcript)
    lane_d = _lane_digest(profile, step)
    admit = _admit_digest(profile, step, prior_transcript)
    ready = "true" if sync_ready else "false"
    parts = content.encode() + ready.encode() + lane_d.encode() + admit.encode()
    return _sha(parts)


def _report_digest(runs: list[dict[str, Any]]) -> str:
    ordered = sorted(runs, key=lambda r: (r["profile"], r["run_index"]))
    payload = [
        {
            "profile": r["profile"],
            "run_index": r["run_index"],
            "role_version": r["role_version"],
            "content_digest": r["content_digest"],
            "delegation_expiry": r["delegation_expiry"],
            "stage_transcript_hex": r["stage_transcript_hex"],
        }
        for r in ordered
    ]
    body = json.dumps(payload, separators=(",", ":"))
    return _sha(body.encode())


def _clear_state() -> None:
    if STATE.exists():
        shutil.rmtree(STATE)
    STATE.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()


def _rebuild() -> None:
    subprocess.run(["bash", "-c", "cd /app/environment && /app/ci/rebuild.sh"], check=True, timeout=120)


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, timeout=60, text=True, capture_output=True)


def _pipeline(profile: str, step: int = 0) -> None:
    _run([str(BIN_PULL), "--profile", profile, "--step", str(step)])
    _run([str(BIN_SYNC), "--profile", profile, "--step", str(step)])
    _run([str(BIN_META), "--profile", profile, "--step", str(step)])
    _run([str(BIN_COLLECT), "--profile", profile, "--out", str(OUT)])


def _load_out() -> dict[str, Any]:
    return json.loads(OUT.read_text(encoding="utf-8"))


def _runs_for(doc: dict[str, Any], profile: str) -> list[dict[str, Any]]:
    return [r for r in doc["runs"] if r["profile"] == profile]


def _assert_row(
    row: dict[str, Any],
    profile: str,
    step: int,
    run_index: int,
    prior_transcript: str | None = None,
) -> None:
    sync_ready = _expected_sync_ready(profile, step)
    assert row["profile"] == profile
    assert row["run_index"] == run_index
    assert row["role_version"] == _role_version(_active_targets_gen(profile, step))
    assert row["delegation_expiry"] == _active_expiry(profile, step)
    assert row["content_digest"] == _expected_content(profile, step, prior_transcript)
    assert row["stage_transcript_hex"] == _expected_transcript(
        profile, step, sync_ready, prior_transcript
    )


def _assert_lane_quorum_rejected(proc: subprocess.CompletedProcess[str]) -> None:
    assert proc.returncode != 0
    err = f"{proc.stderr or ''}{proc.stdout or ''}".lower()
    stage_terms = ("pull", "sync", "walk", "gate", "probe", "collect", "quorum", "lane")
    assert (
        "mixed" in err
        or "mismatch" in err
        or ("step" in err and any(term in err for term in stage_terms))
    )


def _mirror_view() -> dict[str, Any]:
    path = STATE / "mirror_view.json"
    assert path.exists()
    return json.loads(path.read_text(encoding="utf-8"))


def _drop_mirror_view() -> None:
    path = STATE / "mirror_view.json"
    if path.exists():
        path.unlink()


def _ledger() -> dict[str, Any]:
    path = STATE / "promo_ledger.json"
    assert path.exists()
    return json.loads(path.read_text(encoding="utf-8"))


def _full_session() -> dict[str, Any]:
    _clear_state()
    _pipeline("p1", 0)
    _pipeline("p2", 0)
    _pipeline("p2", 1)
    _pipeline("p3", 0)
    _pipeline("p3", 1)
    return _load_out()


def _assert_export_equal(left: dict[str, Any], right: dict[str, Any]) -> None:
    assert left["profiles"] == right["profiles"]
    assert len(left["runs"]) == len(right["runs"])
    by = {(r["profile"], r["run_index"]): r for r in right["runs"]}
    for row in left["runs"]:
        key = (row["profile"], row["run_index"])
        assert key in by
        for field in (
            "role_version",
            "content_digest",
            "delegation_expiry",
            "stage_transcript_hex",
        ):
            assert row[field] == by[key][field]
    assert left["report_digest"] == right["report_digest"]


@pytest.fixture(scope="module", autouse=True)
def _module_rebuild() -> None:
    _rebuild()


class TestKVExport:
    def test_uninterrupted_session_matrix(self):
        """Full five-run session retains all profiles with active-step digests and chaining."""
        doc = _full_session()
        assert len(doc["runs"]) == 5
        assert doc["profiles"] == ["p1", "p2", "p3"]

        p1 = _runs_for(doc, "p1")[0]
        _assert_row(p1, "p1", 0, 0)

        p2_0 = _runs_for(doc, "p2")[0]
        _assert_row(p2_0, "p2", 0, 0)
        p2_1 = _runs_for(doc, "p2")[1]
        _assert_row(p2_1, "p2", 1, 1, prior_transcript=p2_0["stage_transcript_hex"])

        p3_0 = _runs_for(doc, "p3")[0]
        _assert_row(p3_0, "p3", 0, 0)
        assert _expected_sync_ready("p3", 0) is False
        p3_1 = _runs_for(doc, "p3")[1]
        _assert_row(p3_1, "p3", 1, 1, prior_transcript=p3_0["stage_transcript_hex"])
        assert _expected_sync_ready("p3", 1) is False
        assert p3_1["role_version"] == _role_version(2)
        assert doc["report_digest"] == _report_digest(doc["runs"])

        mirror = _mirror_view()
        assert mirror["owner"] == "p3"
        assert int(mirror["max_tier"]) == 1
        ledger = _ledger()
        assert len(ledger["events"]) == 5
        tip = ledger["events"][-1]
        assert tip["owner"] == mirror["owner"]
        assert tip["tier"] == mirror["max_tier"]
        assert tip["epoch"] == mirror["epoch"]

    def test_cross_profile_epoch_isolation(self):
        """Owner switch after replica lag must reset promotion epoch and keep p1 ready."""
        _clear_state()
        _pipeline("p3", 0)
        after_p3 = _mirror_view()
        assert after_p3["owner"] == "p3"
        assert after_p3["epoch"] == 1
        assert after_p3["max_tier"] == 1

        _pipeline("p1", 0)
        after_p1 = _mirror_view()
        assert after_p1["owner"] == "p1"
        assert after_p1["epoch"] == 1
        assert after_p1["max_tier"] == 2

        doc = _load_out()
        p1 = _runs_for(doc, "p1")[0]
        _assert_row(p1, "p1", 0, 0)
        assert set(doc["profiles"]) == {"p1", "p3"}
        tip = _ledger()["events"][-1]
        assert tip["owner"] == "p1"
        assert tip["tier"] == 2
        assert tip["epoch"] == 1

    def test_same_profile_anchor_chain(self):
        """Second same-profile run must bind the prior stage transcript into content_digest."""
        _clear_state()
        _pipeline("p2", 0)
        first = _runs_for(_load_out(), "p2")[0]
        _pipeline("p2", 1)
        second = _runs_for(_load_out(), "p2")[1]
        _assert_row(second, "p2", 1, 1, prior_transcript=first["stage_transcript_hex"])
        assert second["content_digest"] != _expected_content("p2", 1, prior_transcript=None)
        append_bound = (
            _manifest_bytes(_load_seed("p2")["image_tag"])
            + _targets_bytes(_active_targets_gen("p2", 1))
            + first["stage_transcript_hex"].encode()
        )
        hint = f"t{_active_targets_gen('p2', 1)}"
        seq = _active_expiry("p2", 1) - 1
        if seq < 1_000_000_000:
            seq = 1_000_000_000
        append_digest = _sha(hint.encode() + bytes([seq & 0xFF]) + append_bound)
        assert second["content_digest"] != append_digest

    def test_replica_lag_crash_recovery_parity(self):
        """Losing mirror_view between replica-lag steps must match an uninterrupted export."""
        continuous = _full_session()

        _clear_state()
        _pipeline("p1", 0)
        _pipeline("p2", 0)
        _pipeline("p2", 1)
        _pipeline("p3", 0)
        first = _runs_for(_load_out(), "p3")[0]
        assert first["stage_transcript_hex"] == _expected_transcript("p3", 0, False)
        assert _mirror_view()["max_tier"] == 1

        _drop_mirror_view()
        assert (STATE / "mirror_view.owner").exists()
        assert (STATE / "promo_ledger.json").exists()

        _pipeline("p3", 1)
        recovered = _load_out()
        second = _runs_for(recovered, "p3")[1]
        _assert_row(second, "p3", 1, 1, prior_transcript=first["stage_transcript_hex"])
        assert _expected_sync_ready("p3", 1) is False
        assert second["stage_transcript_hex"] == _expected_transcript(
            "p3", 1, False, first["stage_transcript_hex"]
        )
        # Inventing readiness from sidecar/ledger tip would flip sync_ready and break parity.
        assert second["stage_transcript_hex"] != _expected_transcript(
            "p3", 1, True, first["stage_transcript_hex"]
        )
        after = _mirror_view()
        assert after["owner"] == "p3"
        assert after["epoch"] == 1
        assert after["max_tier"] == 1
        _assert_export_equal(recovered, continuous)

    def test_recovered_same_owner_epoch_restarts(self):
        """After mirror loss, same-profile chaining continues while promotion epoch restarts."""
        _clear_state()
        _pipeline("p2", 0)
        first = _runs_for(_load_out(), "p2")[0]
        before = _mirror_view()
        assert before["owner"] == "p2"
        assert before["epoch"] == 1

        _drop_mirror_view()
        _pipeline("p2", 1)
        after = _mirror_view()
        assert after["owner"] == "p2"
        assert after["epoch"] == 1
        assert after["max_tier"] == 2

        second = _runs_for(_load_out(), "p2")[1]
        _assert_row(second, "p2", 1, 1, prior_transcript=first["stage_transcript_hex"])

    def test_lane_quorum_rejects_skew(self):
        """Collect must reject lanes where probe ran at a different step than gate/walk."""
        profile = "p1"
        _clear_state()
        _run([str(BIN_PULL), "--profile", profile, "--step", "0"])
        _run([str(BIN_SYNC), "--profile", profile, "--step", "1"], check=False)
        lane_path = STATE / "lanes" / f"{profile}.json"
        assert lane_path.exists()
        lane = json.loads(lane_path.read_text(encoding="utf-8"))
        lane["stage"]["sync_step_idx"] = 1
        lane_path.write_text(json.dumps(lane), encoding="utf-8")
        _run([str(BIN_META), "--profile", profile, "--step", "0"])
        proc = _run([str(BIN_COLLECT), "--profile", profile, "--out", str(OUT)], check=False)
        _assert_lane_quorum_rejected(proc)
        assert not OUT.exists()

        _clear_state()
        _run([str(BIN_PULL), "--profile", "p2", "--step", "0"])
        _run([str(BIN_SYNC), "--profile", "p2", "--step", "0"])
        _run([str(BIN_META), "--profile", "p2", "--step", "1"])
        bad_walk = _run(
            [str(BIN_COLLECT), "--profile", "p2", "--out", str(OUT)], check=False
        )
        _assert_lane_quorum_rejected(bad_walk)
        assert not OUT.exists()

    def test_proxy_active_step_surfaces(self):
        """Proxy-required profile must honor step overrides for digests and expiry."""
        _clear_state()
        _pipeline("p2", 0)
        row = _runs_for(_load_out(), "p2")[0]
        _assert_row(row, "p2", 0, 0)
        seed = _load_seed("p2")
        assert row["delegation_expiry"] != int(seed["expiry"])
        assert row["role_version"] == 1
        gen = int(seed["targets_gen"])
        expiry = int(seed["expiry"])
        raw = _manifest_bytes(seed["image_tag"]) + _targets_bytes(gen)
        hint = f"t{gen}"
        seq = expiry
        if seq < 1_000_000_000:
            seq = 1_000_000_000
        profile_default = _sha(hint.encode() + bytes([seq & 0xFF]) + raw)
        assert row["content_digest"] != profile_default

    def test_interrupt_resume_then_rollup(self):
        """Paused gate/probe resume plus later profiles must roll up the full session."""
        _clear_state()
        _run([str(BIN_PULL), "--profile", "p1", "--step", "0"])
        _run([str(BIN_SYNC), "--profile", "p1", "--step", "0"])
        _run([str(BIN_META), "--profile", "p1", "--step", "0"])
        _run([str(BIN_COLLECT), "--profile", "p1", "--out", str(OUT)])
        _assert_row(_runs_for(_load_out(), "p1")[0], "p1", 0, 0)

        _pipeline("p3", 0)
        _pipeline("p2", 0)
        p2_first = _runs_for(_load_out(), "p2")[0]
        _pipeline("p2", 1)
        doc = _load_out()
        assert doc["profiles"] == ["p1", "p2", "p3"]
        assert [r["run_index"] for r in _runs_for(doc, "p2")] == [0, 1]
        _assert_row(_runs_for(doc, "p2")[1], "p2", 1, 1, prior_transcript=p2_first["stage_transcript_hex"])
        assert doc["report_digest"] == _report_digest(doc["runs"])

    def test_handoff_does_not_poison_replica_catchup(self):
        """A ready profile must not raise replica-lag sync_ready on the next owner."""
        _clear_state()
        _pipeline("p1", 0)
        assert _mirror_view()["max_tier"] == 2
        _pipeline("p3", 0)
        row = _runs_for(_load_out(), "p3")[0]
        assert _mirror_view()["max_tier"] == 1
        assert _expected_sync_ready("p3", 0) is False
        _assert_row(row, "p3", 0, 0)
        assert row["stage_transcript_hex"] != _expected_transcript("p3", 0, True)
