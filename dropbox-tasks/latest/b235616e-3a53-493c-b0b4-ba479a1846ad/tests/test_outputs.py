"""Verifier for the bayctl account-lock journal workflow."""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest

APP_ROOT = Path("/app")
BAYCTL = APP_ROOT / "bin" / "bayctl"
LEDGER = APP_ROOT / "output" / "lock_ledger.json"
AUDIT = APP_ROOT / "output" / "lock_audit.json"
STATE_DIR = APP_ROOT / "state"
JOURNAL_ROOT = STATE_DIR / "journal"
GENERATED_FROM = "baylock-lock-v2"
AUDIT_GENERATED_FROM = "baylock-audit-v1"
SEED_SCENARIO = APP_ROOT / "data" / "scenarios" / "seed.json"
MULTI_SCENARIO = APP_ROOT / "data" / "scenarios" / "multi.json"
TRUNC_SCENARIO = APP_ROOT / "data" / "scenarios" / "truncate.json"
SEED_BATCH = APP_ROOT / "data" / "batches" / "seed.jsonl"
LEGACY_BATCH = APP_ROOT / "data" / "batches" / "legacy.jsonl"
# Matches FailureLimit in /app/internal/domain/models.go
FAILURE_LIMIT = 3
MAX_FAILURE_CAP = 99

EVENT_ID_RE = re.compile(r"^LE-[A-Z0-9]{6}$")
REPLICA_RE = re.compile(r"^REP-[A-Z0-9]{3,6}$")
PRINCIPAL_RE = re.compile(r"^[a-z][a-z0-9-]{2,31}$")

REJECTION_RANKS = {
    "missing_required": 1,
    "unexpected_fields": 2,
    "invalid_types": 3,
    "invalid_event_id": 4,
    "invalid_principal": 5,
    "invalid_view_id": 6,
    "invalid_operation": 7,
    "invalid_logical_time": 8,
    "invalid_seq": 9,
    "invalid_replica": 10,
    "invalid_amount": 11,
    "missing_target": 12,
    "invalid_target": 13,
    "invalid_expires_at": 14,
    "invalid_epoch": 15,
    "duplicate_event_id": 16,
    "stale_seq": 17,
    "principal_suspended": 18,
    "principal_not_suspended": 19,
    "resume_replica_mismatch": 20,
    "revert_self": 21,
    "revert_replica_mismatch": 22,
    "revert_cross_principal": 23,
    "revert_target_missing": 24,
    "revert_target_not_applied": 25,
    "revert_already_reversed": 26,
    "revert_invalid_target": 27,
    "grace_target_missing": 28,
    "grace_invalid_target": 29,
}

if not SEED_SCENARIO.is_file():
    pytest.skip("task data is only available inside the task container", allow_module_level=True)


def ledger_digest(body: dict) -> str:
    payload = {k: v for k, v in body.items() if k != "ledger_digest"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audit_digest(body: dict) -> str:
    payload = {k: v for k, v in body.items() if k != "audit_digest"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def reset_state() -> None:
    for path in (STATE_DIR, APP_ROOT / "output"):
        if path.exists():
            shutil.rmtree(path)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (APP_ROOT / "output").mkdir(parents=True, exist_ok=True)
    (JOURNAL_ROOT / "batches").mkdir(parents=True, exist_ok=True)


def write_scenario(principal: str, password: str) -> Path:
    payload = {"principal": principal, "password": password, "bad_rounds": 3}
    fd, name = tempfile.mkstemp(suffix=".json", dir="/tmp")
    path = Path(name)
    with open(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


def write_batch(events: list[dict]) -> Path:
    fd, name = tempfile.mkstemp(suffix=".jsonl", dir="/tmp")
    path = Path(name)
    with open(fd, "w", encoding="utf-8") as handle:
        for ev in events:
            handle.write(json.dumps(ev, separators=(",", ":")) + "\n")
    return path


def run_setup(scenario: Path) -> None:
    subprocess.run([str(BAYCTL), "setup", "--scenario", str(scenario)], check=True, cwd=APP_ROOT)


def run_ingest(batch: str, events: Path) -> None:
    subprocess.run(
        [str(BAYCTL), "ingest", "--batch", batch, "--events", str(events)],
        check=True,
        cwd=APP_ROOT,
    )


def run_rebuild() -> None:
    subprocess.run([str(BAYCTL), "rebuild"], check=True, cwd=APP_ROOT)


def run_attempt(password: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(BAYCTL), "attempt", "--password", password],
        cwd=APP_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def run_enter_ns() -> None:
    subprocess.run([str(BAYCTL), "enter-ns"], check=True, cwd=APP_ROOT)


def run_unlock(principal: str) -> None:
    subprocess.run([str(BAYCTL), "unlock", "--principal", principal], check=True, cwd=APP_ROOT)


def run_report() -> dict:
    subprocess.run(
        [str(BAYCTL), "report", "--out", str(LEDGER)],
        check=True,
        cwd=APP_ROOT,
    )
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def run_audit() -> dict:
    subprocess.run(
        [str(BAYCTL), "audit", "--out", str(AUDIT)],
        check=True,
        cwd=APP_ROOT,
    )
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def view_for(ledger: dict, view_id: str, principal: str) -> dict | None:
    for row in ledger.get("views", []):
        if row["view_id"] == view_id and row["principal"] == principal:
            return row
    return None


def ensure_runtime(principal: str = "journal-user", password: str = "pw") -> None:
    runtime = {
        "active_view": "host",
        "principal": principal,
        "password": password,
        "attempt_count": 0,
        "audit_seq": 0,
        "audits": [],
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8")


def assert_ledger_valid(ledger: dict, principal: str) -> None:
    assert ledger["generated_from"] == GENERATED_FROM
    for key in (
        "attempt_count",
        "failure_total",
        "event_line_count",
        "applied_count",
        "rejected_count",
    ):
        assert isinstance(ledger[key], int)
    assert isinstance(ledger["projection_digest"], str)
    views = ledger["views"]
    audits = ledger["audits"]
    assert isinstance(views, list)
    assert isinstance(audits, list)
    host = view_for(ledger, "host", principal)
    ns = view_for(ledger, "ns", principal)
    assert host is not None
    assert ns is not None
    assert host["failure_count"] == ns["failure_count"]
    assert host["locked"] == ns["locked"]
    assert host["failure_count"] == ledger["failure_total"]
    seqs = [row["seq"] for row in audits]
    assert seqs == sorted(seqs)
    for row in audits:
        for key in ("view_id", "principal", "actor_ref", "seq"):
            assert key in row
        assert row["actor_ref"].startswith(f"{row['view_id']}:")
    digest = ledger_digest(ledger)
    assert ledger["ledger_digest"] == digest


def bad_attempts(count: int, password: str = "wrong") -> None:
    for _ in range(count):
        run_attempt(password)


def switch_principal(principal: str, password: str) -> None:
    runtime_path = STATE_DIR / "runtime.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime["principal"] = principal
    runtime["password"] = password
    runtime["attempt_count"] = 0
    runtime_path.write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8")


def parse_time(raw: str) -> datetime:
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


@dataclass
class PrincipalState:
    failures: int = 0
    locked: bool = False
    suspended: bool = False
    suspended_by: str = ""
    epoch: int = 1


@dataclass
class FoldState:
    principals: dict[str, PrincipalState] = field(default_factory=dict)
    applied: dict[str, dict] = field(default_factory=dict)
    rejected_ids: set[str] = field(default_factory=set)
    reversed: set[str] = field(default_factory=set)
    seq_highwater: dict[tuple[str, str], int] = field(default_factory=dict)
    grace_expires: dict[str, str] = field(default_factory=dict)
    seen: dict[str, dict] = field(default_factory=dict)
    applied_count: int = 0
    rejected_count: int = 0
    skipped: int = 0


def _reject(state: FoldState, event_id: str, reason: str) -> None:
    state.rejected_count += 1
    if event_id:
        state.rejected_ids.add(event_id)


def reference_fold(events: list[dict]) -> dict[str, PrincipalState]:
    """Independent Python fold mirroring correct pol engine semantics."""
    state = FoldState()
    indexed = list(enumerate(events))
    indexed.sort(key=lambda item: (parse_time(item[1]["logical_time"]), item[1]["event_id"], item[0]))
    watermark = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def ensure(principal: str) -> PrincipalState:
        return state.principals.setdefault(principal, PrincipalState())

    for _, ev in indexed:
        event_id = ev["event_id"].upper()
        op = ev["operation"].upper()
        principal = ev.get("principal", "")
        replica = ev["source_replica"].upper()
        seq = int(ev["seq"])
        lt = parse_time(ev["logical_time"])
        if lt > watermark:
            watermark = lt

        canon = json.dumps(ev, sort_keys=True, separators=(",", ":"))
        if event_id in state.seen:
            if state.seen[event_id] != canon:
                _reject(state, event_id, "duplicate_event_id")
            else:
                state.skipped += 1
            continue
        state.seen[event_id] = canon

        ps = state.principals.get(principal, PrincipalState())
        attempt_like = op in {"FAILED_ATTEMPT", "GRACE_HOLD", "CORRECTION_TALLY", "LOCKOUT_CLEAR"}
        if attempt_like and ps.suspended:
            _reject(state, event_id, "principal_suspended")
            continue
        if op == "ENFORCE_RESUME":
            if not ps.suspended:
                _reject(state, event_id, "principal_not_suspended")
                continue
            if ps.suspended_by and ps.suspended_by != replica:
                _reject(state, event_id, "resume_replica_mismatch")
                continue
        sk = (principal, replica)
        if seq <= state.seq_highwater.get(sk, 0):
            _reject(state, event_id, "stale_seq")
            continue
        if op == "REVERT_ATTEMPT":
            target_id = ev["target_event_id"].upper()
            if target_id == event_id:
                _reject(state, event_id, "revert_self")
                continue
            if target_id in state.reversed:
                _reject(state, event_id, "revert_already_reversed")
                continue
            target = state.applied.get(target_id)
            if target is None:
                reason = (
                    "revert_target_not_applied"
                    if target_id in state.rejected_ids
                    else "revert_target_missing"
                )
                _reject(state, event_id, reason)
                continue
            if target["source_replica"].upper() != replica:
                _reject(state, event_id, "revert_replica_mismatch")
                continue
            if target.get("principal") != principal:
                _reject(state, event_id, "revert_cross_principal")
                continue
            if target["operation"].upper() != "FAILED_ATTEMPT":
                _reject(state, event_id, "revert_invalid_target")
                continue
        if op == "GRACE_RELEASE":
            target_id = ev["target_event_id"].upper()
            if target_id not in state.grace_expires:
                _reject(state, event_id, "grace_target_missing")
                continue

        ps = ensure(principal)
        if op == "FAILED_ATTEMPT":
            ps.failures += 1
            ps.locked = ps.failures >= FAILURE_LIMIT
        elif op == "LOCKOUT_CLEAR":
            ps.failures = 0
            ps.locked = False
        elif op == "GRACE_HOLD":
            state.grace_expires[event_id] = ev["expires_at"]
        elif op == "GRACE_RELEASE":
            state.grace_expires.pop(ev["target_event_id"].upper(), None)
        elif op == "REVERT_ATTEMPT":
            if ps.failures > 0:
                ps.failures -= 1
            ps.locked = ps.failures >= FAILURE_LIMIT
            state.reversed.add(ev["target_event_id"].upper())
        elif op == "CORRECTION_TALLY":
            ps.failures = int(ev["amount"])
            ps.locked = ps.failures >= FAILURE_LIMIT
        elif op == "ENFORCE_SUSPEND":
            ps.suspended = True
            ps.suspended_by = replica
        elif op == "ENFORCE_RESUME":
            ps.suspended = False
            ps.suspended_by = ""
        elif op == "EPOCH_CARRY":
            ps.failures = min(ps.failures * 2, MAX_FAILURE_CAP)
            ps.locked = ps.failures >= FAILURE_LIMIT
            for eid, _ in list(state.grace_expires.items()):
                applied = state.applied.get(eid)
                if applied and applied.get("principal") == principal:
                    del state.grace_expires[eid]
            ps.epoch = int(ev["epoch"])

        state.applied[event_id] = ev
        state.seq_highwater[sk] = seq
        state.applied_count += 1

    exp_rows = []
    for eid, exp_str in state.grace_expires.items():
        if eid in state.reversed:
            continue
        applied = state.applied.get(eid)
        if not applied or applied["operation"].upper() != "GRACE_HOLD":
            continue
        exp = parse_time(exp_str)
        if watermark >= exp:
            exp_rows.append((exp, eid, applied["principal"]))
    exp_rows.sort(key=lambda row: (row[0], row[1]))
    for _, eid, principal in exp_rows:
        ps = ensure(principal)
        ps.failures += 1
        ps.locked = ps.failures >= FAILURE_LIMIT
        del state.grace_expires[eid]

    return state.principals


def test_live_cross_view_enforcement() -> None:
    """Host and namespace views must agree after enter-ns and live attempts."""
    reset_state()
    run_setup(SEED_SCENARIO)
    bad_attempts(FAILURE_LIMIT)
    run_enter_ns()
    result = run_attempt("s3cret-host")
    assert "attempt rejected" in result.stdout
    ledger = run_report()
    assert_ledger_valid(ledger, "operator-a")
    host = view_for(ledger, "host", "operator-a")
    ns = view_for(ledger, "ns", "operator-a")
    assert host is not None and ns is not None
    assert host["locked"] is True
    assert ns["locked"] is True


def test_multi_principal_isolation() -> None:
    """Interleaved principals must keep independent authoritative counters."""
    reset_state()
    run_setup(SEED_SCENARIO)
    bad_attempts(2)
    multi = json.loads(MULTI_SCENARIO.read_text(encoding="utf-8"))
    switch_principal(multi["principal"], multi["password"])
    bad_attempts(FAILURE_LIMIT)
    ledger = run_report()
    assert_ledger_valid(ledger, "operator-b")
    b = view_for(ledger, "host", "operator-b")
    assert b is not None
    assert b["failure_count"] == FAILURE_LIMIT
    assert b["locked"] is True
    auth_a = STATE_DIR / "auth" / "operator-a.tally"
    assert auth_a.is_file()
    tally_a = json.loads(auth_a.read_text(encoding="utf-8"))
    assert tally_a["failures"] == 2
    assert tally_a["locked"] is False
    switch_principal("operator-a", "s3cret-host")
    ledger_a = run_report()
    assert_ledger_valid(ledger_a, "operator-a")
    a = view_for(ledger_a, "host", "operator-a")
    assert a is not None
    assert a["failure_count"] == 2
    assert a["locked"] is False


def test_journal_durable_prefix_recovery(tmp_path: Path) -> None:
    """Truncated batch tails must not poison durable journal replay."""
    reset_state()
    events = [
        {
            "event_id": "LE-TRN001",
            "principal": "trunc-user",
            "operation": "PRINCIPAL_BIND",
            "logical_time": "2026-02-01T08:00:00Z",
            "seq": 1,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-TRN002",
            "principal": "trunc-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-02-01T09:00:00Z",
            "seq": 2,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-TRN003",
            "principal": "trunc-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-02-01T09:01:00Z",
            "seq": 3,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-TRN004",
            "principal": "trunc-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-02-01T09:02:00Z",
            "seq": 4,
            "source_replica": "REP-HOST1",
        },
    ]
    batch = write_batch(events)
    try:
        run_ingest("trunc", batch)
        batch_file = JOURNAL_ROOT / "batches" / "trunc.jsonl"
        data = batch_file.read_bytes()
        corrupt_tail = b'{"event_id":"LE-BROKEN","operation":"FAILED_ATT'
        batch_file.write_bytes(data + corrupt_tail)
        run_rebuild()
        tally_path = STATE_DIR / "auth" / "trunc-user.tally"
        assert tally_path.is_file()
        tally = json.loads(tally_path.read_text(encoding="utf-8"))
        assert tally["failures"] == FAILURE_LIMIT
        assert tally["locked"] is True
    finally:
        batch.unlink(missing_ok=True)


def test_idempotent_ingest_and_rebuild() -> None:
    """Re-import and double-rebuild must not change semantic projection."""
    reset_state()
    ensure_runtime("operator-a", "s3cret-host")
    run_ingest("seed", SEED_BATCH)
    run_rebuild()
    first = run_report()
    run_ingest("seed", SEED_BATCH)
    run_rebuild()
    run_rebuild()
    second = run_report()
    assert first["projection_digest"] == second["projection_digest"]
    assert first["applied_count"] == second["applied_count"]


def test_legacy_tally_migration() -> None:
    """Legacy tally_v0 rows must merge into authoritative auth store on rebuild."""
    reset_state()
    run_ingest("legacy", LEGACY_BATCH)
    run_rebuild()
    auth_path = STATE_DIR / "auth" / "operator-legacy.tally"
    assert auth_path.is_file()
    tally = json.loads(auth_path.read_text(encoding="utf-8"))
    assert tally["failures"] >= FAILURE_LIMIT
    assert tally["locked"] is True
    host_shadow = STATE_DIR / "views" / "host" / "operator-legacy.tally"
    ns_shadow = STATE_DIR / "views" / "ns" / "operator-legacy.tally"
    assert host_shadow.is_file()
    assert ns_shadow.is_file()
    host = json.loads(host_shadow.read_text(encoding="utf-8"))
    ns = json.loads(ns_shadow.read_text(encoding="utf-8"))
    assert host["failures"] == ns["failures"] == tally["failures"]


def test_chronological_replay_order(tmp_path: Path) -> None:
    """Replay must follow logical_time order, not file order."""
    reset_state()
    events = [
        {
            "event_id": "LE-ORD002",
            "principal": "order-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-03-01T10:00:00Z",
            "seq": 2,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-ORD001",
            "principal": "order-user",
            "operation": "LOCKOUT_CLEAR",
            "logical_time": "2026-03-01T09:00:00Z",
            "seq": 1,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-ORD003",
            "principal": "order-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-03-01T11:00:00Z",
            "seq": 3,
            "source_replica": "REP-HOST1",
        },
    ]
    batch = write_batch(events)
    try:
        run_ingest("order", batch)
        run_rebuild()
        expected = reference_fold(events)
        tally_path = STATE_DIR / "auth" / "order-user.tally"
        tally = json.loads(tally_path.read_text(encoding="utf-8"))
        assert tally["failures"] == expected["order-user"].failures
        assert tally["locked"] == expected["order-user"].locked
    finally:
        batch.unlink(missing_ok=True)


def test_generated_principal_live_workflow() -> None:
    """Generated principals through live workflow must produce valid digests."""
    reset_state()
    rng = random.Random(44012)
    principal = f"gen-{rng.randint(1000, 9999)}"
    password = f"pw-{rng.randint(1000, 9999)}"
    scenario = write_scenario(principal, password)
    try:
        run_setup(scenario)
        rounds = rng.randint(3, 5)
        bad_attempts(rounds)
        run_enter_ns()
        run_unlock(principal)
        bad_attempts(1)
        ledger = run_report()
        assert_ledger_valid(ledger, principal)
        assert ledger["failure_total"] in {0, 1}
    finally:
        scenario.unlink(missing_ok=True)


def test_unlock_idempotent_digest() -> None:
    """Repeated unlock must be idempotent and keep digest stable."""
    reset_state()
    run_setup(SEED_SCENARIO)
    bad_attempts(FAILURE_LIMIT)
    run_unlock("operator-a")
    first = run_report()
    assert_ledger_valid(first, "operator-a")
    run_unlock("operator-a")
    second = run_report()
    assert_ledger_valid(second, "operator-a")
    assert second["ledger_digest"] == first["ledger_digest"]
    host = view_for(second, "host", "operator-a")
    assert host is not None
    assert host["locked"] is False
    assert host["failure_count"] == 0


def test_truncated_shadow_ignored() -> None:
    """Truncated shadow tally files must not break authoritative enforcement."""
    reset_state()
    run_setup(TRUNC_SCENARIO)
    bad_attempts(2)
    shadow = STATE_DIR / "views" / "host" / "operator-c.tally"
    assert shadow.is_file()
    data = shadow.read_bytes()
    shadow.write_bytes(data[: max(1, len(data) // 2)])
    bad_attempts(1)
    run_enter_ns()
    ledger = run_report()
    assert_ledger_valid(ledger, "operator-c")
    assert ledger["failure_total"] >= FAILURE_LIMIT


def test_audit_trail_consistency() -> None:
    """Audit trail digests must match rebuilt projection and journal."""
    reset_state()
    ensure_runtime("operator-a", "s3cret-host")
    run_ingest("seed", SEED_BATCH)
    run_rebuild()
    ledger = run_report()
    trail = run_audit()
    assert trail["generated_from"] == AUDIT_GENERATED_FROM
    assert trail["projection_digest"] == ledger["projection_digest"]
    assert trail["batch_count"] >= 1
    assert trail["audit_digest"] == audit_digest(trail)


def test_restart_persistence_across_cli(tmp_path: Path) -> None:
    """State must survive separate ingest/rebuild/report invocations."""
    reset_state()
    rng = random.Random(99123)
    principal = f"dyn-{rng.randint(1000, 9999)}"
    ensure_runtime(principal, "dyn-pw")
    event_id = f"LE-{rng.randint(100000, 999999):06d}"[-9:]
    if not EVENT_ID_RE.match(event_id):
        event_id = "LE-DYN001"
    events = [
        {
            "event_id": event_id,
            "principal": principal,
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-04-01T08:00:00Z",
            "seq": 1,
            "source_replica": "REP-HOST1",
        },
    ]
    batch = write_batch(events)
    try:
        run_ingest("dyn", batch)
        run_rebuild()
        expected = reference_fold(events)
        auth_path = STATE_DIR / "auth" / f"{principal}.tally"
        assert auth_path.is_file()
        tally = json.loads(auth_path.read_text(encoding="utf-8"))
        assert tally["failures"] == expected[principal].failures
        run_report()
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        assert ledger["applied_count"] >= 1
    finally:
        batch.unlink(missing_ok=True)


def test_grace_hold_expiration_after_rebuild() -> None:
    """Grace holds must convert to strikes when expires_at <= rebuild watermark."""
    reset_state()
    ensure_runtime("grace-user", "pw")
    events = [
        {
            "event_id": "LE-GRC001",
            "principal": "grace-user",
            "operation": "GRACE_HOLD",
            "logical_time": "2026-05-01T09:00:00Z",
            "seq": 1,
            "source_replica": "REP-HOST1",
            "expires_at": "2026-05-01T10:00:00Z",
        },
        {
            "event_id": "LE-GRC002",
            "principal": "grace-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-05-01T10:00:00Z",
            "seq": 2,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-GRC003",
            "principal": "grace-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-05-01T10:01:00Z",
            "seq": 3,
            "source_replica": "REP-HOST1",
        },
    ]
    batch = write_batch(events)
    try:
        run_ingest("grace", batch)
        run_rebuild()
        expected = reference_fold(events)
        tally = json.loads((STATE_DIR / "auth" / "grace-user.tally").read_text(encoding="utf-8"))
        assert tally["failures"] == expected["grace-user"].failures
        assert tally["failures"] == 3
        assert tally["locked"] is True
    finally:
        batch.unlink(missing_ok=True)


def test_revert_attempt_out_of_order_ingest() -> None:
    """REVERT_ATTEMPT must apply after chronological FAILED_ATTEMPT despite file order."""
    reset_state()
    ensure_runtime("rev-user", "pw")
    events = [
        {
            "event_id": "LE-REV002",
            "principal": "rev-user",
            "operation": "REVERT_ATTEMPT",
            "logical_time": "2026-05-02T11:00:00Z",
            "seq": 2,
            "source_replica": "REP-HOST1",
            "target_event_id": "LE-REV001",
        },
        {
            "event_id": "LE-REV001",
            "principal": "rev-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-05-02T10:00:00Z",
            "seq": 1,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-REV003",
            "principal": "rev-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-05-02T12:00:00Z",
            "seq": 3,
            "source_replica": "REP-HOST1",
        },
    ]
    batch = write_batch(events)
    try:
        run_ingest("revert", batch)
        run_rebuild()
        expected = reference_fold(events)
        tally = json.loads((STATE_DIR / "auth" / "rev-user.tally").read_text(encoding="utf-8"))
        assert tally["failures"] == expected["rev-user"].failures
        assert tally["failures"] == 1
        assert tally["locked"] is False
    finally:
        batch.unlink(missing_ok=True)


def test_enforce_suspend_blocks_until_resume() -> None:
    """ENFORCE_SUSPEND rejects attempts until matching ENFORCE_RESUME."""
    reset_state()
    ensure_runtime("sus-user", "pw")
    events = [
        {
            "event_id": "LE-SUS001",
            "principal": "sus-user",
            "operation": "ENFORCE_SUSPEND",
            "logical_time": "2026-05-03T09:00:00Z",
            "seq": 1,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-SUS002",
            "principal": "sus-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-05-03T09:30:00Z",
            "seq": 2,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-SUS003",
            "principal": "sus-user",
            "operation": "ENFORCE_RESUME",
            "logical_time": "2026-05-03T10:00:00Z",
            "seq": 3,
            "source_replica": "REP-OTHER",
        },
        {
            "event_id": "LE-SUS004",
            "principal": "sus-user",
            "operation": "ENFORCE_RESUME",
            "logical_time": "2026-05-03T10:05:00Z",
            "seq": 4,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-SUS005",
            "principal": "sus-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-05-03T10:10:00Z",
            "seq": 5,
            "source_replica": "REP-HOST1",
        },
    ]
    batch = write_batch(events)
    try:
        run_ingest("suspend", batch)
        run_rebuild()
        expected = reference_fold(events)
        tally = json.loads((STATE_DIR / "auth" / "sus-user.tally").read_text(encoding="utf-8"))
        assert tally["failures"] == expected["sus-user"].failures
        assert tally["failures"] == 1
        ledger = run_report()
        assert ledger["rejected_count"] >= 2
    finally:
        batch.unlink(missing_ok=True)


def test_epoch_carry_doubles_failures() -> None:
    """EPOCH_CARRY doubles failures, caps at 99, and clears grace holds."""
    reset_state()
    ensure_runtime("epoch-user", "pw")
    events = [
        {
            "event_id": "LE-EPC001",
            "principal": "epoch-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-05-04T09:00:00Z",
            "seq": 1,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-EPC002",
            "principal": "epoch-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-05-04T09:01:00Z",
            "seq": 2,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-EPC003",
            "principal": "epoch-user",
            "operation": "GRACE_HOLD",
            "logical_time": "2026-05-04T09:02:00Z",
            "seq": 3,
            "source_replica": "REP-HOST1",
            "expires_at": "2026-05-04T12:00:00Z",
        },
        {
            "event_id": "LE-EPC004",
            "principal": "epoch-user",
            "operation": "EPOCH_CARRY",
            "logical_time": "2026-05-04T09:03:00Z",
            "seq": 4,
            "source_replica": "REP-HOST1",
            "epoch": 2,
        },
    ]
    batch = write_batch(events)
    try:
        run_ingest("epoch", batch)
        run_rebuild()
        expected = reference_fold(events)
        tally = json.loads((STATE_DIR / "auth" / "epoch-user.tally").read_text(encoding="utf-8"))
        assert tally["failures"] == expected["epoch-user"].failures
        assert tally["failures"] == 4
        assert tally["locked"] is True
    finally:
        batch.unlink(missing_ok=True)


def test_anti_hardcoding_generated_batches() -> None:
    """Random journal batches must match independent reference_fold tallies."""
    reset_state()
    rng = random.Random(778811)
    principal = f"ah-{rng.randint(1000, 9999)}"
    ensure_runtime(principal, "ah-pw")
    events: list[dict] = []
    seq = 0
    for i in range(6):
        seq += 1
        events.append(
            {
                "event_id": f"LE-AH{1000 + i:03d}"[-9:],
                "principal": principal,
                "operation": "FAILED_ATTEMPT",
                "view_id": "host",
                "logical_time": f"2026-06-01T{10 + i:02d}:00:00Z",
                "seq": seq,
                "source_replica": "REP-HOST1",
            }
        )
    if rng.random() > 0.2:
        seq += 1
        events.append(
            {
                "event_id": "LE-AHREV1",
                "principal": principal,
                "operation": "REVERT_ATTEMPT",
                "logical_time": "2026-06-01T16:30:00Z",
                "seq": seq,
                "source_replica": "REP-HOST1",
                "target_event_id": events[0]["event_id"],
            }
        )
    batch = write_batch(events)
    try:
        run_ingest("anti", batch)
        run_rebuild()
        expected = reference_fold(events)
        tally = json.loads((STATE_DIR / "auth" / f"{principal}.tally").read_text(encoding="utf-8"))
        assert tally["failures"] == expected[principal].failures
        assert tally["locked"] == expected[principal].locked
    finally:
        batch.unlink(missing_ok=True)


def test_delayed_validation_corrupt_after_rebuild() -> None:
    """Corrupt rows must surface via rejected_count only after rebuild+report."""
    reset_state()
    ensure_runtime("delay-user", "pw")
    events = [
        {
            "event_id": "BAD!",
            "principal": "delay-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-07-01T09:00:00Z",
            "seq": 1,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-DLY001",
            "principal": "delay-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-07-01T09:01:00Z",
            "seq": 1,
            "source_replica": "REP-HOST1",
        },
    ]
    batch = write_batch(events)
    try:
        run_ingest("delay", batch)
        assert not (STATE_DIR / "auth" / "delay-user.tally").is_file()
        run_rebuild()
        ledger = run_report()
        assert ledger["rejected_count"] >= 1
        assert ledger["applied_count"] >= 1
        tally = json.loads((STATE_DIR / "auth" / "delay-user.tally").read_text(encoding="utf-8"))
        assert tally["failures"] == 1
    finally:
        batch.unlink(missing_ok=True)


def test_shuffled_batch_ingest_same_digest() -> None:
    """Shuffled ingest order for the same events must yield the same projection digest."""
    reset_state()
    ensure_runtime("shuf-user", "pw")
    base = [
        {
            "event_id": "LE-SHF001",
            "principal": "shuf-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-08-01T09:00:00Z",
            "seq": 1,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-SHF002",
            "principal": "shuf-user",
            "operation": "FAILED_ATTEMPT",
            "view_id": "host",
            "logical_time": "2026-08-01T10:00:00Z",
            "seq": 2,
            "source_replica": "REP-HOST1",
        },
        {
            "event_id": "LE-SHF003",
            "principal": "shuf-user",
            "operation": "LOCKOUT_CLEAR",
            "logical_time": "2026-08-01T08:00:00Z",
            "seq": 1,
            "source_replica": "REP-AAA",
        },
    ]
    batch_a = write_batch(base)
    shuffled = list(base)
    random.Random(42).shuffle(shuffled)
    batch_b = write_batch(shuffled)
    try:
        run_ingest("shuf-a", batch_a)
        run_rebuild()
        first = run_report()
        reset_state()
        ensure_runtime("shuf-user", "pw")
        run_ingest("shuf-b", batch_b)
        run_rebuild()
        second = run_report()
        assert first["projection_digest"] == second["projection_digest"]
        assert first["applied_count"] == second["applied_count"]
        expected = reference_fold(base)
        tally = json.loads((STATE_DIR / "auth" / "shuf-user.tally").read_text(encoding="utf-8"))
        assert tally["failures"] == expected["shuf-user"].failures
    finally:
        batch_a.unlink(missing_ok=True)
        batch_b.unlink(missing_ok=True)
