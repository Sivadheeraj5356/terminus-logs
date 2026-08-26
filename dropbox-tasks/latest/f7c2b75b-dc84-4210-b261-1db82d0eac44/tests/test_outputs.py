import json
import os
import shutil
import subprocess
import textwrap
from copy import deepcopy
from pathlib import Path

import pytest

APP = Path("/app")
OUT = APP / "output" / "wp_report.json"
DATA = APP / "data"
JOURNAL = DATA / "journal.json"
VIVO = "/usr/local/bin/vivostep"
ENV_ROOT = APP / "environment"

PHASE_REPLAY = "neighbor_replay"
PHASE_ATTACH = "endpoint_attach"


def _reset_data() -> None:
    if DATA.exists():
        shutil.rmtree(DATA)
    if OUT.exists():
        OUT.unlink()
    DATA.mkdir(parents=True, exist_ok=True)


def _vivo(*args: str, seed: int | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if seed is not None:
        env["VIVO_SCHED_SEED"] = str(seed)
    return subprocess.run(
        [VIVO, *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd="/app",
    )


def _emit_report() -> dict:
    if OUT.exists():
        OUT.unlink()
    _vivo("emit", "-o", str(OUT))
    return json.loads(OUT.read_text())


def _dual_surfaces() -> list[dict]:
    proc = _vivo("examine", "--surface", "dual")
    payload = json.loads(proc.stdout)
    return payload["surfaces"]


def _gate_tick(cycle: dict, phase: str) -> int:
    for gate in cycle["gate_timings"]:
        if gate["phase"] == phase:
            return gate["completed_at_tick"]
    raise AssertionError(f"missing gate {phase}")


def _canonicalize_for_digest(cycles: list[dict], surfaces: list[dict]) -> tuple[list[dict], list[dict]]:
    cycles_copy = deepcopy(cycles)
    surfaces_copy = deepcopy(surfaces)
    cycles_copy.sort(key=lambda c: c["cycle_id"])
    for cycle in cycles_copy:
        cycle["gate_timings"].sort(key=lambda g: g["phase"])
    surfaces_copy.sort(key=lambda s: s["name"])
    return cycles_copy, surfaces_copy


def _sha256_hex(data: bytes) -> str:
    proc = subprocess.run(
        ["sha256sum"],
        input=data,
        check=True,
        capture_output=True,
    )
    return proc.stdout.decode().split()[0]


def _run_go_package_test(package_rel: str, filename: str, source: str) -> None:
    test_path = ENV_ROOT / package_rel / filename
    test_path.write_text(textwrap.dedent(source).lstrip())
    try:
        subprocess.run(
            ["go", "test", f"./{package_rel}"],
            cwd=ENV_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        test_path.unlink(missing_ok=True)


def _expected_digest(cycles: list[dict], surfaces: list[dict]) -> str:
    cycles_copy, surfaces_copy = _canonicalize_for_digest(cycles, surfaces)
    payload = {"cycles": cycles_copy, "surfaces": surfaces_copy}
    encoded = json.dumps(payload, separators=(",", ":"))
    return _sha256_hex(encoded.encode())


def _assert_cycle_invariants(cycle: dict) -> None:
    for pair in cycle["epoch_pairs"]:
        assert pair["forward_epoch"] == pair["journal_head_generation"]
    if cycle["cycle_id"] not in {"wp-maint", "cold-boot"}:
        return
    assert cycle["gate_timings"]
    assert cycle["epoch_pairs"]
    replay = _gate_tick(cycle, PHASE_REPLAY)
    attach = _gate_tick(cycle, PHASE_ATTACH)
    assert replay > 0
    assert attach > replay


def _assert_report_invariants(report: dict) -> None:
    assert report["cycles"]
    assert report["surfaces"]
    assert report["record_digest"] == _expected_digest(report["cycles"], report["surfaces"])
    assert any(cycle["cycle_id"] == "wp-maint" for cycle in report["cycles"])
    for cycle in report["cycles"]:
        _assert_cycle_invariants(cycle)
    surfaces = {s["name"]: s["epoch"] for s in report["surfaces"]}
    assert surfaces["forward"] == surfaces["journal"]


def _journal_payload() -> dict:
    return json.loads(JOURNAL.read_text())


def _run_cold_maint(seed: int = 1) -> dict:
    _reset_data()
    _vivo("run", "--scenario", "wp-maint", "--cold", seed=seed)
    _vivo("run", "--scenario", "wp-maint", seed=seed)
    report = _emit_report()
    _assert_report_invariants(report)
    return report


@pytest.fixture(scope="session", autouse=True)
def _session_build() -> None:
    subprocess.run(["make", "-C", "/app/environment", "install"], check=True)


def test_alpha_startup() -> None:
    """Cold boot converges with aligned epochs and ordered gates."""
    report = _run_cold_maint()
    cycle_ids = {cycle["cycle_id"] for cycle in report["cycles"]}
    assert "cold-boot" in cycle_ids
    assert "wp-maint" in cycle_ids
    assert len(report["cycles"]) >= 2


def test_beta_drift() -> None:
    """Maintenance return keeps dual authority epochs aligned."""
    _reset_data()
    _vivo("run", "--scenario", "wp-maint", "--cold")
    _vivo("run", "--scenario", "wp-maint")
    surfaces = {s["name"]: s["epoch"] for s in _dual_surfaces()}
    assert surfaces["forward"] == surfaces["journal"]
    report = _emit_report()
    _assert_report_invariants(report)


def test_gamma_boundary() -> None:
    """Process reopen after first cycle still yields matching dual epochs."""
    _reset_data()
    _vivo("run", "--scenario", "wp-maint", "--cold")
    _vivo("run", "--scenario", "wp-maint")
    first = {s["name"]: s["epoch"] for s in _dual_surfaces()}
    assert first["forward"] == first["journal"]
    _vivo("reopen")
    _vivo("run", "--scenario", "wp-maint")
    second = {s["name"]: s["epoch"] for s in _dual_surfaces()}
    assert second["forward"] == second["journal"]
    report = _emit_report()
    _assert_report_invariants(report)
    for cycle in report["cycles"]:
        if cycle["cycle_id"] == "wp-maint":
            _assert_cycle_invariants(cycle)


def test_delta_agreement() -> None:
    """Three schedule seeds keep dual examine epochs aligned."""
    for seed in (1, 2, 3):
        _reset_data()
        _vivo("run", "--scenario", "wp-maint", "--cold", seed=seed)
        _vivo("run", "--scenario", "wp-maint", seed=seed)
        surfaces = {s["name"]: s["epoch"] for s in _dual_surfaces()}
        assert surfaces["forward"] == surfaces["journal"]
        report = _emit_report()
        _assert_report_invariants(report)


def test_epsilon_order() -> None:
    """Gate timings always place neighbor replay before endpoint attach."""
    report = _run_cold_maint(seed=2)
    for cycle in report["cycles"]:
        if cycle["cycle_id"] == "wp-maint":
            replay = _gate_tick(cycle, PHASE_REPLAY)
            attach = _gate_tick(cycle, PHASE_ATTACH)
            assert replay < attach


def test_zeta_epochs() -> None:
    """Every epoch pair aligns forward and journal head generations."""
    report = _run_cold_maint(seed=3)
    for cycle in report["cycles"]:
        for pair in cycle["epoch_pairs"]:
            assert pair["forward_epoch"] == pair["journal_head_generation"]


def test_eta_repeat() -> None:
    """Consecutive maintenance returns append history and advance the final epoch."""
    _reset_data()
    _vivo("run", "--scenario", "wp-maint", "--cold")
    _vivo("run", "--scenario", "wp-maint")
    first = _emit_report()
    _assert_report_invariants(first)
    _vivo("run", "--scenario", "wp-maint")
    second = _emit_report()
    _assert_report_invariants(second)
    assert len(second["cycles"]) == len(first["cycles"]) + 1
    f_epochs = [p["forward_epoch"] for c in first["cycles"] for p in c["epoch_pairs"]]
    s_epochs = [p["forward_epoch"] for c in second["cycles"] for p in c["epoch_pairs"]]
    assert f_epochs[-1] < s_epochs[-1]
    assert first["record_digest"] != second["record_digest"]


def test_theta_trap() -> None:
    """Epoch and gate invariants require coordinated queue and journal fixes."""
    report = _run_cold_maint()
    for cycle in report["cycles"]:
        if cycle["cycle_id"] == "wp-maint":
            _assert_cycle_invariants(cycle)


def test_iota_digest() -> None:
    """Record digest matches independently recomputed canonical SHA-256."""
    report = _run_cold_maint(seed=4)
    assert report["record_digest"] == _expected_digest(report["cycles"], report["surfaces"])


def test_kappa_reopen_journal() -> None:
    """Reopen drops stale journal generations below the active forwarding epoch."""
    _reset_data()
    _vivo("run", "--scenario", "wp-maint", "--cold")
    _vivo("run", "--scenario", "wp-maint")
    forward_epoch = {s["name"]: s["epoch"] for s in _dual_surfaces()}["forward"]
    _vivo("reopen")
    _vivo("run", "--scenario", "wp-maint")
    journal = _journal_payload()
    for entry in journal["entries"]:
        assert entry["generation"] >= forward_epoch
    report = _emit_report()
    _assert_report_invariants(report)


def test_lambda_reopen_repeat() -> None:
    """After reopen, repeated maintenance returns continue epoch progression."""
    _reset_data()
    _vivo("run", "--scenario", "wp-maint", "--cold")
    _vivo("run", "--scenario", "wp-maint")
    _vivo("reopen")
    _vivo("run", "--scenario", "wp-maint")
    first = _emit_report()
    _vivo("run", "--scenario", "wp-maint")
    second = _emit_report()
    _assert_report_invariants(first)
    _assert_report_invariants(second)
    assert len(second["cycles"]) > len(first["cycles"])
    first_epochs = [p["forward_epoch"] for c in first["cycles"] for p in c["epoch_pairs"]]
    second_epochs = [p["forward_epoch"] for c in second["cycles"] for p in c["epoch_pairs"]]
    assert first_epochs[-1] < second_epochs[-1]


def test_mu_varied_seeds() -> None:
    """Different schedule seeds produce distinct digests with the same invariants."""
    digests: set[str] = set()
    for seed in (1, 2, 3, 4, 5, 6, 7):
        _reset_data()
        _vivo("run", "--scenario", "wp-maint", "--cold", seed=seed)
        _vivo("run", "--scenario", "wp-maint", seed=seed)
        report = _emit_report()
        _assert_report_invariants(report)
        digests.add(report["record_digest"])
    assert len(digests) >= 3


def test_nu_phase_merge_waits_for_both_signals() -> None:
    """Phase merge does not complete until both role and announcement signals close."""
    _run_go_package_test(
        "orchestrate",
        "ext_test.go",
        r'''
        package orchestrate_test

        import (
            "context"
            "testing"
            "time"

            "vivostep.local/sim/orchestrate"
        )

        func TestPhaseMergeWaitsForAnnouncementAfterRole(t *testing.T) {
            roleDone := make(chan struct{})
            announceDone := make(chan struct{})
            done := make(chan error, 1)

            close(roleDone)
            go func() {
                _, err := orchestrate.PhaseMergeExported(context.Background(), roleDone, announceDone)
                done <- err
            }()

            select {
            case err := <-done:
                t.Fatalf("merge completed before announcement signal: %v", err)
            case <-time.After(50 * time.Millisecond):
            }

            close(announceDone)
            select {
            case err := <-done:
                if err != nil {
                    t.Fatalf("merge returned error after both signals: %v", err)
                }
            case <-time.After(time.Second):
                t.Fatal("merge did not complete after both signals")
            }
        }

        func TestPhaseMergeWaitsForRoleAfterAnnouncement(t *testing.T) {
            roleDone := make(chan struct{})
            announceDone := make(chan struct{})
            done := make(chan error, 1)

            close(announceDone)
            go func() {
                _, err := orchestrate.PhaseMergeExported(context.Background(), roleDone, announceDone)
                done <- err
            }()

            select {
            case err := <-done:
                t.Fatalf("merge completed before role signal: %v", err)
            case <-time.After(50 * time.Millisecond):
            }

            close(roleDone)
            select {
            case err := <-done:
                if err != nil {
                    t.Fatalf("merge returned error after both signals: %v", err)
                }
            case <-time.After(time.Second):
                t.Fatal("merge did not complete after both signals")
            }
        }
        ''',
    )


def test_xi_gate_release_requires_replay_before_attach() -> None:
    """Endpoint attach remains pending until replay has completed for the epoch."""
    _run_go_package_test(
        "role",
        "ext_test.go",
        r'''
        package role_test

        import (
            "testing"

            "vivostep.local/sim/role"
            "vivostep.local/sim/util"
        )

        func TestGateReleaseRequiresReplayBeforeAttach(t *testing.T) {
            clock := util.NewTickClock()
            q := role.NewWorkQueue(clock)
            q.Enqueue("neighbor_replay", 7)
            q.Enqueue("endpoint_attach", 7)

            clock.Set(10)
            if err := role.GateReleaseExported(q, 7); err != nil {
                t.Fatalf("release before replay returned error: %v", err)
            }
            if q.ItemDone("endpoint_attach", 7) {
                t.Fatal("endpoint attach completed before replay")
            }
            if q.ItemDone("neighbor_replay", 7) {
                t.Fatal("gate release should not mark replay complete")
            }

            q.MarkDone("neighbor_replay", 7)
            clock.Set(11)
            if err := role.GateReleaseExported(q, 7); err != nil {
                t.Fatalf("release after replay returned error: %v", err)
            }
            if !q.ItemDone("endpoint_attach", 7) {
                t.Fatal("endpoint attach did not complete after replay")
            }
            if got := q.GateTick("endpoint_attach"); got != 11 {
                t.Fatalf("endpoint attach tick = %d, want 11", got)
            }
        }

        func TestGateReleaseDoesNotInventMissingAttach(t *testing.T) {
            clock := util.NewTickClock()
            q := role.NewWorkQueue(clock)
            q.Enqueue("neighbor_replay", 9)
            q.MarkDone("neighbor_replay", 9)

            if err := role.GateReleaseExported(q, 9); err != nil {
                t.Fatalf("release without attach returned error: %v", err)
            }
            if q.ItemDone("endpoint_attach", 9) {
                t.Fatal("missing endpoint attach was treated as complete")
            }
        }
        ''',
    )


def test_omicron_publish_hold_respects_barrier_and_frames() -> None:
    """Publish hold waits for the barrier and rejects missing or invalid frames."""
    _run_go_package_test(
        "l2pub",
        "ext_test.go",
        r'''
        package l2pub_test

        import (
            "strings"
            "testing"
            "time"

            "vivostep.local/sim/l2pub"
            "vivostep.local/sim/util"
        )

        func TestHoldUntilWaitsForBarrierBeforeFlush(t *testing.T) {
            clock := util.NewTickClock()
            d := l2pub.NewDispatcher(clock)
            d.QueueFrame(4, "frame-4")

            barrier := make(chan struct{})
            done := make(chan error, 1)
            go func() {
                done <- l2pub.HoldUntilExported(d, 4, barrier)
            }()

            select {
            case err := <-done:
                t.Fatalf("publish hold completed before barrier release: %v", err)
            case <-time.After(50 * time.Millisecond):
            }
            if got := len(d.FramesForEpoch(4)); got != 1 {
                t.Fatalf("pending frames changed before barrier release: got %d", got)
            }

            clock.Set(12)
            close(barrier)
            select {
            case err := <-done:
                if err != nil {
                    t.Fatalf("publish hold returned error after barrier release: %v", err)
                }
            case <-time.After(time.Second):
                t.Fatal("publish hold did not complete after barrier release")
            }
            if got := len(d.FramesForEpoch(4)); got != 0 {
                t.Fatalf("frames were not flushed after barrier release: got %d", got)
            }
            if got := d.ReplayTick(); got != 12 {
                t.Fatalf("replay tick = %d, want 12", got)
            }
        }

        func TestHoldUntilRejectsMissingFrame(t *testing.T) {
            d := l2pub.NewDispatcher(util.NewTickClock())
            barrier := make(chan struct{})
            close(barrier)

            if err := l2pub.HoldUntilExported(d, 5, barrier); err == nil {
                t.Fatal("missing publish frame was accepted")
            }
        }

        func TestHoldUntilRejectsInvalidFrames(t *testing.T) {
            cases := []struct {
                name string
                body string
            }{
                {name: "empty", body: ""},
                {name: "oversize", body: strings.Repeat("x", 1501)},
            }
            for _, tc := range cases {
                t.Run(tc.name, func(t *testing.T) {
                    d := l2pub.NewDispatcher(util.NewTickClock())
                    d.QueueFrame(6, tc.body)
                    barrier := make(chan struct{})
                    close(barrier)

                    if err := l2pub.HoldUntilExported(d, 6, barrier); err == nil {
                        t.Fatalf("%s publish frame was accepted", tc.name)
                    }
                })
            }
        }
        ''',
    )
