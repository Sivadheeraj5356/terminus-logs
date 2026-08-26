"""
Property battery for harden-java-compose-release-gates.

Tests verify the CDSS v4 release-gate HTTP service against an independent
reference engine (tests/authoring/reference_engine.py).  Every test that
expects an approve decision is paired with a deny sub-assertion executed
first, so the test function as a whole fails on the unmodified (NOP) starting
state.  Tests expecting deny fail NOP directly because the Decision stub
always renders approve.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml as _yaml

sys.path.insert(0, "/tests/authoring")
import reference_engine as _re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UTC = timezone.utc
API = "http://127.0.0.1:8971"
PAYMENTS_STACK = "/app/repos/payments-stack"
HOOK_BROKEN = "/app/repos/hook-broken"
H2_JAR = "/opt/jars/h2.jar"
DB_PATH = "/app/data/approvals"   # no extension; H2 appends .mv.db
DB_FILE = "/app/data/approvals.mv.db"
SEED_SQL = "/app/data/seed_approvals.sql"
STANDARD_FILE = "/app/standard/cdss_v4.md"
GNUPGHOME = "/root/.gnupg-cdss"

# Canonical evaluation timestamp for the visible fixture (within all seed
# exception windows that should be active).
EVAL_TIME_STR = "2026-06-15T12:00:00Z"
EVAL_TIME = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)

# Digest of cdss_v4.md as shipped in the final image (oracle confirmed).
STANDARD_SHA256_KNOWN = (
    "a0504e4e108f68cc45381d95b040c3f102d9a959189cf4b2abcf2560574c2a5f"
)

# Deterministic image pin used across all fixture compose files.
PIN = "sha256:0e7a76c893f22fd3d1fd53497c88b91af9f0d1057b1e6ba6faf7ff5b2c6ecbcd"

# Known fingerprints from build_repo_fixture.sh / seed_approvals.sql.
FP_A = "942607601B2B8AD9D8EB26A7574D706A78FF540D"   # active
FP_B = "DF25FE22A636F090D6443D9B9561D6AF8BF3A3C3"   # rotated
FP_C = "ECB920EA86252FA81CE4FBF623BC54402BB0A9DC"   # compromised

# Seed approved_keys — mirrors seed_approvals.sql exactly.
SEED_KEYS = [
    _re.ApprovedKey(FP_A, "Gate Signer Alpha", "active",
                    datetime(2026, 1, 1, tzinfo=UTC), None),
    _re.ApprovedKey(FP_B, "Gate Signer Bravo", "rotated",
                    datetime(2026, 1, 1, tzinfo=UTC),
                    datetime(2026, 3, 10, 8, 0, 0, tzinfo=UTC)),
    _re.ApprovedKey(FP_C, "Gate Signer Charlie", "compromised",
                    datetime(2026, 1, 1, tzinfo=UTC),
                    datetime(2026, 4, 5, 14, 0, 0, tzinfo=UTC)),
]

# Seed exception_windows — mirrors seed_approvals.sql exactly.
# Window id=1: §12.3 / cache* / approved_at 2026-03-15 (BEFORE A7 effective 2026-05-01).
SEED_WINDOWS = [
    _re.ExceptionWindow(1, "§12.3", "cache*",
                        datetime(2026, 1, 15, tzinfo=UTC),
                        datetime(2027, 1, 15, tzinfo=UTC),
                        datetime(2026, 3, 15, tzinfo=UTC)),
    _re.ExceptionWindow(2, "§8.1", "*",
                        datetime(2026, 1, 1, tzinfo=UTC),
                        datetime(2027, 1, 1, tzinfo=UTC),
                        datetime(2026, 2, 1, tzinfo=UTC)),
    _re.ExceptionWindow(3, "§14.5", "bulk*",
                        datetime(2026, 6, 1, tzinfo=UTC),
                        datetime(2026, 7, 1, tzinfo=UTC),
                        datetime(2026, 5, 15, tzinfo=UTC)),
]

SEED_INFRA = _re.InfraRegistry(services={"db"})

# Known tag evidence derived from build_repo_fixture.sh GIT_COMMITTER_DATE
# values and known signing keys.  Tag creation dates are from the fixture
# script; fingerprints are the full primary fingerprints as stored in the DB.
ACTIVE_TAG_EV = _re.TagEvidence(True, FP_A, datetime(2026, 6, 1, 10, tzinfo=UTC))
ROTATED_GRACE_EV = _re.TagEvidence(True, FP_B, datetime(2026, 3, 11, 9, tzinfo=UTC))
ROTATED_LATE_EV = _re.TagEvidence(True, FP_B, datetime(2026, 3, 14, 9, tzinfo=UTC))
COMPROMISED_EV = _re.TagEvidence(True, FP_C, datetime(2026, 4, 6, 9, tzinfo=UTC))
UNSIGNED_EV = _re.TagEvidence(False, None, None)

# Tag names in the fixture repos (all exist in PAYMENTS_STACK and HOOK_BROKEN).
TAG_ACTIVE = "release/v2.1.0"
TAG_ROTATED_GRACE = "release/v2.5.0-rotated-grace"
TAG_ROTATED_LATE = "release/v2.5.1-rotated-late"
TAG_COMPROMISED = "release/v2.4.0-compromised"
TAG_UNSIGNED = "release/v2.2.0-unsigned"
TAG_UNAPPROVED = "release/v2.3.0-unapproved"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def gate(repo: str, tag: str, eval_time: str) -> dict:
    """POST to /gate/evaluate; return parsed JSON response."""
    body = json.dumps({"repo": repo, "tag": tag,
                        "evaluationTime": eval_time}).encode()
    req = urllib.request.Request(
        f"{API}/gate/evaluate", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def reset_db() -> None:
    """Delete and re-seed the H2 approvals database from the canonical SQL."""
    for f in glob.glob("/app/data/approvals*"):
        os.unlink(f)
    subprocess.run(
        ["java", "-cp", H2_JAR, "org.h2.tools.RunScript",
         "-url", f"jdbc:h2:file:{DB_PATH}", "-user", "sa",
         "-script", SEED_SQL],
        check=True, capture_output=True,
    )


def mutate_db(sql: str) -> None:
    """Execute arbitrary SQL against the existing approvals DB."""
    with tempfile.NamedTemporaryFile(suffix=".sql", mode="w", delete=False) as f:
        f.write(sql)
        fname = f.name
    try:
        subprocess.run(
            ["java", "-cp", H2_JAR, "org.h2.tools.RunScript",
             "-url", f"jdbc:h2:file:{DB_PATH}", "-user", "sa",
             "-script", fname],
            check=True, capture_output=True,
        )
    finally:
        os.unlink(fname)


def _standard_sha256() -> str:
    return hashlib.sha256(Path(STANDARD_FILE).read_bytes()).hexdigest()


def _pre_push_marker_sha(repo_path: str) -> str | None:
    hook = Path(repo_path) / ".githooks" / "pre-push"
    if not hook.exists():
        return None
    m = re.search(r"CDSS-STANDARD-SHA256: ([0-9a-fA-F]{64})", hook.read_text())
    return m.group(1) if m else None


def _hooks_path(repo_path: str) -> str | None:
    r = subprocess.run(
        ["git", "-C", repo_path, "config", "core.hooksPath"],
        capture_output=True, text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else None


def _pre_push_executable(repo_path: str) -> bool:
    p = Path(repo_path) / ".githooks" / "pre-push"
    return p.exists() and os.access(str(p), os.X_OK)


def _unapproved_fp() -> str | None:
    """Return the per-build ephemeral fingerprint of Gate Signer Unapproved."""
    r = subprocess.run(
        ["gpg", "--list-keys", "--with-colons", "U@gate.example"],
        env={**os.environ, "GNUPGHOME": GNUPGHOME},
        capture_output=True, text=True,
    )
    for line in r.stdout.splitlines():
        if line.startswith("fpr:"):
            return line.split(":")[9]
    return None



# ---------------------------------------------------------------------------
# Compose YAML helpers
# ---------------------------------------------------------------------------

def _write_raw(path: str, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def _base_compose(extra_services: dict[str, str] = None) -> str:
    """Canonical four-service base compose. extra_services is raw YAML per-svc."""
    extras = ""
    if extra_services:
        for name, block in extra_services.items():
            extras += f"\n  {name}:\n" + "\n".join(
                f"    {ln}" for ln in block.splitlines()
            ) + "\n"
    return f"""services:
  web:
    image: nginx@{PIN}
    labels:
      cdss.tier: web
    read_only: true
    cap_drop: [ALL]
    ports:
      - "8080:80"

  worker:
    image: alpine@{PIN}
    labels:
      cdss.tier: internal
    read_only: true
    cap_drop: [ALL]

  db:
    image: postgres@{PIN}
    labels:
      cdss.tier: infra
    read_only: true
    cap_drop: [ALL]
    tmpfs:
      - /tmp

  payments-api:
    image: paymentapi@{PIN}
    labels:
      cdss.tier: web
    read_only: true
    cap_drop: [ALL]
    ports:
      - "8443:8443"
{extras}"""


def _override_with_cache(port: str = '"6379:6379"', read_only: bool = False,
                          class_label: str = "cache",
                          tier_label: str = "infra") -> str:
    ro = "true" if read_only else "false"
    label_line = (f"      cdss.class: {class_label}\n" if class_label else "")
    port_block = (f"    ports:\n      - {port}\n" if port else "")
    return (
        f"services:\n"
        f"  cache:\n"
        f"    image: redis@{PIN}\n"
        f"    labels:\n"
        f"      cdss.tier: {tier_label}\n"
        f"{label_line}"
        f"    cap_drop: [ALL]\n"
        f"{port_block}"
        f"    read_only: {ro}\n"
    )


def _svcs_from_yaml(compose_yaml: str) -> dict:
    """Extract the services dict from a compose YAML string via safe_load."""
    return (_yaml.safe_load(compose_yaml) or {}).get("services", {})


def make_repo(base_yaml: str, override_yaml: str | None = None) -> str:
    """
    Copy payments-stack to a temp dir (preserving signed git tags) and write
    specified compose YAML files.  Returns the temp repo path.
    """
    tmp = tempfile.mkdtemp(prefix="gate-test-")
    shutil.copytree(PAYMENTS_STACK, tmp, dirs_exist_ok=True)
    _write_raw(os.path.join(tmp, "docker-compose.yml"), base_yaml)
    prod = os.path.join(tmp, "docker-compose.prod.yml")
    if override_yaml is not None:
        _write_raw(prod, override_yaml)
    elif os.path.exists(prod):
        os.unlink(prod)
    return tmp


# ---------------------------------------------------------------------------
# Reference-engine wrapper
# ---------------------------------------------------------------------------

def _repo_obj(path: str, services: dict) -> _re.Repository:
    return _re.Repository(
        root=Path(path),
        hooks_path=_hooks_path(path),
        pre_push_executable=_pre_push_executable(path),
        pre_push_marker_sha=_pre_push_marker_sha(path),
        resolved_services=services,
    )


def ref_decide(
    *,
    base_svc_map: dict,
    override_svc_map: dict | None = None,
    tag_ev: _re.TagEvidence | None = None,
    keys: list | None = None,
    windows: list | None = None,
    infra: set | None = None,
    eval_time: datetime | None = None,
    repo_path: str = PAYMENTS_STACK,
    hooks_path: str = ".githooks",
    pre_push_exec: bool = True,
    pre_push_marker_sha: str | None = None,
) -> dict:
    """Compute the expected decision via the reference engine."""
    merged = _re.merge_compose(
        {"services": base_svc_map} if base_svc_map else None,
        {"services": override_svc_map} if override_svc_map else None,
    )
    services = merged.get("services", {})
    if pre_push_marker_sha is None:
        pre_push_marker_sha = _standard_sha256()
    repo = _re.Repository(
        root=Path(repo_path),
        hooks_path=hooks_path,
        pre_push_executable=pre_push_exec,
        pre_push_marker_sha=pre_push_marker_sha,
        resolved_services=services,
    )
    return _re.evaluate(
        repo=repo,
        tag_evidence=tag_ev if tag_ev is not None else ACTIVE_TAG_EV,
        approved_keys=keys if keys is not None else SEED_KEYS,
        windows=windows if windows is not None else SEED_WINDOWS,
        infra=_re.InfraRegistry(services=infra if infra is not None else {"db"}),
        eval_time=eval_time if eval_time is not None else EVAL_TIME,
        standard_sha256=_standard_sha256(),
    )


def assert_match(actual: dict, expected: dict) -> None:
    """Assert API response matches reference-engine output."""
    assert actual["decision"] == expected["decision"], (
        f"decision: got {actual['decision']!r}, want {expected['decision']!r}\n"
        f"  actual reasons:   {actual.get('reasons')}\n"
        f"  expected reasons: {expected.get('reasons')}"
    )
    if expected["decision"] == "deny":
        exp = {(r["code"], r["service"]) for r in expected["reasons"]}
        act = {(r["code"], r["service"]) for r in actual["reasons"]}
        assert act == exp, (
            f"reason mismatch:\n  got:  {act}\n  want: {exp}"
        )


# ===========================================================================
# Integrity tests
# ===========================================================================

def test_standard_file_sha256():
    """
    The shipped cdss_v4.md must have the exact digest recorded at oracle
    hand-off.  A content change would silently break the hook-marker check
    and shift all predicate decisions.
    """
    got = _standard_sha256()
    assert got == STANDARD_SHA256_KNOWN, (
        f"cdss_v4.md sha256 changed: {got}"
    )


def _dump_db_stripped() -> str:
    """Dump the H2 DB to SQL, strip the SA user SALT/HASH line, return text."""
    with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f:
        fname = f.name
    try:
        subprocess.run(
            ["java", "-cp", H2_JAR, "org.h2.tools.Script",
             "-url", f"jdbc:h2:file:{DB_PATH};IFEXISTS=TRUE",
             "-user", "sa", "-script", fname],
            check=True, capture_output=True,
        )
        content = Path(fname).read_text()
    finally:
        os.unlink(fname)
    lines = [ln for ln in content.splitlines()
             if not re.search(r"(?i)(ALTER USER|HASH|SALT)", ln)]
    return "\n".join(lines)


def test_db_dump_integrity_after_reseed():
    """
    After reset_db(), the H2 dump (SA-salt line stripped) must hash to a
    stable value, confirming the seed SQL is deterministic and the app-data
    rows were not altered by prior runs.  Compares two independent seeds.
    """
    reset_db()
    d1 = hashlib.sha256(_dump_db_stripped().encode()).hexdigest()
    reset_db()
    d2 = hashlib.sha256(_dump_db_stripped().encode()).hexdigest()
    assert d1 == d2, "DB dump not deterministic across two fresh seeds"


# ===========================================================================
# Baseline decision tests
# ===========================================================================

def test_visible_fixture_denies_cdss_svc_012():
    """
    Visible fixture (payments-stack repo, tag release/v2.1.0, eval
    2026-06-15) must deny with exactly one reason: CDSS-SVC-012 on service
    cache.  This is state (v) of the five-state trace: the chain requires
    compose merge, port-zone reclassification, Amendment 7 supersession, AND
    the §15.3 temporal-binding predicate (waiver approved_at < A7 effective
    → window does not suppress A7 obligation).  Any partial implementation
    produces approve, so this test fails on the NOP starting state.
    """
    reset_db()
    r = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    assert r["decision"] == "deny", f"expected deny, got {r}"
    codes = [(x["code"], x["service"]) for x in r["reasons"]]
    assert codes == [("CDSS-SVC-012", "cache")], (
        f"expected exactly [('CDSS-SVC-012', 'cache')], got {codes}"
    )


def test_compose_missing_denies_cdss_svc_024():
    """
    A repo without any compose files produces no resolved services, which
    must trigger CDSS-SVC-024 (§24.9 compose model absent).
    """
    tmp = tempfile.mkdtemp(prefix="gate-empty-")
    shutil.copytree(PAYMENTS_STACK, tmp, dirs_exist_ok=True)
    try:
        for fname in ("docker-compose.yml", "docker-compose.prod.yml"):
            p = os.path.join(tmp, fname)
            if os.path.exists(p):
                os.unlink(p)
        r = gate(tmp, TAG_ACTIVE, EVAL_TIME_STR)
        assert r["decision"] == "deny"
        codes = [x["code"] for x in r["reasons"]]
        assert "CDSS-SVC-024" in codes, f"expected CDSS-SVC-024 in {codes}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# Hook and signature tests
# ===========================================================================

def test_hook_check_fails_on_broken_repo():
    """
    The hook-broken fixture repo has a pre-push marker sha that does not
    match cdss_v4.md.  The service must deny with CDSS-HOOK-022.
    The deny verifies Ch.22 hook-check is implemented (NOP stub returns
    false for every repo, but Decision stub renders approve, so this test
    correctly fails NOP because NOP always returns approve).
    """
    reset_db()
    r = gate(HOOK_BROKEN, TAG_ACTIVE, EVAL_TIME_STR)
    assert r["decision"] == "deny", f"expected deny for broken hook, got {r}"
    codes = [x["code"] for x in r["reasons"]]
    assert "CDSS-HOOK-022" in codes, f"CDSS-HOOK-022 missing from {codes}"


def test_unsigned_tag_denies_cdss_key_invsig():
    """
    An unsigned annotated tag (no GPG signature) must produce CDSS-KEY-INVSIG
    because signature_valid is false.
    """
    reset_db()
    r = gate(PAYMENTS_STACK, TAG_UNSIGNED, EVAL_TIME_STR)
    assert r["decision"] == "deny", f"expected deny for unsigned tag, got {r}"
    codes = [x["code"] for x in r["reasons"]]
    assert "CDSS-KEY-INVSIG" in codes, f"CDSS-KEY-INVSIG missing from {codes}"


def test_unapproved_key_denies_cdss_key_017():
    """
    A tag signed by a key whose fingerprint is absent from approved_keys
    must deny with CDSS-KEY-017.  The unapproved key (FP_U) is ephemeral per
    image build and is never seeded in the DB.
    """
    reset_db()
    r = gate(PAYMENTS_STACK, TAG_UNAPPROVED, EVAL_TIME_STR)
    assert r["decision"] == "deny", f"expected deny for unapproved key, got {r}"
    codes = [x["code"] for x in r["reasons"]]
    assert "CDSS-KEY-017" in codes, f"CDSS-KEY-017 missing from {codes}"


def test_rotated_key_outside_72h_grace_denies():
    """
    release/v2.5.1-rotated-late is signed by FP_B (rotated, revoked_at
    2026-03-10T08:00:00Z) at 2026-03-14T09:00:00Z — outside the 72-hour
    grace window.  The service must deny with CDSS-KEY-017.
    """
    reset_db()
    r = gate(PAYMENTS_STACK, TAG_ROTATED_LATE, EVAL_TIME_STR)
    assert r["decision"] == "deny", f"expected deny for late-rotated key, got {r}"
    codes = [x["code"] for x in r["reasons"]]
    assert "CDSS-KEY-017" in codes, f"CDSS-KEY-017 missing from {codes}"


def test_compromised_key_after_revocation_denies():
    """
    release/v2.4.0-compromised is signed by FP_C (compromised, revoked_at
    2026-04-05T14:00:00Z) at 2026-04-06T09:00:00Z — after revocation.
    Compromised status has no grace interval; the service must deny with
    CDSS-KEY-017.
    """
    reset_db()
    r = gate(PAYMENTS_STACK, TAG_COMPROMISED, EVAL_TIME_STR)
    assert r["decision"] == "deny", f"expected deny for compromised key, got {r}"
    codes = [x["code"] for x in r["reasons"]]
    assert "CDSS-KEY-017" in codes, f"CDSS-KEY-017 missing from {codes}"


def test_rotated_key_within_72h_grace_approves():
    """
    release/v2.5.0-rotated-grace is signed by FP_B at 2026-03-11T09:00:00Z,
    which is within 72 hours after revoked_at 2026-03-10T08:00:00Z.  The
    service must approve (key in grace window).

    This test also asserts the out-of-grace deny first so the function fails
    on the NOP starting state (NOP Decision stub always renders approve).
    """
    reset_db()
    # Deny sub-case first so NOP path fails this test function.
    r_late = gate(PAYMENTS_STACK, TAG_ROTATED_LATE, EVAL_TIME_STR)
    assert r_late["decision"] == "deny", (
        f"rotated-late must deny but got {r_late}"
    )
    # Grace-window sub-case: compose still has §12.3 cache violation, but
    # for this sub-case we use the reference engine to know the expected output
    # (it may deny for compose reasons even with an approved key).
    # Use a clean-compose repo so key approval is the only variable.
    tmp = make_repo(_base_compose())  # no override → no cache service
    try:
        r_grace = gate(tmp, TAG_ROTATED_GRACE, EVAL_TIME_STR)
        exp = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=None,
            tag_ev=ROTATED_GRACE_EV,
        )
        assert_match(r_grace, exp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# Property battery — §15.3 waiver temporal binding
# ===========================================================================

def test_waiver_temporal_binding_denies_before_a7_effective():
    """
    §15.3: waiver.approved_at strictly before Amendment 7 effective_date
    (2026-05-01) does not suspend the amendment's added obligation.  The
    visible fixture already tests this (approved_at 2026-03-15); here we
    bracket at one second before the boundary to confirm it is a predicate,
    not a hardcoded flag.
    """
    reset_db()
    mutate_db("UPDATE exception_windows "
              "SET approved_at = TIMESTAMP '2026-04-30 23:59:59' WHERE id = 1;")
    r = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    assert r["decision"] == "deny", (
        f"approved_at one second before A7 effective must deny; got {r}"
    )
    codes = [x["code"] for x in r["reasons"]]
    assert "CDSS-SVC-012" in codes, f"CDSS-SVC-012 missing from {codes}"
    reset_db()


def test_waiver_temporal_binding_approves_at_and_after_a7_effective():
    """
    §15.3: waiver.approved_at exactly at, and one second after, Amendment 7
    effective_date suspends the amendment's obligation.  Both sub-cases
    approve.  The deny sub-case (before boundary) executes first so the
    function fails the NOP starting state.
    """
    reset_db()
    # Deny sub-case first so NOP path fails.
    mutate_db("UPDATE exception_windows "
              "SET approved_at = TIMESTAMP '2026-04-30 23:59:59' WHERE id = 1;")
    r_before = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    assert r_before["decision"] == "deny", (
        f"deny sub-case for temporal-binding bracket: got {r_before}"
    )

    # Exactly at A7 effective_date → window binds A7 → approve.
    A7 = _re.AMENDMENT_7_EFFECTIVE
    modified_windows = [
        _re.ExceptionWindow(1, "§12.3", "cache*",
                            datetime(2026, 1, 15, tzinfo=UTC),
                            datetime(2027, 1, 15, tzinfo=UTC),
                            A7),  # approved_at == effective_date
        SEED_WINDOWS[1], SEED_WINDOWS[2],
    ]
    mutate_db("UPDATE exception_windows "
              "SET approved_at = TIMESTAMP '2026-05-01 00:00:00' WHERE id = 1;")
    r_at = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    exp_at = ref_decide(
        base_svc_map=_svcs_from_yaml(_base_compose()),
        override_svc_map=_svcs_from_yaml(_override_with_cache()),
        windows=modified_windows,
    )
    assert_match(r_at, exp_at)

    # One second after A7 effective_date → still approve.
    modified_windows2 = [
        _re.ExceptionWindow(1, "§12.3", "cache*",
                            datetime(2026, 1, 15, tzinfo=UTC),
                            datetime(2027, 1, 15, tzinfo=UTC),
                            A7 + timedelta(seconds=1)),
        SEED_WINDOWS[1], SEED_WINDOWS[2],
    ]
    mutate_db("UPDATE exception_windows "
              "SET approved_at = TIMESTAMP '2026-05-01 00:00:01' WHERE id = 1;")
    r_after = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    exp_after = ref_decide(
        base_svc_map=_svcs_from_yaml(_base_compose()),
        override_svc_map=_svcs_from_yaml(_override_with_cache()),
        windows=modified_windows2,
    )
    assert_match(r_after, exp_after)
    reset_db()


def test_no_waiver_denies_amended_obligation():
    """
    With no exception window for §12.3, the amended obligation (Amendment 7
    for cache-class services reclassified via port zone) must deny regardless
    of §15.3 temporal binding.
    """
    reset_db()
    mutate_db("DELETE FROM exception_windows WHERE id = 1;")
    windows_no_cache = [SEED_WINDOWS[1], SEED_WINDOWS[2]]
    r = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    exp = ref_decide(
        base_svc_map=_svcs_from_yaml(_base_compose()),
        override_svc_map=_svcs_from_yaml(_override_with_cache()),
        windows=windows_no_cache,
    )
    assert_match(r, exp)
    assert r["decision"] == "deny"
    reset_db()


def test_waivable_non_amended_clause_not_over_fired_by_binding_rule():
    """
    §15.3 binding rule must not over-fire: a window approved before A7's
    effective_date on a waivable clause NOT targeted by any amendment still
    suspends the clause normally.  Uses §9.4 (cap_drop) with an injected
    window and an infra-label-only service (not in registry → NOT infra →
    §9.4 applies).

    Deny sub-case first (no window → violation present) so NOP fails.
    """
    reset_db()
    # Inject a service with cdss.tier=infra label but NOT in infra_registry
    # and without cap_drop → §9.4 violation.
    override = (
        f"services:\n"
        f"  svc-no-cap:\n"
        f"    image: alpine@{PIN}\n"
        f"    labels:\n"
        f"      cdss.tier: internal\n"
        f"    read_only: true\n"
        f"    cap_drop: []\n"  # empty → §9.4 violated
    )
    tmp = make_repo(_base_compose(), override)
    try:
        # Deny sub-case: no window for §9.4/svc-no-cap.
        r_deny = gate(tmp, TAG_ACTIVE, EVAL_TIME_STR)
        assert r_deny["decision"] == "deny", (
            f"no window: expected deny for missing cap_drop; got {r_deny}"
        )

        # Now insert a §9.4 window with approved_at BEFORE A7 effective_date.
        # §9.4 is NOT targeted by Amendment 7, so §15.3 binding does not
        # restrict suspension — the window must suppress the violation.
        mutate_db(
            "INSERT INTO exception_windows VALUES ("
            "10, '§9.4', 'svc-no-cap', "
            "TIMESTAMP '2026-01-01 00:00:00', "
            "TIMESTAMP '2027-01-01 00:00:00', "
            "'ops-team', "
            "TIMESTAMP '2026-02-01 00:00:00');"  # approved_at well before A7
        )
        windows_with_9_4 = SEED_WINDOWS + [
            _re.ExceptionWindow(10, "§9.4", "svc-no-cap",
                                datetime(2026, 1, 1, tzinfo=UTC),
                                datetime(2027, 1, 1, tzinfo=UTC),
                                datetime(2026, 2, 1, tzinfo=UTC)),
        ]
        r_approve = gate(tmp, TAG_ACTIVE, EVAL_TIME_STR)
        base_m = _svcs_from_yaml(_base_compose())
        ov_m = _svcs_from_yaml(override)
        exp = ref_decide(
            base_svc_map=base_m, override_svc_map=ov_m,
            windows=windows_with_9_4,
        )
        assert_match(r_approve, exp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        reset_db()


# ===========================================================================
# Property battery — cache-class port-zone permutations (matrix cases 2-8)
# ===========================================================================

def test_cache_class_no_web_zone_port_approves():
    """
    Cache-class service with no published port does not become web-tier via
    port zone; §12.3 base exemption applies; the service must NOT generate
    a §12.3 violation.

    Deny sub-case first: same service WITH a web-zone port (6379) denies.
    Approve sub-case: same service WITHOUT port approves.
    NOP always returns approve so the deny sub-case makes this non-vacuous.
    """
    reset_db()
    # Deny sub-case: cache with web-zone port → Amendment 7 fires → deny.
    deny_yaml = _override_with_cache(port='"6379:6379"', read_only=False)
    tmp_d = make_repo(_base_compose(), deny_yaml)
    try:
        r_d = gate(tmp_d, TAG_ACTIVE, EVAL_TIME_STR)
        assert r_d["decision"] == "deny", f"deny sub-case: got {r_d}"
    finally:
        shutil.rmtree(tmp_d, ignore_errors=True)

    # Approve sub-case: cache with NO port → not web-tier via port zone.
    approve_yaml = _override_with_cache(port="", read_only=False)
    tmp_a = make_repo(_base_compose(), approve_yaml)
    try:
        exp = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(approve_yaml),
        )
        r_a = gate(tmp_a, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r_a, exp)
    finally:
        shutil.rmtree(tmp_a, ignore_errors=True)


def test_cache_class_port_in_internal_zone_approves():
    """
    A cache-class service whose published port falls in the internal zone
    (9000–9999) is NOT web-tier via port zone and NOT classified as web-tier
    by label.  §12.3 base exemption applies; must approve.

    Deny sub-case first: web-zone port 6379 → deny (non-vacuous).
    """
    reset_db()
    deny_yaml = _override_with_cache(port='"6379:6379"', read_only=False)
    tmp_d = make_repo(_base_compose(), deny_yaml)
    try:
        r_d = gate(tmp_d, TAG_ACTIVE, EVAL_TIME_STR)
        assert r_d["decision"] == "deny", f"deny sub-case: got {r_d}"
    finally:
        shutil.rmtree(tmp_d, ignore_errors=True)

    approve_yaml = _override_with_cache(port='"9000:9000"', read_only=False)
    tmp_a = make_repo(_base_compose(), approve_yaml)
    try:
        exp = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(approve_yaml),
        )
        r_a = gate(tmp_a, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r_a, exp)
    finally:
        shutil.rmtree(tmp_a, ignore_errors=True)


def test_cache_read_only_true_compliant():
    """
    A cache-class service in the web zone with read_only: true satisfies
    the amended §12.3 obligation and must approve.

    Deny sub-case first: same service with read_only: false → deny.
    """
    reset_db()
    deny_yaml = _override_with_cache(port='"6379:6379"', read_only=False)
    tmp_d = make_repo(_base_compose(), deny_yaml)
    try:
        r_d = gate(tmp_d, TAG_ACTIVE, EVAL_TIME_STR)
        assert r_d["decision"] == "deny", f"deny sub-case: got {r_d}"
    finally:
        shutil.rmtree(tmp_d, ignore_errors=True)

    approve_yaml = _override_with_cache(port='"6379:6379"', read_only=True)
    tmp_a = make_repo(_base_compose(), approve_yaml)
    try:
        exp = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(approve_yaml),
        )
        r_a = gate(tmp_a, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r_a, exp)
    finally:
        shutil.rmtree(tmp_a, ignore_errors=True)


def test_non_cache_web_tier_denies_base_requirement():
    """
    A web-tier service without any cache-class label violates §12.3 directly
    via the base rule.  The service is named 'frontend' (does not match the
    seed window glob 'cache*'), so no window suppresses it.  The reference
    engine confirms the expected deny and the test fails NOP.
    """
    reset_db()
    override = (
        f"services:\n"
        f"  frontend:\n"
        f"    image: nginx@{PIN}\n"
        f"    labels:\n"
        f"      cdss.tier: web\n"
        f"    read_only: false\n"
        f"    cap_drop: [ALL]\n"
        f'    ports:\n      - "8080:80"\n'
    )
    tmp = make_repo(_base_compose(), override)
    try:
        exp = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(override),
        )
        r = gate(tmp, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r, exp)
        assert r["decision"] == "deny"
        codes = [x["code"] for x in r["reasons"]]
        assert "CDSS-SVC-012" in codes
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_cache_in_base_compose_also_denies():
    """
    When the cache service (with web-zone port) is placed in the BASE compose
    file rather than the override, the service is visible even to the naive
    loader stub.  A solver who fixed the loader but whose Amendment 7 chain is
    missing still approves; one with the chain denies.

    The reference engine confirms the expected decision; the test fails NOP
    because Decision.render always returns approve.
    """
    reset_db()
    cache_block = (
        f"  cache:\n"
        f"    image: redis@{PIN}\n"
        f"    labels:\n"
        f"      cdss.tier: infra\n"
        f"      cdss.class: cache\n"
        f"    cap_drop: [ALL]\n"
        f'    ports:\n      - "6379:6379"\n'
        f"    read_only: false\n"
    )
    base_yaml = _base_compose() + cache_block
    tmp = make_repo(base_yaml)  # no override
    try:
        base_m = _svcs_from_yaml(base_yaml)
        exp = ref_decide(base_svc_map=base_m, override_svc_map=None)
        r = gate(tmp, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r, exp)
        assert r["decision"] == "deny"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# Property battery — cache-class label mutations
# ===========================================================================

def test_cache_class_label_determines_amendment_path():
    """
    cache-class classification is label-only (cdss.class=cache, case-sensitive
    exact match).  Correct label → Amendment 7 path (subject='a7'): the pre-A7
    waiver does NOT suppress → DENY.  Misspelled or absent label → base §12.3
    path (subject='base'): the 'cache*' window suppresses the base obligation
    → APPROVE.  This contrast proves the label drives the decision path, not
    the service name.

    The deny sub-case (correct label) executes first so the function fails on
    the NOP starting state.
    """
    reset_db()
    # Sub-case 1: correct label → A7 path → waiver pre-dates A7 → DENY.
    r_correct = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    assert r_correct["decision"] == "deny", (
        f"correct cdss.class=cache label must deny (A7 path); got {r_correct}"
    )

    # Sub-case 2: misspelled label → base §12.3 path → window suppresses.
    override_ms = _override_with_cache(class_label="Cache")  # wrong capitalisation
    tmp_ms = make_repo(_base_compose(), override_ms)
    try:
        exp_ms = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(override_ms),
        )
        r_ms = gate(tmp_ms, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r_ms, exp_ms)
        # Reference engine: subject='base' → cache* window suppresses → approve.
        assert r_ms["decision"] == "approve", (
            f"misspelled label: base path, 'cache*' window suppresses → expect approve; "
            f"got {r_ms}"
        )
    finally:
        shutil.rmtree(tmp_ms, ignore_errors=True)

    # Sub-case 3: absent class label → same base path → window suppresses.
    override_ab = _override_with_cache(class_label="")
    tmp_ab = make_repo(_base_compose(), override_ab)
    try:
        exp_ab = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(override_ab),
        )
        r_ab = gate(tmp_ab, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r_ab, exp_ab)
    finally:
        shutil.rmtree(tmp_ab, ignore_errors=True)


# ===========================================================================
# Property battery — non-waivable clauses
# ===========================================================================

def test_nonwaivable_clause_8_1_not_suspended_by_window():
    """
    §8.1 (privileged containers) is listed in Appendix B as non-waivable.
    The seed DB contains a §8.1 window for '*', which covers any service.
    Adding a privileged service must still deny despite the window.
    """
    reset_db()
    override = (
        f"services:\n"
        f"  priv-svc:\n"
        f"    image: alpine@{PIN}\n"
        f"    labels:\n"
        f"      cdss.tier: internal\n"
        f"    privileged: true\n"
        f"    read_only: true\n"
        f"    cap_drop: [ALL]\n"
    )
    tmp = make_repo(_base_compose(), override)
    try:
        exp = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(override),
        )
        r = gate(tmp, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r, exp)
        assert r["decision"] == "deny"
        codes = [x["code"] for x in r["reasons"]]
        assert "CDSS-SVC-008" in codes
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_nonwaivable_clause_14_5_not_suspended_by_window():
    """
    §14.5 (bind-mount prefix allowlist) is non-waivable.  The seed DB has a
    §14.5 window for bulk* at eval time 2026-06-15.  A service named
    bulk-svc mounting /var/run/docker.sock must still deny despite the window.
    """
    reset_db()
    override = (
        f"services:\n"
        f"  bulk-svc:\n"
        f"    image: alpine@{PIN}\n"
        f"    labels:\n"
        f"      cdss.tier: internal\n"
        f"    read_only: true\n"
        f"    cap_drop: [ALL]\n"
        f"    volumes:\n"
        f"      - /var/run/docker.sock:/var/run/docker.sock\n"
    )
    tmp = make_repo(_base_compose(), override)
    try:
        exp = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(override),
        )
        r = gate(tmp, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r, exp)
        assert r["decision"] == "deny"
        codes = [x["code"] for x in r["reasons"]]
        assert "CDSS-SVC-014" in codes
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# Property battery — exception window half-open boundary
# ===========================================================================

def test_exception_window_half_open_boundaries():
    """
    Exception windows use a half-open [starts_at, ends_at) interval.
    Three boundary sub-cases for the §12.3/cache* window (id=1):
      a) eval_time at starts_at → window applies → approve (approved_at >= A7).
      b) eval_time one second before ends_at → window applies → approve.
      c) eval_time exactly at ends_at → window NOT active → deny.

    For (a) and (b) the window must suppress the amended obligation so we
    first set approved_at to A7 effective_date (window binds A7).
    Deny sub-case (c) executes last; the sub-case (a) deny counterpart uses
    a pre-A7 approved_at to seed the deny in a different ordering check.
    """
    reset_db()

    # Arrange: set window starts_at and ends_at to known values; set
    # approved_at >= A7 so sub-cases a and b approve.
    STARTS = "2026-05-15 00:00:00"
    ENDS = "2026-07-01 00:00:00"
    APPROVED_AT_AFTER_A7 = "2026-05-01 00:00:00"  # exactly A7 effective_date
    mutate_db(
        f"UPDATE exception_windows SET "
        f"starts_at = TIMESTAMP '{STARTS}', "
        f"ends_at   = TIMESTAMP '{ENDS}', "
        f"approved_at = TIMESTAMP '{APPROVED_AT_AFTER_A7}' "
        f"WHERE id = 1;"
    )
    A7 = _re.AMENDMENT_7_EFFECTIVE
    w_modified = [
        _re.ExceptionWindow(1, "§12.3", "cache*",
                            datetime(2026, 5, 15, tzinfo=UTC),
                            datetime(2026, 7, 1, tzinfo=UTC),
                            A7),
        SEED_WINDOWS[1], SEED_WINDOWS[2],
    ]

    base_m = _svcs_from_yaml(_base_compose())
    ov_m = _svcs_from_yaml(_override_with_cache())

    # Sub-case a: eval at starts_at (inclusive).
    r_a = gate(PAYMENTS_STACK, TAG_ACTIVE, "2026-05-15T00:00:00Z")
    exp_a = ref_decide(base_svc_map=base_m, override_svc_map=ov_m,
                       windows=w_modified,
                       eval_time=datetime(2026, 5, 15, tzinfo=UTC))
    assert_match(r_a, exp_a)

    # Sub-case b: eval one second before ends_at (inclusive).
    r_b = gate(PAYMENTS_STACK, TAG_ACTIVE, "2026-06-30T23:59:59Z")
    exp_b = ref_decide(base_svc_map=base_m, override_svc_map=ov_m,
                       windows=w_modified,
                       eval_time=datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC))
    assert_match(r_b, exp_b)

    # Sub-case c: eval at ends_at (exclusive → not active → deny).
    r_c = gate(PAYMENTS_STACK, TAG_ACTIVE, "2026-07-01T00:00:00Z")
    exp_c = ref_decide(base_svc_map=base_m, override_svc_map=ov_m,
                       windows=w_modified,
                       eval_time=datetime(2026, 7, 1, tzinfo=UTC))
    assert_match(r_c, exp_c)
    assert r_c["decision"] == "deny", "ends_at exclusive: window inactive → deny"

    reset_db()


# ===========================================================================
# Property battery — infra-tier classification
# ===========================================================================

def test_infra_tier_requires_both_label_and_registry_row():
    """
    §3.7: infra-tier requires BOTH cdss.tier=infra label AND a row in
    infra_registry.  Label-only is not infra (§9.4 cap_drop applies).
    Row-only (different name in registry) is not infra (cap_drop applies).
    Both together → IS infra → cap_drop not required.

    Sub-case 1 (label only, no registry row, cap_drop absent) → deny §9.4.
    Sub-case 3 (both label + row + cap_drop absent) → approve.
    """
    reset_db()
    # Override: infra-labeled service NOT in infra_registry, cap_drop absent.
    override_label_only = (
        f"services:\n"
        f"  svc-infra-label:\n"
        f"    image: alpine@{PIN}\n"
        f"    labels:\n"
        f"      cdss.tier: infra\n"
        f"    read_only: true\n"
    )
    tmp_label = make_repo(_base_compose(), override_label_only)
    try:
        # svc-infra-label is NOT in infra_registry → NOT infra → §9.4 applies.
        exp_label = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(override_label_only),
            infra={"db"},  # only db in registry, not svc-infra-label
        )
        r_label = gate(tmp_label, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r_label, exp_label)
        assert r_label["decision"] == "deny", (
            f"label-only infra: expected deny §9.4; got {r_label}"
        )
    finally:
        shutil.rmtree(tmp_label, ignore_errors=True)

    # Sub-case 3: Add registry row for svc-infra-label → IS infra → no §9.4.
    mutate_db(
        "INSERT INTO infra_registry VALUES ('svc-infra-label', 'infrastructure');"
    )
    tmp_both = make_repo(_base_compose(), override_label_only)
    try:
        exp_both = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(override_label_only),
            infra={"db", "svc-infra-label"},
        )
        r_both = gate(tmp_both, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r_both, exp_both)
    finally:
        shutil.rmtree(tmp_both, ignore_errors=True)
        reset_db()


def test_port_zone_supersedes_cdss_tier_label_for_web_tier():
    """
    §1.3: port-zone-derived classification takes precedence over label.  A
    service with cdss.tier=infra label but a web-zone port is web-tier; §12.3
    applies if read_only is absent.  The reference engine models this via
    is_web_tier() returning True (port zone) regardless of label.

    The infra_registry has only 'db'; the test service is NOT in the registry,
    so it is also not infra-tier per §3.7 (label-AND-row).
    """
    reset_db()
    override = (
        f"services:\n"
        f"  svc-infra-web:\n"
        f"    image: alpine@{PIN}\n"
        f"    labels:\n"
        f"      cdss.tier: infra\n"  # infra label, but web port → web-tier
        f"    read_only: false\n"
        f"    cap_drop: [ALL]\n"
        f'    ports:\n      - "8080:80"\n'
    )
    tmp = make_repo(_base_compose(), override)
    try:
        exp = ref_decide(
            base_svc_map=_svcs_from_yaml(_base_compose()),
            override_svc_map=_svcs_from_yaml(override),
            infra={"db"},  # svc-infra-web NOT in registry
        )
        r = gate(tmp, TAG_ACTIVE, EVAL_TIME_STR)
        assert_match(r, exp)
        assert r["decision"] == "deny"
        codes = [x["code"] for x in r["reasons"]]
        assert "CDSS-SVC-012" in codes
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# Sort-order enforcement
# ===========================================================================

def test_deny_reasons_ordered_code_then_service():
    """
    The API contract requires reasons sorted by code ASC then service ASC.
    This test uses a two-service compose that produces exactly two violations —
    service 'alpha' violates §8.1 (privileged: true; §8.1 is non-waivable so
    the seed §8.1/* window does NOT suppress it) and service 'beta' violates
    §12.3 (web-zone port + read_only: false; no window matches 'beta') — and
    asserts the full ordered list verbatim, not as a set.  An implementation
    that emits reasons in insertion or map-iteration order rather than
    (code, service) order fails this test even if the set of codes is correct.
    """
    reset_db()
    alpha_beta_yaml = (
        f"services:\n"
        f"  alpha:\n"
        f"    image: nginx@{PIN}\n"
        f"    cap_drop: [ALL]\n"
        f"    privileged: true\n"
        f"  beta:\n"
        f"    image: nginx@{PIN}\n"
        f"    cap_drop: [ALL]\n"
        f"    read_only: false\n"
        f'    ports:\n      - "8080:80"\n'
    )
    tmp = make_repo(alpha_beta_yaml, override_yaml=None)
    try:
        svc_map = _svcs_from_yaml(alpha_beta_yaml)
        exp = ref_decide(base_svc_map=svc_map, override_svc_map=None)
        r = gate(tmp, TAG_ACTIVE, EVAL_TIME_STR)
        assert r["decision"] == "deny", f"expected deny; got {r}"
        assert len(exp["reasons"]) >= 2, "reference engine returned < 2 reasons (probe the scenario)"
        # Exact ordered list equality — position 0 must be CDSS-SVC-008/alpha,
        # position 1 must be CDSS-SVC-012/beta (code ASC then service ASC).
        assert r["reasons"] == exp["reasons"], (
            f"reasons list order mismatch:\n  got:  {r['reasons']}\n  want: {exp['reasons']}"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        reset_db()


# ===========================================================================
# Statelessness and determinism
# ===========================================================================

def test_no_docker_processes_spawned_during_evaluation():
    """
    The service must perform static analysis only; it must not invoke docker
    or docker compose at request time.  Snapshot process count before and
    after a batch of requests and assert no docker/compose processes appear.

    This is a structural integrity check.  NOP also spawns no docker
    processes, but it is paired with the deny assertion on the visible fixture
    so the test function as a whole fails the NOP starting state.
    """
    reset_db()

    def _docker_pids() -> set:
        """Scan /proc for processes with docker/docker-compose in their cmdline."""
        found = set()
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cmd = (entry / "cmdline").read_bytes().replace(
                    b"\x00", b" "
                ).decode("utf-8", errors="replace")
                if re.search(r"\b(docker|docker-compose)\b", cmd):
                    found.add(entry.name)
            except (PermissionError, FileNotFoundError):
                pass
        return found

    pids_before = _docker_pids()

    # Visible fixture: must deny (fails NOP).
    r = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    assert r["decision"] == "deny", f"visible fixture must deny; got {r}"

    # Additional requests to stress any lazy spawning path.
    gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)

    pids_after = _docker_pids()
    new_pids = pids_after - pids_before
    assert not new_pids, (
        f"docker/compose processes appeared during evaluation: {new_pids}"
    )


def test_no_interpreter_subprocess_during_evaluation():
    """
    The gate service must implement its policy in compiled Java only; it must
    not shell out to python3, python, or any other script interpreter at
    request time.  A plumb-through implementation that delegates decisions to
    /tests/authoring/reference_engine.py via a subprocess call would appear
    as a new python process in /proc during the request window.

    Snapshot /proc for interpreter pids before issuing requests, then assert
    no new interpreter processes appeared after.  Paired with a deny assertion
    on the visible fixture so the function fails the NOP starting state.
    """
    reset_db()

    def _interp_pids() -> set:
        """Scan /proc for python/interpreter processes by cmdline."""
        found = set()
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                cmd = (entry / "cmdline").read_bytes().replace(
                    b"\x00", b" "
                ).decode("utf-8", errors="replace")
                if re.search(r"\bpython[23]?\b|\bpython\b|\bruby\b|\bnode\b|\bperl\b", cmd):
                    found.add(entry.name)
            except (PermissionError, FileNotFoundError):
                pass
        return found

    pids_before = _interp_pids()

    # Visible fixture: must deny (fails NOP).
    r = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    assert r["decision"] == "deny", f"visible fixture must deny; got {r}"

    # Additional requests to stress any lazy spawning path.
    gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)

    pids_after = _interp_pids()
    new_pids = pids_after - pids_before
    assert not new_pids, (
        f"interpreter processes appeared during evaluation: {new_pids}"
    )


def test_db_bytes_unchanged_after_requests():
    """
    The service opens a read-only connection per request and must not write
    to the DB file.  Assert the DB file's sha256 is identical before and
    after a batch of requests.

    Paired with a visible-fixture deny assertion so the test fails NOP.
    """
    reset_db()
    digest_before = hashlib.sha256(Path(DB_FILE).read_bytes()).hexdigest()

    r = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    assert r["decision"] == "deny", f"visible fixture must deny; got {r}"
    gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)

    digest_after = hashlib.sha256(Path(DB_FILE).read_bytes()).hexdigest()
    assert digest_before == digest_after, (
        "DB file was modified by request processing (not read-only)"
    )


def test_deterministic_responses_across_repeated_calls():
    """
    The same request must produce byte-identical JSON responses across repeated
    calls, confirming no non-deterministic state accumulates between requests.

    Includes visible-fixture deny assertion so the test fails NOP.
    """
    reset_db()
    r1 = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    assert r1["decision"] == "deny", f"visible fixture must deny; got {r1}"
    r2 = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    r3 = gate(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    assert r1 == r2 == r3, (
        f"Non-deterministic responses:\n  r1={r1}\n  r2={r2}\n  r3={r3}"
    )


# ===========================================================================
# HTTP wire contract
# ===========================================================================

def test_health_returns_exact_body_and_content_type():
    """
    GET /health must return exactly the byte sequence b'{"status":"ok"}' with
    no trailing newline and Content-Type: application/json.  An implementation
    that adds a trailing newline, wraps extra fields, or omits the Content-Type
    header fails this test even if the JSON value is correct.
    """
    req = urllib.request.Request(f"{API}/health", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read()
        ct = resp.headers.get("Content-Type", "")
    assert body == b'{"status":"ok"}', (
        f"health body mismatch: got {body!r}"
    )
    assert "application/json" in ct, (
        f"health Content-Type missing application/json: got {ct!r}"
    )


def test_malformed_request_returns_400():
    """
    POST /gate/evaluate with a malformed request body must return HTTP 400 and
    body {"error":"malformed request"} in all four malformation cases defined
    by the API contract: missing required key, extra key beyond the three
    required, non-string value for a string field, and evaluationTime value
    that is not a valid ISO-8601 UTC timestamp.
    """
    def _post_raw(payload: bytes) -> tuple[int, bytes]:
        req = urllib.request.Request(
            f"{API}/gate/evaluate", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    cases = [
        # Missing required key (evaluationTime absent).
        json.dumps({"repo": PAYMENTS_STACK, "tag": TAG_ACTIVE}).encode(),
        # Extra key beyond the three required.
        json.dumps({"repo": PAYMENTS_STACK, "tag": TAG_ACTIVE,
                    "evaluationTime": EVAL_TIME_STR, "extra": "x"}).encode(),
        # Non-string value for evaluationTime.
        json.dumps({"repo": PAYMENTS_STACK, "tag": TAG_ACTIVE,
                    "evaluationTime": 20260615}).encode(),
        # evaluationTime is a string but not a valid ISO-8601 UTC timestamp.
        json.dumps({"repo": PAYMENTS_STACK, "tag": TAG_ACTIVE,
                    "evaluationTime": "not-a-date"}).encode(),
    ]
    for payload in cases:
        status, body = _post_raw(payload)
        parsed = json.loads(body)
        assert status == 400, (
            f"expected HTTP 400 for {payload!r}; got {status} body={body!r}"
        )
        assert parsed == {"error": "malformed request"}, (
            f"unexpected 400 body for {payload!r}: {parsed!r}"
        )


def test_all_decisions_return_http_200():
    """
    The API contract requires HTTP 200 for all evaluation outcomes, including
    deny.  An implementation that uses 4xx for policy denials violates the
    contract.  Asserts 200 on the visible-fixture deny (which also fails NOP)
    and on a clean approve (cache-class + compliant read_only).
    """
    reset_db()

    def _gate_status(repo: str, tag: str, eval_time: str) -> tuple[int, dict]:
        body = json.dumps({"repo": repo, "tag": tag,
                           "evaluationTime": eval_time}).encode()
        req = urllib.request.Request(
            f"{API}/gate/evaluate", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())

    # Deny case — visible fixture; fails NOP (NOP returns approve).
    status_deny, r_deny = _gate_status(PAYMENTS_STACK, TAG_ACTIVE, EVAL_TIME_STR)
    assert r_deny["decision"] == "deny", f"visible fixture must deny; got {r_deny}"
    assert status_deny == 200, f"deny response used non-200 status: {status_deny}"

    # Approve case — cache-class service, no web-zone port, read_only compliant.
    tmp = make_repo(_base_compose(), _override_with_cache(port=None, read_only=True))
    try:
        status_app, r_app = _gate_status(tmp, TAG_ACTIVE, EVAL_TIME_STR)
        assert r_app["decision"] == "approve", f"expected approve; got {r_app}"
        assert status_app == 200, f"approve response used non-200 status: {status_app}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
