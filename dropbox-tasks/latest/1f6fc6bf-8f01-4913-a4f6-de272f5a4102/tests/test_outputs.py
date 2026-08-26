"""Verifier for pooled relay linger governor task."""

from __future__ import annotations

import csv
import json
import signal
import socket
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

APP = Path("/app")
OUT = Path("/output")
BIN = APP / "bin" / "relayctl"
SMOKE_4 = APP / "fixtures" / "workloads" / "smoke_4.json"
SMOKE_16 = APP / "fixtures" / "workloads" / "smoke_16.json"
GEN = Path("/tests/harness/gen_workload.py")
EXPECT = Path("/tests/harness/expect.py")
MOCK = Path("/tests/harness/mock_shard_server.py")
POLICY = APP / "config" / "relay_policy.toml"
BUNDLE_ID = APP / "docs" / "relay_bundle_id.txt"


def _import_expect():
    import importlib.util

    spec = importlib.util.spec_from_file_location("prlg_expect", EXPECT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _policy_idle_close_ms() -> int:
    for line in POLICY.read_text().splitlines():
        if line.startswith("idle_close_ms"):
            _, _, value = line.partition("=")
            return int(value.strip())
    raise AssertionError("idle_close_ms missing from policy")


def _policy_descriptor_ceiling() -> int:
    for line in POLICY.read_text().splitlines():
        if line.startswith("descriptor_ceiling"):
            _, _, value = line.partition("=")
            return int(value.strip())
    raise AssertionError("descriptor_ceiling missing from policy")


def _effective_limit(base: int, pool_generation: int) -> int:
    return max(0, base - (pool_generation * 2))


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last_err: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError as exc:
            last_err = exc
            time.sleep(0.05)
    raise AssertionError(f"shard {host}:{port} not ready: {last_err}")


def _rebuild() -> None:
    """Compile relayctl from /app/environment and install it to /app/bin/relayctl."""
    proc = subprocess.run(
        [
            "/usr/local/cargo/bin/cargo",
            "build",
            "--release",
            "--locked",
            "--manifest-path",
            "/app/environment/Cargo.toml",
        ],
        text=True,
        capture_output=True,
        timeout=900,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    built = Path("/app/environment/target/release/relayctl")
    BIN.parent.mkdir(parents=True, exist_ok=True)
    BIN.write_bytes(built.read_bytes())


def _ensure_binary() -> None:
    """Ensure /app/bin/relayctl exists, copying or rebuilding from the workspace target."""
    if BIN.exists():
        return
    built = Path("/app/environment/target/release/relayctl")
    if built.exists():
        BIN.parent.mkdir(parents=True, exist_ok=True)
        BIN.write_bytes(built.read_bytes())
        return
    _rebuild()


@pytest.fixture(scope="session", autouse=True)
def _build_once() -> None:
    _ensure_binary()


@pytest.fixture(scope="session")
def mock_shards() -> list[subprocess.Popen]:
    procs: list[subprocess.Popen] = []
    idle_ms = _policy_idle_close_ms()
    for port in (19001, 19002):
        proc = subprocess.Popen(
            [
                "python3",
                str(MOCK),
                "--port",
                str(port),
                "--idle-close-ms",
                str(idle_ms),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(proc)
    for port in (19001, 19002):
        _wait_for_port("127.0.0.1", port)
    yield procs
    for proc in procs:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _paths(tag: str) -> tuple[Path, Path, Path, Path]:
    base = OUT / tag
    base.mkdir(parents=True, exist_ok=True)
    return (
        base / "relay_run_report.json",
        base / "pool_journal.csv",
        base / "relay_trace.ndjson",
        base / "state.db",
    )


def _run(
    workload: Path,
    tag: str,
    *,
    phase: str = "all",
    workload_rounds: int | None = None,
    expect_code: int = 0,
    reuse_state: bool = False,
    seed: int = 0,
    policy: Path | None = None,
    descriptor_ceiling: int | None = None,
    binary: Path | None = None,
) -> subprocess.CompletedProcess:
    """Invoke relayctl run for a workload and assert the expected exit code."""
    rep, journal, trace, state = _paths(tag)
    if not reuse_state:
        for path in (rep, journal, trace, state):
            if path.exists():
                path.unlink()
    if descriptor_ceiling is not None:
        policy_path = OUT / tag / "policy.toml"
        _write_tight_descriptor_policy(policy_path, descriptor_ceiling=descriptor_ceiling)
    else:
        policy_path = policy or POLICY
    relay_bin = binary or BIN
    run_kwargs = {"text": True, "capture_output": True, "timeout": 600}
    if workload_rounds is not None:
        proc = subprocess.run(
            [
                str(relay_bin),
                "run",
                "--policy",
                str(policy_path),
                "--root",
                str(workload),
                "--state",
                str(state),
                "--seed",
                str(seed),
                "--report",
                str(rep),
                "--journal",
                str(journal),
                "--trace",
                str(trace),
                "--phase",
                phase,
                "--shard-profile",
                "all",
                "--workload-rounds",
                str(workload_rounds),
            ],
            **run_kwargs,
        )
    else:
        proc = subprocess.run(
            [
                str(relay_bin),
                "run",
                "--policy",
                str(policy_path),
                "--root",
                str(workload),
                "--state",
                str(state),
                "--seed",
                str(seed),
                "--report",
                str(rep),
                "--journal",
                str(journal),
                "--trace",
                str(trace),
                "--phase",
                phase,
                "--shard-profile",
                "all",
            ],
            **run_kwargs,
        )
    assert proc.returncode == expect_code, proc.stderr + proc.stdout
    return proc


def _gen_workload(count: int, seed: int) -> Path:
    """Generate a seeded workload JSON file via the verifier harness."""
    base = Path(tempfile.mkdtemp(prefix=f"prlg_gen_{seed}_"))
    out = base / "workload.json"
    proc = subprocess.run(
        ["python3", str(GEN), "--count", str(count), "--seed", str(seed), "--out", str(out)],
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return out


def _load_report(tag: str) -> dict:
    rep, _, _, _ = _paths(tag)
    return json.loads(rep.read_text())


def _load_journal(tag: str) -> list[dict]:
    _, journal, _, _ = _paths(tag)
    with journal.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _load_trace(tag: str) -> list[dict]:
    _, _, trace, _ = _paths(tag)
    rows = []
    for line in trace.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _state_path(tag: str) -> Path:
    _, _, _, state = _paths(tag)
    return state


def _sqlite_reclaims(state: Path) -> list[tuple[int, int, str, int]]:
    conn = sqlite3.connect(state)
    try:
        rows = conn.execute(
            "SELECT socket_id, shard, event, round_index FROM reclaim_events ORDER BY round_index, socket_id"
        ).fetchall()
    finally:
        conn.close()
    return [(int(r[0]), int(r[1]), str(r[2]), int(r[3])) for r in rows]


def _sqlite_generation_sealed(state: Path, generation: int) -> bool:
    conn = sqlite3.connect(state)
    try:
        row = conn.execute(
            "SELECT sealed FROM generation_seals WHERE pool_generation = ?",
            (generation,),
        ).fetchone()
    finally:
        conn.close()
    return bool(row and int(row[0]) != 0)


def _sqlite_pool_generation(state: Path) -> int:
    conn = sqlite3.connect(state)
    try:
        row = conn.execute("SELECT pool_generation FROM run_meta WHERE id = 1").fetchone()
    finally:
        conn.close()
    assert row is not None
    return int(row[0])


def _assert_report_schema(rep: dict, state: Path) -> None:
    assert rep["schema_version"] == 1
    assert rep["state_bytes"] == state.stat().st_size


def _write_tight_descriptor_policy(path: Path, *, descriptor_ceiling: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "pool_max_per_shard = 64",
                f"descriptor_ceiling = {descriptor_ceiling}",
                "idle_close_ms = 200",
                "populate_sleep_ms = 50",
                "",
                "[[shards]]",
                "id = 0",
                'host = "127.0.0.1"',
                "port = 19001",
                "",
                "[[shards]]",
                "id = 1",
                'host = "127.0.0.1"',
                "port = 19002",
                "",
            ]
        )
    )


def _write_timing_policy(path: Path, *, idle_close_ms: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "pool_max_per_shard = 64",
                "descriptor_ceiling = 128",
                f"idle_close_ms = {idle_close_ms}",
                "populate_sleep_ms = 50",
                "",
                "[[shards]]",
                "id = 0",
                'host = "127.0.0.1"',
                "port = 19001",
                "",
                "[[shards]]",
                "id = 1",
                'host = "127.0.0.1"',
                "port = 19002",
                "",
            ]
        )
    )


def _start_mock_shards(idle_close_ms: int, close_delay_ms: int) -> list[subprocess.Popen]:
    procs: list[subprocess.Popen] = []
    for port in (19001, 19002):
        proc = subprocess.Popen(
            [
                "python3",
                str(MOCK),
                "--port",
                str(port),
                "--idle-close-ms",
                str(idle_close_ms),
                "--close-delay-ms",
                str(close_delay_ms),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        procs.append(proc)
    for port in (19001, 19002):
        _wait_for_port("127.0.0.1", port)
    return procs


def _stop_mock_shards(procs: list[subprocess.Popen]) -> None:
    for proc in procs:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


class TestPooledRelayLingerGovernor:
    def test_r1_four_round_finish(self, mock_shards) -> None:
        """Bundled four-round workload exits 0 with post-increment pool_generation in exports."""
        tag = "run4"
        _run(SMOKE_4, tag)
        rep = _load_report(tag)
        state = _state_path(tag)
        _assert_report_schema(rep, state)
        assert rep["workload_id"] == "smoke_4"
        assert rep["round_count"] == 4
        assert rep["checkouts_total"] == 4
        assert rep["pool_generation"] == 1
        journal = _load_journal(tag)
        trace = _load_trace(tag)
        assert len(trace) >= 4
        assert all(int(row["pool_generation"]) == 1 for row in journal)
        assert all(int(ev["pool_generation"]) == 1 for ev in trace)
        assert rep["reclaims_total"] == len(journal)

    def test_r2_quiet_fin_rows(self, mock_shards) -> None:
        """Full pipeline exits 0 and records linger_reclaim rows after mock shards close idle sockets."""
        tag = "idle"
        _run(SMOKE_4, tag, phase="all")
        rep = _load_report(tag)
        _assert_report_schema(rep, _state_path(tag))
        assert rep["reclaims_total"] > 0
        journal = _load_journal(tag)
        events = {row["event"] for row in journal}
        assert "linger_reclaim" in events

    def test_r3_fresh_phase_nine(self, mock_shards) -> None:
        """Idle phase on a fresh state database exits 9 because governance is not yet ready."""
        tag = "cold"
        _run(SMOKE_4, tag, phase="idle", expect_code=9)

    def test_r4_wide_matrix_zero(self, mock_shards) -> None:
        """Large generated workload exits 0 without breaching the static descriptor ceiling (exit 5)."""
        tag = "budg"
        ceiling = _policy_descriptor_ceiling()
        manifest = _gen_workload(ceiling + 8, 42)
        _run(manifest, tag, expect_code=0)

    def test_r5_peak_cap(self, mock_shards) -> None:
        """Sixteen-round workload exits 0 with pool_peak at or below the policy descriptor_ceiling."""
        tag = "pk16"
        ceiling = _policy_descriptor_ceiling()
        _run(SMOKE_16, tag)
        rep = _load_report(tag)
        _assert_report_schema(rep, _state_path(tag))
        assert rep["checkouts_total"] == 16
        assert rep["pool_peak"] <= ceiling

    def test_r6_fold_hex(self, mock_shards) -> None:
        """Successful run exits 0 and journal_digest matches SQLite-derived canonical bytes."""
        expect = _import_expect()
        tag = "digest"
        _run(SMOKE_4, tag)
        rep = _load_report(tag)
        state = _state_path(tag)
        _assert_report_schema(rep, state)
        rows = _sqlite_reclaims(state)
        assert rep["journal_digest"] == expect.journal_digest(rows)

    def test_r7_phase_set(self, mock_shards) -> None:
        """Successful run exits 0 and trace includes checkout, pong, and checkin phases for ping rounds."""
        tag = "trace"
        _run(SMOKE_4, tag)
        phases = {ev["phase"] for ev in _load_trace(tag)}
        for phase_name in ("checkout", "pong", "checkin"):
            assert phase_name in phases

    def test_r8_triple_count(self, mock_shards) -> None:
        """Successful run exits 0 with matching reclaims_total across report, journal, and SQLite."""
        tag = "cross"
        _run(SMOKE_16, tag)
        rep = _load_report(tag)
        state = _state_path(tag)
        _assert_report_schema(rep, state)
        journal = _load_journal(tag)
        sqlite_rows = _sqlite_reclaims(state)
        assert rep["reclaims_total"] == len(journal) == len(sqlite_rows)

    def test_r9_bundle_tag(self, mock_shards) -> None:
        """Relay bundle id file remains at the documented constant (no relayctl invocation)."""
        assert BUNDLE_ID.read_text().strip() == "prlg-relay-bundle-v1-8f2c31"

    def test_r10_regen_fold(self, mock_shards) -> None:
        """Repeated runs with the same seed exit 0 and reproduce journal_digest; different seeds diverge."""
        tag = "regen"
        workload = _gen_workload(12, 2026)
        _run(workload, tag, seed=2026)
        first = _load_report(tag)
        first_digest = first["journal_digest"]
        rep_path, journal_path, trace_path, state = _paths(tag)
        for path in (rep_path, journal_path, trace_path, state):
            path.unlink()
        _run(workload, tag, seed=2026)
        second_digest = _load_report(tag)["journal_digest"]
        assert first_digest == second_digest
        other_wl = _gen_workload(20, 9091)
        _run(other_wl, "alt", seed=9091)
        other = _load_report("alt")
        assert other["workload_id"] != first["workload_id"]
        assert other["checkouts_total"] != first["checkouts_total"]

    def test_r11_gen_pin(self, mock_shards) -> None:
        """Generational pinning exits 0, seals the populate generation, and reclaims only on later runs."""
        tag = "pin"
        _run(SMOKE_4, tag)
        rep = _load_report(tag)
        state = _state_path(tag)
        _assert_report_schema(rep, state)
        pin_gen = rep["pool_generation"]
        assert rep["reclaims_total"] == 1
        journal = _load_journal(tag)
        assert len(journal) == 1
        reclaimed = journal[0]
        assert int(reclaimed["pool_generation"]) == pin_gen
        assert reclaimed["event"] == "linger_reclaim"
        checkin_count = sum(
            1
            for ev in _load_trace(tag)
            if ev["phase"] == "checkin" and int(ev["pool_generation"]) == pin_gen
        )
        assert checkin_count == 4
        assert _sqlite_generation_sealed(state, pin_gen)
        _run(SMOKE_4, tag, reuse_state=True)
        rep2 = _load_report(tag)
        assert rep2["pool_generation"] == 2
        assert rep2["reclaims_total"] >= 2
        journal2 = _load_journal(tag)
        reclaimed_gens = {int(row["pool_generation"]) for row in journal2}
        assert pin_gen in reclaimed_gens

    def test_r12_reclaim_order(self, mock_shards) -> None:
        """Successful run exits 0 with reclaim trace and journal rows in canonical sorted order."""
        tag = "order"
        _run(SMOKE_16, tag)
        journal = _load_journal(tag)
        journal_keys = [(int(r["round_index"]), int(r["socket_id"])) for r in journal]
        assert journal_keys == sorted(journal_keys)
        reclaim_sids = [
            int(ev["socket_id"]) for ev in _load_trace(tag) if ev["phase"] == "reclaim"
        ]
        assert reclaim_sids == sorted(reclaim_sids)

    def test_r13_effective_limit(self, mock_shards) -> None:
        """Repeated reuse runs exit 0 until effective limit reaches zero, then the next run exits 7."""
        tag = "lim7"
        ceiling = _policy_descriptor_ceiling()
        workload = _gen_workload(1, 9001)
        _run(workload, tag, seed=9001)
        state = _state_path(tag)
        iterations = 0
        while _effective_limit(ceiling, _sqlite_pool_generation(state)) > 0:
            iterations += 1
            assert iterations < 20, "pool_generation not incrementing"
            _run(workload, tag, reuse_state=True, seed=9001)
            state = _state_path(tag)
        gen = _sqlite_pool_generation(state)
        assert _effective_limit(ceiling, gen) == 0
        _run(workload, tag, reuse_state=True, seed=9001, expect_code=7)

    def test_concurrent_sweep_timing(self) -> None:
        """Wide idle inventory linger sweep exits 0 concurrently and exports sorted reclaim rows."""
        idle_ms = 200
        close_delay_ms = 200
        procs = _start_mock_shards(idle_ms, close_delay_ms)
        try:
            tag = "wide"
            _paths(tag)
            policy_path = OUT / tag / "policy.toml"
            _write_timing_policy(policy_path, idle_close_ms=idle_ms)
            workload = _gen_workload(64, 88064)
            start = time.monotonic()
            _run(workload, tag, seed=88064, policy=policy_path)
            elapsed = time.monotonic() - start
            assert elapsed < 5.0, f"sweep took {elapsed:.1f}s, likely sequential"
            rep = _load_report(tag)
            _assert_report_schema(rep, _state_path(tag))
            assert rep["checkouts_total"] == 64
            assert rep["reclaims_total"] > 0
            journal = _load_journal(tag)
            journal_keys = [(int(r["round_index"]), int(r["socket_id"])) for r in journal]
            assert journal_keys == sorted(journal_keys)
            assert len(journal) == rep["reclaims_total"]
            reclaim_sids = [
                int(ev["socket_id"]) for ev in _load_trace(tag) if ev["phase"] == "reclaim"
            ]
            assert reclaim_sids == sorted(reclaim_sids)
            assert len(reclaim_sids) == rep["reclaims_total"]
        finally:
            _stop_mock_shards(procs)

    def test_r14_descriptor_ceiling_exit_five(self, mock_shards) -> None:
        """Populate beyond a tight descriptor ceiling exits 5; fixed coordinator reuses and exits 0."""
        tag = "xc5"
        workload = _gen_workload(4, 5005)
        nop_bin = APP / "bin" / "relayctl-nop"
        assert nop_bin.exists(), "relayctl-nop baseline binary missing from image"
        _run(
            workload,
            tag + "_nop",
            seed=5005,
            descriptor_ceiling=2,
            phase="populate",
            expect_code=5,
            binary=nop_bin,
        )
        _run(workload, tag, seed=5005, descriptor_ceiling=2, phase="populate", expect_code=0)

    def test_r15_export_mismatch_exit_six(self, mock_shards) -> None:
        """Verify-only on an unpopulated state database exits 6 for cross-surface export mismatch."""
        tag = "xc6"
        _run(SMOKE_16, tag, phase="verify", expect_code=6)
