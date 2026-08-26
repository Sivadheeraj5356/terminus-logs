import glob
import json
import os
import re
import subprocess
import tempfile

import pytest

APP = "/app"
TESTS = "/tests"
REF_SRC = os.path.join(TESTS, "ref", "chomp_ref.cpp")
FIX = os.path.join(TESTS, "fixtures")

GRADER = tempfile.mkdtemp(prefix="chomp_grader_")

# Answers are four fields: "V C G R" (value, winning-move count, Grundy value,
# remoteness).
OUT_RE = re.compile(r"[NP] \d+ \d+ \d+")

# Substrings of known combinatorial-game / solver engines or precomputed answer
# tooling. The agent must implement the retrograde itself, not vendor an oracle.
BANNED = [
    "cgsuite",
    "cgtcalc",
    "combinatorialgame",
    "sprague",
    "grundydb",
    "chompsolver",
    "tablebase",
    "nnue",
]


def _compile(sources, out, defines=None):
    cmd = ["g++", "-O2", "-std=c++17"]
    if defines:
        cmd += ["-D" + d for d in defines]
    cmd += sources + ["-o", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return out if r.returncode == 0 and os.path.exists(out) else None


def _build_agent():
    srcs = sorted(glob.glob(os.path.join(APP, "src", "*.cpp")))
    if not srcs:
        return None
    return _compile(srcs, os.path.join(GRADER, "agent_chomp"))


def _build_ref(name, defines=None):
    return _compile([REF_SRC], os.path.join(GRADER, name), defines)


AGENT = _build_agent()
REF = _build_ref("ref_full")
REF_NORMAL = _build_ref("ref_normal", ["NORMAL_TERMINAL"])
REF_WINLOSS = _build_ref("ref_winloss", ["WINLOSS_GRUNDY"])
REF_NAIVE_R = _build_ref("ref_naive_r", ["NAIVE_REMOTENESS"])


def _load(name):
    with open(os.path.join(FIX, name)) as fh:
        return json.load(fh)


HIDDEN = _load("hidden.json")
VISIBLE = _load("visible.json")
METAMORPHIC = _load("metamorphic.json")
ALL_GRADED = VISIBLE + HIDDEN


def run(binary, text):
    if binary is None:
        return None
    try:
        r = subprocess.run(
            [binary], input=text, capture_output=True, text=True, timeout=120
        )
    except subprocess.TimeoutExpired:
        return None
    out = r.stdout.strip()
    if not OUT_RE.fullmatch(out):
        return None
    return out


def _agent_sources_text():
    text = ""
    for p in sorted(glob.glob(os.path.join(APP, "src", "*.cpp"))) + sorted(
        glob.glob(os.path.join(APP, "src", "*.hpp"))
    ):
        with open(p, "r", errors="ignore") as fh:
            text += fh.read() + "\n"
    return text


def _strip_comments(text):
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return text


def test_builds():
    """Agent sources and every reference variant compile."""
    assert AGENT is not None, "agent sources under /app/src did not compile"
    assert REF is not None and REF_NORMAL is not None
    assert REF_WINLOSS is not None and REF_NAIVE_R is not None


def test_hidden_set_is_large_enough():
    """The hidden battery holds at least sixty independently graded positions."""
    assert len(HIDDEN) >= 60


@pytest.mark.parametrize("fx", ALL_GRADED, ids=[f["id"] for f in ALL_GRADED])
def test_reference_matches_expected(fx):
    """The C++ reference reproduces the independently computed expected answer."""
    assert run(REF, fx["input"]) == fx["expected"]


@pytest.mark.parametrize("fx", HIDDEN, ids=[f["id"] for f in HIDDEN])
def test_hidden_agent_matches_reference(fx):
    """On each hidden position the agent equals the independently recomputed reference."""
    ref = run(REF, fx["input"])
    assert ref == fx["expected"]
    assert run(AGENT, fx["input"]) == ref


@pytest.mark.parametrize("fx", VISIBLE, ids=[f["id"] for f in VISIBLE])
def test_visible_agent_matches_expected(fx):
    """On each visible sanity position the agent matches the expected answer."""
    assert run(REF, fx["input"]) == fx["expected"]
    assert run(AGENT, fx["input"]) == fx["expected"]


@pytest.mark.parametrize("m", METAMORPHIC, ids=[m["id"] for m in METAMORPHIC])
def test_metamorphic_relabel_invariance(m):
    """Relabelling the non-poison elements (a poset isomorphism) leaves V C G R invariant."""
    a = run(AGENT, m["input_a"])
    b = run(AGENT, m["input_b"])
    assert a == m["expected"]
    assert b == m["expected"]
    assert a == b


def test_normal_terminal_baseline_fails_widely():
    """A normal-play (poison-eatable) engine mismatches on most hidden positions."""
    diffs = sum(1 for fx in HIDDEN if run(REF_NORMAL, fx["input"]) != fx["expected"])
    assert diffs >= 40


def test_winloss_grundy_baseline_fails_widely():
    """Collapsing the Grundy value to a win/loss bit mismatches on many positions."""
    diffs = sum(1 for fx in HIDDEN if run(REF_WINLOSS, fx["input"]) != fx["expected"])
    assert diffs >= 30


def test_naive_remoteness_baseline_fails_widely():
    """A shortest-path remoteness (no parity/optimal play) mismatches on many positions."""
    diffs = sum(1 for fx in HIDDEN if run(REF_NAIVE_R, fx["input"]) != fx["expected"])
    assert diffs >= 25


def test_each_wrong_baseline_fails_somewhere():
    """No single wrong-rule engine matches the reference on every hidden position."""
    for partial in (REF_NORMAL, REF_WINLOSS, REF_NAIVE_R):
        diffs = sum(
            1 for fx in HIDDEN if run(partial, fx["input"]) != run(REF, fx["input"])
        )
        assert diffs >= 1


def test_poison_only_terminal_is_previous_player_loss():
    """A single non-poison element above the poison is an N-position 'N 1 1 1'."""
    # poset: poison 0 with one element 1 directly above -> the only move empties
    # to the poison-only ideal (P, Grundy 0, remoteness 0), so this is N.
    assert run(AGENT, "2 1\n0 1\n") == "N 1 1 1"


def test_grundy_zero_iff_p_position():
    """Across the hidden set, V == P exactly when the reported Grundy value is 0."""
    for fx in HIDDEN:
        out = run(AGENT, fx["input"])
        assert out is not None
        v, _c, g, _r = out.split()
        assert (v == "P") == (int(g) == 0)


def test_value_matches_remoteness_parity():
    """Across the hidden set, N-positions have odd remoteness and P-positions even."""
    for fx in HIDDEN:
        out = run(AGENT, fx["input"])
        assert out is not None
        v, _c, _g, r = out.split()
        assert (v == "N") == (int(r) % 2 == 1)


def test_agent_output_is_four_fields():
    """The agent emits a parseable 'V C G R' line for a normal query."""
    out = run(AGENT, HIDDEN[0]["input"])
    assert out is not None and OUT_RE.fullmatch(out)


def test_reference_is_deterministic():
    """Recomputing a hidden position twice yields the identical reference answer."""
    fx = HIDDEN[len(HIDDEN) // 2]
    assert run(REF, fx["input"]) == run(REF, fx["input"])


def test_agent_is_deterministic():
    """The agent returns the same answer on a repeated identical query."""
    fx = HIDDEN[0]
    assert run(AGENT, fx["input"]) == run(AGENT, fx["input"])


def test_no_external_engine_library():
    """The agent sources do not import or vendor a known game-solving engine or table."""
    text = _strip_comments(_agent_sources_text()).lower()
    for banned in BANNED:
        assert banned not in text, f"forbidden reference found: {banned}"


def test_no_bundled_answer_data():
    """The project ships no precomputed answer artifact."""
    bad = []
    for root, _dirs, files in os.walk(APP):
        for fn in files:
            if fn.lower().endswith((".bin", ".egt", ".book", ".nnue", ".dat")):
                bad.append(os.path.join(root, fn))
    assert not bad, f"unexpected data artifacts: {bad}"
