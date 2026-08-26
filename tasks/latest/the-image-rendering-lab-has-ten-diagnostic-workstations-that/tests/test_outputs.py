"""Verifier for the Rego workstation compliance library.

The verifier runs OPA against the submitted /app/policy/*.rego for every
workstation in the DuckDB inventory, then compares the emitted plans
against the golden plan JSON committed under /app/golden/. Every assertion
checks a behavior (action content, ordering, or per-family emission), not
just structural presence.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import duckdb
import pytest

POLICY_DIR = Path("/app/policy")
HARNESS = Path("/app/harness")
GOLDEN = Path("/app/golden")
DB = Path("/app/inventory/workstations.duckdb")


def _workstation_ids() -> list[str]:
    con = duckdb.connect(str(DB), read_only=True)
    ids = [row[0] for row in con.execute(
        "SELECT id FROM v_workstation ORDER BY id"
    ).fetchall()]
    con.close()
    return ids


def _run_policy(ws_id: str) -> dict:
    """Run /app/harness/run_policy.sh against a workstation id and parse json."""
    result = subprocess.run(
        ["bash", str(HARNESS / "run_policy.sh"), ws_id],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        pytest.fail(
            f"run_policy.sh returned {result.returncode} for {ws_id}:\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
    return json.loads(result.stdout)


def _golden_plan(ws_id: str) -> dict:
    fname = GOLDEN / f"plan_{ws_id.replace('-', '')}.json"
    return json.loads(fname.read_text())


# --- 1: structural preconditions --------------------------------------------

def test_policy_directory_has_at_least_one_rego_file():
    files = sorted(POLICY_DIR.glob("*.rego"))
    assert files, (
        f"expected at least one .rego file under {POLICY_DIR}, found none"
    )


def test_policy_declares_workstation_plan_package():
    files = sorted(POLICY_DIR.glob("*.rego"))
    combined = "\n".join(p.read_text() for p in files)
    assert "package workstation.plan" in combined, (
        "expected `package workstation.plan` declaration in the Rego library; "
        "the harness queries data.workstation.plan.actions and cannot resolve "
        "a differently-named package"
    )


def test_opa_can_parse_the_policy():
    r = subprocess.run(
        ["opa", "check", str(POLICY_DIR)],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, (
        f"opa check failed: {r.stderr}\nstdout: {r.stdout}"
    )


# --- 2: per-workstation golden matches --------------------------------------

@pytest.mark.parametrize("ws_id", _workstation_ids())
def test_plan_matches_golden_exactly(ws_id: str):
    emitted = _run_policy(ws_id)
    golden = _golden_plan(ws_id)
    assert emitted["workstation_id"] == golden["workstation_id"], (
        f"workstation_id mismatch for {ws_id}: emitted "
        f"{emitted['workstation_id']!r}, golden {golden['workstation_id']!r}"
    )
    assert emitted["actions"] == golden["actions"], (
        f"actions mismatch for {ws_id}:\n"
        f"  golden: {json.dumps(golden['actions'], indent=2)}\n"
        f"  emitted: {json.dumps(emitted['actions'], indent=2)}"
    )


# --- 3: behavior spot-checks against specific action families ---------------

def test_ws001_emits_ptrace_and_debug_group_actions():
    """ws-001 has ptrace_scope=3, not in debug group, plus other drift."""
    emitted = _run_policy("ws-001")
    actions = emitted["actions"]
    assert "sysctl:kernel.yama.ptrace_scope=0" in actions, (
        "ws-001 has ptrace_scope=3 and must trigger the Yama remediation"
    )
    assert "group:add:mediauser:debug" in actions, (
        "ws-001 is not in the debug group and must trigger the debug-group add"
    )
    # Terminal action always present
    assert "fixture-perms:/app/fixtures/tiff/sample.tiff:0644" in actions, (
        "ws-001 runs the TIFF workload and must emit the TIFF fixture-perms"
    )


def test_ws003_plan_is_two_actions_only():
    """ws-003 is compliant on everything except suid_dumpable."""
    emitted = _run_policy("ws-003")
    assert emitted["actions"] == [
        "sysctl:fs.suid_dumpable=2",
        "fixture-perms:/app/fixtures/mp4/sample.mp4:0644",
    ], (
        f"ws-003 should emit exactly the suid_dumpable and MP4 fixture-perms "
        f"actions (in that order), got {emitted['actions']}"
    )


def test_ws006_emits_immutable_clearance():
    """ws-006 is the only workstation with the immutable attribute set."""
    emitted = _run_policy("ws-006")
    actions = emitted["actions"]
    assert "fsattr:-i:/var/lib/media/scratch" in actions, (
        "ws-006 has scratch immutable=true and must emit the fsattr clearance"
    )
    # Ordering: perms action must come immediately before fsattr per Section 10
    perm_idx = actions.index("perms:/var/lib/media/scratch:2770:mediauser:media")
    fsattr_idx = actions.index("fsattr:-i:/var/lib/media/scratch")
    assert fsattr_idx == perm_idx + 1, (
        f"canonical ordering requires perms:...:2770:... immediately before "
        f"fsattr:-i:..., got perm_idx={perm_idx}, fsattr_idx={fsattr_idx}"
    )


def test_no_workstation_emits_an_empty_plan():
    """Every plan must contain at least the terminal fixture-perms action."""
    for ws_id in _workstation_ids():
        emitted = _run_policy(ws_id)
        assert len(emitted["actions"]) >= 1, (
            f"{ws_id} produced an empty plan; every plan must contain at "
            f"least the terminal fixture-perms action"
        )
        assert emitted["actions"][-1].startswith("fixture-perms:/app/fixtures/"), (
            f"{ws_id} last action must be the fixture-perms action, got "
            f"{emitted['actions'][-1]!r}"
        )


def test_canonical_ordering_prefix_sysctl_first():
    """Any sysctl action in a plan must come before any non-sysctl action."""
    for ws_id in _workstation_ids():
        emitted = _run_policy(ws_id)
        actions = emitted["actions"]
        seen_nonsysctl = False
        for a in actions:
            if a.startswith("sysctl:"):
                assert not seen_nonsysctl, (
                    f"{ws_id}: sysctl action {a!r} appears after a "
                    f"non-sysctl action; canonical order puts all sysctl "
                    f"actions first"
                )
            else:
                seen_nonsysctl = True


def test_workload_to_fixture_perms_is_consistent():
    """The fixture-perms path must match the workstation's workload AND appear
    as the terminal action with the exact expected string."""
    con = duckdb.connect(str(DB), read_only=True)
    try:
        pairs = con.execute("SELECT id, workload FROM v_workstation").fetchall()
    finally:
        con.close()
    for ws_id, workload in pairs:
        emitted = _run_policy(ws_id)
        expected = f"fixture-perms:/app/fixtures/{workload}/sample.{workload}:0644"
        # Terminal position (Section 10 says fixture-perms is always last)
        assert emitted["actions"][-1] == expected, (
            f"{ws_id} runs workload {workload!r}; expected terminal action "
            f"{expected!r} but got {emitted['actions'][-1]!r}"
        )
        # And the fixture-perms action must appear exactly once
        matches = [a for a in emitted["actions"] if a == expected]
        assert len(matches) == 1, (
            f"{ws_id} plan should contain the fixture-perms action exactly "
            f"once; got {len(matches)} occurrences of {expected!r} in "
            f"{emitted['actions']}"
        )
        # Cross-check: no OTHER workload's fixture-perms action leaks in
        for other_workload in ("tiff", "png", "mp4"):
            if other_workload == workload:
                continue
            other_expected = f"fixture-perms:/app/fixtures/{other_workload}/sample.{other_workload}:0644"
            assert other_expected not in emitted["actions"], (
                f"{ws_id} runs workload {workload!r} but plan contains the "
                f"{other_workload!r} fixture-perms action {other_expected!r}; "
                f"only the workstation's assigned workload may appear"
            )


def test_action_strings_use_only_canonical_prefixes():
    """No action string may fall outside the documented families."""
    canonical_prefixes = (
        "sysctl:", "systemd:", "group:add:", "ulimit:", "perms:",
        "fsattr:", "fixture-perms:",
    )
    for ws_id in _workstation_ids():
        emitted = _run_policy(ws_id)
        for a in emitted["actions"]:
            assert a.startswith(canonical_prefixes), (
                f"{ws_id}: action {a!r} does not use a canonical family "
                f"prefix; allowed prefixes are {canonical_prefixes}"
            )


def test_no_duplicated_actions_in_any_plan():
    """No plan may contain the same action string twice."""
    for ws_id in _workstation_ids():
        emitted = _run_policy(ws_id)
        assert len(emitted["actions"]) == len(set(emitted["actions"])), (
            f"{ws_id} plan contains a duplicate action: "
            f"{emitted['actions']}"
        )
