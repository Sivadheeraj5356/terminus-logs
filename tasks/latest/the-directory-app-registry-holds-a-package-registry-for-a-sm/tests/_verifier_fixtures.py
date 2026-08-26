"""Perturbation fixtures for the R11 resolver-generality tests in
test_outputs.py. Both registries here are disjoint from /app/registry and
from each other, and neither is consulted when grading the agent's actual
/app/out/lock.json (see check_lockfile() in test_outputs.py for that); they
exist only so the agent's own resolver binary can be run a second time
against inputs it has never seen and checked against a known answer.
"""
import json
import os


def write_perturbation_fixture(root):
    """Writes a small registry+manifest pair that R11's resolver-generality
    test runs the agent's resolver against. The correct assignment only
    needs R1/R2/R4 to filter one out-of-range version and follow one
    reachable chain; this checks that the resolver reads its arguments and
    searches, instead of only ever answering for the graph it was written
    next to."""
    reg_dir = os.path.join(root, "check-registry")
    manifest_path = os.path.join(root, "check-manifest.toml")

    def write_index(pkg, ver, requires=None):
        version_dir = os.path.join(reg_dir, pkg, ver)
        os.makedirs(version_dir, exist_ok=True)
        index = {"name": pkg, "version": ver, "requires": requires or [], "conflicts": []}
        with open(os.path.join(version_dir, "index.json"), "w", encoding="utf-8") as fh:
            json.dump(index, fh)

    write_index("check-root", "1.0.0", requires=[{"package": "check-relay", "range": ">=1.5.0"}])
    write_index("check-relay", "1.0.0")
    write_index("check-relay", "2.0.0", requires=[{"package": "check-sink", "range": "=1.0.0"}])
    write_index("check-sink", "1.0.0")

    with open(manifest_path, "w", encoding="utf-8") as fh:
        fh.write(
            '[package]\n'
            'name = "check"\n'
            '\n'
            '[[requires]]\n'
            'package = "check-root"\n'
            'range = "=1.0.0"\n'
        )

    expected = {"check-relay": "2.0.0", "check-root": "1.0.0", "check-sink": "1.0.0"}
    return reg_dir, manifest_path, expected


def write_any_of_conflict_perturbation_fixture(root):
    """Writes a second unseen registry+manifest pair that exercises R3's
    any_of alternatives together with a conflict. branch-root requires
    branch-anchor (a plain requirement) and, separately, an any_of naming
    branch-optA and branch-optB; branch-anchor conflicts with branch-optA,
    so a resolver that tries the any_of alternatives in listed order picks
    branch-optA first, discovers the conflict against the already-required
    branch-anchor, and must backtrack to branch-optB, the only alternative
    that resolves the group. A resolver that only records any_of
    constraints without ever scheduling an alternative as a variable to
    assign cannot produce any assignment here at all, and one that does not
    backtrack chronologically past a failed any_of choice cannot land on
    branch-optB either."""
    reg_dir = os.path.join(root, "branch-registry")
    manifest_path = os.path.join(root, "branch-manifest.toml")

    def write_index(pkg, ver, requires=None, conflicts=None):
        version_dir = os.path.join(reg_dir, pkg, ver)
        os.makedirs(version_dir, exist_ok=True)
        index = {
            "name": pkg,
            "version": ver,
            "requires": requires or [],
            "conflicts": conflicts or [],
        }
        with open(os.path.join(version_dir, "index.json"), "w", encoding="utf-8") as fh:
            json.dump(index, fh)

    write_index(
        "branch-root",
        "1.0.0",
        requires=[
            {"package": "branch-anchor", "range": ">=1.0.0"},
            {"any_of": [
                {"package": "branch-optA", "range": ">=1.0.0"},
                {"package": "branch-optB", "range": ">=1.0.0"},
            ]},
        ],
    )
    write_index(
        "branch-anchor",
        "1.0.0",
        conflicts=[{"package": "branch-optA", "range": ">=1.0.0"}],
    )
    write_index("branch-optA", "1.0.0")
    write_index("branch-optB", "1.0.0")

    with open(manifest_path, "w", encoding="utf-8") as fh:
        fh.write(
            '[package]\n'
            'name = "branch"\n'
            '\n'
            '[[requires]]\n'
            'package = "branch-root"\n'
            'range = "=1.0.0"\n'
        )

    expected = {"branch-anchor": "1.0.0", "branch-optB": "1.0.0", "branch-root": "1.0.0"}
    return reg_dir, manifest_path, expected
