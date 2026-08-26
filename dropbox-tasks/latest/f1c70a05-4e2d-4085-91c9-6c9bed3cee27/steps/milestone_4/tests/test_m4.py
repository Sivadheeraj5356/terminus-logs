"""Milestone 4 verifier: lang gated pruning and the loaded manifest set.

Each test runs the modverse graph subcommand, which reports both the build list
and the set of manifest files read. The tests check two independent conditions:
the build list is still correct under pruning, and the loaded set excludes the
manifests that pruning skips while including the ones an unpruned chain forces.
The discriminator fixture makes a non pruning implementation and an over
aggressive pruning implementation each produce a different, wrong build list.
"""

import json
import os
import subprocess
import tempfile

import pytest

import fixtures
import modref as M

CLI = "/usr/local/bin/modverse"


def run_graph(reg, main):
    out = os.path.join(tempfile.mkdtemp(), "result.json")
    proc = subprocess.run(
        [CLI, "graph", "--registry", reg, "--main", main, "--out", out],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"CLI failed: {proc.stderr}"
    with open(out) as f:
        data = json.load(f)
    return data["buildList"], set(data["loaded"])


def reference(reg, main):
    sel, loaded = M.resolve(M.Registry(reg), main)
    return {k: v.display for k, v in sel.items()}, set(loaded)


class TestMilestone4:
    def test_pruned_chain_build_list_correct(self):
        """A chain behind a properly versioned dependency still produces the full
        and correct build list."""
        reg, main = fixtures.make("pruned_chain")
        bl, _ = run_graph(reg, main)
        assert bl == {"G": "v1.0.0", "H": "v1.0.0", "I": "v1.0.0", "J": "v1.0.0"}

    def test_pruned_chain_skips_deeper_manifests(self):
        """The deeper manifests behind the properly versioned dependency are not
        read; only the dependency's own manifest is loaded."""
        reg, main = fixtures.make("pruned_chain")
        _, loaded = run_graph(reg, main)
        assert "G@v1.0.0/module.mod" in loaded
        assert "H@v1.0.0/module.mod" not in loaded
        assert "I@v1.0.0/module.mod" not in loaded
        assert "J@v1.0.0/module.mod" not in loaded

    def test_unpruned_chain_reads_full_closure(self):
        """The same chain below the threshold reads every manifest in the
        transitive closure."""
        reg, main = fixtures.make("unpruned_chain")
        bl, loaded = run_graph(reg, main)
        assert bl == {"G": "v1.0.0", "H": "v1.0.0", "I": "v1.0.0", "J": "v1.0.0"}
        for m in ("G", "H", "I", "J"):
            assert f"{m}@v1.0.0/module.mod" in loaded

    def test_mixed_thresholds(self):
        """With one pruned and one unpruned subtree, the build list is complete
        while the loaded set reads the unpruned subtree fully and the pruned
        subtree only at its top."""
        reg, main = fixtures.make("mixed")
        bl, loaded = run_graph(reg, main)
        ref_bl, ref_loaded = reference(reg, main)
        assert bl == ref_bl
        # pruned subtree: only P read
        assert "P@v1.0.0/module.mod" in loaded
        assert "Q@v1.0.0/module.mod" not in loaded
        assert "R@v1.0.0/module.mod" not in loaded
        # unpruned subtree: all of S, T, U read
        assert "S@v1.0.0/module.mod" in loaded
        assert "T@v1.0.0/module.mod" in loaded
        assert "U@v1.0.0/module.mod" in loaded

    def test_non_pruning_implementation_would_overload(self):
        """The loaded set on the pruned chain is strictly smaller than the full
        closure, so an implementation that loads everything fails this check even
        though it gets the build list right."""
        reg, main = fixtures.make("pruned_chain")
        _, loaded = run_graph(reg, main)
        full_closure = {
            "G@v1.0.0/module.mod",
            "H@v1.0.0/module.mod",
            "I@v1.0.0/module.mod",
            "J@v1.0.0/module.mod",
        }
        assert loaded != full_closure
        assert loaded < full_closure

    def test_pruned_indirect_recorded_in_build_list(self):
        """A pruned dependency's recorded indirect requirement still appears in
        the build list at the recorded version, while its manifest is not read.
        An over aggressive pruner that drops the recorded indirect entry omits it
        and a non pruner that descends into it pulls a different version's deeper
        dependency, so both fail this exact build list."""
        reg, main = fixtures.make("pruned_drops_wrong_indirect")
        bl, loaded = run_graph(reg, main)
        assert bl == {"K": "v1.0.0", "L": "v2.0.0"}
        assert "M" not in bl
        assert "L@v2.0.0/module.mod" not in loaded
        assert "L@v1.0.0/module.mod" not in loaded

    @pytest.mark.parametrize(
        "name", ["pruned_chain", "unpruned_chain", "mixed", "pruned_drops_wrong_indirect"]
    )
    def test_all_fixtures_match_reference(self, name):
        """Every pruning fixture build list and loaded set match the independent
        reference."""
        reg, main = fixtures.make(name)
        bl, loaded = run_graph(reg, main)
        ref_bl, ref_loaded = reference(reg, main)
        assert bl == ref_bl
        assert loaded == ref_loaded
