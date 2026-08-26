"""Behavioral verifier for the masked-exponent recovery task.

The verifier builds the held-out challenge suite from a fixed seed, keeping the
planted messages in memory, then runs the candidate's Julia source over it.
Grading is purely behavioral and conjunctive: for every challenge the candidate's
hex line must equal the planted message. Nothing is graded by reading the
candidate's source. Build and launch checks are zero-credit preconditions.
"""

import collections
import os
import shutil
import subprocess
import tempfile

import pytest

import baselines
import gen_challenges
import rsa_common

SEED = 20260717
APP = os.environ.get("CICADA_APP", "/app")
ATTACK = os.path.join(APP, "environment", "attack", "main.jl")
SUITE = gen_challenges.build_suite(SEED)

ROOT_FAMILIES = {"rooted", "rooted_masked", "crossed"}
UNTRUSTED_FAMILIES = {"masked", "rooted_masked", "crossed"}


def _julia_ok():
    try:
        r = subprocess.run(["julia", "--version"], capture_output=True, timeout=180)
        return r.returncode == 0
    except Exception:
        return False


JULIA = _julia_ok()


def _write_input(path, challenges, reverse=False):
    with open(path, "w") as f:
        f.write(str(len(challenges)) + "\n")
        for c in challenges:
            cc = dict(c)
            if reverse:
                cc["rows"] = list(reversed(c["rows"]))
            f.write(gen_challenges.public_line(cc) + "\n")


def _run(challenges, reverse=False):
    if not (JULIA and os.path.isfile(ATTACK)):
        return None
    tmp = tempfile.mkdtemp(prefix="run_")
    src = os.path.join(tmp, "main.jl")
    shutil.copyfile(ATTACK, src)
    inp = os.path.join(tmp, "in.txt")
    outp = os.path.join(tmp, "out.txt")
    _write_input(inp, challenges, reverse)
    proc = subprocess.run(
        ["julia", src, inp, outp], capture_output=True, text=True, timeout=900
    )
    if proc.returncode != 0 or not os.path.isfile(outp):
        return {}
    res = {}
    with open(outp) as f:
        for line in f:
            p = line.split()
            if len(p) >= 2:
                res[p[0]] = p[1]
    return res


RESULTS = _run(SUITE)


def test_candidate_runs():
    assert JULIA, "julia not available"
    assert os.path.isfile(ATTACK), "candidate main.jl missing"
    assert RESULTS, "candidate produced no output"


@pytest.mark.parametrize("challenge", SUITE, ids=[str(c["id"]) for c in SUITE])
def test_candidate_recovers(challenge):
    """The graded case: the candidate's line must be the planted message."""
    assert RESULTS is not None and RESULTS != {}
    got = RESULTS.get(str(challenge["id"]))
    ctx = f"id {challenge['id']} family {challenge['family']} root {challenge['root']}"
    assert got == challenge["m_hex"], ctx


def test_metamorphic_row_order():
    """Reversing the row order of every challenge leaves each recovery
    unchanged: the rows are a set, not a sequence."""
    rev = _run(SUITE, reverse=True)
    assert rev, "candidate produced no output on reordered input"
    for c in SUITE:
        assert rev.get(str(c["id"])) == c["m_hex"], c["id"]


def test_candidate_output_stable():
    sample = SUITE[:8]
    assert _run(sample) == _run(sample)


def test_case_floor_and_spread():
    assert len(SUITE) >= 60, len(SUITE)
    fams = collections.Counter(c["family"] for c in SUITE)
    assert set(gen_challenges.FAMILIES) <= set(fams), set(fams)
    assert len({c["bits"] for c in SUITE}) >= 3
    # The root order is redrawn per challenge, so no single value can be assumed.
    assert len({c["root"] for c in SUITE if c["root"] > 1}) >= 3


def test_every_lift_is_representable():
    """The width leaves no slack: every residue modulo n fits the published byte
    length, so the byte length can never stand in for the header when a challenge
    offers several candidate messages."""
    for c in SUITE:
        n = int(c["n"])
        assert n.bit_length() == 8 * c["L"], c["id"]
        assert (n - 1) < (1 << (8 * c["L"])), c["id"]


def test_root_families_really_need_a_root():
    """In a root family the authentic rows only reach a proper power of the
    message, and that power's order really divides the field order, so a root has
    to be extracted rather than inverted."""
    seen = 0
    for c in SUITE:
        if c["family"] not in ROOT_FAMILIES:
            continue
        seen += 1
        root, q = c["root"], int(c["q"])
        assert root > 1, c["id"]
        assert (q - 1) % root == 0, c["id"]
        if c["family"] == "crossed":
            assert (int(c["p"]) - 1) % root == 0, c["id"]
    assert seen >= 30, seen


def test_untrusted_families_really_carry_forgeries():
    """A row list that is called untrusted has rows that are genuinely not
    encryptions of the message under the challenge's mask."""
    for c in SUITE:
        if c["family"] not in UNTRUSTED_FAMILIES:
            continue
        assert c["authentic"] < len(c["rows"]), c["id"]


def test_input_carries_no_answer():
    """The published line never contains the message in any published form."""
    for c in SUITE:
        line = gen_challenges.public_line(c)
        m = int(c["m_hex"], 16)
        assert c["m_hex"] not in line, c["id"]
        assert str(m) not in line.split(), c["id"]
        for _, _, cc in c["rows"]:
            assert int(cc) % int(c["n"]) != m, c["id"]


def test_public_reference_recovers():
    for c in SUITE:
        rec = rsa_common.recover_general(int(c["n"]), gen_challenges.rows_of(c), c["L"])
        assert rec is not None, c["id"]
        assert rec.to_bytes(c["L"], "big").hex() == c["m_hex"], c["id"]


def test_two_routes_agree():
    """A route that is handed the secret primes, eliminates the mask through
    pairwise determinants inside each prime field and never enters Z/n reproduces
    every planted message. It is not used to filter generation, so this can fail:
    ground truth rests on neither implementation alone."""
    for c in SUITE:
        priv = rsa_common.recover_via_factors(
            int(c["p"]), int(c["q"]), gen_challenges.rows_of(c), c["L"]
        )
        assert priv == int(c["m_hex"], 16), (c["id"], c["family"])


def test_generation_deterministic():
    a = gen_challenges.build_suite(SEED)
    b = gen_challenges.build_suite(SEED)
    assert [c["rows"] for c in a] == [c["rows"] for c in b]
    assert [c["m_hex"] for c in a] == [c["m_hex"] for c in b]


def _score(fn):
    by = collections.defaultdict(lambda: [0, 0])
    total = 0
    for c in SUITE:
        n = int(c["n"])
        try:
            val = fn(n, gen_challenges.rows_of(c), c["L"])
            h = None
            if val is not None:
                h = (val % n).to_bytes(c["L"], "big").hex()
        except Exception:
            h = None
        by[c["family"]][1] += 1
        if h == c["m_hex"]:
            by[c["family"]][0] += 1
            total += 1
    return total, by


@pytest.mark.parametrize("name", sorted(baselines.ALL))
def test_wrong_baseline_is_bounded(name):
    """Each attack that drops one obligation must score zero on every family the
    obligation binds, must stay under its per-family cap where the drop only
    leaves a guess, and must stay under its ceiling over the whole suite."""
    total, by = _score(baselines.ALL[name])
    for fam in baselines.EXPECT_FAIL[name]:
        assert by[fam][1] > 0, f"{name}: target family {fam} empty"
        assert by[fam][0] == 0, (
            f"{name} passed {by[fam][0]}/{by[fam][1]} of target family {fam}"
        )
    for fam, cap in baselines.MAX_FAMILY.get(name, {}).items():
        assert by[fam][0] <= cap, f"{name} scored {by[fam][0]} on {fam}, cap {cap}"
    assert total <= baselines.MAX_TOTAL[name], (
        f"{name} scored {total}/{len(SUITE)}, ceiling {baselines.MAX_TOTAL[name]}"
    )
