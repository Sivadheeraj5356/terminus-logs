"""Verifier for GMP lot-release integrity attestation governance.

Independent def reference gate expectations live in policy_* helpers below.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auth_eval_driver import attest_release as driver_attest  # noqa: E402
from auth_eval_driver import census as driver_census  # noqa: E402
from auth_eval_driver import attestation_entry  # noqa: E402
from auth_eval_driver import traced_exec as run  # noqa: E402

APP = Path("/app")
ENV = APP / "environment"
BASE = ENV / "metadata" / "base"
STAGE = APP / "state" / "batch-release-snapshot.json"
REPORT = Path("/app/output/batch-release-audit.json")
LEDGER = Path("/app/state/release-auth-ledger.json")
HIDDEN_CLEAN = Path("/opt/verifier-fixtures/batch-release/clean-release")
HIDDEN_EXCURSION = Path("/opt/verifier-fixtures/batch-release/excursion-edge")
HIDDEN_GRACE = Path("/opt/verifier-fixtures/batch-release/grace-edge")
HIDDEN_DOC_SIGNED = Path("/opt/verifier-fixtures/batch-release/doc-signed-trap")
HIDDEN_EM_START = Path("/opt/verifier-fixtures/batch-release/em-start-boundary")


def load(root: Path) -> dict:
    return {
        "batch": json.loads((root / "batch.json").read_text()),
        "policy": json.loads((root / "batch_policy.json").read_text()),
        "qc": json.loads((root / "qc_records.json").read_text()),
        "equipment": json.loads((root / "equipment_status.json").read_text()),
        "environmental": json.loads((root / "environmental_logs.json").read_text()),
        "documentation": json.loads((root / "documentation_manifest.json").read_text()),
    }


def ordinal(text: str) -> int:
    """Day number matching the release policy calendar ordinal rule."""
    y, m, d = map(int, text.split("-"))
    a = (14 - m) // 12
    y = y + 4800 - a
    m = m + 12 * a - 3
    return d + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def stable_digest(parts: list[str]) -> str:
    v = 14695981039346656037
    for part in sorted(parts):
        for b in part.encode():
            v ^= b
            v = (v * 1099511628211) & 0xFFFFFFFFFFFFFFFF
        v ^= 10
        v = (v * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"batch-fnv64-{v:016x}"


def seal_bytes(data: bytes) -> str:
    v = 14695981039346656037
    for b in data:
        v ^= b
        v = (v * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"batch-fnv64-{v:016x}"


def digest_parts(meta: dict) -> list[str]:
    batch = meta["batch"]
    policy = meta["policy"]
    parts = [
        f"b|{batch['batch_id']}|{batch['product_code']}|{batch['manufacturing_start']}|{batch['manufacturing_end']}",
        f"p|{policy['batch_id']}|{policy['em_monitoring_days']}",
    ]
    for q in meta["qc"]:
        parts.append(f"q|{q['test_id']}|{q['status']}|{q['signed_off']}")
    for e in meta["equipment"]:
        parts.append(
            f"e|{e['equipment_id']}|{e['status']}|{e['calibration_expires']}|{str(e['used_in_batch']).lower()}"
        )
    for env in meta["environmental"]:
        parts.append(
            f"v|{env['reading_id']}|{env['observed_at']}|{str(env['excursion']).lower()}|{str(env['resolved']).lower()}"
        )
    for d in meta["documentation"]:
        parts.append(f"d|{d['doc_type']}|{d['status']}|{d['version']}")
    return sorted(parts)


def in_em_window(observed: str, batch: dict, policy: dict) -> bool:
    obs = ordinal(observed)
    start = ordinal(batch["manufacturing_start"])
    end = ordinal(batch["evaluation_date"])
    window_start = end - int(policy["em_monitoring_days"])
    return obs >= start and obs <= end and obs >= window_start


def policy_gate_decisions(meta: dict) -> list[dict]:
    batch = meta["batch"]
    policy = meta["policy"]
    gates: list[dict] = []

    qc_blockers: list[str] = []
    approved = {r["test_id"] for r in meta["qc"] if r["status"] == "approved"}
    for test in policy["required_qc_tests"]:
        if test not in approved:
            qc_blockers.append(f"missing-qc:{test}")
    mfg_end = ordinal(batch["manufacturing_end"])
    for rec in meta["qc"]:
        if rec["status"] == "approved" and ordinal(rec["signed_off"]) > mfg_end:
            qc_blockers.append(f"late-signoff:{rec['test_id']}")
    qc_blockers = sorted(set(qc_blockers))
    gates.append({"gate": "qc", "passed": not qc_blockers, "blockers": qc_blockers})

    eq_blockers: list[str] = []
    eval_day = ordinal(batch["evaluation_date"])
    grace = int(policy["equipment_grace_days"])
    for row in meta["equipment"]:
        if not row["used_in_batch"]:
            continue
        if row["status"] != "released":
            eq_blockers.append(f"equipment-not-released:{row['equipment_id']}")
        if ordinal(row["calibration_expires"]) + grace < eval_day:
            eq_blockers.append(f"calibration-expired:{row['equipment_id']}")
    eq_blockers = sorted(set(eq_blockers))
    gates.append({"gate": "equipment", "passed": not eq_blockers, "blockers": eq_blockers})

    env_blockers: list[str] = []
    for row in meta["environmental"]:
        if (
            in_em_window(row["observed_at"], batch, policy)
            and row["excursion"]
            and not row["resolved"]
        ):
            env_blockers.append(f"open-excursion:{row['reading_id']}")
    env_blockers = sorted(set(env_blockers))
    gates.append({"gate": "environmental", "passed": not env_blockers, "blockers": env_blockers})

    doc_blockers: list[str] = []
    approved_docs = {d["doc_type"] for d in meta["documentation"] if d["status"] == "approved"}
    for doc in policy["required_doc_types"]:
        if doc not in approved_docs:
            doc_blockers.append(f"missing-doc:{doc}")
    doc_blockers = sorted(set(doc_blockers))
    gates.append({"gate": "documentation", "passed": not doc_blockers, "blockers": doc_blockers})

    gates.sort(key=lambda g: g["gate"])
    return gates


def policy_snapshot(meta: dict) -> dict:
    gates = policy_gate_decisions(meta)
    return {
        "schema_version": 1,
        "batch_id": meta["batch"]["batch_id"],
        "generated_at": meta["policy"]["generated_at"],
        "metadata_digest": stable_digest(digest_parts(meta)),
        "gate_results": gates,
    }


def policy_report(meta: dict, snap: dict, stage_bytes: bytes, evaluation_seq: int) -> dict:
    gates = snap["gate_results"]
    passed = sum(1 for g in gates if g["passed"])
    failed = len(gates) - passed
    release_ready = all(g["passed"] for g in gates)
    env_gate = next(g for g in gates if g["gate"] == "environmental")
    return {
        "schema_version": 1,
        "batch_id": meta["batch"]["batch_id"],
        "release_ready": release_ready,
        "status": "released" if release_ready else "hold",
        "gate_results": gates,
        "summary": {
            "gates_passed": passed,
            "gates_failed": failed,
            "qc_tests_required": len(meta["policy"]["required_qc_tests"]),
            "qc_tests_approved": sum(1 for r in meta["qc"] if r["status"] == "approved"),
            "equipment_units": sum(1 for e in meta["equipment"] if e["used_in_batch"]),
            "equipment_released": sum(
                1 for e in meta["equipment"] if e["used_in_batch"] and e["status"] == "released"
            ),
            "environmental_excursions_open": len(env_gate["blockers"]),
            "documentation_required": len(meta["policy"]["required_doc_types"]),
            "documentation_approved": sum(
                1 for d in meta["documentation"] if d["status"] == "approved"
            ),
        },
        "metadata_digest": snap["metadata_digest"],
        "staging_seal": seal_bytes(stage_bytes),
        "evaluation_seq": evaluation_seq,
    }


def reset_ledger() -> None:
    if LEDGER.exists():
        LEDGER.unlink()


def run_issuance(args: list[str], env: dict | None = None) -> Any:
    """Invoke a documented integrity attestation issuance mode."""
    return run([str(part) for part in args], env=env)


def run_eval(metadata: Path, stage: Path, report: Path, env: dict | None = None) -> Any:
    return driver_attest(metadata, stage, report, env=env)


def test_attestation_entry_exists():
    """The documented integrity attestation entry must be present under /app/bin."""
    entry = attestation_entry()
    assert entry.is_file(), f"missing attestation entry {entry}"


def test_census_base_counts():
    """census on base dossier reports expected evidence counts."""
    proc = driver_census(BASE)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["batch_id"] == "LOT-PHX-2406-A"
    assert payload["qc_count"] == 4
    assert payload["equipment_count"] == 3


def test_attest_release_writes_artifacts():
    """attest-release must write snapshot, ledger, and trust attestation at the documented paths."""
    reset_ledger()
    if STAGE.exists():
        STAGE.unlink()
    if REPORT.exists():
        REPORT.unlink()
    proc = run_eval(BASE, STAGE, REPORT)
    assert STAGE.is_file(), proc.stderr
    assert REPORT.is_file(), proc.stderr
    assert LEDGER.is_file(), proc.stderr
    assert STAGE.as_posix() == "/app/state/batch-release-snapshot.json"
    assert REPORT.as_posix() == "/app/output/batch-release-audit.json"
    assert LEDGER.as_posix() == "/app/state/release-auth-ledger.json"
    assert proc.returncode == 1


def test_base_snapshot_matches_integrity_model():
    """Staging snapshot for base dossier must match independent integrity-model gates."""
    reset_ledger()
    stage = APP / "state" / "ref-stage.json"
    report = APP / "output" / "ref-report.json"
    run_eval(BASE, stage, report)
    meta = load(BASE)
    expected = policy_snapshot(meta)
    actual = json.loads(stage.read_text())
    assert actual == expected


def test_base_report_matches_integrity_model():
    """Trust attestation for base dossier must match independent integrity-model summary including seal and seq."""
    reset_ledger()
    stage = APP / "state" / "ref-report-stage.json"
    report = APP / "output" / "ref-report-out.json"
    run_eval(BASE, stage, report)
    meta = load(BASE)
    snap = policy_snapshot(meta)
    expected = policy_report(meta, snap, stage.read_bytes(), 1)
    actual = json.loads(report.read_text())
    assert actual == expected
    assert actual["release_ready"] is False
    assert actual["status"] == "hold"
    assert actual["status"] not in {"ready", "blocked"}


def test_qc_gate_blockers_base():
    """Base dossier QC gate must flag missing sterility approval."""
    reset_ledger()
    stage = APP / "state" / "qc-stage.json"
    report = APP / "output" / "qc-report.json"
    run_eval(BASE, stage, report)
    actual = json.loads(stage.read_text())
    qc = next(g for g in actual["gate_results"] if g["gate"] == "qc")
    assert "missing-qc:sterility" in qc["blockers"]


def test_equipment_calibration_blocker_base():
    """Base dossier equipment gate must flag expired calibration on used equipment."""
    reset_ledger()
    stage = APP / "state" / "eq-stage.json"
    report = APP / "output" / "eq-report.json"
    run_eval(BASE, stage, report)
    actual = json.loads(stage.read_text())
    eq = next(g for g in actual["gate_results"] if g["gate"] == "equipment")
    assert "calibration-expired:FILL-02" in eq["blockers"]


def test_environmental_open_excursion_base():
    """Base dossier environmental gate must flag in-window unresolved excursions only."""
    reset_ledger()
    stage = APP / "state" / "env-stage.json"
    report = APP / "output" / "env-report.json"
    run_eval(BASE, stage, report)
    actual = json.loads(stage.read_text())
    env = next(g for g in actual["gate_results"] if g["gate"] == "environmental")
    assert "open-excursion:EM-118" in env["blockers"]
    assert "open-excursion:EM-050" not in env["blockers"]


def test_documentation_gate_passes_base():
    """Base dossier documentation gate passes when all required docs are approved."""
    reset_ledger()
    stage = APP / "state" / "doc-stage.json"
    report = APP / "output" / "doc-report.json"
    run_eval(BASE, stage, report)
    actual = json.loads(stage.read_text())
    doc = next(g for g in actual["gate_results"] if g["gate"] == "documentation")
    assert doc["passed"] is True


def test_gate_results_sorted():
    """gate_results must be sorted by gate name ascending."""
    reset_ledger()
    stage = APP / "state" / "sorted-stage.json"
    report = APP / "output" / "sorted-report.json"
    run_eval(BASE, stage, report)
    gates = json.loads(stage.read_text())["gate_results"]
    names = [g["gate"] for g in gates]
    assert names == sorted(names)


def test_idempotent_gate_math_with_seq_advance():
    """Repeated attest-release keeps snapshot gate math stable while evaluation_seq advances."""
    reset_ledger()
    stage = APP / "state" / "idem-stage.json"
    report = APP / "output" / "idem-report.json"
    run_eval(BASE, stage, report)
    first_snap = json.loads(stage.read_text())
    first_report = json.loads(report.read_text())
    assert first_report["evaluation_seq"] == 1
    run_eval(BASE, stage, report)
    second_snap = json.loads(stage.read_text())
    second_report = json.loads(report.read_text())
    assert second_snap["gate_results"] == first_snap["gate_results"]
    assert second_snap["metadata_digest"] == first_snap["metadata_digest"]
    assert second_report["evaluation_seq"] == 2
    assert second_report["staging_seal"] == seal_bytes(stage.read_bytes())
    ledger = json.loads(LEDGER.read_text())
    assert ledger["evaluation_seq"] == 2


def test_metadata_dir_override_absolute():
    """BATCH_METADATA_DIR must override --metadata when set to an absolute path."""
    reset_ledger()
    stage = APP / "state" / "override-stage.json"
    report = APP / "output" / "override-report.json"
    env = os.environ.copy()
    env["BATCH_METADATA_DIR"] = str(Path("/opt/verifier-fixtures/batch-release/clean-release"))
    proc = run_eval(BASE, stage, report, env=env)
    meta = load(Path("/opt/verifier-fixtures/batch-release/clean-release"))
    expected = policy_report(meta, policy_snapshot(meta), stage.read_bytes(), 1)
    assert json.loads(report.read_text()) == expected
    assert proc.returncode == 0


def test_hidden_clean_release_ready():
    """Hidden clean-release fixture under /opt/verifier-fixtures must attest as release_ready true."""
    reset_ledger()
    stage = APP / "state" / "clean-stage.json"
    report = APP / "output" / "clean-report.json"
    hidden_dir = Path("/opt/verifier-fixtures/batch-release/clean-release")
    proc = run_eval(hidden_dir, stage, report)
    payload = json.loads(report.read_text())
    assert payload["release_ready"] is True
    assert payload["status"] == "released"
    assert payload["staging_seal"] == seal_bytes(stage.read_bytes())
    assert proc.returncode == 0


def test_hidden_excursion_window_trap():
    """Hidden excursion-edge under /opt/verifier-fixtures must ignore pre-mfg excursions but block in-window ones."""
    reset_ledger()
    stage = APP / "state" / "exc-stage.json"
    report = APP / "output" / "exc-report.json"
    hidden_dir = Path("/opt/verifier-fixtures/batch-release/excursion-edge")
    run_eval(hidden_dir, stage, report)
    meta = load(hidden_dir)
    env = next(g for g in policy_gate_decisions(meta) if g["gate"] == "environmental")
    assert "open-excursion:EM-PRE" not in env["blockers"]
    assert "open-excursion:EM-IN" in env["blockers"]
    actual_env = next(
        g for g in json.loads(stage.read_text())["gate_results"] if g["gate"] == "environmental"
    )
    assert actual_env == env


def test_hidden_grace_boundary_release_ready():
    """Hidden grace-edge under /opt/verifier-fixtures: calibration plus grace equals evaluation_date stays release-ready."""
    reset_ledger()
    stage = APP / "state" / "grace-stage.json"
    report = APP / "output" / "grace-report.json"
    hidden_dir = Path("/opt/verifier-fixtures/batch-release/grace-edge")
    proc = run_eval(hidden_dir, stage, report)
    payload = json.loads(report.read_text())
    eq = next(g for g in payload["gate_results"] if g["gate"] == "equipment")
    assert not any(b.startswith("calibration-expired:") for b in eq["blockers"])
    assert payload["release_ready"] is True
    assert payload["status"] == "released"
    assert proc.returncode == 0


def test_compact_json_trailing_newline():
    """Report file must be compact JSON with a single trailing newline."""
    reset_ledger()
    stage = APP / "state" / "compact-stage.json"
    report = APP / "output" / "compact-report.json"
    run_eval(BASE, stage, report)
    raw = report.read_text()
    assert raw.endswith("\n")
    assert "\n\n" not in raw
    assert "  " not in raw.splitlines()[0]


def test_relative_metadata_override_fails():
    """Relative BATCH_METADATA_DIR must exit with usage error code 2."""
    proc = run_issuance(
        [
            str(attestation_entry()),
            "attest-release",
            "--metadata",
            str(BASE),
            "--stage",
            str(STAGE),
            "--output",
            str(REPORT),
        ],
        env={**os.environ, "BATCH_METADATA_DIR": "relative/path"},
    )
    assert proc.returncode == 2


def test_equipment_not_released_ignored_for_spare():
    """Equipment rows with used_in_batch false must not add equipment gate blockers."""
    reset_ledger()
    stage = APP / "state" / "spare-stage.json"
    report = APP / "output" / "spare-report.json"
    run_eval(BASE, stage, report)
    eq = next(g for g in json.loads(stage.read_text())["gate_results"] if g["gate"] == "equipment")
    assert not any(b.startswith("equipment-not-released:STORE-09") for b in eq["blockers"])
    assert not any(b.startswith("calibration-expired:STORE-09") for b in eq["blockers"])


def test_late_signoff_blocker_when_qc_approved_after_mfg_end():
    """QC approved after manufacturing_end must add a late-signoff blocker."""
    reset_ledger()
    tmp = APP / "state" / "late-signoff-meta"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(BASE, tmp)
    qc = json.loads((tmp / "qc_records.json").read_text())
    for row in qc:
        if row["test_id"] == "sterility":
            row["status"] = "approved"
            row["signed_off"] = "2024-06-15"
    (tmp / "qc_records.json").write_text(json.dumps(qc) + "\n")
    meta = load(tmp)
    qc_gate = next(g for g in policy_gate_decisions(meta) if g["gate"] == "qc")
    assert "late-signoff:sterility" in qc_gate["blockers"]
    assert "missing-qc:sterility" not in qc_gate["blockers"]

    stage = APP / "state" / "late-signoff-stage.json"
    report = APP / "output" / "late-signoff-report.json"
    proc = run_eval(tmp, stage, report)
    assert proc.returncode == 1
    actual = json.loads(report.read_text())
    actual_qc = next(g for g in actual["gate_results"] if g["gate"] == "qc")
    assert "late-signoff:sterility" in actual_qc["blockers"]
    assert "missing-qc:sterility" not in actual_qc["blockers"]


def test_staging_seal_matches_on_disk_bytes():
    """staging_seal must seal the exact on-disk staging snapshot bytes after attest-release."""
    reset_ledger()
    stage = APP / "state" / "seal-stage.json"
    report = APP / "output" / "seal-report.json"
    run_eval(BASE, stage, report)
    payload = json.loads(report.read_text())
    assert payload["staging_seal"] == seal_bytes(stage.read_bytes())
    assert payload["metadata_digest"] == json.loads(stage.read_text())["metadata_digest"]


def test_ledger_persists_last_digest():
    """Authorization ledger must persist last_batch_id and last_digest after attest-release."""
    reset_ledger()
    stage = APP / "state" / "ledger-stage.json"
    report = APP / "output" / "ledger-report.json"
    run_eval(BASE, stage, report)
    snap = json.loads(stage.read_text())
    ledger = json.loads(LEDGER.read_text())
    assert ledger["schema_version"] == 1
    assert ledger["last_batch_id"] == snap["batch_id"]
    assert ledger["last_digest"] == snap["metadata_digest"]
    assert ledger["evaluation_seq"] == 1


def test_hidden_doc_signed_not_approved():
    """Hidden doc-signed-trap: status signed must not satisfy required documentation types."""
    reset_ledger()
    stage = APP / "state" / "doc-signed-stage.json"
    report = APP / "output" / "doc-signed-report.json"
    proc = run_eval(HIDDEN_DOC_SIGNED, stage, report)
    meta = load(HIDDEN_DOC_SIGNED)
    expected_doc = next(g for g in policy_gate_decisions(meta) if g["gate"] == "documentation")
    assert expected_doc["passed"] is False
    assert any(b.startswith("missing-doc:") for b in expected_doc["blockers"])
    actual = json.loads(report.read_text())
    actual_doc = next(g for g in actual["gate_results"] if g["gate"] == "documentation")
    assert actual_doc == expected_doc
    assert actual["release_ready"] is False
    assert actual["status"] == "hold"
    assert proc.returncode == 1


def test_hidden_em_start_boundary_blocks():
    """Hidden em-start-boundary: open excursion on manufacturing_start must block release."""
    reset_ledger()
    stage = APP / "state" / "em-start-stage.json"
    report = APP / "output" / "em-start-report.json"
    proc = run_eval(HIDDEN_EM_START, stage, report)
    meta = load(HIDDEN_EM_START)
    expected_env = next(g for g in policy_gate_decisions(meta) if g["gate"] == "environmental")
    assert "open-excursion:EM-START" in expected_env["blockers"]
    actual_env = next(
        g for g in json.loads(stage.read_text())["gate_results"] if g["gate"] == "environmental"
    )
    assert actual_env == expected_env
    payload = json.loads(report.read_text())
    assert payload["release_ready"] is False
    assert payload["status"] == "hold"
    assert proc.returncode == 1


def test_metadata_digest_uses_inter_part_lf():
    """metadata_digest must include the documented ASCII LF inter-part FNV step."""
    reset_ledger()
    stage = APP / "state" / "digest-lf-stage.json"
    report = APP / "output" / "digest-lf-report.json"
    run_eval(BASE, stage, report)
    meta = load(BASE)
    parts = digest_parts(meta)
    with_lf = stable_digest(parts)
    # Naive FNV without inter-part LF must not match the contract digest.
    v = 14695981039346656037
    for part in sorted(parts):
        for b in part.encode():
            v ^= b
            v = (v * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    without_lf = f"batch-fnv64-{v:016x}"
    assert with_lf != without_lf
    snap = json.loads(stage.read_text())
    assert snap["metadata_digest"] == with_lf
    assert snap["metadata_digest"] != without_lf
