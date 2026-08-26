"""Verifier for algebraic-real-continued-fraction-exact.

Loads the agent's Julia program at /app/src/solver.jl, runs its compute over
many generated polynomial-and-index problems, and requires its six outputs to
equal an independent exact oracle. The oracle and the generated cases live in a
separate module (oracle.py) that this file imports ONCE and then DELETES from
disk before any candidate runs, so the answer path is never readable by a
candidate at runtime. Nothing in THIS file reveals an answer: it holds only the
candidate-driving harness, the labelled-line comparison, and the test bodies;
the case inputs and expected outputs are computed at import time from oracle.py
and kept only in memory. Grading is behavioral only.
"""

import os
import shutil
import subprocess
import sys

from oracle import (
    KNOWN_QUAD,
    META_CASES,
    QUAD_CASES,
    cases,
    continued_fraction,
    self_check,
)

# Move the oracle and the generated cases out of the candidate-visible runtime:
# the module object stays imported in THIS process's memory, but its source file
# and any compiled bytecode are removed from disk before a single candidate
# program runs, so a candidate cannot read, import, parse, or delegate to the
# answer path at /tests. (test.sh runs pytest, which imports this module and
# executes the removal below during collection, before any test invokes a
# candidate.)
sys.dont_write_bytecode = True
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    os.remove(os.path.join(_TESTS_DIR, "oracle.py"))
except OSError:
    pass
shutil.rmtree(os.path.join(_TESTS_DIR, "__pycache__"), ignore_errors=True)

SOLVER = "/app/src/solver.jl"
DRIVER = "/tmp/cf_driver.jl"
JULIA = ["julia", "--startup-file=no"]
KEYS = ["count", "quotients", "numerators", "denominators", "terminated", "period"]


DRIVER_SRC = r"""
include("SOLVER_PATH")
function run_batch()
    toks = split(read(stdin, String))
    idx = 1
    T = parse(Int, toks[idx]); idx += 1
    for _ in 1:T
        d = parse(Int, toks[idx]); idx += 1
        coeffs = BigInt[parse(BigInt, toks[idx + i]) for i in 0:d]
        idx += d + 1
        r = parse(Int, toks[idx]); idx += 1
        k = parse(Int, toks[idx]); idx += 1
        res = compute(coeffs, r, k)
        println("count = ", res.count)
        println("quotients = ", join(string.(res.quotients), " "))
        println("numerators = ", join(string.(res.numerators), " "))
        println("denominators = ", join(string.(res.denominators), " "))
        println("terminated = ", res.terminated)
        println("period = ", res.period)
        println("===")
    end
end
run_batch()
""".replace("SOLVER_PATH", SOLVER)


def _write_driver():
    with open(DRIVER, "w") as f:
        f.write(DRIVER_SRC)


def encode(coeffs, r, k):
    d = len(coeffs) - 1
    return f"{d}\n" + " ".join(map(str, coeffs)) + f"\n{r}\n{k}\n"


def _batch_input(case_list):
    lines = [str(len(case_list))]
    for coeffs, r, k in case_list:
        lines.append(str(len(coeffs) - 1))
        lines.append(" ".join(map(str, coeffs)))
        lines.append(str(r))
        lines.append(str(k))
    return "\n".join(lines) + "\n"


def run_batch(case_list):
    """Run the agent's compute() over many cases in a single Julia process.

    Returns (parsed_dicts, raw_blocks), each aligned with case_list. Driving the
    agent's own compute in one process avoids paying Julia startup and
    compilation once per case while still grading the agent's executed behavior.
    """
    _write_driver()
    r = subprocess.run(
        JULIA + [DRIVER],
        input=_batch_input(case_list),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=1700,
    )
    assert r.returncode == 0, r.stderr
    blocks = [b for b in r.stdout.split("===\n") if b.strip()]
    assert len(blocks) == len(case_list), (
        f"expected {len(case_list)} result blocks, got {len(blocks)}\n{r.stdout}"
    )
    return [parse(b) for b in blocks], [b.strip("\n") for b in blocks]


def run_candidate(data):
    """Run the actual program end-to-end through real stdin/stdout (one case)."""
    r = subprocess.run(
        JULIA + [SOLVER],
        input=data,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def parse(out):
    d = {}
    for line in out.strip().splitlines():
        if "=" not in line:
            continue
        key, rhs = line.split("=", 1)
        d[key.strip()] = [int(t) for t in rhs.split()]
    return d


ALL = cases()


COMBINED = list(ALL) + QUAD_CASES + META_CASES


N_ALL = len(ALL)


N_QUAD = len(QUAD_CASES)


_combined = None


def combined_results():
    global _combined
    if _combined is None:
        _combined = run_batch(COMBINED)
    return _combined


def test_matches_exact_oracle():
    """The program reproduces the exact continued fraction the oracle computes."""
    assert len(ALL) >= 60
    got_all, _ = combined_results()
    for i, (coeffs, r, k) in enumerate(ALL):
        exp = continued_fraction(coeffs, r, k)
        self_check(coeffs, r, exp)
        got = got_all[i]
        for key in KEYS:
            assert got.get(key) == exp[key], (
                f"case {i} {coeffs} r={r} k={k} key {key}: got {got.get(key)} want {exp[key]}"
            )


def test_known_quadratic_periods():
    """Textbook quadratic surds have their documented repeating-block lengths."""
    got_all, _ = combined_results()
    quad = got_all[N_ALL : N_ALL + N_QUAD]
    for (coeffs, (r, quo, per)), got in zip(KNOWN_QUAD.items(), quad):
        exp = continued_fraction(list(coeffs), r, 6)
        assert exp["quotients"] == quo and exp["period"] == [per]
        assert got["quotients"] == quo and got["period"] == [per]


def test_metamorphic_relations():
    """Integer shift moves a_0; constant rescale leaves the expansion invariant."""
    got_all, _ = combined_results()
    base, shifted, scaled = got_all[N_ALL + N_QUAD :]
    assert shifted["quotients"][0] == base["quotients"][0] + 5
    assert shifted["quotients"][1:] == base["quotients"][1:]
    assert scaled["quotients"] == base["quotients"]
    assert scaled["numerators"] == base["numerators"]


def test_end_to_end_program():
    """The actual program, driven through real stdin/stdout, matches the oracle."""
    coeffs, r, k = ALL[len(ALL) // 2]
    exp = continued_fraction(coeffs, r, k)
    got = parse(run_candidate(encode(coeffs, r, k)))
    for key in KEYS:
        assert got.get(key) == exp[key], (
            f"e2e {coeffs} r={r} k={k} key {key}: got {got.get(key)} want {exp[key]}"
        )


def test_determinism_second_run():
    """A second run over a representative subset yields byte-identical output."""
    _, first = combined_results()
    sub = COMBINED[:15]
    _, second = run_batch(sub)
    assert first[: len(sub)] == second
