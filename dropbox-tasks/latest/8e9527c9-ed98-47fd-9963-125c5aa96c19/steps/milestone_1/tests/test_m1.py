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


CASES_LIST = load("cases_m1.json")
EXPECTED = load("expected_m1.json")
BY_ID = {c["id"]: c for c in CASES_LIST}


class TestMilestone1:
    def test_build_produces_binary(self):
        """The toolkit builds to /app/bin/bvm."""
        assert BVM.exists()

    def test_all_cases_match_ground_truth(self):
        """Every milestone-1 fixture reproduces the ground-truth output."""
        assert len(CASES_LIST) >= 50
        failures = []
        for c in CASES_LIST:
            got, _ = run(c["args"])
            want = EXPECTED[c["id"]]
            if got != want:
                failures.append(f"{c['id']}:\n  got : {got!r}\n  want: {want!r}")
        assert not failures, "case mismatches:\n" + "\n".join(failures[:12])

    def test_getfield_resolves_inherited_field(self):
        """getfield finds a field declared on an ancestor of the named type."""
        cid = next(c["id"] for c in CASES_LIST if c["id"].startswith("opcheck_get"))
        got, _ = run(BY_ID[cid]["args"])
        assert got == EXPECTED[cid]
        assert "type error" not in got

    def test_call_accepts_subtype_argument(self):
        """A subtype value is accepted where a supertype parameter is expected."""
        cid = next(c["id"] for c in CASES_LIST if c["id"].startswith("opcheck_call"))
        got, _ = run(BY_ID[cid]["args"])
        assert got == EXPECTED[cid]
        assert "type error" not in got

    def test_comparison_pushes_bool(self):
        """icmp leaves a bool on the operand stack."""
        cid = next(c["id"] for c in CASES_LIST if c["id"].startswith("stackmap_cmp"))
        got, _ = run(BY_ID[cid]["args"])
        assert got == EXPECTED[cid]
        assert "locals=[bool]" in got

    def test_swap_exchanges_top_two(self):
        """swap actually exchanges the two top operand-stack slots."""
        cid = next(c["id"] for c in CASES_LIST if c["id"].startswith("stackmap_swap"))
        got, _ = run(BY_ID[cid]["args"])
        assert got == EXPECTED[cid]

    def test_conditional_branch_has_two_successors(self):
        """cfg lists both the taken target and the fall-through of a br_if."""
        diamonds = [c["id"] for c in CASES_LIST if c["id"].startswith("cfg_diamond")]
        assert diamonds
        for cid in diamonds:
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]
            assert "b0 -> b2, b1" in got

    def test_disasm_round_trips(self):
        """disasm renders canonical module text matching the contract."""
        cid = next(c["id"] for c in CASES_LIST if c["id"].startswith("disasm_"))
        got, _ = run(BY_ID[cid]["args"])
        assert got == EXPECTED[cid]

    def test_parse_reports_checksum(self):
        """parse lists types, function signatures and the canonical checksum."""
        ids = [c["id"] for c in CASES_LIST if c["id"].startswith("parse_")]
        assert ids
        for cid in ids:
            got, _ = run(BY_ID[cid]["args"])
            assert got == EXPECTED[cid]
        sample, _ = run(BY_ID[ids[0]]["args"])
        assert "checksum: 0x" in sample
