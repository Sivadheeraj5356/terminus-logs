import json
import subprocess
from collections import Counter
from pathlib import Path

OUT = Path("/app/output/schedule_audit.json")
LANE = Path("/app/output/scheduler_lane_state.json")
VARIANT_DIR = Path("/app/output/variants")
CFG_DEFAULT = Path("/app/environment/profiles/default.json")
CFG_DIAMOND = Path("/app/environment/profiles/diamond_mesh.json")
CFG_LINEAR = Path("/app/environment/profiles/linear_smoke.json")
CFG_GRADUAL = Path("/app/environment/profiles/gradual_mesh.json")
CFG_FAN = Path("/app/environment/profiles/fan_in.json")
CFG_CASCADE = Path("/app/environment/profiles/cascade_wave.json")
FIXTURE_DIAMOND = Path("/app/environment/fixtures/diamond_mesh.json")
FIXTURE_LINEAR = Path("/app/environment/fixtures/linear_smoke.json")
FIXTURE_GRADUAL = Path("/app/environment/fixtures/gradual_mesh.json")
FIXTURE_FAN = Path("/app/environment/fixtures/fan_in.json")
FIXTURE_CASCADE = Path("/app/environment/fixtures/cascade_wave.json")

PROFILE_FIXTURES = (
    (CFG_DEFAULT, FIXTURE_DIAMOND),
    (CFG_DIAMOND, FIXTURE_DIAMOND),
    (CFG_LINEAR, FIXTURE_LINEAR),
    (CFG_GRADUAL, FIXTURE_GRADUAL),
    (CFG_FAN, FIXTURE_FAN),
    (CFG_CASCADE, FIXTURE_CASCADE),
)

STALL_PROFILES = (CFG_DEFAULT, CFG_DIAMOND, CFG_GRADUAL, CFG_FAN, CFG_CASCADE)
CONTROL_PROFILES = (CFG_LINEAR,)
ALL_PROFILES = STALL_PROFILES + CONTROL_PROFILES

SEED_MATRIX = (42, 7, 9001, 1337, 2024, 31415, 271828)
EXTENDED_SEEDS = (42, 7, 9001, 1337, 2024, 31415, 271828, 161803, 577215, 999983, 1234567)
ADVERSARIAL_SUITE = Path("/app/environment/profiles/adversarial_suite.json")
BOUNDARY_BY_PROFILE = {
    "default": 6,
    "diamond_mesh": 6,
    "gradual_mesh": 5,
    "fan_in": 4,
    "linear_smoke": 3,
    "cascade_wave": 8,
}
CHAIN_BOUNDARIES = {
    "cascade_wave": [5, 11, 17],
    "diamond_mesh": [4, 8],
    "fan_in": [3, 6],
}


def _sha256_hex(payload: bytes) -> str:
    proc = subprocess.run(
        ["sha256sum"],
        input=payload,
        stdout=subprocess.PIPE,
        check=True,
    )
    return proc.stdout.decode().split()[0]


def _variant(base: Path, **overrides) -> Path:
    obj = json.loads(base.read_text())
    obj.update(overrides)
    VARIANT_DIR.mkdir(parents=True, exist_ok=True)
    tag = _sha256_hex(json.dumps(obj, sort_keys=True).encode())[:12]
    path = VARIANT_DIR / f"{base.stem}_{tag}.json"
    path.write_text(json.dumps(obj, indent=2) + "\n")
    return path


def _run(cfg: Path, out: Path = OUT) -> dict:
    if out.exists():
        out.unlink()
    if LANE.exists():
        LANE.unlink()
    subprocess.check_call(
        ["bash", "/app/environment/tools/runner.sh", str(cfg), str(out)]
    )
    return json.loads(out.read_text())


def _load_fixture(path: Path) -> dict:
    return json.loads(path.read_text())


def _job_count(path: Path) -> int:
    return len(_load_fixture(path)["jobs"])


def _fixture_jobs(path: Path) -> dict[str, dict]:
    return {row["job_id"]: row for row in _load_fixture(path)["jobs"]}


def _by_id(report: dict) -> dict[str, dict]:
    return {row["job_id"]: row for row in report["jobs"]}


def _p95_from_waits(waits: list[int]) -> int:
    positive = sorted(w for w in waits if w > 0)
    if not positive:
        return 0
    idx = (len(positive) * 95 + 99) // 100
    if idx >= len(positive):
        idx = len(positive) - 1
    return positive[idx]


def _same_tick_start_count(rows: dict[str, dict], names: tuple[str, ...]) -> int:
    starts = [rows[name]["start_tick"] for name in names]
    return max(Counter(starts).values())


def _start_tick_spread(rows: dict[str, dict], names: tuple[str, ...]) -> int:
    starts = [rows[name]["start_tick"] for name in names]
    return max(starts) - min(starts)


def _positive_waits(report: dict) -> list[int]:
    return [row["queue_wait_ticks"] for row in report["jobs"] if row["queue_wait_ticks"] > 0]


def _fingerprint_from_rows(jobs: list[dict]) -> str:
    lines = [
        f"{row['job_id']}|{row['start_tick']}|{row['finish_tick']}|{row['queue_wait_ticks']}"
        for row in sorted(jobs, key=lambda r: r["job_id"])
    ]
    payload = "\n".join(lines).encode()
    proc = subprocess.run(
        ["sha256sum"],
        input=payload,
        stdout=subprocess.PIPE,
        check=True,
    )
    return proc.stdout.decode().split()[0]


def _tick_dispatch_digest(ticks: list[dict]) -> str:
    lines = [
        f"{t['tick']}|{t['running_count']}|{t['ready_count']}|{t['blocked_on_partition']}|{t['idle_nodes']}"
        for t in ticks
    ]
    return _sha256_hex("\n".join(lines).encode())


def _ledger_fingerprint(ledger: list[dict]) -> str:
    lines = [
        f"{r['partition_id']}|{r['writer_job']}|{r['publish_tick']}|{r['visible_tick']}"
        for r in ledger
    ]
    return _sha256_hex("\n".join(lines).encode())


def _seal_digest(config_id: str, seed: int, run_mode: str, boundary: int, fingerprint: str) -> str:
    payload = "\n".join(
        [config_id, str(seed), run_mode, str(boundary), fingerprint]
    )
    return _sha256_hex(payload.encode())


def _max_finish_tick(report: dict) -> int:
    finished = [row["finish_tick"] for row in report["jobs"] if row["finish_tick"] >= 0]
    return max(finished) if finished else -1


def _peak_utilization_from_ticks(report: dict) -> float:
    peak = max(snap["running_count"] for snap in report["ticks"])
    return peak / report["node_count"]


def _stall_index_from_final_tick(report: dict) -> float:
    final = report["ticks"][-1]
    if final["queued_count"] == 0:
        return 0.0
    return final["idle_nodes"] / (final["queued_count"] + 1)


def _ledger_by_partition(report: dict) -> dict[int, dict]:
    return {row["partition_id"]: row for row in report["partition_ledger"]}


def _completed_through_tick(report: dict, tick: int) -> int:
    return sum(
        1
        for row in report["jobs"]
        if row["finish_tick"] >= 0 and row["finish_tick"] <= tick
    )


def _assert_full_schedule_parity(left: dict, right: dict) -> None:
    assert left["summary"]["schedule_fingerprint"] == right["summary"]["schedule_fingerprint"]
    assert left["summary"]["tick_dispatch_digest"] == right["summary"]["tick_dispatch_digest"]
    assert left["summary"]["ledger_fingerprint"] == right["summary"]["ledger_fingerprint"]
    assert left["jobs"] == right["jobs"]
    assert left["ticks"] == right["ticks"]
    assert left["partition_ledger"] == right["partition_ledger"]


def _assert_no_capacity_stall_while_blocked(report: dict) -> None:
    total = report["summary"]["jobs_submitted"]
    for snap in report["ticks"]:
        if _completed_through_tick(report, snap["tick"]) >= total:
            continue
        if snap["blocked_on_partition"] >= 1 and snap["idle_nodes"] >= 2:
            raise AssertionError(
                f"tick {snap['tick']}: blocked_on_partition={snap['blocked_on_partition']} "
                f"while idle_nodes={snap['idle_nodes']} with incomplete work"
            )


def _assert_unblocked_ready_pile_uses_capacity(report: dict) -> None:
    total = report["summary"]["jobs_submitted"]
    for snap in report["ticks"]:
        if _completed_through_tick(report, snap["tick"]) >= total:
            continue
        if (
            snap["ready_count"] >= 2
            and snap["idle_nodes"] >= 2
            and snap["blocked_on_partition"] == 0
        ):
            assert snap["running_count"] >= 2, (
                f"tick {snap['tick']}: ready_count={snap['ready_count']} "
                f"with idle_nodes={snap['idle_nodes']} but running_count={snap['running_count']}"
            )


def _assert_strict_dep_gaps(report: dict, fixture: Path) -> None:
    rows = _by_id(report)
    spec = _fixture_jobs(fixture)
    for job_id, job in spec.items():
        child = rows[job_id]
        if child["start_tick"] < 0:
            continue
        for dep in job["deps"]:
            parent = rows[dep]
            assert parent["finish_tick"] < child["start_tick"], (
                f"{dep}.finish_tick={parent['finish_tick']} must be < "
                f"{job_id}.start_tick={child['start_tick']}"
            )


def _boundary_for(cfg: Path) -> int:
    profile = json.loads(cfg.read_text())
    return BOUNDARY_BY_PROFILE.get(profile["profile"], profile["tick_horizon"] // 3)


def _chain_boundaries_for(cfg: Path) -> list[int]:
    profile = json.loads(cfg.read_text())
    return CHAIN_BOUNDARIES.get(profile["profile"], [profile.get("boundary_tick", 6)])


def _resume_count_chain(horizon: int, boundaries: list[int]) -> int:
    return sum(horizon - b for b in boundaries)


def test_report_schema_and_documented_entry():
    """Audit JSON exposes documented fields including checkpoint digests."""
    schema = Path("/app/environment/docs/schedule_audit_schema.md").read_text()
    for token in (
        "schedule_fingerprint",
        "tick_dispatch_digest",
        "ledger_fingerprint",
        "resume_tick_count",
        "queue_wait_p95",
        "partition_ledger",
        "blocked_on_partition",
        "node_utilization",
        "stall_index",
        "schedule_duration_ticks",
        "run_mode",
        "boundary_tick",
        "checkpoint_chain",
        "boundary_ticks",
    ):
        assert token in schema
    subprocess.check_call(
        [
            "bash",
            "/app/environment/tools/runner.sh",
            "/app/environment/profiles/default.json",
            "/app/output/schedule_audit.json",
        ]
    )
    r = _run(CFG_DEFAULT, OUT)
    required = {
        "config_id",
        "seed",
        "profile",
        "graph_id",
        "run_mode",
        "boundary_tick",
        "tick_horizon",
        "node_count",
        "partition_count",
        "flags",
        "jobs",
        "summary",
        "ticks",
        "partition_ledger",
    }
    assert required <= set(r.keys())
    summary = r["summary"]
    for key in (
        "jobs_submitted",
        "jobs_completed",
        "schedule_duration_ticks",
        "node_utilization",
        "queue_wait_p95",
        "stall_index",
        "schedule_fingerprint",
        "tick_dispatch_digest",
        "ledger_fingerprint",
        "resume_tick_count",
    ):
        assert key in summary
    ids = [row["job_id"] for row in r["jobs"]]
    assert ids == sorted(ids)
    assert len(r["ticks"]) == r["tick_horizon"]


def test_derived_digest_matrix_all_profiles():
    """Fingerprints, tick digests, and ledger digests recompute on every profile."""
    for cfg, _fixture in PROFILE_FIXTURES:
        r = _run(cfg, OUT)
        assert r["summary"]["schedule_fingerprint"] == _fingerprint_from_rows(r["jobs"])
        assert r["summary"]["tick_dispatch_digest"] == _tick_dispatch_digest(r["ticks"])
        assert r["summary"]["ledger_fingerprint"] == _ledger_fingerprint(r["partition_ledger"])
        ids = [row["partition_id"] for row in r["partition_ledger"]]
        assert ids == list(range(r["partition_count"]))
        for tick in r["ticks"]:
            assert tick["running_count"] <= r["node_count"]
            assert tick["idle_nodes"] + tick["running_count"] == r["node_count"]


def test_summary_derived_fields_matrix():
    """P95, duration, utilization, and stall index recompute across profiles."""
    for cfg, fixture in PROFILE_FIXTURES:
        r = _run(cfg, OUT)
        waits = _positive_waits(r)
        assert r["summary"]["queue_wait_p95"] == _p95_from_waits(waits)
        assert r["summary"]["schedule_duration_ticks"] == _max_finish_tick(r)
        if cfg in (CFG_DIAMOND, CFG_FAN, CFG_DEFAULT, CFG_CASCADE):
            assert r["summary"]["node_utilization"] == _peak_utilization_from_ticks(r)
        if cfg in (CFG_DIAMOND, CFG_FAN, CFG_LINEAR):
            assert r["summary"]["stall_index"] == _stall_index_from_final_tick(r)
        expected = _fixture_jobs(fixture)
        for row in r["jobs"]:
            assert row["duration_ticks"] == expected[row["job_id"]]["duration"]
            if row["finish_tick"] >= 0:
                assert row["start_tick"] >= 0
                assert row["finish_tick"] >= row["start_tick"]
                assert row["node_id"] >= 0
        profile = json.loads(cfg.read_text())
        assert r["flags"] == profile["flags"]


def test_steady_checkpoint_resume_parity_matrix():
    """Steady and checkpoint_resume modes must match on stall profiles and seeds."""
    for cfg in STALL_PROFILES:
        boundary = _boundary_for(cfg)
        for seed in SEED_MATRIX:
            steady_cfg = _variant(cfg, run_mode="steady", seed=seed)
            ckpt_cfg = _variant(
                cfg,
                run_mode="checkpoint_resume",
                seed=seed,
                boundary_tick=boundary,
            )
            steady = _run(steady_cfg, OUT)
            ckpt = _run(ckpt_cfg, OUT)
            _assert_full_schedule_parity(steady, ckpt)
            assert ckpt["summary"]["resume_tick_count"] == ckpt["tick_horizon"] - boundary
            assert ckpt["run_mode"] == "checkpoint_resume"
            assert LANE.exists()
            lane = json.loads(LANE.read_text())
            assert lane["poison_accepted"] is False
            assert lane["seal_digest"] == _seal_digest(
                lane["config_id"],
                lane["seed"],
                lane["run_mode"],
                lane["boundary_tick"],
                lane["schedule_fingerprint"],
            )


def test_checkpoint_chain_parity_matrix():
    """Steady and checkpoint_chain modes must match across seeds and chain boundaries."""
    for cfg in (CFG_CASCADE, CFG_DIAMOND, CFG_FAN):
        boundaries = _chain_boundaries_for(cfg)
        for seed in SEED_MATRIX:
            steady_cfg = _variant(cfg, run_mode="steady", seed=seed)
            chain_cfg = _variant(
                cfg,
                run_mode="checkpoint_chain",
                seed=seed,
                boundary_ticks=boundaries,
            )
            steady = _run(steady_cfg, OUT)
            chain = _run(chain_cfg, OUT)
            _assert_full_schedule_parity(steady, chain)
            assert chain["run_mode"] == "checkpoint_chain"
            assert chain["summary"]["resume_tick_count"] == _resume_count_chain(
                chain["tick_horizon"], boundaries
            )
            assert LANE.exists()


def test_checkpoint_chain_prefix_ticks_at_each_boundary():
    """Prefix tick snapshots through each chain boundary minus one match steady."""
    cfg = CFG_CASCADE
    boundaries = _chain_boundaries_for(cfg)
    steady = _run(_variant(cfg, run_mode="steady"), OUT)
    chain = _run(
        _variant(cfg, run_mode="checkpoint_chain", boundary_ticks=boundaries),
        OUT,
    )
    for boundary in boundaries:
        assert steady["ticks"][:boundary] == chain["ticks"][:boundary]


def test_checkpoint_prefix_ticks_match_through_boundary():
    """Prefix tick snapshots through boundary-1 must match between modes."""
    for cfg in (CFG_DIAMOND, CFG_GRADUAL, CFG_FAN, CFG_CASCADE):
        boundary = _boundary_for(cfg)
        steady = _run(_variant(cfg, run_mode="steady"), OUT)
        ckpt = _run(
            _variant(cfg, run_mode="checkpoint_resume", boundary_tick=boundary),
            OUT,
        )
        assert steady["ticks"][:boundary] == ckpt["ticks"][:boundary]


def test_chain_replay_idempotent_fingerprints():
    """Repeated checkpoint_chain runs stay bitwise identical across stall profiles."""
    for cfg in (CFG_CASCADE, CFG_DIAMOND, CFG_FAN):
        boundaries = _chain_boundaries_for(cfg)
        chain_cfg = _variant(
            cfg, run_mode="checkpoint_chain", boundary_ticks=boundaries
        )
        first = _run(chain_cfg, OUT)
        second = _run(chain_cfg, OUT)
        third = _run(chain_cfg, OUT)
        fp = first["summary"]["schedule_fingerprint"]
        assert second["summary"]["schedule_fingerprint"] == fp
        assert third["summary"]["schedule_fingerprint"] == fp
        assert first["jobs"] == second["jobs"] == third["jobs"]
        assert first["partition_ledger"] == second["partition_ledger"]


def test_seed_matrix_completion_and_capacity_invariants():
    """Alternate seeds must complete stall graphs without capacity stalls."""
    for cfg in STALL_PROFILES:
        for seed in SEED_MATRIX:
            r = _run(_variant(cfg, seed=seed), OUT)
            assert r["summary"]["jobs_completed"] == r["summary"]["jobs_submitted"]
            _assert_no_capacity_stall_while_blocked(r)
            if cfg in (CFG_DIAMOND, CFG_FAN, CFG_CASCADE):
                _assert_unblocked_ready_pile_uses_capacity(r)


def test_strict_dependency_gaps_all_profiles():
    """Every dependency edge obeys strict finish_tick < start_tick when strict_deps is on."""
    for cfg, fixture in PROFILE_FIXTURES:
        if cfg == CFG_LINEAR:
            continue
        r = _run(cfg, OUT)
        assert r["flags"]["strict_deps"] is True
        _assert_strict_dep_gaps(r, fixture)


def test_epoch_visible_tick_strict_deps_delay():
    """Published partitions under strict_deps become visible one tick after publish."""
    for cfg in (CFG_DIAMOND, CFG_CASCADE):
        r = _run(cfg, OUT)
        for row in r["partition_ledger"]:
            if row["publish_tick"] < 0:
                continue
            assert row["visible_tick"] == row["publish_tick"] + 1


def test_partition_visibility_matrix_stall_profiles():
    """Consumers never start before input partitions become visible."""
    for cfg, fixture in PROFILE_FIXTURES:
        if cfg == CFG_LINEAR:
            continue
        r = _run(cfg, OUT)
        rows = _by_id(r)
        ledger = _ledger_by_partition(r)
        spec = _fixture_jobs(fixture)
        for job_id, job in spec.items():
            row = rows[job_id]
            if row["start_tick"] < 0:
                continue
            for part in job["input_parts"]:
                visible = ledger[part]["visible_tick"]
                assert visible >= 0
                assert row["start_tick"] >= visible


def test_poison_lane_state_ignored_on_resume():
    """Foreign lane seal must not alter checkpoint resume output."""
    cfg = _variant(CFG_DIAMOND, run_mode="checkpoint_resume", boundary_tick=6)
    poison = {
        "config_id": "foreign",
        "seed": 1,
        "run_mode": "checkpoint_resume",
        "boundary_tick": 99,
        "schedule_fingerprint": "deadbeef",
        "seal_digest": "0" * 64,
        "poison_accepted": True,
    }
    LANE.parent.mkdir(parents=True, exist_ok=True)
    LANE.write_text(json.dumps(poison))
    steady = _run(_variant(CFG_DIAMOND, run_mode="steady"), OUT)
    ckpt = _run(cfg, OUT)
    _assert_full_schedule_parity(steady, ckpt)
    lane = json.loads(LANE.read_text())
    assert lane["poison_accepted"] is False
    assert lane["config_id"] == "diamond_mesh"


def test_cross_profile_fingerprints_differ():
    """Distinct graph profiles must not collapse to the same schedule fingerprint."""
    diamond = _run(CFG_DIAMOND, OUT)
    fan = _run(CFG_FAN, OUT)
    cascade = _run(CFG_CASCADE, OUT)
    fps = {
        diamond["summary"]["schedule_fingerprint"],
        fan["summary"]["schedule_fingerprint"],
        cascade["summary"]["schedule_fingerprint"],
    }
    assert len(fps) == 3


def test_no_capacity_stall_while_partition_blocked():
    """Incomplete schedules must not hold blocked jobs while two or more nodes idle."""
    for cfg in (CFG_DIAMOND, CFG_GRADUAL, CFG_FAN, CFG_DEFAULT, CFG_CASCADE):
        r = _run(cfg, OUT)
        _assert_no_capacity_stall_while_blocked(r)


def test_unblocked_ready_pile_uses_idle_nodes():
    """When ready work is unblocked, multiple idle nodes must be consumed."""
    for cfg in (CFG_DIAMOND, CFG_FAN, CFG_CASCADE):
        r = _run(cfg, OUT)
        _assert_unblocked_ready_pile_uses_capacity(r)


def test_linear_smoke_completes_within_bounds():
    """Linear control completes every job within documented duration."""
    r = _run(CFG_LINEAR, OUT)
    assert r["summary"]["jobs_submitted"] == _job_count(FIXTURE_LINEAR)
    assert r["summary"]["jobs_completed"] == r["summary"]["jobs_submitted"]
    assert r["summary"]["schedule_duration_ticks"] <= 12
    assert r["summary"]["queue_wait_p95"] == 0


def test_linear_chain_dependency_gaps():
    """Linear chain respects parent finish before child start."""
    r = _run(CFG_LINEAR, OUT)
    rows = _by_id(r)
    assert rows["step_a"]["finish_tick"] < rows["step_b"]["start_tick"]
    assert rows["step_b"]["finish_tick"] < rows["step_c"]["start_tick"]


def test_diamond_mesh_utilization_and_waits():
    """Diamond mesh meets utilization, wait, and duration bands."""
    r = _run(CFG_DIAMOND, OUT)
    assert r["summary"]["jobs_submitted"] == _job_count(FIXTURE_DIAMOND)
    assert r["summary"]["jobs_completed"] == r["summary"]["jobs_submitted"]
    assert r["summary"]["node_utilization"] >= 0.5
    assert r["summary"]["queue_wait_p95"] == 0
    assert r["summary"]["schedule_duration_ticks"] <= 12


def test_diamond_mesh_branches_start_together():
    """Left and right branches start within one tick on diamond mesh."""
    r = _run(CFG_DIAMOND, OUT)
    rows = _by_id(r)
    assert rows["root"]["finish_tick"] < rows["left"]["start_tick"]
    assert rows["root"]["finish_tick"] < rows["right"]["start_tick"]
    assert _start_tick_spread(rows, ("left", "right")) == 0
    assert _same_tick_start_count(rows, ("left", "right")) == 2


def test_diamond_mesh_merge_starts_after_branches():
    """Merge starts only after both branch jobs finish."""
    r = _run(CFG_DIAMOND, OUT)
    rows = _by_id(r)
    branch_done = max(rows["left"]["finish_tick"], rows["right"]["finish_tick"])
    assert rows["merge"]["start_tick"] > branch_done


def test_diamond_mesh_concurrent_branch_phase():
    """Branch phase uses multiple nodes on the first branch start tick."""
    r = _run(CFG_DIAMOND, OUT)
    rows = _by_id(r)
    start = min(rows["left"]["start_tick"], rows["right"]["start_tick"])
    tick = next(t for t in r["ticks"] if t["tick"] == start)
    assert tick["running_count"] >= 2


def test_gradual_mesh_submit_ticks_respected():
    """Staggered submit ticks precede or coincide with each job start."""
    r = _run(CFG_GRADUAL, OUT)
    rows = _by_id(r)
    spec = _fixture_jobs(FIXTURE_GRADUAL)
    for job_id, job in spec.items():
        row = rows[job_id]
        assert row["start_tick"] >= job["submit_tick"]


def test_gradual_mesh_merge_starts_after_branches():
    """Gradual mesh merge respects both branch finish ticks."""
    r = _run(CFG_GRADUAL, OUT)
    rows = _by_id(r)
    branch_done = max(rows["left"]["finish_tick"], rows["right"]["finish_tick"])
    assert rows["merge"]["start_tick"] > branch_done


def test_fan_in_parallel_dispatch_burst():
    """Fan-in starts parallel arms together and completes bundle."""
    r = _run(CFG_FAN, OUT)
    assert r["summary"]["jobs_completed"] == _job_count(FIXTURE_FAN)
    rows = _by_id(r)
    arms = ("arm_a", "arm_b", "arm_c", "arm_d")
    assert rows["root"]["finish_tick"] < min(rows[a]["start_tick"] for a in arms)
    assert _start_tick_spread(rows, arms) == 0
    assert _same_tick_start_count(rows, arms) == 4
    start = min(rows[a]["start_tick"] for a in arms)
    tick = next(t for t in r["ticks"] if t["tick"] == start)
    assert tick["running_count"] == r["node_count"]
    assert rows["bundle"]["finish_tick"] >= 0
    assert rows["bundle"]["queue_wait_ticks"] == 0
    assert r["summary"]["node_utilization"] == 1.0
    assert r["summary"]["schedule_duration_ticks"] <= 10


def test_fan_in_bundle_starts_after_all_arms():
    """Bundle starts only after every arm finishes."""
    r = _run(CFG_FAN, OUT)
    rows = _by_id(r)
    arms = ("arm_a", "arm_b", "arm_c", "arm_d")
    arm_done = max(rows[a]["finish_tick"] for a in arms)
    assert rows["bundle"]["start_tick"] > arm_done


def test_cascade_wave_completes_with_wave_geometry():
    """Cascade wave completes all jobs with wave-0 parallelism and finale finish."""
    r = _run(CFG_CASCADE, OUT)
    assert r["summary"]["jobs_completed"] == _job_count(FIXTURE_CASCADE)
    assert r["summary"]["schedule_duration_ticks"] <= 24
    assert r["summary"]["queue_wait_p95"] == 0
    rows = _by_id(r)
    assert rows["wave0_a"]["start_tick"] == rows["wave0_b"]["start_tick"]
    assert rows["wave2_finale"]["finish_tick"] >= 0
    _assert_strict_dep_gaps(r, FIXTURE_CASCADE)


def test_cascade_wave_checkpoint_chain_matches_steady():
    """Cascade checkpoint_chain at documented boundaries matches steady schedule."""
    boundaries = CHAIN_BOUNDARIES["cascade_wave"]
    steady = _run(_variant(CFG_CASCADE, run_mode="steady"), OUT)
    chain = _run(
        _variant(CFG_CASCADE, run_mode="checkpoint_chain", boundary_ticks=boundaries),
        OUT,
    )
    _assert_full_schedule_parity(steady, chain)


def test_partition_ledger_visibility():
    """Completed producers leave partitions readable in the ledger."""
    r = _run(CFG_DIAMOND, OUT)
    rows = _by_id(r)
    ledger = {row["partition_id"]: row for row in r["partition_ledger"]}
    for job_id, part in (("root", 0), ("left", 1), ("right", 2), ("merge", 3)):
        if rows[job_id]["finish_tick"] < 0:
            continue
        row = ledger[part]
        assert row["writer_job"] == ""
        assert row["visible_tick"] >= 0


def test_idle_nodes_used_when_ready_pile():
    """First parallel arm dispatch tick must consume every idle worker slot."""
    r = _run(CFG_FAN, OUT)
    rows = _by_id(r)
    arm_names = ("arm_a", "arm_b", "arm_c", "arm_d")
    first_arm_tick = min(rows[name]["start_tick"] for name in arm_names)
    burst = next(s for s in r["ticks"] if s["tick"] == first_arm_tick)
    assert burst["running_count"] == r["node_count"]
    assert burst["idle_nodes"] == 0


def test_restore_preserves_ledger_visible_ticks():
    """Checkpoint resume must not rewrite published visible_tick values."""
    cfg = _variant(CFG_CASCADE, run_mode="checkpoint_resume", boundary_tick=8)
    steady = _run(_variant(CFG_CASCADE, run_mode="steady"), OUT)
    ckpt = _run(cfg, OUT)
    assert steady["partition_ledger"] == ckpt["partition_ledger"]


def _run_probe(cfg: Path) -> dict:
    proc = subprocess.run(
        ["/app/bin/sched_probe", "--config", str(cfg)],
        stdout=subprocess.PIPE,
        check=True,
    )
    return json.loads(proc.stdout.decode())


def test_shallow_probe_insufficient_for_checkpoint_parity():
    """sched_probe completion_ratio does not alone satisfy verifier parity requirements."""
    cfg = _variant(CFG_CASCADE, run_mode="checkpoint_resume", boundary_tick=8)
    steady = _run(_variant(CFG_CASCADE, run_mode="steady"), OUT)
    ckpt = _run(cfg, OUT)
    probe_steady = _run_probe(_variant(CFG_CASCADE, run_mode="steady"))
    probe_ckpt = _run_probe(cfg)
    assert probe_steady["completion_ratio"] == 1.0
    assert probe_ckpt["completion_ratio"] == 1.0
    _assert_full_schedule_parity(steady, ckpt)


def test_adversarial_suite_all_members():
    """Every adversarial suite member must match steady parity for its geometry."""
    suite = json.loads(ADVERSARIAL_SUITE.read_text())
    for member in suite["members"]:
        base = Path(member["profile"])
        seed = member.get("seed", 42)
        run_mode = member["run_mode"]
        overrides = {"seed": seed, "run_mode": run_mode}
        if run_mode == "checkpoint_resume":
            overrides["boundary_tick"] = member["boundary_tick"]
        elif run_mode == "checkpoint_chain":
            overrides["boundary_ticks"] = member["boundary_ticks"]
        variant = _variant(base, **overrides)
        steady = _run(_variant(base, seed=seed, run_mode="steady"), OUT)
        actual = _run(variant, OUT)
        _assert_full_schedule_parity(steady, actual)


def _warm_marathon_profiles():
    """Run a long interleaved profile sequence before held-out checks."""
    sequence = [
        (CFG_LINEAR, {"run_mode": "steady"}),
        (CFG_DIAMOND, {"run_mode": "steady"}),
        (CFG_GRADUAL, {"run_mode": "steady"}),
        (CFG_FAN, {"run_mode": "steady"}),
        (CFG_DEFAULT, {"run_mode": "checkpoint_resume", "boundary_tick": 4}),
        (CFG_CASCADE, {"run_mode": "steady"}),
        (CFG_DIAMOND, {"run_mode": "checkpoint_resume", "boundary_tick": 5}),
        (CFG_FAN, {"run_mode": "checkpoint_chain", "boundary_ticks": [3, 6]}),
        (CFG_GRADUAL, {"run_mode": "checkpoint_resume", "boundary_tick": 4}),
        (CFG_DEFAULT, {"run_mode": "steady"}),
        (CFG_CASCADE, {"run_mode": "checkpoint_resume", "boundary_tick": 7}),
        (CFG_LINEAR, {"run_mode": "steady"}),
    ]
    for cfg, overrides in sequence:
        _run(_variant(cfg, **overrides), OUT)


def test_warm_marathon_cascade_chain_after_twelve_profiles():
    """Held-out cascade checkpoint_chain parity after warm marathon."""
    _warm_marathon_profiles()
    boundaries = CHAIN_BOUNDARIES["cascade_wave"]
    steady = _run(_variant(CFG_CASCADE, run_mode="steady", seed=161803), OUT)
    chain = _run(
        _variant(
            CFG_CASCADE,
            run_mode="checkpoint_chain",
            boundary_ticks=boundaries,
            seed=161803,
        ),
        OUT,
    )
    _assert_full_schedule_parity(steady, chain)


def test_extended_seed_sweep_diamond():
    """Diamond mesh must complete across extended seed sweep without capacity stalls."""
    for seed in EXTENDED_SEEDS:
        r = _run(_variant(CFG_DIAMOND, seed=seed), OUT)
        assert r["summary"]["jobs_completed"] == r["summary"]["jobs_submitted"]
        _assert_no_capacity_stall_while_blocked(r)
        _assert_strict_dep_gaps(r, FIXTURE_DIAMOND)


def test_lane_seal_cross_seed_binding():
    """Lane seal_digest must bind config_id, seed, run_mode, boundary, and fingerprint."""
    for seed in (42, 1337, 271828):
        cfg = _variant(CFG_DIAMOND, run_mode="checkpoint_resume", boundary_tick=6, seed=seed)
        r = _run(cfg, OUT)
        assert LANE.exists()
        lane = json.loads(LANE.read_text())
        assert lane["poison_accepted"] is False
        assert lane["schedule_fingerprint"] == r["summary"]["schedule_fingerprint"]
        assert lane["seal_digest"] == _seal_digest(
            lane["config_id"],
            lane["seed"],
            lane["run_mode"],
            lane["boundary_tick"],
            lane["schedule_fingerprint"],
        )
