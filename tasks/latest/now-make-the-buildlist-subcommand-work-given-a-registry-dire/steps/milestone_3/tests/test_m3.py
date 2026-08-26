"""Milestone 3 verifier: main module replace and exclude authority.

Each test runs the modverse buildlist subcommand against a registry whose main
manifest carries a replace or exclude directive and checks the resulting build
list against the independent reference. Discriminator tests pin the cases where a
wrong implementation that honours a transitive replace, ignores a main module
replace, or honours a dependency level exclude would produce a different build
list.
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
        return json.load(f)["buildList"]


def reference_buildlist(reg, main):
    sel, _ = M.resolve(M.Registry(reg), main)
    return {k: v.display for k, v in sel.items()}


class TestMilestone3:
    def test_replace_downgrade_follows_target(self):
        """A main module replace that points below the required maximum wins, so
        the build list takes the replacement target version, not the higher
        required one."""
        reg, main = fixtures.make("replace_downgrade")
        got = run_buildlist(reg, main)
        assert got == {"A": "v1.0.0", "B": "v1.0.0", "C": "v1.1.0"}

    def test_replace_versionless_rewrites_all(self):
        """A replace with no version on the left rewrites every version of the
        module."""
        reg, main = fixtures.make("replace_versionless")
        got = run_buildlist(reg, main)
        assert got["C"] == "v1.0.0"

    def test_replace_to_local_refeeds_requirements(self):
        """A replace whose target is a local manifest contributes that manifest's
        own requirements, so a new dependency appears and the registry version's
        dependency disappears."""
        reg, main = fixtures.make("replace_to_local")
        got = run_buildlist(reg, main)
        assert got == {"A": "v1.0.0", "D": "v1.0.0"}
        assert "C" not in got

    def test_exclude_falls_to_next_highest(self):
        """Excluding the required version forces selection to the next highest
        required and not excluded version."""
        reg, main = fixtures.make("exclude_next_highest")
        got = run_buildlist(reg, main)
        assert got["C"] == "v1.3.0"

    def test_dependency_replace_and_exclude_ignored(self):
        """Replace and exclude written in a dependency manifest are inert; only
        the required version is selected."""
        reg, main = fixtures.make("dependency_directives_ignored")
        got = run_buildlist(reg, main)
        assert got["C"] == "v1.2.0"

    def test_combined_replace_and_exclude(self):
        """A main manifest that both excludes one module's version and replaces
        another's edge applies both correctly."""
        reg, main = fixtures.make("exclude_with_replace")
        got = run_buildlist(reg, main)
        assert got == reference_buildlist(reg, main)
        assert got["C"] == "v1.3.0"
        assert got["E"] == "v1.5.0"

    def test_pure_build_list_still_correct_without_directives(self):
        """A main manifest with no replace or exclude still computes the plain
        maximum of required versions, so this milestone did not break the core
        rule."""
        reg = tempfile.mkdtemp()
        os.makedirs(os.path.join(reg, "A@v1.0.0"), exist_ok=True)
        os.makedirs(os.path.join(reg, "C@v1.2.0"), exist_ok=True)
        with open(os.path.join(reg, "A@v1.0.0", "module.mod"), "w") as f:
            f.write("module A\nlang 1.16\nrequire C v1.2.0\n")
        with open(os.path.join(reg, "C@v1.2.0", "module.mod"), "w") as f:
            f.write("module C\nlang 1.16\n")
        main = os.path.join(tempfile.mkdtemp(), "main.mod")
        with open(main, "w") as f:
            f.write("module app\nlang 1.16\nrequire A v1.0.0\n")
        got = run_buildlist(reg, main)
        assert got == {"A": "v1.0.0", "C": "v1.2.0"}

    @pytest.mark.parametrize(
        "name",
        [
            "replace_downgrade",
            "replace_versionless",
            "replace_to_local",
            "exclude_next_highest",
            "dependency_directives_ignored",
            "exclude_with_replace",
        ],
    )
    def test_all_fixtures_match_reference(self, name):
        """Every replace and exclude fixture build list matches the independent
        reference exactly."""
        reg, main = fixtures.make(name)
        assert run_buildlist(reg, main) == reference_buildlist(reg, main)
