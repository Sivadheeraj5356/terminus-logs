"""Milestone 2 verifier: the build list selection rule and the lazy walk.

Every test runs the freshly built modverse CLI as a black box against a registry
materialised under a temp directory, parses its JSON, and compares the build list
against the independent Python reference in modref.py. The fixtures include
shapes where the naive answer of taking the latest version present in the
registry differs from the maximum of the versions actually required, and a foil
where a backtracking solver would converge on a different build list.
"""

import json
import os
import subprocess
import tempfile

import pytest

import fixtures
import modref as M

CLI = "/usr/local/bin/modverse"


def run_buildlist(reg, main):
    out = os.path.join(tempfile.mkdtemp(), "result.json")
    proc = subprocess.run(
        [CLI, "buildlist", "--registry", reg, "--main", main, "--out", out],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"CLI failed: {proc.stderr}"
    with open(out) as f:
        return json.load(f)


def reference_buildlist(reg, main):
    sel, _ = M.resolve(M.Registry(reg), main)
    return {k: v.display for k, v in sel.items()}


class TestMilestone2:
    def test_diamond_selects_max_of_required(self):
        """A diamond picks the higher of two required versions of the shared
        dependency, not a higher version that exists in the registry but is
        required by nobody."""
        reg, main = fixtures.make("diamond")
        got = run_buildlist(reg, main)["buildList"]
        assert got == {"A": "v1.0.0", "B": "v1.0.0", "C": "v1.2.0"}

    def test_unrequired_latest_is_not_selected(self):
        """A module is taken at the version required, even when far higher
        versions sit in the registry unreferenced."""
        reg, main = fixtures.make("unrequired_latest")
        got = run_buildlist(reg, main)["buildList"]
        assert got["D"] == "v1.0.0"
        assert "v9.9.9" not in got.values()

    def test_deep_chain_versions_exact(self):
        """A deep linear chain selects each module at exactly its required
        version, matching the reference end to end."""
        reg, main = fixtures.make("deep_chain")
        got = run_buildlist(reg, main)["buildList"]
        assert got == reference_buildlist(reg, main)
        assert got["E"] == "v1.4.0"

    def test_backtracking_foil(self):
        """In a graph with a mutual upgrade, the selection rises to the highest
        requirement reached with no search. A backtracking solver that tries to
        minimise versions would land on a different, wrong build list."""
        reg, main = fixtures.make("backtrack_foil")
        got = run_buildlist(reg, main)["buildList"]
        assert got == {"A": "v1.2.0", "B": "v1.3.0", "X": "v1.0.0"}

    def test_incompatible_outranks_plain_core(self):
        """When one requirement names the incompatible release of a shared
        dependency, it outranks the plain numeric core and is selected."""
        reg, main = fixtures.make("incompatible_select")
        got = run_buildlist(reg, main)["buildList"]
        assert got["C"] == "v2.0.0+incompatible"

    def test_empty_main_yields_empty_build_list(self):
        """A main module that requires nothing produces an empty build list and
        does not include itself."""
        reg, main = fixtures.make("empty")
        got = run_buildlist(reg, main)
        assert got["buildList"] == {}

    def test_main_module_absent_from_build_list(self):
        """No fixture build list contains the main module's own name."""
        for name in ("diamond", "deep_chain", "backtrack_foil"):
            reg, main = fixtures.make(name)
            got = run_buildlist(reg, main)["buildList"]
            assert "app" not in got

    @pytest.mark.parametrize("seed", range(40))
    def test_random_registries_match_reference(self, seed):
        """Over many randomly generated registries, the CLI build list matches
        the independent reference exactly. The registries embed unreferenced
        higher versions so that taking the registry maximum would diverge."""
        reg, main = _random_registry(seed)
        got = run_buildlist(reg, main)["buildList"]
        assert got == reference_buildlist(reg, main)


def _random_registry(seed):
    import random

    rng = random.Random(seed * 7919 + 13)
    root = tempfile.mkdtemp(prefix=f"mv_m2_rand_{seed}_")
    reg = os.path.join(root, "reg")
    os.makedirs(reg, exist_ok=True)
    n = rng.randint(3, 8)
    names = [f"m{i}" for i in range(n)]

    def ver():
        return f"v{rng.randint(1,3)}.{rng.randint(0,5)}.{rng.randint(0,3)}"

    # give each module a small set of versions, including a deliberately high
    # unreferenced one
    versions = {}
    for nm in names:
        vs = set()
        for _ in range(rng.randint(2, 4)):
            vs.add(ver())
        vs.add("v9.0.0")  # decoy nobody requires
        versions[nm] = sorted(vs)

    # build a DAG of requires
    reqs = {}
    for i, nm in enumerate(names):
        rq = []
        for j in range(i + 1, n):
            if rng.random() < 0.5:
                target = names[j]
                chosen = rng.choice([v for v in versions[target] if v != "v9.0.0"])
                rq.append((target, chosen))
        reqs[nm] = rq

    for nm in names:
        for v in versions[nm]:
            lines = [f"module {nm}", "lang 1.16"]
            # only the real (non decoy) versions carry requires
            if v != "v9.0.0" and reqs[nm]:
                lines.append("require (")
                for path, rv in reqs[nm]:
                    lines.append(f"\t{path} {rv}")
                lines.append(")")
            text = "\n".join(lines) + "\n"
            mdir = os.path.join(reg, f"{nm}@{v}", "module.mod")
            os.makedirs(os.path.dirname(mdir), exist_ok=True)
            with open(mdir, "w") as f:
                f.write(text)

    # main requires the first module at a real version
    first = names[0]
    fv = rng.choice([v for v in versions[first] if v != "v9.0.0"])
    main_text = f"module app\nlang 1.16\nrequire {first} {fv}\n"
    main = os.path.join(root, "main.mod")
    with open(main, "w") as f:
        f.write(main_text)
    return reg, main
