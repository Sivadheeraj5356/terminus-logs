"""Behavioral verifier for passenger-rebooking-engine."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from rebooking_reference import build_outputs, export_outputs

APP = Path("/app")
BINARY = APP / "bin" / "passenger-rebooking-engine"
DATA_DIR = APP / "data"
BASELINE_BACKUP = Path("/tmp/rebooking-baseline-backup")
CANDIDATE_USER = "rebooker"
TRUSTED_RUNUSER = Path("/opt/verifier-scripts/run-as-rebooker")

HIDDEN_COMPETING = Path("/opt/verifier-fixtures/rebook-hidden-competing-seats")
HIDDEN_CONNECTION = Path("/opt/verifier-fixtures/rebook-hidden-connection")
HIDDEN_ALLIANCE = Path("/opt/verifier-fixtures/rebook-hidden-alliance")
HIDDEN_MANIFEST_ORDER = Path("/opt/verifier-fixtures/rebook-hidden-manifest-order")
HIDDEN_TIEBREAK = Path("/opt/verifier-fixtures/rebook-hidden-tiebreak")
HIDDEN_FARE_RULES = Path("/opt/verifier-fixtures/rebook-hidden-fare-rules")
HIDDEN_PARTIAL_LEGS = Path("/opt/verifier-fixtures/rebook-hidden-partial-legs")
HIDDEN_CONN_CANCEL_NEXT = Path("/opt/verifier-fixtures/rebook-hidden-conn-cancel-next")
HIDDEN_PARTNER_OK = Path("/opt/verifier-fixtures/rebook-hidden-partner-ok")
HIDDEN_UPGRADE_OK = Path("/opt/verifier-fixtures/rebook-hidden-upgrade-ok")
HIDDEN_UPGRADE_OFF = Path("/opt/verifier-fixtures/rebook-hidden-upgrade-off")
HIDDEN_FARE_CLASS_TIEBREAK = Path("/opt/verifier-fixtures/rebook-hidden-fare-class-tiebreak")


def _trusted_runuser() -> Path:
    assert TRUSTED_RUNUSER.is_file(), "trusted run-as-rebooker wrapper missing"
    mode = TRUSTED_RUNUSER.stat().st_mode & 0o777
    assert mode & 0o222 == 0, f"run-as-rebooker must not be writable (mode={oct(mode)})"
    return TRUSTED_RUNUSER


def _chown_candidate(*paths: Path | str) -> None:
    for path in paths:
        subprocess.run(
            ["chown", "-R", f"{CANDIDATE_USER}:{CANDIDATE_USER}", str(path)],
            check=False,
        )


def _make_traversable(path: Path) -> None:
    """Allow the candidate user to walk into pytest/root-owned ancestors."""
    current = path.resolve()
    while True:
        try:
            mode = current.stat().st_mode
            os.chmod(current, mode | 0o711)
        except OSError:
            pass
        if current in (Path("/"), Path("/tmp")):
            break
        if current.parent == current:
            break
        current = current.parent


def _ensure_app_writable_dirs() -> None:
    """Keep /app/state and /app/output present and owned by the candidate user."""
    for path in (APP / "state", APP / "output", APP / "bin"):
        path.mkdir(parents=True, exist_ok=True)
    # Candidate must read datasets and execute the rebuilt binary.
    subprocess.run(["chmod", "-R", "a+rX", str(APP / "data")], check=False)
    subprocess.run(["chmod", "a+rx", str(APP / "bin")], check=False)
    if BINARY.exists():
        subprocess.run(["chmod", "a+x", str(BINARY)], check=False)
    _chown_candidate(APP / "state", APP / "output", APP / "bin")


def _clear_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _rebuild() -> None:
    rebuild = Path("/opt/verifier-scripts/rebuild-rebooking")
    assert rebuild.is_file(), "trusted rebuild helper missing"
    mode = rebuild.stat().st_mode & 0o777
    assert mode & 0o222 == 0, f"rebuild helper must not be writable (mode={oct(mode)})"
    proc = subprocess.run([str(rebuild)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    _ensure_app_writable_dirs()


def _run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    runuser = _trusted_runuser()
    cmd = [str(runuser), "-u", CANDIDATE_USER, "--", str(BINARY), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=run_env)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _prepare_tmp_workspace(tmp: Path) -> None:
    _make_traversable(tmp)
    _chown_candidate(tmp)
    # Keep contents group/world-traversable under candidate ownership.
    subprocess.run(["chmod", "-R", "u+rwX,go+rX", str(tmp)], check=False)


def _build_with_data(data_src: Path, tmp: Path) -> subprocess.CompletedProcess[str]:
    data = tmp / "data"
    state = tmp / "state"
    out = tmp / "output"
    for p in (data, state, out):
        if p.exists():
            shutil.rmtree(p)
    shutil.copytree(data_src, data)
    state.mkdir()
    out.mkdir()
    _prepare_tmp_workspace(tmp)
    env = {
        "TB3_DATA_DIR": str(data),
        "TB3_STATE_DIR": str(state),
        "TB3_OUTPUT_DIR": str(out),
    }
    return _run_cli("build", env=env)


def _restore_app_outputs() -> None:
    _clear_dir(APP / "state")
    _clear_dir(APP / "output")
    _ensure_app_writable_dirs()
    proc = _run_cli("build")
    assert proc.returncode == 0, proc.stderr


@pytest.fixture(scope="module", autouse=True)
def backup_baseline():
    if not BASELINE_BACKUP.exists():
        shutil.copytree(DATA_DIR, BASELINE_BACKUP)
    _rebuild()
    _restore_app_outputs()
    yield
    if BASELINE_BACKUP.exists():
        shutil.rmtree(DATA_DIR, ignore_errors=True)
        shutil.copytree(BASELINE_BACKUP, DATA_DIR)
        _ensure_app_writable_dirs()


@pytest.fixture(autouse=True)
def isolate_app_outputs():
    """Keep /app/state and /app/output coherent across tests regardless of collection order."""
    yield
    if not (APP / "state" / "rebooking-snapshot.json").is_file():
        _restore_app_outputs()


class TestCoreCorrectness:
    """Core CLI behavior against bundled fixtures."""

    def test_version_subcommand(self) -> None:
        """Version must print the documented engine identifier."""
        proc = _run_cli("version")
        assert proc.returncode == 0
        assert "passenger-rebooking-engine/1.0.0" in proc.stdout

    def test_no_args_runs_build(self) -> None:
        """Invoking the binary with no subcommand must run the same pipeline as build."""
        state = APP / "state"
        out = APP / "output"
        _clear_dir(state)
        _clear_dir(out)
        _ensure_app_writable_dirs()
        proc = _run_cli()
        assert proc.returncode == 0, proc.stderr
        assert (state / "rebooking-snapshot.json").is_file()
        assert (state / "rebooking-ledger.json").is_file()
        assert (out / "rebooking-plan.json").is_file()
        assert (out / "passenger-summary.json").is_file()
        ref_snap, _, ref_plan, ref_summary = build_outputs(DATA_DIR)
        assert _load(state / "rebooking-snapshot.json") == ref_snap
        assert _load(out / "rebooking-plan.json") == ref_plan
        assert _load(out / "passenger-summary.json") == ref_summary
        plan = _load(out / "rebooking-plan.json")
        summary = _load(out / "passenger-summary.json")
        assert "ledger_stage_sequence" in plan
        assert "ledger_stage_sequence" not in summary

    def test_build_writes_snapshot_and_exports(self) -> None:
        """Build must stage snapshot and ledger then export plan and summary."""
        state = APP / "state"
        out = APP / "output"
        _clear_dir(state)
        _clear_dir(out)
        _ensure_app_writable_dirs()
        proc = _run_cli("build")
        assert proc.returncode == 0, proc.stderr
        assert (state / "rebooking-snapshot.json").is_file()
        assert (state / "rebooking-ledger.json").is_file()
        assert (out / "rebooking-plan.json").is_file()
        assert (out / "passenger-summary.json").is_file()

    def test_snapshot_matches_reference(self) -> None:
        """Staged snapshot must match independent reference reconciliation."""
        ref_snap, ref_led, _, _ = build_outputs(DATA_DIR)
        snap = _load(APP / "state" / "rebooking-snapshot.json")
        led = _load(APP / "state" / "rebooking-ledger.json")
        assert snap == ref_snap
        assert led["input_digest"] == ref_led["input_digest"]
        assert led["priority_pick_mode"] == ref_led["priority_pick_mode"]
        assert led["remaining_seat_map"] == ref_led["remaining_seat_map"]

    def test_input_digest_matches_reference(self) -> None:
        """Ledger input_digest must hash the full input bundle including alliances."""
        _, ref_led, _, _ = build_outputs(DATA_DIR)
        led = _load(APP / "state" / "rebooking-ledger.json")
        assert led["input_digest"] == ref_led["input_digest"]
        assert led["stage_sequence"] == ref_led["stage_sequence"]

    def test_export_matches_reference(self) -> None:
        """Export outputs must match reference plan and summary."""
        snap = _load(APP / "state" / "rebooking-snapshot.json")
        led = _load(APP / "state" / "rebooking-ledger.json")
        ref_plan, ref_summary = export_outputs(snap, led)
        plan = _load(APP / "output" / "rebooking-plan.json")
        summary = _load(APP / "output" / "passenger-summary.json")
        assert plan == ref_plan
        assert summary == ref_summary
        assert "ledger_stage_sequence" in plan
        assert "ledger_stage_sequence" not in summary

    def test_collapsed_cancellation_count(self) -> None:
        """Snapshot must collapse duplicate cancellation revisions."""
        snap = _load(APP / "state" / "rebooking-snapshot.json")
        assert snap["collapsed_cancellation_count"] == 2
        assert snap["cancelled_flights"] == ["UA101", "UA310"]

    def test_priority_rebooks_gold_before_silver(self) -> None:
        """Higher priority passenger receives the scarce J seat first."""
        snap = _load(APP / "state" / "rebooking-snapshot.json")
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-001"]["status"] == "rebooked"
        assert by_id["PAX-001"]["rebooked_legs"][0]["replacement_flight"] == "UA201"
        assert by_id["PAX-002"]["status"] == "rebooked"
        assert by_id["PAX-002"]["rebooked_legs"][0]["replacement_flight"] == "UA202"

    def test_unaffected_passenger_status(self) -> None:
        """Passengers on non-cancelled flights remain unaffected."""
        snap = _load(APP / "state" / "rebooking-snapshot.json")
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-003"]["status"] == "unaffected"
        assert by_id["PAX-003"]["rebooked_legs"] == []

    def test_bundled_multileg_connection_protection(self) -> None:
        """Bundled multi-leg passenger must reject tight replacements against the next-leg schedule."""
        snap = _load(APP / "state" / "rebooking-snapshot.json")
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-004"]["status"] == "rebooked"
        assert by_id["PAX-004"]["rebooked_legs"][0]["replacement_flight"] == "UA312"

    def test_idempotent_build(self) -> None:
        """Repeated build on unchanged inputs yields byte-identical snapshot, ledger, and export files."""
        first_snap = (APP / "state" / "rebooking-snapshot.json").read_bytes()
        first_led = (APP / "state" / "rebooking-ledger.json").read_bytes()
        first_plan = (APP / "output" / "rebooking-plan.json").read_bytes()
        first_summary = (APP / "output" / "passenger-summary.json").read_bytes()
        proc = _run_cli("build")
        assert proc.returncode == 0
        assert (APP / "state" / "rebooking-snapshot.json").read_bytes() == first_snap
        assert (APP / "state" / "rebooking-ledger.json").read_bytes() == first_led
        assert (APP / "output" / "rebooking-plan.json").read_bytes() == first_plan
        assert (APP / "output" / "passenger-summary.json").read_bytes() == first_summary

    def test_stage_sequence_increments_on_input_change(self, tmp_path: Path) -> None:
        """Ledger stage_sequence increments when the input digest changes after a successful stage."""
        data = tmp_path / "data"
        state = tmp_path / "state"
        out = tmp_path / "output"
        shutil.copytree(DATA_DIR, data)
        state.mkdir()
        out.mkdir()
        _prepare_tmp_workspace(tmp_path)
        env = {
            "TB3_DATA_DIR": str(data),
            "TB3_STATE_DIR": str(state),
            "TB3_OUTPUT_DIR": str(out),
        }
        proc = _run_cli("stage", env=env)
        assert proc.returncode == 0, proc.stderr
        led1 = _load(state / "rebooking-ledger.json")
        assert led1["stage_sequence"] == 1
        passengers = _load(data / "passengers.json")
        passengers["passengers"][0]["name"] = "Changed Name"
        (data / "passengers.json").write_text(json.dumps(passengers, indent=2) + "\n", encoding="utf-8")
        _prepare_tmp_workspace(tmp_path)
        proc2 = _run_cli("stage", env=env)
        assert proc2.returncode == 0, proc2.stderr
        led2 = _load(state / "rebooking-ledger.json")
        assert led2["stage_sequence"] == 2
        assert led2["input_digest"] != led1["input_digest"]

    def test_export_without_stage_fails(self, tmp_path: Path) -> None:
        """Export when snapshot is missing must exit with code 2 without mutating shared /app/state."""
        state = tmp_path / "state"
        out = tmp_path / "output"
        state.mkdir()
        out.mkdir()
        _prepare_tmp_workspace(tmp_path)
        proc = _run_cli(
            "export",
            env={
                "TB3_STATE_DIR": str(state),
                "TB3_OUTPUT_DIR": str(out),
            },
        )
        assert proc.returncode == 2


class TestAdversarialTraps:
    """Hidden fixtures exercising competing seats, connections, and alliance rules."""

    def test_hidden_competing_seats_priority(self, tmp_path: Path) -> None:
        """When only one J seat exists, lower priority passenger is standby."""
        proc = _build_with_data(HIDDEN_COMPETING, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_COMPETING)
        assert snap == ref_snap
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-A"]["status"] == "rebooked"
        assert by_id["PAX-B"]["status"] == "standby"

    def test_hidden_manifest_passenger_order(self, tmp_path: Path) -> None:
        """manifest_passenger_order must preserve passengers.json array order over score."""
        proc = _build_with_data(HIDDEN_MANIFEST_ORDER, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_MANIFEST_ORDER)
        assert snap == ref_snap
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-B"]["status"] == "rebooked"
        assert by_id["PAX-A"]["status"] == "standby"

    def test_hidden_connection_protection(self, tmp_path: Path) -> None:
        """Replacement must satisfy connection window against the next leg."""
        proc = _build_with_data(HIDDEN_CONNECTION, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_CONNECTION)
        assert snap == ref_snap
        leg = snap["passenger_records"][0]["rebooked_legs"][0]
        assert leg["replacement_flight"] == "UA502"

    def test_hidden_alliance_rejects_non_partner(self, tmp_path: Path) -> None:
        """Non-alliance carrier in pool is skipped for eligible UA replacement."""
        proc = _build_with_data(HIDDEN_ALLIANCE, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_ALLIANCE)
        assert snap == ref_snap
        leg = snap["passenger_records"][0]["rebooked_legs"][0]
        assert leg["replacement_flight"] == "UA901"
        assert leg["carrier"] == "UA"

    def test_hidden_equal_revision_event_id_tiebreak(self, tmp_path: Path) -> None:
        """Equal-revision cancellations keep the lexicographically smallest event_id pool."""
        proc = _build_with_data(HIDDEN_TIEBREAK, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_TIEBREAK)
        assert snap == ref_snap
        leg = snap["passenger_records"][0]["rebooked_legs"][0]
        assert leg["replacement_flight"] == "UA701"

    def test_hidden_fare_downgrade_and_upgrade_cap(self, tmp_path: Path) -> None:
        """Fare downgrades are rejected and upgrades beyond max steps are rejected."""
        proc = _build_with_data(HIDDEN_FARE_RULES, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_FARE_RULES)
        assert snap == ref_snap
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-DOWN"]["status"] == "standby"
        assert by_id["PAX-GAP"]["status"] == "standby"

    def test_hidden_partner_carrier_allowed(self, tmp_path: Path) -> None:
        """Eligible alliance partner carrier must be accepted when same-carrier inventory is absent."""
        proc = _build_with_data(HIDDEN_PARTNER_OK, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_PARTNER_OK)
        assert snap == ref_snap
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-PART"]["status"] == "rebooked"
        leg = by_id["PAX-PART"]["rebooked_legs"][0]
        assert leg["replacement_flight"] == "LH950"
        assert leg["carrier"] == "LH"

    def test_hidden_one_step_upgrade_allowed(self, tmp_path: Path) -> None:
        """A one-step fare upgrade must succeed when upgrade_on_cancel is true."""
        proc = _build_with_data(HIDDEN_UPGRADE_OK, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_UPGRADE_OK)
        assert snap == ref_snap
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-UP"]["status"] == "rebooked"
        assert by_id["PAX-UP"]["rebooked_legs"][0]["fare_class"] == "W"

    def test_hidden_upgrade_on_cancel_false(self, tmp_path: Path) -> None:
        """When upgrade_on_cancel is false, an otherwise eligible upgrade must not rebook."""
        proc = _build_with_data(HIDDEN_UPGRADE_OFF, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_UPGRADE_OFF)
        assert snap == ref_snap
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-UP"]["status"] == "standby"
        assert by_id["PAX-UP"]["rebooked_legs"] == []

    def test_hidden_fare_class_lex_tiebreak(self, tmp_path: Path) -> None:
        """Same flight_id with multiple eligible fare classes must pick ascending fare_class."""
        proc = _build_with_data(HIDDEN_FARE_CLASS_TIEBREAK, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_FARE_CLASS_TIEBREAK)
        assert snap == ref_snap
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-FC"]["status"] == "rebooked"
        assert by_id["PAX-FC"]["rebooked_legs"][0]["fare_class"] == "W"
        assert by_id["PAX-FC"]["rebooked_legs"][0]["replacement_flight"] == "UA951"

    def test_hidden_partial_multileg_standby(self, tmp_path: Path) -> None:
        """Status is standby when only some cancelled legs receive replacements."""
        proc = _build_with_data(HIDDEN_PARTIAL_LEGS, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_PARTIAL_LEGS)
        assert snap == ref_snap
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-P1"]["status"] == "standby"
        assert len(by_id["PAX-P1"]["rebooked_legs"]) == 1

    def test_hidden_connection_when_next_leg_cancelled(self, tmp_path: Path) -> None:
        """Connection uses the original next-leg schedule even when that next leg is cancelled."""
        proc = _build_with_data(HIDDEN_CONN_CANCEL_NEXT, tmp_path)
        assert proc.returncode == 0, proc.stderr
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        ref_snap, _, _, _ = build_outputs(HIDDEN_CONN_CANCEL_NEXT)
        assert snap == ref_snap
        by_id = {r["passenger_id"]: r for r in snap["passenger_records"]}
        assert by_id["PAX-CC"]["status"] == "rebooked"
        legs = {r["leg_seq"]: r for r in by_id["PAX-CC"]["rebooked_legs"]}
        assert legs[1]["replacement_flight"] == "UA502"
        assert legs[2]["replacement_flight"] == "UA601"

    def test_export_reads_snapshot_only(self, tmp_path: Path) -> None:
        """Export must ignore live inputs — material mutations and missing data roots must not change outputs."""
        proc = _build_with_data(DATA_DIR, tmp_path)
        assert proc.returncode == 0
        plan_path = tmp_path / "output" / "rebooking-plan.json"
        summary_path = tmp_path / "output" / "passenger-summary.json"
        plan_before = plan_path.read_bytes()
        summary_before = summary_path.read_bytes()

        data = tmp_path / "data"
        pax = _load(data / "passengers.json")
        # Swap loyalty and reverse array order — would reshuffle priority allocation if reloaded.
        pax["passengers"][0]["loyalty_tier"] = "none"
        pax["passengers"][1]["loyalty_tier"] = "platinum"
        pax["passengers"] = list(reversed(pax["passengers"]))
        (data / "passengers.json").write_text(json.dumps(pax, indent=2) + "\n", encoding="utf-8")

        pol = _load(data / "airline-policies.json")
        pol["priority_pick_mode"] = "manifest_passenger_order"
        pol["upgrade_on_cancel"] = False
        pol["connection_protection_minutes"] = 9999
        (data / "airline-policies.json").write_text(json.dumps(pol, indent=2) + "\n", encoding="utf-8")

        seats = _load(data / "seat-inventory.json")
        for flight in seats["flights"]:
            for fare_class in list(flight["inventory"].keys()):
                flight["inventory"][fare_class] = 0
        (data / "seat-inventory.json").write_text(json.dumps(seats, indent=2) + "\n", encoding="utf-8")

        cans = _load(data / "flight-cancellations.json")
        cans["cancellations"] = []
        (data / "flight-cancellations.json").write_text(json.dumps(cans, indent=2) + "\n", encoding="utf-8")

        # Staged TB3 data root must not remain available for a live reload.
        shutil.rmtree(data)

        # Also poison /app/data so export cannot secretly fall back to the bundled root.
        app_pax = _load(DATA_DIR / "passengers.json")
        app_pax["passengers"][0]["loyalty_tier"] = "none"
        (DATA_DIR / "passengers.json").write_text(json.dumps(app_pax, indent=2) + "\n", encoding="utf-8")
        app_pol = _load(DATA_DIR / "airline-policies.json")
        app_pol["priority_pick_mode"] = "manifest_passenger_order"
        (DATA_DIR / "airline-policies.json").write_text(
            json.dumps(app_pol, indent=2) + "\n", encoding="utf-8"
        )
        subprocess.run(["chmod", "-R", "a-rwx", str(DATA_DIR)], check=False)

        try:
            _prepare_tmp_workspace(tmp_path)
            proc2 = _run_cli(
                "export",
                env={
                    "TB3_DATA_DIR": str(tmp_path / "data"),
                    "TB3_STATE_DIR": str(tmp_path / "state"),
                    "TB3_OUTPUT_DIR": str(tmp_path / "output"),
                },
            )
            assert proc2.returncode == 0, proc2.stderr
            assert plan_path.read_bytes() == plan_before
            assert summary_path.read_bytes() == summary_before
        finally:
            # Restore bundled data for later tests that use /app/data.
            subprocess.run(["chmod", "-R", "u+rwX,a+rX", str(DATA_DIR)], check=False)
            if BASELINE_BACKUP.exists():
                shutil.rmtree(DATA_DIR, ignore_errors=True)
                shutil.copytree(BASELINE_BACKUP, DATA_DIR)
            _ensure_app_writable_dirs()

    def test_tb3_data_dir_absolute_override(self, tmp_path: Path) -> None:
        """TB3_DATA_DIR absolute path redirects stage input root."""
        proc = _build_with_data(HIDDEN_COMPETING, tmp_path)
        assert proc.returncode == 0
        snap = _load(tmp_path / "state" / "rebooking-snapshot.json")
        assert snap["cancelled_flights"] == ["DL100"]

    def test_tb3_data_dir_relative_ignored(self, tmp_path: Path) -> None:
        """Relative TB3_DATA_DIR is ignored and bundled data is used."""
        state = tmp_path / "state"
        out = tmp_path / "output"
        state.mkdir()
        out.mkdir()
        _prepare_tmp_workspace(tmp_path)
        proc = _run_cli(
            "build",
            env={
                "TB3_DATA_DIR": "relative/ignored",
                "TB3_STATE_DIR": str(state),
                "TB3_OUTPUT_DIR": str(out),
            },
        )
        assert proc.returncode == 0
        snap = _load(state / "rebooking-snapshot.json")
        assert snap["cancelled_flights"] == ["UA101", "UA310"]
