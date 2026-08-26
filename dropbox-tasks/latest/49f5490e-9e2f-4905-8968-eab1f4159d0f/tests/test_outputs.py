"""Verifier suite for pam-stack-recovery-token-order."""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
AUTHCTL = APP_ROOT / "bin" / "authctl"
RECOVERY_PROOF = APP_ROOT / "reports" / "recovery-proof.json"
PUBLIC_LAB = APP_ROOT / "work" / "public"
LOGIN_POLICY = APP_ROOT / "policy" / "login.policy"
LOGIN_RUNTIME = APP_ROOT / "runtime" / "pam.d" / "login.conf"


def run(
    cmd: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=APP_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def sha256_file(path: Path) -> str:
    proc = run(
        ["openssl", "dgst", "-sha256", "-r", str(path)],
        check=True,
    )
    return proc.stdout.strip().split()[0]


def expect_allow(*args: str) -> None:
    run([str(AUTHCTL), "login", *args])


def expect_deny(*args: str) -> None:
    proc = run([str(AUTHCTL), "login", *args], check=False)
    if proc.returncode == 0:
        raise AssertionError(f"expected denied login: {' '.join(args)}")


def assert_line(text: str, expected: str) -> None:
    if expected not in text.splitlines():
        raise AssertionError(f"missing line {expected!r} in snapshot:\n{text}")


def snapshot(root: Path, user: str) -> str:
    proc = run([str(AUTHCTL), "snapshot", "--root", str(root), "--user", user])
    return proc.stdout


def parse_audit_counts(snapshot_text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in snapshot_text.splitlines():
        if not line.startswith("audit."):
            continue
        key, _, value = line.partition("=")
        counts[key.removeprefix("audit.")] = int(value)
    return counts


def prepare_hidden_lab(root: Path, suffix: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    fixtures = root / "fixtures"
    pamd = root / "pam.d"
    fixtures.mkdir(parents=True, exist_ok=True)
    pamd.mkdir(parents=True, exist_ok=True)
    (fixtures / "users.db").write_text(
        textwrap.dedent(
            f"""\
            ordinary-{suffix}|ordinary-pass|auth_err
            legacy-{suffix}|legacy-pass|auth_err
            delegated-{suffix}|delegated-pass|ignore
            """
        )
    )
    (fixtures / "tokens.db").write_text(
        textwrap.dedent(
            f"""\
            L-COLLIDE-{suffix}|legacy-{suffix}|legacy-collision
            L-MAIN-{suffix}|legacy-{suffix}|legacy-main
            D-COLLIDE-{suffix}|delegated-{suffix}|delegated-collision
            D-MAIN-{suffix}|delegated-{suffix}|delegated-main
            """
        )
    )
    for conf in (APP_ROOT / "runtime" / "pam.d").glob("*.conf"):
        (pamd / conf.name).write_text(conf.read_text())
    run([str(AUTHCTL), "bootstrap", "--root", str(root)])


def corrupt_user_projections(root: Path, user: str) -> None:
    def rewrite(path: Path, transform) -> None:
        lines = path.read_text().splitlines()
        tmp = path.with_suffix(path.suffix + ".tmp-test")
        tmp.write_text("\n".join(transform(lines)) + "\n")
        tmp.replace(path)

    def faillock(lines: list[str]) -> list[str]:
        out = []
        for line in lines:
            parts = line.split("|")
            if parts and parts[0] == user:
                parts[1] = "99"
                parts[2] = "true"
            out.append("|".join(parts))
        return out

    def tokens(lines: list[str]) -> list[str]:
        out = []
        for line in lines:
            parts = line.split("|")
            if len(parts) > 1 and parts[1] == user:
                parts[3] = "fresh"
                parts[4] = "0"
            out.append("|".join(parts))
        return out

    def sessions(lines: list[str]) -> list[str]:
        out = []
        for line in lines:
            parts = line.split("|")
            if len(parts) > 1 and parts[1] == user:
                parts[3] = "true"
                parts[5] = "0"
            out.append("|".join(parts))
        return out

    def audit(lines: list[str]) -> list[str]:
        return [line for line in lines if line.split("|")[2] != user]

    rewrite(root / "state" / "faillock.db", faillock)
    rewrite(root / "state" / "tokens.db", tokens)
    rewrite(root / "state" / "sessions.db", sessions)
    rewrite(root / "state" / "audit.log", audit)


def assert_rebuild_restores(root: Path, user: str, expected: str) -> None:
    journal = root / "state" / "journal.log"
    journal_before = sha256_file(journal)
    corrupt_user_projections(root, user)
    run([str(AUTHCTL), "rebuild", "--root", str(root)])
    journal_after = sha256_file(journal)
    if journal_before != journal_after:
        raise AssertionError(f"rebuild changed journal for {user}")
    actual = snapshot(root, user)
    if expected != actual:
        raise AssertionError(f"rebuild did not restore projections for {user}")


def assert_recovery_proof_report(proof: dict) -> None:
    for field in ("policy_source_sha256", "policy_runtime_sha256"):
        if field not in proof:
            raise AssertionError(f"missing proof report field {field!r}")

    if proof["policy_source_sha256"] != sha256_file(LOGIN_POLICY):
        raise AssertionError("policy_source_sha256 does not match /app/policy/login.policy")
    if proof["policy_runtime_sha256"] != sha256_file(LOGIN_RUNTIME):
        raise AssertionError(
            "policy_runtime_sha256 does not match /app/runtime/pam.d/login.conf"
        )

    audit = proof.get("audit")
    if not isinstance(audit, dict):
        raise AssertionError("proof report must include an audit object")
    for key in ("login", "logout", "denied"):
        if key not in audit:
            raise AssertionError(f"missing audit.{key} in proof report")

    live_snapshot = snapshot(PUBLIC_LAB, "alice")
    expected_audit = parse_audit_counts(live_snapshot)
    for key in ("login", "logout", "denied"):
        if audit[key] != expected_audit[key]:
            raise AssertionError(
                f"audit.{key}={audit[key]!r} does not match live snapshot "
                f"audit.{key}={expected_audit[key]!r}"
            )

    if proof.get("state_converged") is True:
        before = live_snapshot
        run([str(AUTHCTL), "rebuild", "--root", str(PUBLIC_LAB)])
        after = snapshot(PUBLIC_LAB, "alice")
        if before != after:
            raise AssertionError(
                "state_converged is true but rebuild diverged from live snapshot"
            )

    if proof.get("collision_token") != "fresh":
        raise AssertionError(
            f"collision_token must remain fresh, got {proof.get('collision_token')!r}"
        )


def journal_sequences(root: Path) -> list[tuple[int, str, list[str]]]:
    rows: list[tuple[int, str, list[str]]] = []
    for line in (root / "state" / "journal.log").read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        rows.append((int(parts[0]), parts[1], parts[2:]))
    return rows


def exercise_recovery_cycle(
    root: Path,
    user: str,
    password: str,
    collision_secret: str,
    main_secret: str,
    collision_id: str,
    main_id: str,
    prefix: str,
    suffix: str,
) -> None:
    ordinary = f"ordinary-{suffix}"
    for attempt in range(1, 4):
        expect_deny(
            "--root",
            str(root),
            "--user",
            user,
            "--method",
            "password",
            "--secret",
            f"bad-{prefix}-{attempt}",
            "--session",
            f"{prefix}-bad-{attempt}",
        )
    expect_deny(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "password",
        "--secret",
        password,
        "--session",
        f"{prefix}-locked",
    )

    expect_allow(
        "--root",
        str(root),
        "--user",
        ordinary,
        "--method",
        "password",
        "--secret",
        "ordinary-pass",
        "--session",
        f"{prefix}-occupied",
    )
    expect_deny(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "recovery",
        "--secret",
        collision_secret,
        "--session",
        f"{prefix}-occupied",
    )
    collision_snapshot = snapshot(root, user)
    assert_line(collision_snapshot, "locked=true")
    assert_line(collision_snapshot, f"token.{collision_id}=fresh")
    run(
        [str(AUTHCTL), "logout", "--root", str(root), "--session", f"{prefix}-occupied"]
    )

    expect_allow(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "recovery",
        "--secret",
        main_secret,
        "--session",
        f"{prefix}-main",
    )
    run([str(AUTHCTL), "logout", "--root", str(root), "--session", f"{prefix}-main"])
    expect_deny(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "recovery",
        "--secret",
        main_secret,
        "--session",
        f"{prefix}-main-replay",
    )

    before = snapshot(root, user)
    assert_line(before, "failures=0")
    assert_line(before, "locked=false")
    assert_line(before, f"token.{collision_id}=fresh")
    assert_line(before, f"token.{main_id}=consumed")
    assert_line(before, f"session.{prefix}-main=closed:recovery")
    assert_line(before, "audit.login=1")
    assert_line(before, "audit.logout=1")
    assert_line(before, "audit.denied=6")

    assert_rebuild_restores(root, user, before)
    after = snapshot(root, user)
    if before != after:
        raise AssertionError(f"state diverged after rebuild for {user}")

    expect_deny(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "recovery",
        "--secret",
        main_secret,
        "--session",
        f"{prefix}-main-after-rebuild",
    )
    proc = run(
        [str(AUTHCTL), "logout", "--root", str(root), "--session", f"{prefix}-main"],
        check=False,
    )
    if proc.returncode == 0:
        raise AssertionError(f"closed session reopened after rebuild for {user}")
    expect_allow(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "password",
        "--secret",
        password,
        "--session",
        f"{prefix}-password-after-rebuild",
    )
    run(
        [
            str(AUTHCTL),
            "logout",
            "--root",
            str(root),
            "--session",
            f"{prefix}-password-after-rebuild",
        ]
    )

    expect_allow(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "recovery",
        "--secret",
        collision_secret,
        "--session",
        f"{prefix}-collision-valid",
    )
    run(
        [
            str(AUTHCTL),
            "logout",
            "--root",
            str(root),
            "--session",
            f"{prefix}-collision-valid",
        ]
    )
    expect_deny(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "recovery",
        "--secret",
        collision_secret,
        "--session",
        f"{prefix}-collision-replay",
    )

    before = snapshot(root, user)
    assert_line(before, f"token.{collision_id}=consumed")
    assert_line(before, "audit.login=3")
    assert_line(before, "audit.logout=3")
    assert_line(before, "audit.denied=8")
    assert_rebuild_restores(root, user, before)
    after = snapshot(root, user)
    if before != after:
        raise AssertionError(f"second rebuild diverged for {user}")


def build_and_verify_public() -> dict:
    run(["make", "-C", str(APP_ROOT), "-j2", "all"])
    run([str(APP_ROOT / "scripts" / "regenerate-policy.sh")])
    run([str(APP_ROOT / "scripts" / "verify-public.sh")])
    return json.loads(RECOVERY_PROOF.read_text())


def test_public_verification_pipeline_and_proof_report() -> None:
    """Public verifier, regenerated policy, and recovery-proof.json schema."""
    proof = build_and_verify_public()
    assert_recovery_proof_report(proof)


def test_password_lockout_and_ordinary_login(tmp_path: Path) -> None:
    """Three password failures lock an account; ordinary login still works."""
    build_and_verify_public()
    suffix = str(os.getpid())
    root = tmp_path / "ordinary"
    prepare_hidden_lab(root, suffix)
    user = f"legacy-{suffix}"
    for attempt in range(1, 4):
        expect_deny(
            "--root",
            str(root),
            "--user",
            user,
            "--method",
            "password",
            "--secret",
            f"bad-{attempt}",
            "--session",
            f"lock-{attempt}",
        )
    locked = snapshot(root, user)
    assert_line(locked, "locked=true")
    expect_deny(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "password",
        "--secret",
        "legacy-pass",
        "--session",
        "locked-login",
    )
    ordinary = f"ordinary-{suffix}"
    expect_allow(
        "--root",
        str(root),
        "--user",
        ordinary,
        "--method",
        "password",
        "--secret",
        "ordinary-pass",
        "--session",
        "ordinary-ok",
    )
    run([str(AUTHCTL), "logout", "--root", str(root), "--session", "ordinary-ok"])


def test_recovery_rejected_before_session_leaves_token(tmp_path: Path) -> None:
    """Occupied session rejects recovery without consuming token or lock reset."""
    build_and_verify_public()
    suffix = str(os.getpid())
    root = tmp_path / "reject"
    prepare_hidden_lab(root, suffix)
    user = f"legacy-{suffix}"
    for attempt in range(1, 4):
        expect_deny(
            "--root",
            str(root),
            "--user",
            user,
            "--method",
            "password",
            "--secret",
            f"x-{attempt}",
            "--session",
            f"x-{attempt}",
        )
    expect_allow(
        "--root",
        str(root),
        "--user",
        f"ordinary-{suffix}",
        "--method",
        "password",
        "--secret",
        "ordinary-pass",
        "--session",
        "hold",
    )
    expect_deny(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "recovery",
        "--secret",
        "legacy-collision",
        "--session",
        "hold",
    )
    view = snapshot(root, user)
    assert_line(view, "locked=true")
    assert_line(view, f"token.L-COLLIDE-{suffix}=fresh")
    assert_line(view, f"token.L-MAIN-{suffix}=fresh")


def test_delegated_ignore_recovery_path(tmp_path: Path) -> None:
    """Delegated users with password ignore still complete recovery."""
    build_and_verify_public()
    suffix = str(os.getpid())
    root = tmp_path / "delegated"
    prepare_hidden_lab(root, suffix)
    user = f"delegated-{suffix}"
    for attempt in range(1, 4):
        expect_deny(
            "--root",
            str(root),
            "--user",
            user,
            "--method",
            "password",
            "--secret",
            f"y-{attempt}",
            "--session",
            f"y-{attempt}",
        )
    expect_allow(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "recovery",
        "--secret",
        "delegated-main",
        "--session",
        "delegated-main",
    )
    run([str(AUTHCTL), "logout", "--root", str(root), "--session", "delegated-main"])
    view = snapshot(root, user)
    assert_line(view, "locked=false")
    assert_line(view, f"token.D-MAIN-{suffix}=consumed")


def test_journal_open_before_lock_reset_on_recovery() -> None:
    """Recovery login records session open before lock reset in the journal."""
    build_and_verify_public()
    rows = journal_sequences(PUBLIC_LAB)
    open_seq = None
    reset_seq = None
    for seq, kind, fields in rows:
        if kind == "session_open" and len(fields) >= 2 and fields[0] == "alice-r1":
            open_seq = seq
        if kind == "fail_reset" and fields and fields[0] == "alice":
            if open_seq is not None and reset_seq is None:
                reset_seq = seq
    if open_seq is None or reset_seq is None:
        raise AssertionError("missing session_open or fail_reset rows for recovery login")
    if open_seq >= reset_seq:
        raise AssertionError(
            f"session_open seq {open_seq} must precede fail_reset seq {reset_seq}"
        )


def test_checkpoint_restore_is_idempotent(tmp_path: Path) -> None:
    """Checkpoint restore rewinds journal-backed state and is repeatable."""
    build_and_verify_public()
    suffix = str(os.getpid())
    root = tmp_path / "checkpoint-lab"
    prepare_hidden_lab(root, suffix)
    user = f"legacy-{suffix}"
    expect_allow(
        "--root",
        str(root),
        "--user",
        f"ordinary-{suffix}",
        "--method",
        "password",
        "--secret",
        "ordinary-pass",
        "--session",
        "baseline",
    )
    run([str(AUTHCTL), "logout", "--root", str(root), "--session", "baseline"])
    run([str(AUTHCTL), "checkpoint", "--root", str(root), "--label", "mid"])
    mid_snapshot = snapshot(root, user)

    for attempt in range(1, 4):
        expect_deny(
            "--root",
            str(root),
            "--user",
            user,
            "--method",
            "password",
            "--secret",
            f"z-{attempt}",
            "--session",
            f"z-{attempt}",
        )
    expect_allow(
        "--root",
        str(root),
        "--user",
        user,
        "--method",
        "recovery",
        "--secret",
        "legacy-main",
        "--session",
        "after-mid",
    )
    run([str(AUTHCTL), "logout", "--root", str(root), "--session", "after-mid"])
    after_mid = snapshot(root, user)
    if after_mid == mid_snapshot:
        raise AssertionError("post-checkpoint mutations did not change state")

    run([str(AUTHCTL), "restore", "--root", str(root), "--label", "mid"])
    restored_once = snapshot(root, user)
    if restored_once != mid_snapshot:
        raise AssertionError("first restore did not match checkpoint snapshot")

    run([str(AUTHCTL), "restore", "--root", str(root), "--label", "mid"])
    restored_twice = snapshot(root, user)
    if restored_twice != restored_once:
        raise AssertionError("second restore changed state")
    assert_rebuild_restores(root, user, restored_twice)


def test_hidden_recovery_cycles_and_rebuild_matrix(tmp_path: Path) -> None:
    """Held-out legacy and delegated recovery cycles with rebuild convergence."""
    build_and_verify_public()
    suffix = str(os.getpid())
    hidden_root = tmp_path / "hidden"
    prepare_hidden_lab(hidden_root, suffix)

    ordinary = f"ordinary-{suffix}"
    expect_allow(
        "--root",
        str(hidden_root),
        "--user",
        ordinary,
        "--method",
        "password",
        "--secret",
        "ordinary-pass",
        "--session",
        "ordinary-login",
    )
    run(
        [
            str(AUTHCTL),
            "logout",
            "--root",
            str(hidden_root),
            "--session",
            "ordinary-login",
        ]
    )

    exercise_recovery_cycle(
        hidden_root,
        f"legacy-{suffix}",
        "legacy-pass",
        "legacy-collision",
        "legacy-main",
        f"L-COLLIDE-{suffix}",
        f"L-MAIN-{suffix}",
        "legacy",
        suffix,
    )
    exercise_recovery_cycle(
        hidden_root,
        f"delegated-{suffix}",
        "delegated-pass",
        "delegated-collision",
        "delegated-main",
        f"D-COLLIDE-{suffix}",
        f"D-MAIN-{suffix}",
        "delegated",
        suffix,
    )

    ordinary_before = snapshot(hidden_root, ordinary)
    assert_rebuild_restores(hidden_root, ordinary, ordinary_before)
    ordinary_after = snapshot(hidden_root, ordinary)
    if ordinary_before != ordinary_after:
        raise AssertionError("ordinary password session audit changed after rebuild")
