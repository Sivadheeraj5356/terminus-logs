"""Verifier for PAM lockout authority restoration after cutover drift.

Tests rebuild and replay from live ctl/rt planes. Expected security outcomes
are derived from desk packets under /app/data/corp/. C decision sources must
remain untouched.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
OUT = APP / "output" / "pam_lockout_report.json"
PACK_PATH = APP / "config" / "default_pack.json"
TAPE_DIR = APP / "data" / "tapes"
LEDGER_DIR = APP / "var" / "tally"
CORP = APP / "data" / "corp"
BUILD = APP / "scripts" / "build.sh"
REPLAY = APP / "tools" / "auth_tape_replay"
PLANE_A = APP / "ctl" / "p_a.json"
OPTS = APP / "rt" / "opts.json"
EXPORT_ENV = APP / "rt" / "export_env.sh"

DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
AUDIT_FIELDS = (
    "conversation_id",
    "lockout_active",
    "retry_count",
    "expired_account",
    "stack_binding",
    "binding_rows",
)

STACKS = [
    {"id": "sshd-stack", "service": "sshd", "modules": ["common-auth", "pam_unix", "pam_sss"]},
    {"id": "sudo-stack", "service": "sudo", "modules": ["common-auth", "pam_unix", "pam_wheel"]},
    {"id": "portal-stack", "service": "portal", "modules": ["common-auth", "pam_unix", "pam_otp"]},
    {"id": "su-stack", "service": "su", "modules": ["common-auth", "pam_rootok", "pam_unix"]},
]

C_GUARD_PAIRS = [
    (APP / "cfg" / "load_cfg.c", Path(__file__).resolve().parent / "support" / "c_guard" / "cfg" / "load_cfg.c"),
    (APP / "fail" / "c3_tally.c", Path(__file__).resolve().parent / "support" / "c_guard" / "fail" / "c3_tally.c"),
    (APP / "acct" / "e1_gate.c", Path(__file__).resolve().parent / "support" / "c_guard" / "acct" / "e1_gate.c"),
    (APP / "bind" / "s9_row.c", Path(__file__).resolve().parent / "support" / "c_guard" / "bind" / "s9_row.c"),
    (APP / "canon" / "n4_norm.c", Path(__file__).resolve().parent / "support" / "c_guard" / "canon" / "n4_norm.c"),
    (APP / "lock" / "r2_span.c", Path(__file__).resolve().parent / "support" / "c_guard" / "lock" / "r2_span.c"),
    (APP / "audit" / "run_tape.c", Path(__file__).resolve().parent / "support" / "c_guard" / "audit" / "run_tape.c"),
]


def run_checked(cmd: list[str], *, timeout: int = 180) -> None:
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(cmd)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def desk_deny() -> int:
    chain = json.loads((CORP / "deny_chain.json").read_text(encoding="utf-8"))
    return next(int(link["deny"]) for link in chain["links"] if link.get("tip"))


def desk_modules() -> list[str]:
    desk = json.loads((CORP / "module_desk.json").read_text(encoding="utf-8"))
    return list(next(c["modules"] for c in desk["candidates"] if c.get("active")))


def desk_carry() -> dict[str, int]:
    desk = json.loads((CORP / "carry_desk.json").read_text(encoding="utf-8"))
    return {row["slug"]: int(row["failures"]) for row in desk["rows"] if row.get("active")}


def desk_accounts() -> dict[str, dict]:
    desk = json.loads((CORP / "roster_desk.json").read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for row in desk["principals"]:
        if row.get("tip"):
            out[row["actor"]] = {"expiry": int(row["expiry"])}
    return out


def desk_realm_mode() -> str:
    desk = json.loads((CORP / "roster_desk.json").read_text(encoding="utf-8"))
    return str(desk["realm_mode_tip"])


def _canon_actor(actor: str) -> str:
    if "@" not in actor:
        return actor
    left, realm = actor.rsplit("@", 1)
    if desk_realm_mode() == "lower":
        return f"{left}@{realm.lower()}"
    return actor


def _ledger_slug(actor: str) -> str:
    return actor.split("@", 1)[0].lower()


def _ledger_failures(actor: str) -> int:
    slug = _ledger_slug(actor)
    carry = desk_carry()
    if slug in carry:
        return carry[slug]
    return 0


def _failed_prompt_count(events: list[dict]) -> int:
    actor = events[0]["actor"] if events else ""
    counted = set(desk_modules())
    tally = sum(
        1 for ev in events if ev.get("result") == "fail" and ev.get("module") in counted
    )
    return tally + _ledger_failures(actor)


def _is_expired(actor: str, ts: int) -> bool:
    key = _canon_actor(actor)
    expiry = desk_accounts().get(key, {}).get("expiry", 999999999)
    return ts >= expiry


def _lockout_active(tally: int) -> bool:
    return tally >= desk_deny()


def _stack_for_service(service: str) -> str:
    for row in STACKS:
        if row["service"] == service:
            return row["id"]
    return ""


def _stack_modules(stack_id: str) -> list[str]:
    for row in STACKS:
        if row["id"] == stack_id:
            return list(row["modules"])
    return []


def _binding_rows(events: list[dict], modules: list[str]) -> list[dict]:
    actor = events[0]["actor"] if events else ""
    canon = _canon_actor(actor)
    by_mod = {ev["module"]: ev for ev in events}
    rows: list[dict] = []
    for mod in modules:
        if mod in by_mod:
            ok = by_mod[mod]["result"] == "ok"
            rows.append(
                {
                    "canon_actor": canon,
                    "module_tag": mod,
                    "bound": ok,
                    "reason": "ok" if ok else "mismatch",
                }
            )
        else:
            rows.append(
                {
                    "canon_actor": canon,
                    "module_tag": mod,
                    "bound": False,
                    "reason": "missing",
                }
            )
    rows.sort(key=lambda r: r["module_tag"])
    return rows


def _load_tape(tape_id: str) -> list[dict]:
    rows = []
    for line in (TAPE_DIR / f"{tape_id}.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _digest_of(body: dict) -> str:
    pre = json.dumps(body, separators=(",", ":"), sort_keys=True)
    return __import__("hashlib").sha256(pre.encode()).hexdigest()


def _reference_audit(tape_id: str) -> dict:
    events = _load_tape(tape_id)
    terminal = events[-1]["service"]
    tally = _failed_prompt_count(events)
    stack_id = _stack_for_service(terminal)
    modules = _stack_modules(stack_id)
    body = {
        "conversation_id": tape_id,
        "lockout_active": _lockout_active(tally),
        "retry_count": tally,
        "expired_account": _is_expired(events[0]["actor"], events[0]["ts"]),
        "stack_binding": stack_id,
        "binding_rows": _binding_rows(events, modules),
    }
    body["digest_hex"] = _digest_of(body)
    return body


def _pack_order() -> list[str]:
    cfg = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    return list(cfg["tapes"])


def _submitted_body(row: dict) -> dict:
    return {field: row[field] for field in AUDIT_FIELDS}


def _by_id(report: dict) -> dict[str, dict]:
    return {row["conversation_id"]: row for row in report["audits"]}


def _read_ledger(slug: str) -> int:
    path = LEDGER_DIR / f"{slug}.tally"
    if not path.exists():
        return 0
    failures = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("failures="):
            failures = int(line.split("=", 1)[1].split()[0])
    return failures


def assert_c_untouched() -> None:
    for live, golden in C_GUARD_PAIRS:
        assert live.read_bytes() == golden.read_bytes(), f"C source mutated: {live}"


def assert_runtime_posture() -> None:
    """Secure runtime defaults only — kept off the session critical path so a
    missed export default does not zero every tape assertion."""
    opts = json.loads(OPTS.read_text(encoding="utf-8"))
    assert opts.get("bind_digest") is True
    assert opts.get("honor_legacy_overrides") is False
    assert opts.get("probe_implies_lockout") is False
    assert opts.get("reject_blanket_lockout") is True
    assert opts.get("reject_single_stack_papering") is True
    assert EXPORT_ENV.is_file()
    # Source the export script with PAM_* unset so defaults apply; accept any
    # shell form that yields the secure values (not a specific ${…:-N} spelling).
    clean_env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in (
            "PAM_HONOR_OVERRIDE",
            "PAM_PROBE_IMPLIES_LOCK",
            "PAM_BIND_DIGEST",
            "PAM_REALM_FOLD",
        )
    }
    sourced = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{EXPORT_ENV}" && '
            'printf "%s\\n" "$PAM_HONOR_OVERRIDE" '
            '"$PAM_PROBE_IMPLIES_LOCK" "$PAM_BIND_DIGEST"',
        ],
        text=True,
        capture_output=True,
        env=clean_env,
        check=False,
    )
    assert sourced.returncode == 0, sourced.stderr
    honor, probe, digest = sourced.stdout.strip().splitlines()
    assert honor == "0"
    assert probe == "0"
    assert digest == "1"


def rebuild_and_replay() -> dict:
    run_checked(["bash", str(BUILD)], timeout=180)
    out_dir = APP / "output"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_checked(["python3", str(REPLAY)], timeout=120)
    return json.loads(OUT.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def report() -> dict:
    # Rebuild first so partial authority restoration can still score tape tests.
    # C-source rewrite remains a hard fail for the whole session.
    assert_c_untouched()
    doc = rebuild_and_replay()
    assert_c_untouched()
    return doc


class TestPamLockoutAuthority:
    def test_report_schema_and_order(self, report: dict) -> None:
        """Report lists audits in pack order with every audit field correct."""
        assert "audits" in report and "summary" in report
        names = [r["conversation_id"] for r in report["audits"]]
        assert names == _pack_order()
        for row in report["audits"]:
            exp = _reference_audit(row["conversation_id"])
            for field in AUDIT_FIELDS:
                assert field in row
                assert row[field] == exp[field], (
                    f"{row['conversation_id']}.{field}: {row[field]!r} != {exp[field]!r}"
                )

    def test_row_digests_recomputed(self, report: dict) -> None:
        """Each digest_hex recomputes from the submitted row's own audit fields."""
        for row in report["audits"]:
            assert DIGEST_RE.match(row.get("digest_hex", ""))
            recomputed = _digest_of(_submitted_body(row))
            assert row["digest_hex"] == recomputed
            assert row["digest_hex"] == _reference_audit(row["conversation_id"])["digest_hex"]

    def test_clean_pass_tape(self, report: dict) -> None:
        """Successful sshd tape stays unlocked after phantom ledger cleanup."""
        row = _by_id(report)["clean_pass"]
        exp = _reference_audit("clean_pass")
        assert row["lockout_active"] is False
        assert row["retry_count"] == exp["retry_count"]
        assert _read_ledger("alice") == 0

    def test_retry_block_tape(self, report: dict) -> None:
        """Repeated counted failures trip faillock under the tip deny threshold."""
        row = _by_id(report)["retry_block"]
        exp = _reference_audit("retry_block")
        assert row["lockout_active"] is True
        assert row["retry_count"] == exp["retry_count"]
        assert row["retry_count"] >= desk_deny()
        assert row["binding_rows"] == exp["binding_rows"]

    def test_stale_ledger_carryover(self, report: dict) -> None:
        """Active carryover failures plus one new prompt trip lockout."""
        row = _by_id(report)["stale_ledger"]
        exp = _reference_audit("stale_ledger")
        assert row["lockout_active"] == exp["lockout_active"]
        assert row["retry_count"] == exp["retry_count"]
        assert _read_ledger("ian") == desk_carry()["ian"]

    def test_otp_ok_and_fail(self, report: dict) -> None:
        """Portal otp stack binds correctly; failed otp increments counted tally."""
        ok = _by_id(report)["otp_ok"]
        fail = _by_id(report)["otp_fail"]
        assert ok["stack_binding"] == "portal-stack"
        assert ok["binding_rows"] == _reference_audit("otp_ok")["binding_rows"]
        assert fail["retry_count"] == _reference_audit("otp_fail")["retry_count"]
        assert _read_ledger("dave") == 0

    def test_expired_boundaries(self, report: dict) -> None:
        """Tip roster marks expired_acct and expiry_edge expired inclusively."""
        expired = _by_id(report)["expired_acct"]
        edge = _by_id(report)["expiry_edge"]
        assert expired["expired_account"] is True
        assert edge["expired_account"] is True
        events = _load_tape("expiry_edge")
        assert events[0]["ts"] == desk_accounts()["eve@corp.example.com"]["expiry"]

    def test_terminal_stack_bindings(self, report: dict) -> None:
        """Terminal services bind via wiring table without force-map hijacks."""
        by_id = _by_id(report)
        assert by_id["ssh_bind"]["stack_binding"] == "sshd-stack"
        assert by_id["sudo_bind"]["stack_binding"] == "sudo-stack"
        assert by_id["su_bind"]["stack_binding"] == "su-stack"
        assert by_id["otp_ok"]["stack_binding"] == "portal-stack"
        assert by_id["mixed_svc"]["stack_binding"] == _reference_audit("mixed_svc")["stack_binding"]

    def test_su_missing_rootok(self, report: dict) -> None:
        """Su conversation marks pam_rootok missing and stays unlocked."""
        row = _by_id(report)["su_bind"]
        exp = _reference_audit("su_bind")
        assert row["binding_rows"] == exp["binding_rows"]
        by_mod = {r["module_tag"]: r for r in row["binding_rows"]}
        assert by_mod["pam_rootok"]["reason"] == "missing"
        assert by_mod["pam_rootok"]["bound"] is False
        assert row["lockout_active"] is False
        assert _read_ledger("leo") == 0

    def test_sss_noise_excluded(self, report: dict) -> None:
        """pam_sss failures do not inflate retry_count under the signed count pack."""
        row = _by_id(report)["sss_noise"]
        exp = _reference_audit("sss_noise")
        assert "pam_sss" not in desk_modules()
        assert row["retry_count"] == exp["retry_count"]
        assert row["lockout_active"] is False
        assert row["retry_count"] < desk_deny()
        assert _read_ledger("kate") == 0

    def test_deny_threshold_edge(self, report: dict) -> None:
        """Exactly tip-deny counted fails locks the conversation."""
        row = _by_id(report)["deny_edge"]
        assert row["retry_count"] == desk_deny()
        assert row["lockout_active"] is True

    def test_canon_actor_realm_folded(self, report: dict) -> None:
        """binding_rows canon_actor follows tip realm fold polarity."""
        for tape_id in ("clean_pass", "su_bind", "sss_noise"):
            row = _by_id(report)[tape_id]
            for br in row["binding_rows"]:
                assert br["canon_actor"] == _canon_actor(br["canon_actor"])
                if desk_realm_mode() == "lower":
                    assert "@CORP." not in br["canon_actor"]

    def test_ledger_hygiene_and_anti_papering(self, report: dict) -> None:
        """Active desk carry mirrored on disk; phantoms zeroed; no blanket papering.

        Plane B/C tip polarity and runtime export posture are scored by the tape
        / probe tests — this gate stays on durable ledger hygiene only.
        """
        plane_a = json.loads(PLANE_A.read_text(encoding="utf-8"))
        carry = {k: int(v) for k, v in plane_a.get("carryover", {}).items()}
        tip = desk_carry()
        for slug, expected in tip.items():
            assert carry.get(slug) == expected, f"plane carry {slug}"
            assert _read_ledger(slug) == expected, f"durable tally {slug}"
        for slug in ("alice", "kate", "leo", "carol", "frank", "grace"):
            if slug in carry:
                assert carry[slug] == 0, f"phantom plane carry {slug}"
            if (LEDGER_DIR / f"{slug}.tally").exists():
                assert _read_ledger(slug) == 0, f"phantom tally {slug}"
        locked = [r for r in report["audits"] if r.get("lockout_active") is True]
        unlocked = [r for r in report["audits"] if r.get("lockout_active") is False]
        assert len(locked) >= 3
        assert len(unlocked) >= 3
        assert _by_id(report)["clean_pass"]["lockout_active"] is False
        assert _by_id(report)["sss_noise"]["lockout_active"] is False
        assert _by_id(report)["su_bind"]["lockout_active"] is False

    def test_summary_guard(self, report: dict) -> None:
        """Summary passes the pack guard and total_lockouts matches locked rows."""
        summary = report["summary"]
        assert summary["audited_count"] == len(_pack_order())
        assert summary["pack_ok"] is True
        locked = sum(1 for r in report["audits"] if r.get("lockout_active") is True)
        assert summary["total_lockouts"] == locked
        expected_locked = sum(
            1 for tape_id in _pack_order() if _reference_audit(tape_id)["lockout_active"]
        )
        assert summary["total_lockouts"] == expected_locked
        assert expected_locked >= 3

    def test_probe_does_not_imply_authority(self, report: dict) -> None:
        """Stack probe CLEAN must not substitute for restored lockout authority."""
        assert_runtime_posture()
        probe = subprocess.run(
            ["bash", str(APP / "scripts" / "stack_probe.sh")],
            text=True,
            capture_output=True,
            check=False,
        )
        assert probe.returncode == 0
        assert "CLEAN" in probe.stdout
        assert report["summary"]["pack_ok"] is True
        assert json.loads(OPTS.read_text(encoding="utf-8")).get("probe_implies_lockout") is False
