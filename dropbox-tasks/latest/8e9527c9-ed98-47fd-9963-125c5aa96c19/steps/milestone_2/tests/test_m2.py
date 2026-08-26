import json
import subprocess
from pathlib import Path

APP = Path("/app")
BVM = APP / "bin" / "bvm"
TESTS = Path(__file__).parent
CASES = TESTS / "cases"


def build():
    r = subprocess.run(
        ["go", "build", "-o", str(BVM), "./cmd/bvm"],
        cwd=str(APP), capture_output=True, text=True,
    )
    assert r.returncode == 0, f"go build failed: {r.stderr}"


build()


def load(name):
    return json.loads((TESTS / name).read_text())


def run(args):
    argv = [a.replace("{DIR}", str(CASES)) for a in args]
    r = subprocess.run([str(BVM), *argv], capture_output=True, text=True)
    out = r.stdout.rstrip("\n")
    if r.returncode != 0:
        out = f"<<exit {r.returncode}>> {out}"
    return out, r.returncode


CASES_LIST = load("cases_m2.json")
EXPECTED = load("expected_m2.json")
BY_ID = {c["id"]: c for c in CASES_LIST}


def by_prefix(pfx):
    return [c["id"] for c in CASES_LIST if c["id"].startswith(pfx)]


class TestMilestone2:
    def test_build_produces_binary(self):
        """The toolkit builds to /app/bin/bvm."""
        assert BVM.exists()

    def test_all_cases_match_ground_truth(self):
        """Every milestone-2 fixture reproduces the ground-truth output."""
        assert len(CASES_LIST) >= 60
        failures = []
        for c in CASES_LIST:
            got, _ = run(c["args"])
            want = EXPECTED[c["id"]]
            if got != want:
                failures.append(f"{c['id']}:\n  got : {got!r}\n  want: {want!r}")
        assert not failures, "case mismatches:\n" + "\n".join(failures[:12])

    def test_join_merges_to_common_supertype(self):
        """A value merged from two subtypes keeps the field of their nearest common type."""
        for cid in by_prefix("verify_hier"):
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]
            assert got == "main: verified"

    def test_definite_assignment_across_paths(self):
        """A local assigned on only one branch is rejected when later loaded."""
        for cid in by_prefix("verify_rbw"):
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]
            assert "loaded before assignment" in got

    def test_join_requires_equal_stack_height(self):
        """A join of predecessors with different stack heights is rejected."""
        for cid in by_prefix("verify_height"):
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]
            assert "stack height mismatch" in got

    def test_fixpoint_reaches_back_edge(self):
        """A local invalidated on a loop back-edge is caught at the header."""
        for cid in by_prefix("verify_backwiden"):
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]
            assert "rejected" in got

    def test_dominators_of_join(self):
        """The immediate dominator of a join is the block that dominates all its paths."""
        ids = by_prefix("dom_diamond") + by_prefix("dom_nest")
        assert ids
        for cid in ids:
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]

    def test_max_stack_over_all_paths(self):
        """max_stack accounts for the stack height inherited into each block."""
        for cid in by_prefix("analyze_maxs"):
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]
            assert "max_stack: 3" in got

    def test_run_executes_program(self):
        """run produces the deterministic result of executing main."""
        ids = by_prefix("run_")
        assert ids
        for cid in ids:
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]

    def test_batch_digest(self):
        """batch prints a per-model report followed by an FNV-1a digest."""
        for cid in by_prefix("batch_"):
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]
            assert "digest: 0x" in got

    def test_trace_lists_executed_instructions(self):
        """trace prints each executed instruction before the final result line."""
        ids = by_prefix("trace_")
        assert ids
        for cid in ids:
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]
        sample, _ = run(BY_ID[ids[0]]["args"])
        assert "result:" in sample or "trap:" in sample

    def test_report_has_digest(self):
        """report prints a per-function summary followed by an FNV-1a digest."""
        ids = by_prefix("report_")
        assert ids
        for cid in ids:
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]
        sample, _ = run(BY_ID[ids[0]]["args"])
        assert "digest: 0x" in sample
