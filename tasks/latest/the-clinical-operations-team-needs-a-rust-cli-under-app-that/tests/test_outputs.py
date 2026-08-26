"""Behavioral verifier tests for the hospital analytics engine."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


def discover_app_dir() -> Path:
    """Locate the application root from environment, container layout, or task repo."""
    env_override = os.environ.get("APP_DIR")
    if env_override:
        candidate = Path(env_override)
        if (candidate / "Cargo.toml").is_file():
            return candidate

    container_app = Path("/app")
    if (container_app / "Cargo.toml").is_file():
        return container_app

    task_root = Path(__file__).resolve().parent.parent
    repo_app = task_root / "environment" / "app"
    if (repo_app / "Cargo.toml").is_file():
        return repo_app

    raise RuntimeError("Unable to locate application directory")


APP_DIR = discover_app_dir()
DATA_DIR = APP_DIR / "data"
DEFAULT_OUTPUT = APP_DIR / "output" / "analytics_report.json"
EVENT_FILES = (
    "admissions.csv",
    "transfers.csv",
    "procedures.csv",
    "discharges.csv",
)


@dataclass
class HospitalEvent:
    event_id: str
    event_time: str
    event_seq: int
    kind: str
    fields: dict[str, str]


@dataclass
class BedInfo:
    bed_id: str
    ward: str
    is_icu: bool
    maintenance: bool


@dataclass
class PatientRecord:
    patient_id: str
    acuity_level: int
    admission_time: str
    current_ward: str | None = None
    bed_id: str | None = None
    discharged: bool = False
    discharge_time: str | None = None
    procedure_count: int = 0
    procedure_minutes: int = 0

    def in_facility_at(self, as_of: str) -> bool:
        if self.discharged:
            return bool(self.discharge_time and as_of < self.discharge_time)
        return self.admission_time <= as_of


@dataclass
class FacilityState:
    patients: dict[str, PatientRecord] = field(default_factory=dict)
    beds: dict[str, BedInfo] = field(default_factory=dict)
    ward_capacity: dict[str, int] = field(default_factory=dict)
    bed_assignments: dict[str, str] = field(default_factory=dict)
    ward_occupancy: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    seen_event_ids: set[str] = field(default_factory=set)
    peak_occupancy: int = 0
    rejected_events: list[tuple[HospitalEvent, str]] = field(default_factory=list)


def run_cli(input_dir: Path, output_path: Path, app_dir: Path | None = None) -> dict:
    """Build the Rust binary and return parsed JSON output."""
    root = app_dir or APP_DIR
    binary = root / "target" / "release" / "hospital_analytics"
    subprocess.run(
        ["cargo", "build", "--release", "--locked"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(binary), "--input-dir", str(input_dir), "--output", str(output_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(output_path.read_text(encoding="utf-8"))


def read_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_as_of(input_dir: Path) -> str:
    for line in (input_dir / "README.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("as_of:"):
            return line.split(":", 1)[1].strip()
    raise ValueError("as_of missing")


def all_event_rows(input_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name in EVENT_FILES:
        rows.extend(read_csv_rows(input_dir / name))
    return rows


def duplicate_event_ids(input_dir: Path) -> set[str]:
    counts = Counter(row["event_id"] for row in all_event_rows(input_dir))
    return {event_id for event_id, count in counts.items() if count > 1}


def tied_timestamp_groups(input_dir: Path) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in all_event_rows(input_dir):
        groups[row["event_time"]].append(row)
    return {ts: rows for ts, rows in groups.items() if len(rows) > 1}


def patient_row(report: dict, patient_id: str) -> dict:
    return next(row for row in report["patients"] if row["patient_id"] == patient_id)


def run_and_compare(input_dir: Path, output_path: Path) -> tuple[dict, dict]:
    """Run the CLI and return actual output with the reference expectation."""
    run_cli(input_dir, output_path)
    actual = read_report(output_path)
    expected = compute_report(input_dir)
    return actual, expected


def load_events(input_dir: Path) -> list[HospitalEvent]:
    events: list[HospitalEvent] = []

    for row in read_csv_rows(input_dir / "admissions.csv"):
        events.append(
            HospitalEvent(
                event_id=row["event_id"],
                event_time=row["event_time"],
                event_seq=int(row["event_seq"]),
                kind="admission",
                fields=row,
            )
        )

    for row in read_csv_rows(input_dir / "transfers.csv"):
        events.append(
            HospitalEvent(
                event_id=row["event_id"],
                event_time=row["event_time"],
                event_seq=int(row["event_seq"]),
                kind="transfer",
                fields=row,
            )
        )

    for row in read_csv_rows(input_dir / "procedures.csv"):
        events.append(
            HospitalEvent(
                event_id=row["event_id"],
                event_time=row["event_time"],
                event_seq=int(row["event_seq"]),
                kind="procedure",
                fields=row,
            )
        )

    for row in read_csv_rows(input_dir / "discharges.csv"):
        events.append(
            HospitalEvent(
                event_id=row["event_id"],
                event_time=row["event_time"],
                event_seq=int(row["event_seq"]),
                kind="discharge",
                fields=row,
            )
        )

    events.sort(key=lambda item: (item.event_time, item.event_seq, item.event_id))
    merged: list[HospitalEvent] = []
    seen: set[str] = set()
    for event in events:
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        merged.append(event)
    return merged


def load_beds(input_dir: Path) -> dict[str, BedInfo]:
    beds: dict[str, BedInfo] = {}
    for row in read_csv_rows(input_dir / "beds.csv"):
        beds[row["bed_id"]] = BedInfo(
            bed_id=row["bed_id"],
            ward=row["ward"],
            is_icu=row["is_icu"] == "true",
            maintenance=row["status"] == "maintenance",
        )
    return beds


def load_capacity(input_dir: Path) -> dict[str, int]:
    return {row["ward"]: int(row["max_beds"]) for row in read_csv_rows(input_dir / "capacity.csv")}


def icu_allowed(is_icu: bool, acuity: int, critical_count: int) -> bool:
    if not is_icu:
        return True
    if acuity == 1:
        return True
    return critical_count == 0


def critical_in_facility(state: FacilityState) -> int:
    return sum(1 for patient in state.patients.values() if not patient.discharged and patient.acuity_level == 1)


def ward_at_capacity(state: FacilityState, ward: str) -> bool:
    cap = state.ward_capacity.get(ward, 0)
    return state.ward_occupancy.get(ward, 0) >= cap


def available_beds(state: FacilityState, ward: str, acuity: int) -> list[str]:
    critical = critical_in_facility(state)
    beds = [
        bed.bed_id
        for bed in state.beds.values()
        if bed.ward == ward
        and not bed.maintenance
        and bed.bed_id not in state.bed_assignments
        and icu_allowed(bed.is_icu, acuity, critical)
    ]
    beds.sort()
    return beds


def icu_beds_available(state: FacilityState) -> list[str]:
    return sorted(
        bed.bed_id
        for bed in state.beds.values()
        if bed.is_icu and not bed.maintenance and bed.bed_id not in state.bed_assignments
    )


def assign_bed(state: FacilityState, patient_id: str, ward: str, acuity: int) -> str:
    if ward_at_capacity(state, ward):
        raise ValueError("ward_at_capacity")
    beds = available_beds(state, ward, acuity)
    if not beds:
        if any(b.ward == ward and b.is_icu for b in state.beds.values()) and acuity != 1:
            raise ValueError("icu_priority_violation")
        raise ValueError("no_available_bed")
    bed_id = beds[0]
    state.bed_assignments[bed_id] = patient_id
    state.ward_occupancy[ward] = state.ward_occupancy.get(ward, 0) + 1
    return bed_id


def release_bed(state: FacilityState, bed_id: str) -> None:
    bed = state.beds.get(bed_id)
    if not bed:
        return
    state.bed_assignments.pop(bed_id, None)
    state.ward_occupancy[bed.ward] = max(0, state.ward_occupancy.get(bed.ward, 0) - 1)


def refresh_peak(state: FacilityState) -> None:
    state.peak_occupancy = max(state.peak_occupancy, len(state.bed_assignments))


def reject(state: FacilityState, event: HospitalEvent, reason: str) -> None:
    state.rejected_events.append((event, reason))


def handle_admission(state: FacilityState, event: HospitalEvent) -> None:
    patient_id = event.fields["patient_id"]
    acuity = int(event.fields["acuity_level"])
    preferred = event.fields["preferred_ward"]
    if patient_id in state.patients:
        reject(state, event, "duplicate_admission")
        return

    target = preferred
    if acuity == 1:
        icu = icu_beds_available(state)
        if icu:
            target = state.beds[icu[0]].ward

    try:
        bed_id = assign_bed(state, patient_id, target, acuity)
    except ValueError as exc:
        reject(state, event, str(exc))
        return

    patient = PatientRecord(patient_id, acuity, event.event_time)
    bed = state.beds[bed_id]
    patient.current_ward = bed.ward
    patient.bed_id = bed_id
    state.patients[patient_id] = patient
    refresh_peak(state)


def handle_transfer(state: FacilityState, event: HospitalEvent) -> None:
    status = event.fields["status"]
    if status != "completed":
        return

    patient_id = event.fields["patient_id"]
    to_ward = event.fields["to_ward"]
    patient = state.patients.get(patient_id)
    if not patient or patient.discharged:
        reject(state, event, "unknown_patient" if not patient else "patient_discharged")
        return

    if patient.bed_id:
        release_bed(state, patient.bed_id)
        patient.bed_id = None

    try:
        bed_id = assign_bed(state, patient_id, to_ward, patient.acuity_level)
    except ValueError as exc:
        reject(state, event, str(exc))
        return

    patient.bed_id = bed_id
    patient.current_ward = state.beds[bed_id].ward
    refresh_peak(state)


def handle_procedure(state: FacilityState, event: HospitalEvent) -> None:
    status = event.fields["status"]
    if status in {"cancelled", "scheduled"}:
        return
    if status != "completed":
        return

    patient_id = event.fields["patient_id"]
    patient = state.patients.get(patient_id)
    if not patient:
        reject(state, event, "unknown_patient")
        return
    if patient.discharged and patient.discharge_time and event.event_time >= patient.discharge_time:
        reject(state, event, "patient_discharged")
        return

    patient.procedure_count += 1
    patient.procedure_minutes += int(event.fields["duration_minutes"])


def handle_discharge(state: FacilityState, event: HospitalEvent) -> None:
    patient_id = event.fields["patient_id"]
    patient = state.patients.get(patient_id)
    if not patient:
        reject(state, event, "unknown_patient")
        return
    if patient.discharged:
        reject(state, event, "already_discharged")
        return
    if patient.bed_id:
        release_bed(state, patient.bed_id)
    patient.bed_id = None
    patient.current_ward = None
    patient.discharged = True
    patient.discharge_time = event.event_time


def whole_hours_between(start: str, end: str) -> int:
    def parse_ts(raw: str) -> int:
        trimmed = raw.rstrip("Z")
        date, time = trimmed.split("T", 1)
        year, month, day = (int(part) for part in date.split("-"))
        hour, minute, second = (int(part) for part in time.split(":"))
        return (((year * 372 + month * 31 + day) * 24 + hour) * 60 + minute) * 60 + second

    delta = parse_ts(end) - parse_ts(start)
    return max(0, delta // 3600)


def compute_report(input_dir: Path, as_of: str | None = None) -> dict:
    """Independent reference implementation of the analytics report."""
    snapshot = as_of or load_as_of(input_dir)
    state = FacilityState(beds=load_beds(input_dir), ward_capacity=load_capacity(input_dir))

    for event in load_events(input_dir):
        if event.event_id in state.seen_event_ids:
            continue
        state.seen_event_ids.add(event.event_id)

        if event.kind == "admission":
            handle_admission(state, event)
        elif event.kind == "transfer":
            handle_transfer(state, event)
        elif event.kind == "procedure":
            handle_procedure(state, event)
        elif event.kind == "discharge":
            handle_discharge(state, event)

    patients = []
    for patient_id in sorted(state.patients):
        patient = state.patients[patient_id]
        end = patient.discharge_time or snapshot
        patients.append(
            {
                "patient_id": patient.patient_id,
                "acuity_level": patient.acuity_level,
                "current_ward": patient.current_ward,
                "bed_id": patient.bed_id,
                "status": "in_facility" if patient.in_facility_at(snapshot) else "discharged",
                "procedure_count": patient.procedure_count,
                "procedure_minutes": patient.procedure_minutes,
                "los_hours": whole_hours_between(patient.admission_time, end),
            }
        )

    ward_counts: dict[str, int] = defaultdict(int)
    for patient in state.patients.values():
        if patient.in_facility_at(snapshot) and patient.current_ward:
            ward_counts[patient.current_ward] += 1

    ward_occupancy = [
        {
            "ward": ward,
            "occupied": ward_counts[ward],
            "capacity": state.ward_capacity.get(ward, 0),
        }
        for ward in sorted(ward_counts)
    ]

    rejected = [
        {
            "event_id": event.event_id,
            "event_time": event.event_time,
            "event_seq": event.event_seq,
            "reason": reason,
        }
        for event, reason in sorted(
            state.rejected_events,
            key=lambda item: (item[0].event_time, item[0].event_seq, item[0].event_id),
        )
    ]

    active = sum(1 for patient in state.patients.values() if patient.in_facility_at(snapshot))
    discharged = sum(1 for patient in state.patients.values() if patient.discharged)
    total_procedures = sum(patient.procedure_count for patient in state.patients.values())

    return {
        "as_of": snapshot,
        "summary": {
            "total_admissions": len(state.patients),
            "active_patients": active,
            "discharged_patients": discharged,
            "total_procedures": total_procedures,
            "peak_occupancy": state.peak_occupancy,
            "rejected_event_count": len(rejected),
        },
        "patients": patients,
        "ward_occupancy": ward_occupancy,
        "rejected_events": rejected,
    }


def test_output_schema_and_types() -> None:
    """Verify the JSON report exposes the documented keys and value types."""
    actual, _expected = run_and_compare(DATA_DIR, DEFAULT_OUTPUT)
    assert set(actual) == {"as_of", "summary", "patients", "ward_occupancy", "rejected_events"}
    summary = actual["summary"]
    assert set(summary) == {
        "total_admissions",
        "active_patients",
        "discharged_patients",
        "total_procedures",
        "peak_occupancy",
        "rejected_event_count",
    }
    assert all(isinstance(summary[key], int) for key in summary)
    for row in actual["patients"]:
        assert set(row) == {
            "patient_id",
            "acuity_level",
            "current_ward",
            "bed_id",
            "status",
            "procedure_count",
            "procedure_minutes",
            "los_hours",
        }
        assert row["status"] in {"in_facility", "discharged"}
    for row in actual["ward_occupancy"]:
        assert set(row) == {"ward", "occupied", "capacity"}
    for row in actual["rejected_events"]:
        assert set(row) == {"event_id", "event_time", "event_seq", "reason"}


def test_full_report_matches_reference_engine() -> None:
    """The default fixture report must match the reference engine output."""
    actual, expected = run_and_compare(DATA_DIR, DEFAULT_OUTPUT)
    assert actual == expected


def test_timestamp_tie_break_orders_admissions() -> None:
    """Events sharing a timestamp must respect event_seq ordering."""
    tied_groups = tied_timestamp_groups(DATA_DIR)
    assert tied_groups, "fixture must include tied timestamps"
    actual, expected = run_and_compare(DATA_DIR, DEFAULT_OUTPUT)
    assert actual == expected
    admission_times = {row["event_time"] for row in read_csv_rows(DATA_DIR / "admissions.csv")}
    assert any(len(rows) > 1 and rows[0]["event_time"] in admission_times for rows in tied_groups.values())


def test_bed_capacity_rejects_overflow_admission() -> None:
    """Ward admissions beyond capacity.csv limits are rejected."""
    actual, expected = run_and_compare(DATA_DIR, DEFAULT_OUTPUT)
    assert actual == expected
    overflow = [row for row in expected["rejected_events"] if row["reason"] == "ward_at_capacity"]
    assert overflow, "fixture must include a capacity rejection"


def test_icu_priority_blocks_non_critical_transfer() -> None:
    """Non-critical patients cannot take ICU beds while critical patients remain admitted."""
    actual, expected = run_and_compare(DATA_DIR, DEFAULT_OUTPUT)
    assert actual == expected
    icu_rejections = [
        row for row in expected["rejected_events"] if row["reason"] == "icu_priority_violation"
    ]
    assert icu_rejections, "fixture must include an ICU priority rejection"


def test_cancelled_procedures_excluded_from_totals() -> None:
    """Cancelled procedures must not increase procedure totals."""
    cancelled_rows = [
        row for row in read_csv_rows(DATA_DIR / "procedures.csv") if row["status"] == "cancelled"
    ]
    assert cancelled_rows, "fixture must include cancelled procedures"
    actual, expected = run_and_compare(DATA_DIR, DEFAULT_OUTPUT)
    assert actual == expected
    for row in cancelled_rows:
        patient = patient_row(expected, row["patient_id"])
        completed_minutes = sum(
            int(proc["duration_minutes"])
            for proc in read_csv_rows(DATA_DIR / "procedures.csv")
            if proc["patient_id"] == row["patient_id"] and proc["status"] == "completed"
        )
        assert patient["procedure_minutes"] == completed_minutes


def test_partial_transfer_does_not_move_patient() -> None:
    """Partial transfers leave the patient in the source ward."""
    partial_rows = [
        row for row in read_csv_rows(DATA_DIR / "transfers.csv") if row["status"] == "partial"
    ]
    assert partial_rows, "fixture must include partial transfers"
    actual, expected = run_and_compare(DATA_DIR, DEFAULT_OUTPUT)
    assert actual == expected
    for row in partial_rows:
        patient_id = row["patient_id"]
        assert patient_row(actual, patient_id) == patient_row(expected, patient_id)
        expected_patient = patient_row(expected, patient_id)
        if expected_patient["status"] == "in_facility":
            assert expected_patient["current_ward"] == row["from_ward"]


def test_duplicate_event_ids_are_ignored() -> None:
    """Duplicate event_id rows after the first occurrence are skipped silently."""
    duplicates = duplicate_event_ids(DATA_DIR)
    assert duplicates, "fixture must include duplicate event identifiers"
    actual, expected = run_and_compare(DATA_DIR, DEFAULT_OUTPUT)
    assert actual == expected
    for event_id in duplicates:
        rows = [row for row in all_event_rows(DATA_DIR) if row["event_id"] == event_id]
        rows.sort(key=lambda row: (row["event_time"], int(row["event_seq"]), row["event_id"]))
        kept = rows[0]
        for skipped in rows[1:]:
            if skipped.get("patient_id") and skipped["patient_id"] != kept.get("patient_id"):
                assert skipped["patient_id"] not in {row["patient_id"] for row in actual["patients"]}
        assert event_id not in {row["event_id"] for row in actual["rejected_events"]}


def test_missing_discharge_counts_as_in_facility() -> None:
    """Patients without a discharge remain in_facility at the census snapshot."""
    discharged_ids = {row["patient_id"] for row in read_csv_rows(DATA_DIR / "discharges.csv")}
    actual, expected = run_and_compare(DATA_DIR, DEFAULT_OUTPUT)
    assert actual == expected
    missing_discharge = [
        row
        for row in expected["patients"]
        if row["patient_id"] not in discharged_ids and row["status"] == "in_facility"
    ]
    assert missing_discharge, "fixture must include in-facility patients without discharge rows"
    for row in missing_discharge:
        assert patient_row(actual, row["patient_id"])["status"] == "in_facility"
    assert actual["summary"]["active_patients"] == expected["summary"]["active_patients"]


def test_dynamic_mutation_changes_census() -> None:
    """Mutated inputs must produce a report matching the reference engine, not the baseline."""
    baseline = compute_report(DATA_DIR)
    mutation = {
        "procedure_id": "PROC-777",
        "patient_id": "P003",
        "event_time": "2024-06-20T11:00:00Z",
        "event_seq": "1",
        "event_id": "PROC-E777",
        "procedure_code": "MRI",
        "duration_minutes": "15",
        "status": "completed",
    }
    with tempfile.TemporaryDirectory() as tmp:
        input_dir = Path(tmp) / "input"
        shutil.copytree(DATA_DIR, input_dir)
        procedures_path = input_dir / "procedures.csv"
        rows = read_csv_rows(procedures_path)
        rows.append(mutation)
        with procedures_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        output = Path(tmp) / "report.json"
        actual = run_cli(input_dir, output)
        expected = compute_report(input_dir)
        assert actual == expected
        assert actual != baseline
        delta_minutes = int(mutation["duration_minutes"])
        patient_id = mutation["patient_id"]
        actual_patient = patient_row(actual, patient_id)
        baseline_patient = patient_row(baseline, patient_id)
        assert actual_patient["procedure_count"] == baseline_patient["procedure_count"] + 1
        assert actual_patient["procedure_minutes"] == baseline_patient["procedure_minutes"] + delta_minutes


def test_deterministic_output() -> None:
    """Repeated runs on the same inputs must produce identical JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        out_a = Path(tmp) / "a.json"
        out_b = Path(tmp) / "b.json"
        run_cli(DATA_DIR, out_a)
        run_cli(DATA_DIR, out_b)
        assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")
