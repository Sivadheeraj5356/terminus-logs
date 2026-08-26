"""Black-box contract verifier for the compactor ram seat driver."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

import pytest

APP = Path("/app")
BIN = APP / "bin" / "compactor_seat"
EMIT_BIN = Path("/tmp/tb3-compactor_seat")
FIXTURE_DIR = APP / "fixtures"
OUT = APP / "output"
SEAT_LOG = OUT / "seat_log.jsonl"
SEAT_REPORT = OUT / "seat_report.json"
EDITABLE_ROOT = APP / "src"


def payload_checksum(payload: bytes) -> int:
    acc = 0
    for b in payload:
        acc = (acc + b) & 0xFFFFFFFF
    return acc


def read_cmpr_ram_id(path: Path) -> str:
    data = path.read_bytes()
    assert data[:4] == b"CMPR"
    length = int.from_bytes(data[4:8], "little")
    body = data[8 : 8 + length]
    ram_id, _ = body.decode("utf-8").split("|", 1)
    return ram_id


def read_cmpr_block(path: Path) -> tuple[str, int, int]:
    data = path.read_bytes()
    assert data[:4] == b"CMPR"
    length = int.from_bytes(data[4:8], "little")
    body = data[8 : 8 + length]
    stored = int.from_bytes(data[8 + length : 8 + length + 4], "little")
    expected = payload_checksum(body)
    assert stored == expected, f"fixture block checksum mismatch for {path}"
    ram_id, tonnage_raw = body.decode("utf-8").split("|", 1)
    return ram_id, int(tonnage_raw), expected


def load_journal(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def apply_ram_seat(
    seated: dict[str, tuple[int, int, int]],
    ram_id: str,
    checksum: int,
    tonnage: int,
    epoch: int,
) -> tuple[dict[str, tuple[int, int, int]], bool]:
    """Return updated seated map and whether a ram_seated row should be emitted."""
    if ram_id in seated and seated[ram_id][0] == checksum:
        if epoch > seated[ram_id][2]:
            seated[ram_id] = (checksum, tonnage, epoch)
        return seated, False
    seated[ram_id] = (checksum, tonnage, epoch)
    return seated, True


def durable_payload_fingerprint(entry: dict) -> str:
    return "|".join(
        [
            str(entry.get("op", "")),
            str(entry.get("scenario_tag", "")),
            str(entry.get("cycle_epoch", 0)),
            str(entry.get("ram_block_id", "")),
            str(entry.get("event_id", "")),
        ]
    )


def dedupe_durable_entries(entries: list[dict]) -> list[dict]:
    """Retain durable journal rows after identical-seq and event_id deduplication."""
    rows = sorted(entries, key=lambda row: int(row["seq"]))
    seen_seq: dict[int, str] = {}
    seen_event: set[str] = set()
    retained: list[dict] = []
    for entry in rows:
        fp = durable_payload_fingerprint(entry)
        seq = int(entry["seq"])
        if seq in seen_seq:
            if seen_seq[seq] != fp:
                raise ValueError(f"conflicting durable seq {seq}")
            continue
        event_id = str(entry.get("event_id", ""))
        if event_id and event_id in seen_event:
            continue
        seen_seq[seq] = fp
        if event_id:
            seen_event.add(event_id)
        retained.append(entry)
    return retained


def reference_ram_seated_count(events_path: Path, ram_root: Path) -> int:
    entries = dedupe_durable_entries(load_journal(events_path))
    cycle_epoch = 0
    seated: dict[str, tuple[int, int, int]] = {}
    count = 0
    for entry in entries:
        op = entry.get("op")
        if op == "cycle_arm":
            cycle_epoch = int(entry["cycle_epoch"])
            continue
        if op == "ram_seat":
            block_id = str(entry["ram_block_id"])
            ram_id, tonnage, checksum = read_cmpr_block(ram_root / f"{block_id}.bin")
            epoch = int(entry.get("cycle_epoch") or cycle_epoch)
            seated, emit = apply_ram_seat(seated, ram_id, checksum, tonnage, epoch)
            if emit:
                count += 1
            continue
        if op == "guide_clear":
            seated = {
                ram_id: rec
                for ram_id, rec in seated.items()
                if rec[2] >= cycle_epoch
            }
    return count


def expected_seated_rams(events_path: Path, ram_root: Path) -> set[str]:
    entries = dedupe_durable_entries(load_journal(events_path))
    cycle_epoch = 0
    seated: dict[str, tuple[int, int, int]] = {}
    emitted: set[str] = set()
    for entry in entries:
        op = entry.get("op")
        if op == "cycle_arm":
            cycle_epoch = int(entry["cycle_epoch"])
            continue
        if op == "ram_seat":
            block_id = str(entry["ram_block_id"])
            ram_id, tonnage, checksum = read_cmpr_block(ram_root / f"{block_id}.bin")
            epoch = int(entry.get("cycle_epoch") or cycle_epoch)
            seated, emit = apply_ram_seat(seated, ram_id, checksum, tonnage, epoch)
            if emit:
                emitted.add(ram_id)
            continue
        if op == "guide_clear":
            seated = {
                ram_id: rec
                for ram_id, rec in seated.items()
                if rec[2] >= cycle_epoch
            }
    return emitted


def expected_ram_seated_rows(events_path: Path, ram_root: Path) -> int:
    return reference_ram_seated_count(events_path, ram_root)


def expected_live_ledger(events_path: Path, ram_root: Path) -> dict[str, int]:
    entries = dedupe_durable_entries(load_journal(events_path))

    cycle_epoch = 0
    seated: dict[str, tuple[int, int, int]] = {}

    for entry in entries:
        op = entry.get("op")
        if op == "cycle_arm":
            cycle_epoch = int(entry["cycle_epoch"])
            continue
        if op == "ram_seat":
            block_id = str(entry["ram_block_id"])
            ram_id, tonnage, checksum = read_cmpr_block(ram_root / f"{block_id}.bin")
            epoch = int(entry.get("cycle_epoch") or cycle_epoch)
            seated, _emit = apply_ram_seat(seated, ram_id, checksum, tonnage, epoch)
            continue
        if op == "guide_clear":
            seated = {
                ram_id: rec
                for ram_id, rec in seated.items()
                if rec[2] >= cycle_epoch
            }

    return {
        "rams_seated": len(seated),
        "tonnage_recorded": sum(rec[1] for rec in seated.values()),
    }


def expected_tonnage(events_path: Path, ram_root: Path) -> int:
    return expected_live_ledger(events_path, ram_root)["tonnage_recorded"]


def replay_ledger_state(
    events_path: Path, ram_root: Path
) -> tuple[dict[str, tuple[int, int, int]], int, int]:
    entries = dedupe_durable_entries(load_journal(events_path))
    cycle_epoch = 0
    journal_revision = 0
    seated: dict[str, tuple[int, int, int]] = {}
    for entry in entries:
        op = entry.get("op")
        if op == "cycle_arm":
            cycle_epoch = int(entry["cycle_epoch"])
            journal_revision += 1
            continue
        if op == "ram_seat":
            block_id = str(entry["ram_block_id"])
            ram_id, tonnage, checksum = read_cmpr_block(ram_root / f"{block_id}.bin")
            epoch = int(entry.get("cycle_epoch") or cycle_epoch)
            prior = seated.get(ram_id)
            seated, emit = apply_ram_seat(seated, ram_id, checksum, tonnage, epoch)
            if emit:
                journal_revision += 1
            elif (
                prior is not None
                and prior[0] == checksum
                and epoch > prior[2]
            ):
                journal_revision += 1
            continue
        if op == "guide_clear":
            seated = {
                ram_id: rec
                for ram_id, rec in seated.items()
                if rec[2] >= cycle_epoch
            }
            journal_revision += 1
    return seated, cycle_epoch, journal_revision


def reference_state_digest(events_path: Path, ram_root: Path) -> str:
    seated, cycle_epoch, journal_revision = replay_ledger_state(events_path, ram_root)
    digest = hashlib.sha256()
    for ram_id in sorted(seated.keys()):
        checksum, tonnage, epoch = seated[ram_id]
        digest.update(ram_id.encode("utf-8"))
        digest.update(checksum.to_bytes(4, "little"))
        digest.update(tonnage.to_bytes(4, "little"))
        digest.update(epoch.to_bytes(4, "little"))
    digest.update(cycle_epoch.to_bytes(4, "little"))
    digest.update(journal_revision.to_bytes(8, "little"))
    return digest.hexdigest()


def anchor_tonnage_kg(anchor: dict) -> int:
    return sum(int(rec["tonnage_kg"]) for rec in anchor["rams"].values())


def anchor_state_digest(anchor: dict) -> str:
    digest = hashlib.sha256()
    for ram_id in sorted(anchor["rams"].keys()):
        rec = anchor["rams"][ram_id]
        checksum = int(rec["checksum"])
        tonnage_kg = int(rec["tonnage_kg"])
        cycle_epoch = int(rec["cycle_epoch"])
        digest.update(ram_id.encode("utf-8"))
        digest.update(checksum.to_bytes(4, "little"))
        digest.update(tonnage_kg.to_bytes(4, "little"))
        digest.update(cycle_epoch.to_bytes(4, "little"))
    digest.update(int(anchor["cycle_epoch"]).to_bytes(4, "little"))
    digest.update(int(anchor["journal_revision"]).to_bytes(8, "little"))
    return digest.hexdigest()


def build_driver() -> None:
    if not (APP / "Cargo.toml").is_file():
        raise AssertionError("missing /app/Cargo.toml")
    proc = subprocess.run(
        [
            "cargo",
            "build",
            "--release",
            "--locked",
            "--manifest-path",
            "/app/environment/Cargo.toml",
        ],
        cwd=str(APP),
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError("driver build failed:\n" + proc.stdout + "\n" + proc.stderr)
    BIN.parent.mkdir(parents=True, exist_ok=True)
    built = APP / "target" / "release" / "compactor_seat"
    if not built.is_file():
        raise AssertionError("missing release binary after build")
    BIN.write_bytes(built.read_bytes())
    BIN.chmod(0o755)
    EMIT_BIN.write_bytes(built.read_bytes())
    EMIT_BIN.chmod(0o755)


def drive_seat_allow_fail(
    events_file: Path,
    log_path: Path,
    report_path: Path | None = None,
    *,
    recover: bool = False,
    preseed_log: bytes | None = None,
    preseed_report: bytes | None = None,
) -> subprocess.CompletedProcess:
    parent = log_path.parent
    if not (parent.exists() and parent.is_file()):
        parent.mkdir(parents=True, exist_ok=True)
    if preseed_log is not None:
        log_path.write_bytes(preseed_log)
    elif log_path.exists() and log_path.is_file():
        log_path.unlink()
    if report_path is not None:
        if preseed_report is not None:
            report_path.write_bytes(preseed_report)
        elif report_path.is_file():
            report_path.unlink()
    build_driver()
    mode = "--seat-recover" if recover else "--seat"
    if report_path is not None:
        return subprocess.run(
            [
                str(EMIT_BIN),
                mode,
                str(events_file),
                "--emit-log",
                str(log_path),
                "--emit-report",
                str(report_path),
            ],
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
    return subprocess.run(
        [str(EMIT_BIN), mode, str(events_file), "--emit-log", str(log_path)],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )


def drive_seat(
    events_file: Path,
    log_path: Path,
    report_path: Path | None = None,
    *,
    recover: bool = False,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        log_path.unlink()
    build_driver()
    mode = "--seat-recover" if recover else "--seat"
    if report_path is not None:
        result = subprocess.run(
            [
                str(EMIT_BIN),
                mode,
                str(events_file),
                "--emit-log",
                str(log_path),
                "--emit-report",
                str(report_path),
            ],
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
    else:
        result = subprocess.run(
            [str(EMIT_BIN), mode, str(events_file), "--emit-log", str(log_path)],
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
    if result.returncode != 0:
        raise AssertionError(
            f"command failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def load_ops_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def warnings_precede_revocations(rows: list[dict]) -> bool:
    by_tag: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_tag[str(row["scenario_tag"])].append(row)
    for events in by_tag.values():
        marks = [int(e["seq"]) for e in events if e.get("kind") == "guide_marked"]
        clears = [int(e["seq"]) for e in events if e.get("kind") == "guide_cleared"]
        if not marks or not clears:
            return False
        if min(marks) >= min(clears):
            return False
    return True


def assert_seq_monotone(rows: list[dict]) -> None:
    seqs = [int(r["seq"]) for r in rows]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


def recovery_aborted_at_anchor(report: dict, anchor: dict) -> bool:
    return (
        report["rollback_performed"]
        and not report["ready"]
        and report["rams_seated"] == len(anchor["rams"])
        and report["tonnage_recorded"] == anchor_tonnage_kg(anchor)
        and report["state_digest"] == anchor_state_digest(anchor)
    )


def write_cmpr_block(path: Path, ram_id: str, tonnage_kg: int) -> int:
    """Write a valid CMPR block and return its checksum."""
    body = f"{ram_id}|{tonnage_kg}".encode("utf-8")
    checksum = payload_checksum(body)
    blob = (
        b"CMPR"
        + len(body).to_bytes(4, "little")
        + body
        + checksum.to_bytes(4, "little")
    )
    path.write_bytes(blob)
    return checksum


def count_applied_guide_marks(entries: list[dict]) -> int:
    """Count guide_mark operations that survive durable deduplication."""
    return sum(
        1 for entry in dedupe_durable_entries(entries) if entry.get("op") == "guide_mark"
    )


def expected_report_object(
    events_path: Path,
    ram_root: Path,
    *,
    rollback: bool = False,
    anchor: dict | None = None,
) -> dict:
    """Independently compute the full six-field operator report."""
    entries = load_journal(events_path)
    if rollback:
        assert anchor is not None
        seated, cycle_epoch, journal_revision = {}, anchor["cycle_epoch"], anchor["journal_revision"]
        for ram_id, rec in anchor["rams"].items():
            seated[ram_id] = (
                int(rec["checksum"]),
                int(rec["tonnage_kg"]),
                int(rec["cycle_epoch"]),
            )
        tonnage = anchor_tonnage_kg(anchor)
        rams_seated = len(anchor["rams"])
    else:
        seated_map, cycle_epoch, journal_revision = replay_ledger_state(events_path, ram_root)
        seated = seated_map
        tonnage = sum(rec[1] for rec in seated.values())
        rams_seated = len(seated)

    digest = hashlib.sha256()
    for ram_id in sorted(seated.keys()):
        checksum, tonnage_kg, epoch = seated[ram_id]
        digest.update(ram_id.encode("utf-8"))
        digest.update(checksum.to_bytes(4, "little"))
        digest.update(tonnage_kg.to_bytes(4, "little"))
        digest.update(epoch.to_bytes(4, "little"))
    digest.update(int(cycle_epoch).to_bytes(4, "little"))
    digest.update(int(journal_revision).to_bytes(8, "little"))

    return {
        "rams_seated": rams_seated,
        "guides_marked": count_applied_guide_marks(entries),
        "tonnage_recorded": tonnage,
        "state_digest": digest.hexdigest(),
        "rollback_performed": rollback,
        "ready": not rollback and rams_seated > 0,
    }


def assert_no_temp_artifacts(tmp_root: Path, log_path: Path, report_path: Path | None) -> None:
    """Assert staging and temporary publication siblings were removed."""
    for path in (log_path, report_path):
        if path is None:
            continue
        assert not path.parent.joinpath(f".{path.name}.stage").exists()
        for suffix in range(3):
            assert not Path(f"{path}.tmp.{suffix}").exists()
    for path in tmp_root.rglob("*.stage"):
        raise AssertionError(f"unexpected staging artifact: {path}")
    for path in tmp_root.rglob("*.tmp.*"):
        raise AssertionError(f"unexpected temporary artifact: {path}")


@pytest.fixture(autouse=True)
def clear_output_dir() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in (SEAT_LOG, SEAT_REPORT):
        if path.exists():
            path.unlink()


def test_warnings_precede_revocations_in_seat_log() -> None:
    """Stakeholder guide warnings must appear before revocations for every scenario tag."""
    drive_seat(FIXTURE_DIR / "run_alpha.jsonl", SEAT_LOG, SEAT_REPORT)
    rows = load_ops_rows(SEAT_LOG)
    assert warnings_precede_revocations(rows)
    assert_seq_monotone(rows)
    assert any(r.get("kind") == "ram_seated" for r in rows)


def test_shuffled_journal_follows_durable_sequence() -> None:
    """Permuted fixture files must still replay in ascending durable sequence order."""
    drive_seat(FIXTURE_DIR / "run_beta.jsonl", SEAT_LOG)
    assert warnings_precede_revocations(load_ops_rows(SEAT_LOG))


def test_operator_totals_stable_under_repeated_publication() -> None:
    """Publishing the same ram block twice must not inflate seated totals or log rows."""
    events = FIXTURE_DIR / "run_beta.jsonl"
    drive_seat(events, SEAT_LOG, SEAT_REPORT)
    rows = load_ops_rows(SEAT_LOG)
    seated_rows = [r for r in rows if r.get("kind") == "ram_seated"]
    ram_ids = [r["ram_id"] for r in seated_rows]
    assert len(ram_ids) == len(set(ram_ids))
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    expected_count = len(expected_seated_rams(events, APP / "data" / "rams"))
    assert report["rams_seated"] == expected_count
    assert len(seated_rows) == expected_count


def test_revision_bind_updates_live_tonnage() -> None:
    """A changed block for an already-seated ram must refresh tonnage and seating evidence."""
    events = FIXTURE_DIR / "run_delta.jsonl"
    drive_seat(events, SEAT_LOG, SEAT_REPORT)
    rows = load_ops_rows(SEAT_LOG)
    seated = [r for r in rows if r.get("kind") == "ram_seated"]
    ram_root = APP / "data" / "rams"
    assert len(seated) == expected_ram_seated_rows(events, ram_root)
    assert {r["ram_id"] for r in seated} == expected_seated_rams(events, ram_root)
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    live = expected_live_ledger(events, ram_root)
    assert report["rams_seated"] == live["rams_seated"]
    assert report["tonnage_recorded"] == live["tonnage_recorded"]
    assert report["tonnage_recorded"] == expected_tonnage(events, ram_root)


def test_guide_clear_releases_prior_cycle_seatings() -> None:
    """Clearing guides must drop rams seated under earlier cycle epochs from live totals."""
    events = FIXTURE_DIR / "run_epsilon.jsonl"
    drive_seat(events, SEAT_LOG, SEAT_REPORT)
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    live = expected_live_ledger(events, APP / "data" / "rams")
    assert report["rams_seated"] == live["rams_seated"]
    assert report["tonnage_recorded"] == live["tonnage_recorded"]
    assert warnings_precede_revocations(load_ops_rows(SEAT_LOG))


def test_failed_block_run_restores_anchor_snapshot() -> None:
    """Recovery after a corrupt CMPR read must restore anchor state and keep prior log rows."""
    drive_seat(
        FIXTURE_DIR / "run_gamma.jsonl",
        SEAT_LOG,
        SEAT_REPORT,
        recover=True,
    )
    assert SEAT_LOG.is_file()
    assert SEAT_REPORT.is_file()
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    anchor = json.loads((APP / "snapshot" / "compactor_anchor.json").read_text(encoding="utf-8"))
    assert recovery_aborted_at_anchor(report, anchor)
    rows = load_ops_rows(SEAT_LOG)
    recorded = [r for r in rows if r.get("kind") == "ram_seated"]
    bad_ram_id = read_cmpr_ram_id(APP / "data" / "rams" / "seat_gamma_bad.bin")
    good_ram_id = read_cmpr_ram_id(APP / "data" / "rams" / "seat_gamma_ok.bin")
    assert bad_ram_id not in {r.get("ram_id") for r in recorded}
    assert good_ram_id in {r.get("ram_id") for r in recorded}
    assert_seq_monotone(rows)


def test_catalog_view_reflects_live_state_after_policy_change() -> None:
    """Shift-table probe must refresh when journal revision advances without a cycle change."""
    build_driver()
    result = subprocess.run(
        [str(EMIT_BIN), "--probe-shift-table"],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"probe failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    payload = json.loads(result.stdout)
    first = payload["first"]
    second = payload["second"]
    truth = payload["truth"]
    assert second["ram_count"] == truth["ram_count"]
    assert first["ram_count"] != second["ram_count"]
    assert second["journal_revision"] == truth["journal_revision"]
    isolated = payload["isolated"]
    isolated_truth = payload["isolated_truth"]
    assert isolated["ram_count"] == isolated_truth["ram_count"]
    assert isolated["rams"] == isolated_truth["rams"]
    assert isolated["rams"] != payload["first"]["rams"]


def test_summary_reflects_live_ledger_not_row_count() -> None:
    """Operator report totals must follow rebuilt ledger truth, not raw log row counts alone."""
    events = FIXTURE_DIR / "run_alpha.jsonl"
    drive_seat(events, SEAT_LOG, SEAT_REPORT)
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    live = expected_live_ledger(events, APP / "data" / "rams")
    assert report["rams_seated"] == live["rams_seated"]
    assert report["tonnage_recorded"] == live["tonnage_recorded"]
    assert report["guides_marked"] >= 1


def test_full_schedule_end_to_end_contract() -> None:
    """Composite yard schedule must satisfy ordering, seating, revision, and summary contracts."""
    events = FIXTURE_DIR / "run_zeta.jsonl"
    drive_seat(events, SEAT_LOG, SEAT_REPORT)
    rows = load_ops_rows(SEAT_LOG)
    assert warnings_precede_revocations(rows)
    assert_seq_monotone(rows)
    seated = [r for r in rows if r.get("kind") == "ram_seated"]
    ram_root = APP / "data" / "rams"
    assert len(seated) == expected_ram_seated_rows(events, ram_root)
    assert {r["ram_id"] for r in seated} == expected_seated_rams(events, ram_root)
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    live = expected_live_ledger(events, ram_root)
    assert report["rams_seated"] == live["rams_seated"]
    assert report["tonnage_recorded"] == live["tonnage_recorded"]
    assert report["guides_marked"] >= 1


def test_report_contract_fields_and_types() -> None:
    """Operator report must expose the documented schema with correct field types."""
    drive_seat(FIXTURE_DIR / "run_alpha.jsonl", SEAT_LOG, SEAT_REPORT)
    data = json.loads(SEAT_REPORT.read_text(encoding="utf-8").strip())
    assert isinstance(data.get("rams_seated"), int)
    assert isinstance(data.get("guides_marked"), int)
    assert isinstance(data.get("tonnage_recorded"), int)
    assert isinstance(data.get("state_digest"), str)
    assert isinstance(data.get("rollback_performed"), bool)
    assert isinstance(data.get("ready"), bool)


def test_identical_input_yields_identical_summary() -> None:
    """Replaying the same journal twice must produce byte-identical operator reports."""
    events = FIXTURE_DIR / "run_zeta.jsonl"
    report_a = OUT / "seat_report_a.json"
    report_b = OUT / "seat_report_b.json"
    log_a = OUT / "seat_log_a.jsonl"
    log_b = OUT / "seat_log_b.jsonl"
    drive_seat(events, log_a, report_a)
    drive_seat(events, log_b, report_b)
    assert report_a.read_bytes() == report_b.read_bytes()


def test_editable_source_tree_present() -> None:
    """Agent-editable Rust sources remain available under /app/src."""
    assert EDITABLE_ROOT.is_dir(), f"missing editable source tree {EDITABLE_ROOT}"


def test_newer_cycle_republication_refreshes_ownership_without_inflation(
    tmp_path: Path,
) -> None:
    """Same-checksum republication at a newer epoch must refresh ownership without extra rows."""
    journal = tmp_path / "refresh_cycle.jsonl"
    journal.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "op": "cycle_arm",
                        "cycle_epoch": 1,
                        "scenario_tag": "refresh",
                    }
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "op": "ram_seat",
                        "ram_block_id": "seat_epsilon_a",
                        "scenario_tag": "refresh",
                        "cycle_epoch": 1,
                    }
                ),
                json.dumps(
                    {
                        "seq": 3,
                        "op": "cycle_arm",
                        "cycle_epoch": 2,
                        "scenario_tag": "refresh",
                    }
                ),
                json.dumps(
                    {
                        "seq": 4,
                        "op": "ram_seat",
                        "ram_block_id": "seat_epsilon_a",
                        "scenario_tag": "refresh",
                        "cycle_epoch": 2,
                    }
                ),
                json.dumps(
                    {
                        "seq": 5,
                        "op": "guide_clear",
                        "scenario_tag": "refresh",
                        "cycle_epoch": 2,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    drive_seat(journal, SEAT_LOG, SEAT_REPORT)
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    live = expected_live_ledger(journal, APP / "data" / "rams")
    rows = load_ops_rows(SEAT_LOG)
    seated_rows = [r for r in rows if r.get("kind") == "ram_seated"]
    assert report["rams_seated"] == 1
    assert live["rams_seated"] == 1
    assert report["tonnage_recorded"] == live["tonnage_recorded"]
    assert len(seated_rows) == 1


def test_catalog_cache_isolated_between_independent_ledgers() -> None:
    """Cached catalog views must not leak ram state across independent ledgers."""
    build_driver()
    result = subprocess.run(
        [str(EMIT_BIN), "--probe-shift-table"],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"probe failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    payload = json.loads(result.stdout)
    assert payload["second"]["ram_count"] == payload["truth"]["ram_count"]
    assert payload["first"]["ram_count"] != payload["second"]["ram_count"]
    assert payload["isolated"] == payload["isolated_truth"]


def test_failed_normal_run_preserves_existing_publication(tmp_path: Path) -> None:
    """Failed normal seat runs must not mutate or create requested publication artifacts."""
    log_path = tmp_path / "seat_log.jsonl"
    report_path = tmp_path / "seat_report.json"
    prior_log = b'{"kind":"seed","scenario_tag":"seed","seq":1}\n'
    prior_report = b'{"rams_seated":9,"guides_marked":0,"tonnage_recorded":0,"rollback_performed":false,"ready":true}\n'

    result = drive_seat_allow_fail(
        FIXTURE_DIR / "run_gamma.jsonl",
        log_path,
        report_path,
        preseed_log=prior_log,
        preseed_report=prior_report,
    )
    assert result.returncode != 0
    assert log_path.read_bytes() == prior_log
    assert report_path.read_bytes() == prior_report

    absent_log = tmp_path / "absent_log.jsonl"
    absent_report = tmp_path / "absent_report.json"
    result = drive_seat_allow_fail(
        FIXTURE_DIR / "run_gamma.jsonl",
        absent_log,
        absent_report,
    )
    assert result.returncode != 0
    assert not absent_log.exists()
    assert not absent_report.exists()


def test_compound_generated_schedule_matches_reference_model(tmp_path: Path) -> None:
    """A deterministic compound schedule must match an independent reference replay model."""
    journal = tmp_path / "compound.jsonl"
    rows = [
        {"seq": 6, "op": "guide_mark", "cycle_epoch": 2, "scenario_tag": "compound"},
        {"seq": 1, "op": "cycle_arm", "cycle_epoch": 1, "scenario_tag": "compound"},
        {
            "seq": 2,
            "op": "ram_seat",
            "ram_block_id": "seat_beta_x",
            "scenario_tag": "compound",
            "cycle_epoch": 1,
        },
        {
            "seq": 3,
            "op": "ram_seat",
            "ram_block_id": "seat_beta_x",
            "scenario_tag": "compound",
            "cycle_epoch": 1,
        },
        {"seq": 4, "op": "cycle_arm", "cycle_epoch": 2, "scenario_tag": "compound"},
        {
            "seq": 5,
            "op": "ram_seat",
            "ram_block_id": "seat_beta_x",
            "scenario_tag": "compound",
            "cycle_epoch": 2,
        },
        {
            "seq": 7,
            "op": "ram_seat",
            "ram_block_id": "seat_delta_a_rev2",
            "scenario_tag": "compound",
            "cycle_epoch": 2,
        },
        {"seq": 8, "op": "guide_clear", "scenario_tag": "compound", "cycle_epoch": 2},
    ]
    journal.write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )
    drive_seat(journal, SEAT_LOG, SEAT_REPORT)
    ram_root = APP / "data" / "rams"
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    rows_out = load_ops_rows(SEAT_LOG)
    seated_rows = [r for r in rows_out if r.get("kind") == "ram_seated"]
    live = expected_live_ledger(journal, ram_root)
    assert report["rams_seated"] == live["rams_seated"]
    assert report["tonnage_recorded"] == live["tonnage_recorded"]
    assert len(seated_rows) == expected_ram_seated_rows(journal, ram_root)
    assert warnings_precede_revocations(rows_out)


def test_report_state_digest_matches_live_ledger() -> None:
    """Operator report digest must match canonical live-ledger encoding."""
    events = FIXTURE_DIR / "run_delta.jsonl"
    drive_seat(events, SEAT_LOG, SEAT_REPORT)
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    expected = reference_state_digest(events, APP / "data" / "rams")
    assert report["state_digest"] == expected
    assert len(report["state_digest"]) == 64


def test_conflicting_durable_seq_aborts_without_mutation(tmp_path: Path) -> None:
    """Conflicting durable seq values must abort before publication changes."""
    journal = tmp_path / "conflict.jsonl"
    journal.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "op": "cycle_arm",
                        "cycle_epoch": 1,
                        "scenario_tag": "conflict",
                    }
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "op": "ram_seat",
                        "ram_block_id": "seat_beta_x",
                        "scenario_tag": "conflict",
                        "cycle_epoch": 1,
                    }
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "op": "guide_mark",
                        "cycle_epoch": 1,
                        "scenario_tag": "conflict",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "conflict_log.jsonl"
    report_path = tmp_path / "conflict_report.json"
    prior_log = b'{"kind":"seed","scenario_tag":"seed","seq":1}\n'
    result = drive_seat_allow_fail(
        journal,
        log_path,
        report_path,
        preseed_log=prior_log,
    )
    assert result.returncode != 0
    assert log_path.read_bytes() == prior_log
    assert not report_path.exists()


def test_identical_durable_seq_rows_deduped(tmp_path: Path) -> None:
    """Identical rows sharing a seq must apply once without duplicate mutation."""
    journal = tmp_path / "identical_seq.jsonl"
    guide_row = {
        "seq": 2,
        "op": "guide_mark",
        "cycle_epoch": 1,
        "scenario_tag": "identical_seq",
    }
    journal.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "op": "cycle_arm",
                        "cycle_epoch": 1,
                        "scenario_tag": "identical_seq",
                    }
                ),
                json.dumps(guide_row),
                json.dumps(guide_row),
                json.dumps(
                    {
                        "seq": 3,
                        "op": "ram_seat",
                        "ram_block_id": "seat_beta_x",
                        "scenario_tag": "identical_seq",
                        "cycle_epoch": 1,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    drive_seat(journal, SEAT_LOG, SEAT_REPORT)
    ram_root = APP / "data" / "rams"
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    expected = expected_report_object(journal, ram_root)
    assert report["guides_marked"] == expected["guides_marked"] == 1
    assert report["rams_seated"] == expected["rams_seated"] == 1
    assert report["tonnage_recorded"] == expected["tonnage_recorded"]
    assert report["state_digest"] == expected["state_digest"]


def test_duplicate_event_id_rows_deduped(tmp_path: Path) -> None:
    """Duplicate event_id rows must apply only once."""
    journal = tmp_path / "dedup.jsonl"
    journal.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seq": 2,
                        "op": "ram_seat",
                        "ram_block_id": "seat_beta_x",
                        "scenario_tag": "dedup",
                        "cycle_epoch": 1,
                        "event_id": "evt-beta",
                    }
                ),
                json.dumps(
                    {
                        "seq": 1,
                        "op": "cycle_arm",
                        "cycle_epoch": 1,
                        "scenario_tag": "dedup",
                    }
                ),
                json.dumps(
                    {
                        "seq": 3,
                        "op": "ram_seat",
                        "ram_block_id": "seat_beta_y",
                        "scenario_tag": "dedup",
                        "cycle_epoch": 1,
                        "event_id": "evt-beta",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    drive_seat(journal, SEAT_LOG, SEAT_REPORT)
    rows = load_ops_rows(SEAT_LOG)
    seated_rows = [r for r in rows if r.get("kind") == "ram_seated"]
    assert len(seated_rows) == 1


def test_cross_run_log_continues_emit_seq(tmp_path: Path) -> None:
    """Appending to an existing seat log must preserve prior bytes and continue seq."""
    log_path = tmp_path / "append_log.jsonl"
    report_a = tmp_path / "report_a.json"
    report_b = tmp_path / "report_b.json"
    drive_seat(FIXTURE_DIR / "run_alpha.jsonl", log_path, report_a)
    prior_log = log_path.read_bytes()
    first_rows = load_ops_rows(log_path)
    first_max = max(int(r["seq"]) for r in first_rows)
    build_driver()
    result = subprocess.run(
        [
            str(EMIT_BIN),
            "--seat",
            str(FIXTURE_DIR / "run_beta.jsonl"),
            "--emit-log",
            str(log_path),
            "--emit-report",
            str(report_b),
        ],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"append run failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    assert log_path.read_bytes().startswith(prior_log)
    all_rows = load_ops_rows(log_path)
    assert int(all_rows[0]["seq"]) == 1
    new_seqs = sorted(int(r["seq"]) for r in all_rows if int(r["seq"]) > first_max)
    assert new_seqs
    assert min(new_seqs) == first_max + 1
    assert len(new_seqs) == len(set(new_seqs))


def test_recovery_preserves_existing_log_prefix(tmp_path: Path) -> None:
    """Recovery replay must not truncate rows already present in the seat log."""
    log_path = tmp_path / "recover_log.jsonl"
    report_path = tmp_path / "recover_report.json"
    preseed = b'{"kind":"seed","scenario_tag":"seed","seq":50}\n'
    log_path.write_bytes(preseed)
    build_driver()
    result = subprocess.run(
        [
            str(EMIT_BIN),
            "--seat-recover",
            str(FIXTURE_DIR / "run_gamma.jsonl"),
            "--emit-log",
            str(log_path),
            "--emit-report",
            str(report_path),
        ],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"recovery failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    rows = load_ops_rows(log_path)
    assert any(int(r["seq"]) == 50 for r in rows)


def test_recovery_continues_after_highest_existing_seq(tmp_path: Path) -> None:
    """Recovery must continue emitted seq values from the highest valid existing row."""
    log_path = tmp_path / "recover_seq_log.jsonl"
    report_path = tmp_path / "recover_seq_report.json"
    prior = (
        b'{"kind":"seed","scenario_tag":"seed","seq":4}\n'
        b'{"kind":"seed","scenario_tag":"seed","seq":80}\n'
        b'{"kind":"seed","scenario_tag":"seed","seq":17}\n'
    )
    log_path.write_bytes(prior)
    result = drive_seat_allow_fail(
        FIXTURE_DIR / "run_gamma.jsonl",
        log_path,
        report_path,
        recover=True,
        preseed_log=prior,
    )
    assert result.returncode == 0
    assert log_path.read_bytes().startswith(prior)
    rows = load_ops_rows(log_path)
    new_seqs = sorted(int(r["seq"]) for r in rows if int(r["seq"]) > 80)
    assert new_seqs
    assert min(new_seqs) == 81
    assert len(new_seqs) == len(set(new_seqs))
    anchor = json.loads((APP / "snapshot" / "compactor_anchor.json").read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert recovery_aborted_at_anchor(report, anchor)


@pytest.mark.parametrize(
    "journal_body,expect_rollback",
    [
        (
            "\n".join(
                [
                    json.dumps(
                        {
                            "seq": 1,
                            "op": "cycle_arm",
                            "cycle_epoch": 1,
                            "scenario_tag": "recover_case",
                        }
                    ),
                    json.dumps(
                        {
                            "seq": 2,
                            "op": "ram_seat",
                            "ram_block_id": "seat_gamma_bad",
                            "scenario_tag": "recover_case",
                            "cycle_epoch": 1,
                        }
                    ),
                ]
            )
            + "\n",
            True,
        ),
        ('{"seq":1,"op":"cycle_arm","cycle_epoch":1,"scenario_tag":"bad"}\n{broken\n', False),
        (
            "\n".join(
                [
                    json.dumps(
                        {
                            "seq": 1,
                            "op": "warp_drive",
                            "cycle_epoch": 1,
                            "scenario_tag": "bad",
                        }
                    )
                ]
            )
            + "\n",
            False,
        ),
        (
            "\n".join(
                [
                    json.dumps(
                        {
                            "seq": 1,
                            "op": "cycle_arm",
                            "cycle_epoch": 1,
                            "scenario_tag": "bad",
                        }
                    ),
                    json.dumps(
                        {
                            "seq": 2,
                            "op": "ram_seat",
                            "ram_block_id": "seat_beta_x",
                            "scenario_tag": "bad",
                            "cycle_epoch": 1,
                        }
                    ),
                    json.dumps(
                        {
                            "seq": 2,
                            "op": "guide_mark",
                            "cycle_epoch": 1,
                            "scenario_tag": "bad",
                        }
                    ),
                ]
            )
            + "\n",
            False,
        ),
    ],
    ids=[
        "cmpr_checksum_failure_rolls_back",
        "malformed_json_is_fatal",
        "unknown_operation_is_fatal",
        "conflicting_seq_is_fatal",
    ],
)
def test_recovery_only_cmpr_failures_trigger_rollback(
    tmp_path: Path, journal_body: str, expect_rollback: bool
) -> None:
    """Only CMPR block read or checksum failures may succeed as recovery rollback."""
    journal = tmp_path / "recover_case.jsonl"
    journal.write_text(journal_body, encoding="utf-8")
    log_path = tmp_path / "recover_case_log.jsonl"
    report_path = tmp_path / "recover_case_report.json"
    prior_log = b'{"kind":"seed","scenario_tag":"seed","seq":9}\n'
    prior_report = (
        b'{"rams_seated":1,"guides_marked":0,"tonnage_recorded":10,'
        b'"state_digest":"abc","rollback_performed":false,"ready":true}\n'
    )
    result = drive_seat_allow_fail(
        journal,
        log_path,
        report_path,
        recover=True,
        preseed_log=prior_log,
        preseed_report=prior_report,
    )
    if expect_rollback:
        assert result.returncode == 0
        report = json.loads(report_path.read_text(encoding="utf-8"))
        anchor = json.loads(
            (APP / "snapshot" / "compactor_anchor.json").read_text(encoding="utf-8")
        )
        assert recovery_aborted_at_anchor(report, anchor)
        assert log_path.read_bytes().startswith(prior_log)
    else:
        assert result.returncode != 0
        assert log_path.read_bytes() == prior_log
        assert report_path.read_bytes() == prior_report
        assert_no_temp_artifacts(tmp_path, log_path, report_path)


def test_direct_nonconsecutive_cycle_epoch_sets_ledger(tmp_path: Path) -> None:
    """cycle_arm must set the active epoch to the journal value without incrementing."""
    journal = tmp_path / "epoch_jump.jsonl"
    journal.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "op": "cycle_arm",
                        "cycle_epoch": 19,
                        "scenario_tag": "epoch_jump",
                    }
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "op": "ram_seat",
                        "ram_block_id": "seat_beta_x",
                        "scenario_tag": "epoch_jump",
                        "cycle_epoch": 19,
                    }
                ),
                json.dumps(
                    {
                        "seq": 3,
                        "op": "guide_clear",
                        "scenario_tag": "epoch_jump",
                        "cycle_epoch": 19,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    drive_seat(journal, SEAT_LOG, SEAT_REPORT)
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    expected = expected_report_object(journal, APP / "data" / "rams")
    assert report["state_digest"] == expected["state_digest"]
    assert report["rams_seated"] == expected["rams_seated"]
    assert report["tonnage_recorded"] == expected["tonnage_recorded"]


def test_normal_publication_failure_restores_both_artifacts(tmp_path: Path) -> None:
    """Normal seat publication failures must restore both final artifacts transactionally."""
    parent_file = tmp_path / "parent_file"
    parent_file.write_text("not-a-directory", encoding="utf-8")
    log_path = parent_file / "seat_log.jsonl"
    report_path = tmp_path / "seat_report.json"
    prior_report = (
        b'{"rams_seated":2,"guides_marked":1,"tonnage_recorded":42,'
        b'"state_digest":"deadbeef","rollback_performed":false,"ready":true}\n'
    )
    report_path.write_bytes(prior_report)
    result = drive_seat_allow_fail(
        FIXTURE_DIR / "run_alpha.jsonl",
        log_path,
        report_path,
        preseed_report=prior_report,
    )
    assert result.returncode != 0
    assert not log_path.exists()
    assert report_path.read_bytes() == prior_report
    assert_no_temp_artifacts(tmp_path, log_path, report_path)


def test_recovery_publication_failure_is_not_successful_rollback(tmp_path: Path) -> None:
    """Recovery publication failure must not masquerade as successful rollback."""
    log_path = tmp_path / "recover_pub_log.jsonl"
    report_path = tmp_path / "report_dir"
    report_path.mkdir()
    prior_log = b'{"kind":"seed","scenario_tag":"seed","seq":3}\n'
    result = drive_seat_allow_fail(
        FIXTURE_DIR / "run_gamma.jsonl",
        log_path,
        report_path,
        recover=True,
        preseed_log=prior_log,
    )
    assert result.returncode != 0
    assert log_path.read_bytes() == prior_log
    assert report_path.is_dir()
    assert not any(report_path.iterdir())
    assert_no_temp_artifacts(tmp_path, log_path, report_path)


def test_live_tonnage_total_exceeds_u32_without_wrapping(tmp_path: Path) -> None:
    """Aggregate tonnage_recorded must preserve sums above u32::MAX without wrapping."""
    ram_root = tmp_path / "rams"
    ram_root.mkdir()
    block_a = ram_root / "wide_a.bin"
    block_b = ram_root / "wide_b.bin"
    write_cmpr_block(block_a, "wide_ram_a", 2_500_000_000)
    write_cmpr_block(block_b, "wide_ram_b", 2_600_000_000)
    journal = tmp_path / "wide_total.jsonl"
    journal.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "seq": 1,
                        "op": "cycle_arm",
                        "cycle_epoch": 1,
                        "scenario_tag": "wide",
                    }
                ),
                json.dumps(
                    {
                        "seq": 2,
                        "op": "ram_seat",
                        "ram_block_id": "wide_a",
                        "scenario_tag": "wide",
                        "cycle_epoch": 1,
                    }
                ),
                json.dumps(
                    {
                        "seq": 3,
                        "op": "ram_seat",
                        "ram_block_id": "wide_b",
                        "scenario_tag": "wide",
                        "cycle_epoch": 1,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    data_root = APP / "data" / "rams"
    orig_wide_a = data_root / "wide_a.bin"
    orig_wide_b = data_root / "wide_b.bin"
    had_a = orig_wide_a.exists()
    had_b = orig_wide_b.exists()
    if had_a:
        orig_a_bytes = orig_wide_a.read_bytes()
    if had_b:
        orig_b_bytes = orig_wide_b.read_bytes()
    try:
        orig_wide_a.write_bytes(block_a.read_bytes())
        orig_wide_b.write_bytes(block_b.read_bytes())
        drive_seat(journal, SEAT_LOG, SEAT_REPORT)
        report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
        assert report["tonnage_recorded"] == 5_100_000_000
        assert report["rams_seated"] == 2
    finally:
        if had_a:
            orig_wide_a.write_bytes(orig_a_bytes)
        else:
            orig_wide_a.unlink(missing_ok=True)
        if had_b:
            orig_wide_b.write_bytes(orig_b_bytes)
        else:
            orig_wide_b.unlink(missing_ok=True)


def test_cache_fingerprint_collision_keeps_distinct_views() -> None:
    """Equal compact fingerprints must not return another ledger's cached shift-table view."""
    build_driver()
    result = subprocess.run(
        [str(EMIT_BIN), "--probe-shift-table"],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"probe failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    payload = json.loads(result.stdout)
    collision_a = payload["collision_a"]
    collision_b = payload["collision_b"]
    truth_a = payload["collision_truth_a"]
    truth_b = payload["collision_truth_b"]
    assert collision_a == truth_a
    assert collision_b == truth_b
    assert collision_a["rams"] != collision_b["rams"]
    assert collision_a["cycle_epoch"] == collision_b["cycle_epoch"]
    assert collision_a["journal_revision"] == collision_b["journal_revision"]


def test_report_matches_complete_expected_object() -> None:
    """Operator report must match an independently computed six-field object exactly."""
    events = FIXTURE_DIR / "run_delta.jsonl"
    drive_seat(events, SEAT_LOG, SEAT_REPORT)
    report = json.loads(SEAT_REPORT.read_text(encoding="utf-8"))
    expected = expected_report_object(events, APP / "data" / "rams")
    assert set(report.keys()) == {
        "rams_seated",
        "guides_marked",
        "tonnage_recorded",
        "state_digest",
        "rollback_performed",
        "ready",
    }
    assert report == expected
