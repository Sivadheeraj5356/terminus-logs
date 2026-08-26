"""Property verifier for fleetmesh-lockframe-resolve.

This never re-runs the agent's own resolver. It reloads /app/registry and
/app/manifest.toml from scratch, checks the agent's /app/out/lock.json
against RULES.md by definition (bidirectional: missing/out-of-range
packages count as under-resolution, unrequested or mutually conflicting
packages count as over-resolution), and separately assembles a real Go
build from /app/project plus the compat package the agent wrote, so a
lockfile that is symbolically valid but points at a telemetrybus version
the adapter cannot actually satisfy still fails.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# write_perturbation_fixture and write_any_of_conflict_perturbation_fixture
# live in _verifier_fixtures.py so the two unseen registries the R11 tests
# below run the agent's resolver against are not mixed into the property
# checks this file itself holds.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _verifier_fixtures import (  # noqa: E402
    write_any_of_conflict_perturbation_fixture,
    write_perturbation_fixture,
)

REG_DIR = os.environ.get("REG_DIR", "/app/registry")
MANIFEST_PATH = os.environ.get("MANIFEST_PATH", "/app/manifest.toml")
RULES_PATH = os.environ.get("RULES_PATH", "/app/RULES.md")
PROJECT_DIR = os.environ.get("PROJECT_DIR", "/app/project")
CONSUMER_PATH = os.path.join(PROJECT_DIR, "consumer.go")
LOCK_PATH = os.environ.get("LOCK_PATH", "/app/out/lock.json")
COMPAT_DIR = os.path.join(PROJECT_DIR, "compat", "telemetrybusv1")
RESOLVER_SRC_DIR = os.path.join(PROJECT_DIR, "resolver")

RULES_MD_SHA256 = "2702ed7b52b3d7a026bfcdb9341ac450a01161ca99d0cf79e05f4dac45c6809f"
MANIFEST_SHA256 = "ce6e056297ff918d14accf8a0d6e0939906b00d025c238f98fabd7cb88ae22da"
CONSUMER_SHA256 = "480630c0fd6b862dce0dbead71df2a0d6438c61a9bfdfb47bd11dfe2e617d6da"
REGISTRY_TREE_SHA256 = "347da68143002563a74f150fa07d15cb8de48c24296de4c8d327bcc8a44f3269"

# A standalone probe program, assembled alongside consumer.go in the same
# isolated build tree. It reports three events through the agent's compat
# package, the middle one over the byte limit, so the build check can tell
# an adapter that translates the new telemetrybus surface correctly apart
# from one that panics on a missing context, panics on a lost window
# pointer, or silently drops the size error instead of returning it.
PROBE_MAIN_GO = """package main

import (
\t"fmt"
\t"os"
\t"strings"

\t"fleetmesh/compat/telemetrybusv1"
)

func main() {
\tif err := telemetrybusv1.Report("svc.heartbeat ok"); err != nil {
\t\tfmt.Fprintln(os.Stderr, "first:", err)
\t\tos.Exit(1)
\t}
\tfmt.Println("first-ok")

\toversized := strings.Repeat("a", 97)
\tif err := telemetrybusv1.Report(oversized); err != nil {
\t\tfmt.Println("second-error:" + err.Error())
\t} else {
\t\tfmt.Println("second-ok")
\t}

\tif err := telemetrybusv1.Report("svc.stop ok"); err != nil {
\t\tfmt.Fprintln(os.Stderr, "third:", err)
\t\tos.Exit(1)
\t}
\tfmt.Println("third-ok")
}
"""

# A second probe, assembled in the same isolated tree. It reports six
# ordinary events through the agent's compat package and then reads the
# bus's process delivery record back through telemetrybus.Delivered(),
# printing the slot the bus stamped each one with. telemetrybus 3.1.0
# numbers a window's deliveries from its opening slot, a window goes full
# after WindowCapacity (4) deliveries, a process may not open more than
# MaxWindowsPerProcess (2) windows over its life, and a process's
# deliveries are meant to arrive as one continuous slot run from 0, so a
# faithful adapter produces slots 0,1,2,3,4,5 across the window boundary
# using exactly the two windows its budget allows. An adapter that opens a
# fresh window inside every Report restarts the slot each call and stamps
# every delivery 0; one that keeps one window but never carries the run
# past the cap gets ErrWindowFull on the fifth Report and surfaces it as
# an error; one that tracks its own slot counter and opens fresh at
# OpenAt(counter) every call gets the slots right but spends a window per
# event and runs out of budget on the third call. consumer.go only ever
# reports once, under both limits, so nothing but a multi-report run that
# crosses them exposes any of the three misses.
PROBE_SESSION_GO = """package main

import (
\t"fmt"
\t"os"

\t"fleetmesh/compat/telemetrybusv1"
\t"fleetmesh/telemetrybus"
)

func main() {
\tevents := []string{"svc.a start", "svc.b ready", "svc.c serving", "svc.d busy", "svc.e draining", "svc.f gone"}
\tfor _, e := range events {
\t\tif err := telemetrybusv1.Report(e); err != nil {
\t\t\tfmt.Fprintln(os.Stderr, "report:", err)
\t\t\tos.Exit(1)
\t\t}
\t}
\tfor _, rec := range telemetrybus.Delivered() {
\t\tfmt.Printf("%d %s\\n", rec.Slot, rec.Event)
\t}
}
"""


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def sha256_tree(root):
    entries = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            entries.append((rel, sha256_file(path)))
    entries.sort()
    combined = "\n".join(f"{rel}:{digest}" for rel, digest in entries)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ---------- version and range semantics (R1, R2) ----------

def parse_version(s):
    parts = s.split(".")
    assert len(parts) == 3, f"bad version {s!r}"
    return tuple(int(p) for p in parts)


def parse_range(s):
    if s.startswith(">="):
        return ">=", parse_version(s[2:])
    if s.startswith("^"):
        return "^", parse_version(s[1:])
    if s.startswith("="):
        return "=", parse_version(s[1:])
    raise AssertionError(f"bad range {s!r}")


def range_matches(range_str, candidate):
    op, target = parse_range(range_str)
    if op == "=":
        return candidate == target
    if op == ">=":
        return candidate >= target
    if op == "^":
        return candidate[1] == target[1] and candidate[0] >= target[0]
    raise AssertionError(f"bad operator {op!r}")


# ---------- registry and manifest loading (fresh, never via the agent) ----------

def load_registry(root):
    reg = {}
    for pkg in sorted(os.listdir(root)):
        pkg_dir = os.path.join(root, pkg)
        if not os.path.isdir(pkg_dir):
            continue
        reg[pkg] = {}
        for ver in sorted(os.listdir(pkg_dir)):
            ver_dir = os.path.join(pkg_dir, ver)
            index_path = os.path.join(ver_dir, "index.json")
            if not os.path.isfile(index_path):
                continue
            with open(index_path, encoding="utf-8") as fh:
                reg[pkg][ver] = json.load(fh)
    return reg


def load_manifest(path):
    reqs = []
    cur = None
    in_requires = False
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line == "[[requires]]":
                if cur is not None:
                    reqs.append(cur)
                cur = {}
                in_requires = True
                continue
            if line.startswith("["):
                in_requires = False
                continue
            if not in_requires or cur is None:
                continue
            m = re.match(r'(\w+)\s*=\s*"([^"]*)"', line)
            if m:
                cur[m.group(1)] = m.group(2)
    if cur is not None:
        reqs.append(cur)
    return reqs


REGISTRY = load_registry(REG_DIR)
ROOT_REQS = load_manifest(MANIFEST_PATH)


# ---------- checker: bidirectional validation against a lockfile (R3-R6) ----------

def load_lock():
    assert os.path.isfile(LOCK_PATH), f"missing lockfile at {LOCK_PATH}"
    with open(LOCK_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict), "lock.json must be a JSON object"
    for pkg, ver in data.items():
        assert isinstance(pkg, str) and isinstance(ver, str), "lock.json keys and values must be strings"
    return data


def index_of(pkg, ver):
    assert pkg in REGISTRY, f"unknown package {pkg!r} in lockfile"
    assert ver in REGISTRY[pkg], f"{pkg}@{ver} does not exist in the registry"
    return REGISTRY[pkg][ver]


def check_lockfile(lock):
    """Returns a list of violation strings; empty means the lockfile is
    valid under R3-R6. Checks both directions: under-resolution (missing
    package, out-of-range version, unmet any_of) and over-resolution
    (unreachable package, conflicting pair)."""
    problems = []

    for req in ROOT_REQS:
        pkg, rng = req["package"], req["range"]
        if pkg not in lock:
            problems.append(f"under: root requires {pkg} {rng}, missing from lockfile")
            continue
        ver = parse_version(lock[pkg])
        if not range_matches(rng, ver):
            problems.append(f"under: {pkg}={lock[pkg]} does not satisfy root range {rng}")

    for pkg, ver_str in lock.items():
        idx = index_of(pkg, ver_str)
        for entry in idx.get("requires", []):
            if "any_of" in entry:
                alts = entry["any_of"]
                if not any(
                    alt["package"] in lock and range_matches(alt["range"], parse_version(lock[alt["package"]]))
                    for alt in alts
                ):
                    problems.append(f"under: {pkg}={ver_str} any_of unmet: {alts}")
                continue
            target, rng = entry["package"], entry["range"]
            if target not in lock:
                problems.append(f"under: {pkg}={ver_str} requires {target} {rng}, missing from lockfile")
                continue
            if not range_matches(rng, parse_version(lock[target])):
                problems.append(
                    f"under: {pkg}={ver_str} requires {target} {rng}, "
                    f"but lockfile has {target}={lock[target]}"
                )

    for pkg, ver_str in lock.items():
        idx = index_of(pkg, ver_str)
        for c in idx.get("conflicts", []):
            other, rng = c["package"], c["range"]
            if other in lock and range_matches(rng, parse_version(lock[other])):
                problems.append(f"over: {pkg}={ver_str} conflicts with {other}={lock[other]}")

    reachable = compute_reachable(lock, REGISTRY, ROOT_REQS)
    for pkg in lock:
        if pkg not in reachable:
            problems.append(f"over: {pkg}={lock[pkg]} present but not reachable from the manifest")

    return problems


def compute_reachable(lock, registry, root_reqs):
    """R4: the set of packages reachable from the root requirements by
    following each chosen version's requires list. A plain requirement's
    target is reachable through it; an any_of group's reachable member is
    whichever listed alternative is both present in the lock and actually
    matches its declared range (R3 is satisfied by any one of them, so more
    than one can legitimately be reachable this way at once). Parameterized
    on registry/root_reqs, rather than closing over the module-level
    REGISTRY/ROOT_REQS, so this walk can be exercised directly against a
    small synthetic graph instead of only ever through /app/registry."""
    reachable = set()
    frontier = [r["package"] for r in root_reqs if r["package"] in lock]
    while frontier:
        pkg = frontier.pop()
        if pkg in reachable:
            continue
        reachable.add(pkg)
        if pkg not in lock:
            continue
        idx = registry[pkg][lock[pkg]]
        for entry in idx.get("requires", []):
            if "any_of" in entry:
                for alt in entry["any_of"]:
                    nxt = alt["package"]
                    if (
                        nxt in lock
                        and nxt not in reachable
                        and range_matches(alt["range"], parse_version(lock[nxt]))
                    ):
                        frontier.append(nxt)
                continue
            nxt = entry["package"]
            if nxt in lock and nxt not in reachable:
                frontier.append(nxt)
    return reachable


# ---------- fixtures for the bidirectional fuzz (built at collection time,
# static, never from runtime randomness) ----------

def build_reference_lock():
    """A hand-verified satisfying assignment, used only to build the fuzz
    fixtures below. The agent's actual lock.json is graded solely through
    check_lockfile() above and is never compared against this."""
    lock = {f"auxlib{i:02d}": "1.0.0" for i in range(1, 61)}
    lock.update({
        "dispatchctl": "2.0.4",
        "fleetbilling": "2.0.0",
        "wiretype": "1.0.0",
        "ratesync": "2.1.0",
        "routectl": "2.1.0",
        "fleetauth": "2.0.0",
        "quotacap": "2.0.0",
        "telemetrybus": "3.1.0",
        "alertagg": "1.2.0",
        "alertfeed": "3.0.0",
        "backoffpolicy": "1.4.0",
        "backoffcore": "2.0.0",
        "snapreader": "1.3.0",
        "snapwriter": "2.5.0",
    })
    return lock


def test_reference_lock_is_valid():
    """Sanity check on the fixture builder itself: R3-R6 all hold for the
    hand-verified assignment before it is used to derive fuzz mutants."""
    assert check_lockfile(build_reference_lock()) == []


def test_naive_all_high_version_assignment_is_invalid():
    """Guards the core mechanism this task relies on: a resolver that
    always grabs each package's numerically higher compatible version and
    never revisits a choice produces a complete, locally plausible lockfile
    that still violates a conflict somewhere in the graph."""
    naive = {f"auxlib{i:02d}": "1.0.0" for i in range(1, 61)}
    naive.update({
        "dispatchctl": "3.0.0",
        "fleetbilling": "2.0.0",
        "wiretype": "2.0.0",
        "ratesync": "2.1.0",
        "routectl": "3.0.0",
        "fleetauth": "2.2.0",
        "credstore": "1.0.0",
        "quotacap": "2.0.0",
        "telemetrybus": "3.1.0",
        "alertagg": "2.0.0",
        "alertfeed": "3.0.0",
        "backoffpolicy": "2.1.0",
        "backoffcore": "2.0.0",
        "snapreader": "3.0.0",
        "snapwriter": "2.5.0",
    })
    problems = check_lockfile(naive)
    assert any(p.startswith("under:") or p.startswith("over:") for p in problems)


def test_wiretype_pin_breaks_dispatchctl_highest():
    """R3/R4: dispatchctl's newest release wants wiretype 2.0.0, but every
    fleetbilling release pins wiretype to 1.0.0, so pairing dispatchctl's
    newest release with any fleetbilling release is under-resolved on
    wiretype, independent of which fleetbilling version is present."""
    mutant = build_reference_lock()
    mutant["dispatchctl"] = "3.0.0"
    mutant["wiretype"] = "2.0.0"
    problems = check_lockfile(mutant)
    assert any("wiretype" in p for p in problems)


def test_routectl_highest_conflicts_with_ratesync_floor():
    """R3: routectl's newest release conflicts with ratesync at or above
    2.0.0, which is exactly the floor fleetbilling's newest release
    requires, so the two cannot both be the newest release at once."""
    mutant = build_reference_lock()
    mutant["routectl"] = "3.0.0"
    problems = check_lockfile(mutant)
    assert any(p.startswith("over:") and "conflicts" in p for p in problems)


def test_fleetauth_highest_release_reaches_telemetrybus_through_credstore():
    """R3/R4: fleetauth's newest release also pulls credstore, whose only
    release conflicts with telemetrybus at or above 3.0.0; fleetauth's own
    quotacap floor forces quotacap 2.0.0, which forces telemetrybus into
    that exact conflicting range, so the newest fleetauth release only
    becomes unreachable once quotacap and telemetrybus are both resolved,
    not from anything visible where fleetauth itself is chosen."""
    mutant = build_reference_lock()
    mutant["fleetauth"] = "2.2.0"
    mutant["credstore"] = "1.0.0"
    problems = check_lockfile(mutant)
    assert any(p.startswith("over:") and "conflicts" in p for p in problems)


def test_quotacap_below_2_0_0_always_conflicts_with_wiretype():
    """R3: both quotacap releases below 2.0.0 conflict with wiretype at
    exactly 1.0.0, and wiretype is always 1.0.0 once any fleetbilling
    release is present, so neither lower quotacap release ever joins a
    valid resolution regardless of which fleetauth release reached it."""
    mutant = build_reference_lock()
    mutant["quotacap"] = "1.3.0"
    mutant["fleetauth"] = "2.0.0"
    mutant["telemetrybus"] = "2.0.0"
    problems = check_lockfile(mutant)
    assert any(p.startswith("over:") and "conflicts" in p for p in problems)


def test_alertagg_alertfeed_conflict_is_over_resolved():
    """R3/over: an independent conflict pair, unconnected to the rest of
    the graph, still fires regardless of which package's index.json
    carries the declaration."""
    mutant = build_reference_lock()
    mutant["alertagg"] = "2.0.0"
    mutant["alertfeed"] = "3.0.0"
    problems = check_lockfile(mutant)
    assert any(p.startswith("over:") and "conflicts" in p for p in problems)


def test_backoffpolicy_backoffcore_conflict_is_over_resolved():
    """R3/over: same conflict shape as alertagg/alertfeed, on an unrelated
    pair, to confirm the check is not special-cased to one package name."""
    mutant = build_reference_lock()
    mutant["backoffpolicy"] = "2.1.0"
    mutant["backoffcore"] = "2.0.0"
    problems = check_lockfile(mutant)
    assert any(p.startswith("over:") and "conflicts" in p for p in problems)


def test_snapreader_snapwriter_conflict_is_over_resolved():
    """R3/over: a third independent conflict pair."""
    mutant = build_reference_lock()
    mutant["snapreader"] = "3.0.0"
    mutant["snapwriter"] = "2.5.0"
    problems = check_lockfile(mutant)
    assert any(p.startswith("over:") and "conflicts" in p for p in problems)


def test_unreachable_extra_package_is_over_resolved():
    """R4/over: a package nothing requires must not appear, even if every
    range and conflict it is subject to would otherwise be satisfied."""
    mutant = build_reference_lock()
    mutant["auxlib61"] = "1.0.0"
    problems = check_lockfile(mutant)
    assert any("auxlib61" in p and "not reachable" in p for p in problems)


def test_missing_telemetrybus_is_under_resolved():
    """R4/under: quotacap 2.0.0 requires telemetrybus, so dropping it while
    keeping quotacap must fail regardless of any other rule."""
    mutant = build_reference_lock()
    del mutant["telemetrybus"]
    problems = check_lockfile(mutant)
    assert any("telemetrybus" in p for p in problems)


def test_telemetrybus_below_quotacap_floor_is_under_resolved():
    """R2/R4: telemetrybus below quotacap 2.0.0's ">=3.0.0" floor must fail
    even though it is a real registry version and satisfies every other
    range in isolation."""
    mutant = build_reference_lock()
    mutant["telemetrybus"] = "2.0.0"
    problems = check_lockfile(mutant)
    assert any("telemetrybus" in p for p in problems)


def test_caret_excludes_version_below_requested_major():
    """R2: dispatchctl 1.9.0 never satisfies the manifest's ^2.0.0, since
    its major is below the requested floor regardless of its minor."""
    assert not range_matches("^2.0.0", parse_version("1.9.0"))
    assert range_matches("^2.0.0", parse_version("4.0.0"))


def test_dispatchctl_caret_admits_only_the_requested_minor():
    """R2: the manifest asks for dispatchctl ^2.0.0, which under R1/R2 pins
    the minor to 0 and lets the major float upward. dispatchctl 2.1.0 is a
    real registry release and the numerically highest one inside the 2.x
    line, so a resolver that reads ^ as "same major, any higher minor"
    grabs it first and produces a complete, locally consistent lockfile;
    but its minor is 1, not 0, so the manifest range never admits it and
    the lockfile is under-resolved on the root requirement itself. The
    correct minor-0 releases (2.0.0, 2.0.4, and the conflicted 3.0.0) are a
    different set entirely."""
    mutant = build_reference_lock()
    mutant["dispatchctl"] = "2.1.0"
    problems = check_lockfile(mutant)
    assert any(
        "dispatchctl" in p and p.startswith("under:") for p in problems
    ), problems


def test_fleetbilling_caret_floats_major_keeps_minor():
    """R2: fleetbilling ^1.0.0 admits any minor-0 release regardless of
    major (1.0.0, 1.0.2, and 2.0.0 all qualify), while fleetbilling 1.1.0,
    the highest release a same-major reading of ^ would keep inside the 1.x
    line, has minor 1 and is out of range. A resolver carrying the common
    ecosystem convention (^ pins the major, floats the minor) lands on the
    wrong side of both boundaries at once: it takes 1.1.0 and never
    considers 2.0.0. The lockfile that results is under-resolved on the
    root requirement even though every dependency 1.1.0 declares is
    satisfiable."""
    mutant = build_reference_lock()
    mutant["fleetbilling"] = "1.1.0"
    problems = check_lockfile(mutant)
    assert any(
        "fleetbilling" in p and p.startswith("under:") for p in problems
    ), problems


def test_at_least_operator_is_lexicographic():
    """R2: ">=3.0.0" compares major, then minor, then patch in order."""
    assert range_matches(">=3.0.0", parse_version("3.9.0"))
    assert not range_matches(">=3.0.0", parse_version("2.9.9"))


def test_exact_operator_rejects_neighbors():
    """R2: "=1.0.0" matches only that exact triple."""
    assert range_matches("=1.0.0", parse_version("1.0.0"))
    assert not range_matches("=1.0.0", parse_version("1.0.1"))
    assert not range_matches("=1.0.0", parse_version("1.1.0"))


def test_every_lock_entry_is_a_real_registry_version():
    """R1/R6: every (package, version) the agent writes must exist in the
    registry as shipped."""
    lock = load_lock()
    for pkg, ver in lock.items():
        assert pkg in REGISTRY, f"{pkg} is not a package in /app/registry"
        assert ver in REGISTRY[pkg], f"{pkg}@{ver} is not a released version"


def test_agent_lockfile_satisfies_manifest():
    """R3-R6: the agent's actual /app/out/lock.json, checked fresh against
    the registry and manifest, must have zero violations in either
    direction."""
    problems = check_lockfile(load_lock())
    assert problems == [], "\n".join(problems)


def test_agent_lockfile_reaches_telemetrybus():
    """The manifest never requires telemetrybus directly; a lockfile that
    resolves everything else but never reaches it has not actually solved
    the graph the manifest describes."""
    lock = load_lock()
    assert "telemetrybus" in lock, "lockfile never resolves telemetrybus"


def test_lockfile_keys_are_in_ascending_order():
    """R10: /app/out/lock.json lists its keys in ascending lexicographic
    order by package name in the file's own text, not just as a matter of
    the parsed dict. Checked against the raw token order so a lockfile that
    happens to parse the same set of pairs but writes them out of order
    still fails."""
    with open(LOCK_PATH, encoding="utf-8") as fh:
        text = fh.read()
    keys_in_order = re.findall(r'"([^"]+)"\s*:', text)
    assert keys_in_order, "could not find any \"key\": pairs in lock.json"
    assert keys_in_order == sorted(keys_in_order), (
        "R10 requires lock.json keys in ascending lexicographic order; got "
        + repr(keys_in_order[:6]) + "..."
    )


# ---------- anti-cheat: fixed inputs stay fixed (R9) ----------

def test_registry_untouched():
    """R9: /app/registry must stay byte-identical to what shipped."""
    assert sha256_tree(REG_DIR) == REGISTRY_TREE_SHA256


def test_manifest_untouched():
    """R9: /app/manifest.toml must stay byte-identical to what shipped."""
    assert sha256_file(MANIFEST_PATH) == MANIFEST_SHA256


def test_consumer_untouched():
    """R9: /app/project/consumer.go must stay byte-identical to what shipped."""
    assert sha256_file(CONSUMER_PATH) == CONSUMER_SHA256


def test_rules_md_unchanged():
    """R9: /app/RULES.md must stay byte-identical to what shipped."""
    assert sha256_file(RULES_PATH) == RULES_MD_SHA256


# ---------- build check: assemble a fresh Go module and build it for real ----------

def _assemble_build_tree(tmp, lock):
    shutil.copyfile(os.path.join(PROJECT_DIR, "go.mod"), os.path.join(tmp, "go.mod"))
    shutil.copyfile(CONSUMER_PATH, os.path.join(tmp, "consumer.go"))
    compat_dst = os.path.join(tmp, "compat", "telemetrybusv1")
    assert os.path.isdir(COMPAT_DIR), "agent did not write compat/telemetrybusv1"
    shutil.copytree(COMPAT_DIR, compat_dst)

    assert "telemetrybus" in lock, "lockfile has no telemetrybus entry to build against"
    telemetrybus_ver = lock["telemetrybus"]
    stub_path = os.path.join(REG_DIR, "telemetrybus", telemetrybus_ver, "stub.go")
    assert os.path.isfile(stub_path), f"telemetrybus {telemetrybus_ver} is not a real registry version"
    telemetrybus_dst = os.path.join(tmp, "telemetrybus")
    os.makedirs(telemetrybus_dst, exist_ok=True)
    shutil.copyfile(stub_path, os.path.join(telemetrybus_dst, "telemetrybus.go"))

    probe_dst = os.path.join(tmp, "probe")
    os.makedirs(probe_dst, exist_ok=True)
    with open(os.path.join(probe_dst, "main.go"), "w", encoding="utf-8") as fh:
        fh.write(PROBE_MAIN_GO)

    session_dst = os.path.join(tmp, "probe_session")
    os.makedirs(session_dst, exist_ok=True)
    with open(os.path.join(session_dst, "main.go"), "w", encoding="utf-8") as fh:
        fh.write(PROBE_SESSION_GO)

    return telemetrybus_ver


def _run_in_empty_jail(binary_path, timeout=30):
    """Runs a compiled binary built from the agent's compat package inside a
    chroot jail that holds nothing but a copy of the binary itself. These
    probes need no filesystem access at all to behave correctly (they only
    print to stdout), so a jail with nothing else present turns an adapter
    that tries to read /tests, /solution, or anywhere outside its own
    process (through an injected init() or otherwise) into an open()
    failure instead of a successful read of the verifier's own source."""
    with tempfile.TemporaryDirectory() as jail:
        jailed_bin = os.path.join(jail, "prog")
        shutil.copyfile(binary_path, jailed_bin)
        os.chmod(jailed_bin, 0o755)
        return subprocess.run(
            ["chroot", jail, "/prog"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )


def test_project_builds_against_resolved_lockfile():
    """R7/R8: assemble consumer.go, the agent's compat package, and the
    registry's telemetrybus source at the version lock.json names, in
    complete isolation from anything the agent may have left lying around,
    and confirm `go build ./...` succeeds."""
    lock = load_lock()
    with tempfile.TemporaryDirectory() as tmp:
        _assemble_build_tree(tmp, lock)
        env = dict(os.environ)
        env["GOFLAGS"] = "-mod=mod"
        env["GOPROXY"] = "off"
        result = subprocess.run(
            ["go", "build", "./..."],
            cwd=tmp,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr


def test_project_behaves_like_the_pre_migration_contract():
    """R7: consumer.go expects the compat layer to deliver a single startup
    event the same way the pre-migration Report did; running the built
    program must print notify-ok, not an error."""
    lock = load_lock()
    with tempfile.TemporaryDirectory() as tmp:
        _assemble_build_tree(tmp, lock)
        env = dict(os.environ)
        env["GOFLAGS"] = "-mod=mod"
        env["GOPROXY"] = "off"
        built = os.path.join(tmp, "consumer_bin")
        build = subprocess.run(
            ["go", "build", "-o", built, "."],
            cwd=tmp,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert build.returncode == 0, build.stderr
        run = _run_in_empty_jail(built)
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "notify-ok"


def test_compat_surfaces_the_size_limit_without_crashing():
    """R7: MIGRATION.md documents that Queue reports an oversized event
    before Flush does any work and that a single Window serves any number
    of Queue/Flush cycles. An adapter that forgets context.Background,
    loses track of the window pointer, or swallows Queue's error instead of
    returning it either crashes this probe or prints the wrong line for the
    middle call. The middle line's error text is not pinned to
    telemetrybus's exact wording (an adapter wrapping the error with %w
    before returning it is still a faithful pass-through), only to carrying
    the two byte counts telemetrybus itself reports."""
    lock = load_lock()
    with tempfile.TemporaryDirectory() as tmp:
        _assemble_build_tree(tmp, lock)
        env = dict(os.environ)
        env["GOFLAGS"] = "-mod=mod"
        env["GOPROXY"] = "off"
        built = os.path.join(tmp, "probe_bin")
        build = subprocess.run(
            ["go", "build", "-o", built, "./probe"],
            cwd=tmp,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert build.returncode == 0, build.stderr
        run = _run_in_empty_jail(built)
        assert run.returncode == 0, run.stderr
        lines = run.stdout.strip().splitlines()
        assert len(lines) == 3, run.stdout
        assert lines[0] == "first-ok", run.stdout
        assert lines[2] == "third-ok", run.stdout
        assert lines[1].startswith("second-error:"), run.stdout
        error_text = lines[1][len("second-error:"):]
        assert "97" in error_text and "96" in error_text, (
            "adapter's oversized-event error should surface the byte counts "
            "telemetrybus reports (event size vs limit), got: " + error_text
        )


def test_compat_keeps_one_delivery_window_across_reports():
    """R7: telemetrybus 3.1.0 stamps each delivered event with the next
    slot in the delivering window's run, a window opened with Open starts
    at slot 0 and goes full after WindowCapacity deliveries, OpenAt(slot)
    starts a window's run at slot, and MIGRATION.md documents that a
    process's deliveries are meant to reach the bus as one continuous slot
    run from 0. MIGRATION.md also documents that a process may not open
    more than MaxWindowsPerProcess windows over its life, win or lose,
    which is exactly the number a faithful adapter needs for this probe:
    it reuses one window and, when the fifth event fills it, carries the
    run forward in a second window opened at the process's next slot, so
    the slots come out 0,1,2,3,4,5 with two windows total. Three adapters
    that pass a single-call smoke test miss this: one that opens a fresh
    window inside every Report restarts the slot each call and stamps
    every delivery 0; one that keeps a single window but never carries the
    run past the cap hits ErrWindowFull on the fifth Report and surfaces
    it as an error; and one that tracks its own slot counter and calls
    OpenAt(counter) fresh on every Report gets the slots right but opens a
    sixth window doing it, past the budget MIGRATION.md documents, and
    ErrTooManyWindows surfaces on the third call before the slot sequence
    even matters. consumer.go only reports once, under both the capacity
    and the window budget, so a single-call smoke test cannot tell any of
    the three apart; this run is what forces the adapter to keep the
    process's slot run continuous across the calls and to do it inside
    the window budget the bus allows."""
    lock = load_lock()
    with tempfile.TemporaryDirectory() as tmp:
        _assemble_build_tree(tmp, lock)
        env = dict(os.environ)
        env["GOFLAGS"] = "-mod=mod"
        env["GOPROXY"] = "off"
        built = os.path.join(tmp, "session_bin")
        build = subprocess.run(
            ["go", "build", "-o", built, "./probe_session"],
            cwd=tmp,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert build.returncode == 0, build.stderr
        run = _run_in_empty_jail(built)
        assert run.returncode == 0, run.stderr
        lines = run.stdout.strip().splitlines()
        expected_events = [
            "svc.a start", "svc.b ready", "svc.c serving",
            "svc.d busy", "svc.e draining", "svc.f gone",
        ]
        assert len(lines) == len(expected_events), run.stdout
        slots = []
        got_events = []
        for line in lines:
            slot_str, _, event = line.partition(" ")
            slots.append(int(slot_str))
            got_events.append(event)
        assert slots == list(range(len(expected_events))), (
            "the bus should stamp the process's deliveries as one continuous "
            "slot run 0,1,2,3,4,5; a per-call adapter restarts the slot each "
            "call and a single-window adapter that ignores the capacity "
            "breaks the run at the cap, got slots: " + repr(slots)
        )
        assert got_events == expected_events, run.stdout


def test_no_stray_go_files_outside_compat_and_project():
    """Sanity bound on the agent's footprint: the registry stubs the fuzz
    and build checks depend on must still be the ones shipped, not files
    the agent dropped somewhere under /app/registry."""
    stray = list(glob.glob(os.path.join(REG_DIR, "**", "*.go"), recursive=True))
    assert len(stray) == 104, f"unexpected .go file count under {REG_DIR}: {len(stray)}"


def test_reachability_closure_traverses_satisfied_any_of_alternative():
    """R4: a package that enters the resolved set solely by satisfying an
    any_of group must count as reachable through that requirement, exactly
    like a plain requirement's target. Regression test for a reachability
    walk that used to skip every any_of entry outright: on this synthetic
    two-package graph, optB is reachable only via the any_of on root, with
    no other requirement pointing at it, so a walk that never follows a
    satisfied alternative would mark it unreachable and reject a
    genuinely correct, R3-satisfying lockfile as over-resolved."""
    registry = {
        "root": {
            "1.0.0": {
                "requires": [
                    {"any_of": [
                        {"package": "optA", "range": ">=1.0.0"},
                        {"package": "optB", "range": ">=1.0.0"},
                    ]},
                ],
                "conflicts": [],
            },
        },
        "optA": {"1.0.0": {"requires": [], "conflicts": []}},
        "optB": {"1.0.0": {"requires": [], "conflicts": []}},
    }
    root_reqs = [{"package": "root", "range": "=1.0.0"}]
    lock = {"root": "1.0.0", "optB": "1.0.0"}
    assert compute_reachable(lock, registry, root_reqs) == {"root", "optB"}


# ---------- R11: the resolver must be a real, rerunnable program ----------

def _build_agent_resolver(tmp):
    """Builds the resolver source a submission leaves at
    /app/project/resolver/main.go, exactly the way R11 requires:
    `go build ./resolver` from PROJECT_DIR itself, no copy, no
    reconstruction elsewhere."""
    built = os.path.join(tmp, "agent_resolver")
    env = dict(os.environ)
    env["GOFLAGS"] = "-mod=mod"
    env["GOPROXY"] = "off"
    result = subprocess.run(
        ["go", "build", "-o", built, "./resolver"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, f"resolver at {RESOLVER_SRC_DIR} failed to build: {result.stderr}"
    return built


def _run_resolver_in_jail(resolver_bin, reg_dir, manifest_path, timeout=60):
    """Runs the agent's resolver binary inside a chroot jail holding only a
    copy of the registry directory and manifest it is meant to read, plus
    an empty writable output directory: everything R1-R6 legitimately need,
    nothing under /tests or /solution to read instead. Returns (run,
    lock_dict_or_None), where lock_dict is the parsed output lockfile (read
    from inside the jail before it is torn down) or None if the resolver
    never wrote one."""
    with tempfile.TemporaryDirectory() as jail:
        jailed_bin = os.path.join(jail, "prog")
        shutil.copyfile(resolver_bin, jailed_bin)
        os.chmod(jailed_bin, 0o755)
        shutil.copytree(reg_dir, os.path.join(jail, "registry"))
        shutil.copyfile(manifest_path, os.path.join(jail, "manifest.toml"))
        os.makedirs(os.path.join(jail, "out"), exist_ok=True)
        run = subprocess.run(
            ["chroot", jail, "/prog", "/registry", "/manifest.toml", "/out/lock.json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out_lock_path = os.path.join(jail, "out", "lock.json")
        lock_dict = None
        if os.path.isfile(out_lock_path):
            with open(out_lock_path, encoding="utf-8") as fh:
                lock_dict = json.load(fh)
        return run, lock_dict


def test_agent_resolver_reproduces_its_own_lockfile():
    """R11: re-running the resolver against the real registry and manifest,
    into a fresh output path, must reproduce the exact lockfile already at
    /app/out/lock.json. A lock.json written by hand with no resolver behind
    it fails here, together with the generality check below."""
    assert os.path.isdir(RESOLVER_SRC_DIR), "no resolver source at /app/project/resolver"
    with tempfile.TemporaryDirectory() as tmp:
        resolver_bin = _build_agent_resolver(tmp)
        run, rerun_lock = _run_resolver_in_jail(resolver_bin, REG_DIR, MANIFEST_PATH)
        assert run.returncode == 0, run.stderr
        assert rerun_lock == load_lock(), "resolver re-run does not reproduce /app/out/lock.json"


def test_agent_resolver_solves_an_unseen_registry():
    """R11: the resolver must be a general implementation of R1-R6, not a
    program tuned to the one registry shipped under /app. Run the same
    built binary against a small registry+manifest pair it has never seen
    and check the result against the one correct assignment for that
    pair."""
    assert os.path.isdir(RESOLVER_SRC_DIR), "no resolver source at /app/project/resolver"
    with tempfile.TemporaryDirectory() as tmp:
        resolver_bin = _build_agent_resolver(tmp)
        perturb_reg, perturb_manifest, expected = write_perturbation_fixture(tmp)
        run, got = _run_resolver_in_jail(resolver_bin, perturb_reg, perturb_manifest)
        assert run.returncode == 0, run.stderr
        assert got == expected, f"expected {expected}, got {got}"


def test_agent_resolver_solves_any_of_with_conflict_backtrack():
    """R3/R4/R11: the real graph never gives the resolver an any_of to
    satisfy, so a resolver that only records any_of constraints without
    ever scheduling one of the listed alternatives as a variable to assign
    can pass every check above while still being unable to solve a
    registry that actually needs an alternative package. This fixture
    forces exactly that: the root's any_of lists branch-optA before
    branch-optB, but branch-optA conflicts with the plain-required
    branch-anchor, so the only satisfying assignment drops branch-optA and
    resolves through branch-optB instead, reachable through the any_of, not
    through any other requirement."""
    assert os.path.isdir(RESOLVER_SRC_DIR), "no resolver source at /app/project/resolver"
    with tempfile.TemporaryDirectory() as tmp:
        resolver_bin = _build_agent_resolver(tmp)
        perturb_reg, perturb_manifest, expected = write_any_of_conflict_perturbation_fixture(tmp)
        run, got = _run_resolver_in_jail(resolver_bin, perturb_reg, perturb_manifest)
        assert run.returncode == 0, run.stderr
        assert got == expected, f"expected {expected}, got {got}"
