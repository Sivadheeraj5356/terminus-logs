"""Verifier: evaluating a CUE configuration where a field inside a referenced
inline struct is overridden with a CONFLICTING value must report a conflict
error; valid configurations (including inline overrides that agree or constrain
an abstract field) must keep evaluating without error.

The held-out test is injected into the module at verify time (the agent's /app
has no test for this behaviour), then compiled offline against the agent's edited
sources and run through CUE's public `cuecontext` API — so it exercises the real
evaluator and cannot be satisfied without genuinely fixing it. Every CUE case is
still reported individually (per-case split for the solvability gate), but the
held-out test package is compiled and run in a SINGLE `go test` invocation and
the per-subtest PASS/FAIL lines are parsed out — instead of recompiling the whole
evaluator once per case — so the verifier's wall-clock stays small. Expected
outcomes were established against the upstream fix (an independent reference),
not the code under repair.
"""
import os
import re
import shutil
import subprocess

import pytest

APP = os.environ.get("VERIFIER_APP", "/app")
HERE = os.path.dirname(os.path.abspath(__file__))
VDIR = os.path.join(APP, "verify")
ENV = {**os.environ, "GOFLAGS": "-mod=vendor", "GOPROXY": "off", "GOTOOLCHAIN": "go1.25.0"}

CONFLICT = ["c1_scalar_ref", "c2_string_interp", "c3_bool_derived", "c4_arith",
            "c5_url", "c7_nested_ref", "c8_two_fields"]
GUARD = ["g1_abstract_base", "g2_override_equals", "g3_abstract_stage",
         "g4_two_overrides", "g5_replicas", "g6_default", "g7_concrete_match",
         "g8_struct_merge", "g9_list_ref", "g10_deep_override", "g11_abstract_merge"]


@pytest.fixture(scope="module", autouse=True)
def inject_verifier():
    os.makedirs(VDIR, exist_ok=True)
    with open(os.path.join(VDIR, "z.go"), "w") as f:
        f.write("package verify\n")
    shutil.copy(os.path.join(HERE, "fixtures", "heldout_test.go"),
                os.path.join(VDIR, "heldout_test.go"))
    yield
    shutil.rmtree(VDIR, ignore_errors=True)


@pytest.fixture(scope="module")
def results(inject_verifier):
    """Compile the held-out test package ONCE and run every subtest in a single
    `go test` invocation (compiling CUE's evaluator a single time instead of once
    per case), then parse the per-subtest PASS/FAIL lines. Per-case reporting is
    preserved for the solvability gate while the verifier's compile cost drops by
    a factor of the number of cases. If compilation fails (e.g. a fix that breaks
    the build), no subtest lines are emitted and every case is reported as not
    run against the captured output."""
    r = subprocess.run(
        ["go", "test", "./verify/", "-count=1", "-v",
         "-run", "TestConflictDetected|TestValidUnaffected"],
        cwd=APP, capture_output=True, text=True, env=ENV, timeout=900)
    out = r.stdout + r.stderr
    status = {}
    for m in re.finditer(
            r"--- (PASS|FAIL): (?:TestConflictDetected|TestValidUnaffected)/(\S+)", out):
        status[m.group(2)] = m.group(1)
    return status, out


@pytest.mark.parametrize("name", CONFLICT)
def test_conflict_detected(results, name):
    """A conflicting override of a reference-constrained field inside an inline
    struct must be reported as a conflict error."""
    status, out = results
    got = status.get(name, "not run — the held-out test package failed to compile")
    assert got == "PASS", (
        f"a conflicting inline-struct override was not reported as an error "
        f"(subtest {name}: {got}).\n{out}")


@pytest.mark.parametrize("name", GUARD)
def test_valid_unaffected(results, name):
    """A valid configuration (an inline override that agrees, further constrains
    an abstract field, or is an ordinary merge/list) must keep evaluating without
    error — guarding against an over-aggressive fix."""
    status, out = results
    got = status.get(name, "not run — the held-out test package failed to compile")
    assert got == "PASS", (
        f"a valid configuration was wrongly rejected "
        f"(subtest {name}: {got}).\n{out}")


def test_module_still_builds():
    """The whole module must still compile offline after the fix — this catches a
    fix that removes/renames exported symbols (the 'do not alter the public API'
    constraint) or otherwise breaks unrelated packages."""
    r = subprocess.run(["go", "build", "./..."], cwd=APP,
                       capture_output=True, text=True, env=ENV, timeout=600)
    assert r.returncode == 0, (
        f"`go build ./...` failed after the change (public API or an unrelated "
        f"package was broken).\n--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}")
